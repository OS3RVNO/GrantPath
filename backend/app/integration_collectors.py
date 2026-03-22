from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from ldap3 import ALL, Connection, Server
from ldap3.utils.conv import escape_filter_chars

from app.connector_blueprints import build_connector_blueprints
from app.models import ConnectorRuntimeResponse, ConnectorRuntimeStatus, ConnectorStatus, Entity, InsightNote, Relationship

logger = logging.getLogger(__name__)
GUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
ACCOUNT_ID_PATTERN = re.compile(r"^\d{12}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class CollectionBundle:
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    connectors: list[ConnectorStatus] = field(default_factory=list)
    insights: list[InsightNote] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    runtime_status: ConnectorRuntimeStatus | None = None


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def discover_connector_inventory(
    *,
    latest_status_by_id: dict[str, ConnectorRuntimeStatus] | None = None,
) -> ConnectorRuntimeResponse:
    latest_status_by_id = latest_status_by_id or {}
    blueprints = build_connector_blueprints()
    statuses = []
    for blueprint in blueprints.blueprints:
        status = latest_status_by_id.get(blueprint.id)
        validation_errors = _validation_errors_for_connector(blueprint.id)
        has_required_env = _has_env_values(blueprint.configuration_env)
        configured = has_required_env and not validation_errors
        runtime_available = blueprint.implementation_status in {"live", "partial"}
        notes = list(validation_errors)
        if blueprint.implementation_status == "partial":
            notes.append("Current runtime coverage is partial compared with the full official target model.")
        if not runtime_available:
            notes.insert(0, "Blueprint only: collector implementation pending.")
        statuses.append(
            status
            or ConnectorRuntimeStatus(
                id=blueprint.id,
                name=blueprint.surface,
                source=blueprint.vendor,
                surface=blueprint.surface,
                implementation_status=blueprint.implementation_status,
                configured=configured,
                enabled=configured and runtime_available,
                status=(
                    "configured"
                    if configured and runtime_available
                    else "needs_config"
                    if runtime_available
                    else "disabled"
                ),
                collection_mode=blueprint.collection_mode,
                description=(
                    blueprint.freshness
                    if runtime_available
                    else "Blueprint available. A live collector for this surface is not wired in this runtime yet."
                ),
                required_env=blueprint.configuration_env,
                required_permissions=blueprint.required_permissions,
                supported_entities=blueprint.supported_entities,
                tenant_requirements=blueprint.tenant_requirements,
                official_limitations=blueprint.official_limitations,
                current_runtime_coverage=blueprint.current_runtime_coverage,
                documentation_links=blueprint.documentation_links,
                notes=notes,
            )
        )
    return ConnectorRuntimeResponse(generated_at=utc_now_iso(), connectors=statuses)


def collect_configured_bundles() -> tuple[list[CollectionBundle], dict[str, ConnectorRuntimeStatus]]:
    collectors = [
        _collect_ldap_bundle,
        _collect_graph_bundle,
        _collect_azure_rbac_bundle,
        _collect_okta_bundle,
        _collect_cyberark_bundle,
    ]
    bundles: list[CollectionBundle] = []
    statuses: dict[str, ConnectorRuntimeStatus] = {}
    for collector in collectors:
        bundle = collector()
        if bundle.runtime_status is not None:
            statuses[bundle.runtime_status.id] = bundle.runtime_status
        if bundle.runtime_status and bundle.runtime_status.configured and bundle.runtime_status.enabled:
            bundles.append(bundle)
    return bundles, statuses


def _collect_ldap_bundle() -> CollectionBundle:
    connector_id = "ad-ldap"
    required_env = _required_env_for_connector(connector_id)
    if not _has_env_values(required_env):
        return _not_configured_bundle(
            connector_id,
            "Active Directory / LDAP",
            "Microsoft",
            "hybrid",
            required_env,
        )
    validation_errors = _validation_errors_for_connector(connector_id)
    if validation_errors:
        return _not_configured_bundle(
            connector_id,
            "Active Directory / LDAP",
            "Microsoft",
            "hybrid",
            required_env,
            notes=validation_errors,
        )

    server_uri = os.getenv("EIP_LDAP_SERVER_URI", "")
    bind_dn = os.getenv("EIP_LDAP_BIND_DN", "")
    password = os.getenv("EIP_LDAP_PASSWORD", "")
    base_dn = os.getenv("EIP_LDAP_BASE_DN", "")
    limit = int(os.getenv("EIP_LDAP_ENTRY_LIMIT", "200"))
    started = datetime.now(tz=UTC)

    try:
        server = Server(server_uri, get_info=ALL)
        connection = Connection(server, user=bind_dn, password=password, auto_bind=True)

        entities: list[Entity] = []
        relationships: list[Relationship] = []
        group_by_dn: dict[str, str] = {}
        notes: list[str] = []
        in_chain_supported: bool | None = None

        connection.search(
            base_dn,
            "(objectClass=group)",
            attributes=["cn", "distinguishedName", "member", "objectGUID"],
            size_limit=limit,
        )
        for entry in connection.entries:
            group_dn = str(entry.distinguishedName)
            group_id = _stable_id("ad_group", group_dn)
            group_by_dn[group_dn.lower()] = group_id
            entities.append(
                Entity(
                    id=group_id,
                    name=str(entry.cn),
                    kind="group",
                    source="Active Directory",
                    environment="hybrid",
                    description=f"LDAP group discovered under {base_dn}.",
                    criticality=2,
                    risk_score=28,
                    tags=["ad", "ldap", "group"],
                )
            )

        connection.search(
            base_dn,
            "(|(objectClass=user)(objectClass=person))",
            attributes=["cn", "distinguishedName", "memberOf", "sAMAccountName", "userPrincipalName"],
            size_limit=limit,
        )
        for entry in connection.entries:
            dn = str(entry.distinguishedName)
            entity_id = _stable_id("ad_principal", dn)
            entities.append(
                Entity(
                    id=entity_id,
                    name=str(getattr(entry, "userPrincipalName", None) or getattr(entry, "sAMAccountName", None) or entry.cn),
                    kind="user",
                    source="Active Directory",
                    environment="hybrid",
                    description=f"LDAP principal discovered under {base_dn}.",
                    criticality=2,
                    risk_score=32,
                    tags=["ad", "ldap", "user"],
                )
            )
            memberships = getattr(entry, "memberOf", None)
            membership_values = memberships.values if memberships and hasattr(memberships, "values") else [str(memberships)] if memberships else []
            effective_group_dns: list[str] = []
            effective_origin = "ldap"
            if in_chain_supported is not False:
                transitive_dns = _ldap_transitive_group_dns(
                    connection=connection,
                    base_dn=base_dn,
                    principal_dn=dn,
                    size_limit=limit,
                )
                if transitive_dns is None:
                    in_chain_supported = False
                else:
                    in_chain_supported = True
                    effective_group_dns = transitive_dns
                    effective_origin = "ldap-in-chain"
            if not effective_group_dns:
                effective_group_dns = [str(item) for item in membership_values]
            if memberships and in_chain_supported is False and not any(
                "LDAP_MATCHING_RULE_IN_CHAIN" in note for note in notes
            ):
                notes.append(
                    "LDAP_MATCHING_RULE_IN_CHAIN is not available on this directory endpoint, so the collector fell back to direct memberOf memberships."
                )
            for group_dn in effective_group_dns:
                target_id = group_by_dn.get(str(group_dn).lower())
                if not target_id:
                    continue
                rationale = (
                    "Server-side transitive group expansion discovered this membership path."
                    if effective_origin == "ldap-in-chain"
                    else "Direct LDAP membership discovered through memberOf."
                )
                relationships.append(
                    Relationship(
                        id=_stable_id("rel", f"{entity_id}:{target_id}:member_of"),
                        kind="member_of",
                        source=entity_id,
                        target=target_id,
                        label=f"{str(entry.cn)} member of {str(group_dn).split(',', 1)[0].replace('CN=', '')}",
                        rationale=rationale,
                        removable=True,
                        metadata={"origin": effective_origin},
                    )
                )

        duration_ms = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
        return _successful_bundle(
            connector_id=connector_id,
            name="Active Directory / LDAP",
            source="Microsoft",
            surface="Active Directory / LDAP",
            description="Live LDAP inventory from the configured directory base DN.",
            collection_mode="hybrid",
            required_env=required_env,
            entities=entities,
            relationships=relationships,
            coverage=f"{len(entities)} identities, {len(relationships)} memberships",
            latency_ms=duration_ms,
            notes=notes,
        )
    except Exception as exc:
        return _failed_bundle(connector_id, "Active Directory / LDAP", "Microsoft", "hybrid", required_env, str(exc))


def _collect_graph_bundle() -> CollectionBundle:
    connector_id = "entra-graph"
    required_env = _required_env_for_connector(connector_id)
    if not _has_env_values(required_env):
        return _not_configured_bundle(
            connector_id,
            "Microsoft Graph / Entra ID",
            "Microsoft",
            "incremental",
            required_env,
        )
    validation_errors = _validation_errors_for_connector(connector_id)
    if validation_errors:
        return _not_configured_bundle(
            connector_id,
            "Microsoft Graph / Entra ID",
            "Microsoft",
            "incremental",
            required_env,
            notes=validation_errors,
        )

    tenant_id = os.getenv("EIP_GRAPH_TENANT_ID", "")
    client_id = os.getenv("EIP_GRAPH_CLIENT_ID", "")
    client_secret = os.getenv("EIP_GRAPH_CLIENT_SECRET", "")
    user_limit = int(os.getenv("EIP_GRAPH_USER_LIMIT", "100"))
    group_limit = int(os.getenv("EIP_GRAPH_GROUP_LIMIT", "100"))
    site_ids = _parse_graph_site_ids(os.getenv("EIP_GRAPH_SITE_IDS", ""))

    started = datetime.now(tz=UTC)
    try:
        token = _client_credentials_token(
            token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            client_id=client_id,
            client_secret=client_secret,
            scope="https://graph.microsoft.com/.default",
        )
        headers = {"Authorization": f"Bearer {token}", "ConsistencyLevel": "eventual"}
        notes = [
            "Delta tokens are not yet persisted in this runtime, so the Graph collector still behaves like a bounded snapshot sync."
        ]
        if not site_ids:
            notes.append(
                "SharePoint site permission collection is disabled until EIP_GRAPH_SITE_IDS is configured with semicolon-separated Graph site IDs."
            )

        users = _paginated_get(
            "https://graph.microsoft.com/v1.0/users?$select=id,displayName,userPrincipalName,userType&$top=50",
            headers=headers,
            limit=user_limit,
        )
        groups = _paginated_get(
            "https://graph.microsoft.com/v1.0/groups?$select=id,displayName&$top=50",
            headers=headers,
            limit=group_limit,
        )

        entities: list[Entity] = []
        relationships: list[Relationship] = []
        group_names: dict[str, str] = {}
        known_entity_ids: set[str] = set()

        for group in groups:
            group_id = _stable_id("graph_group", group["id"])
            group_names[str(group["id"])] = group_id
            entities.append(
                Entity(
                    id=group_id,
                    name=str(group.get("displayName") or group["id"]),
                    kind="group",
                    source="Microsoft Graph",
                    environment="cloud",
                    description="Entra ID group discovered through Microsoft Graph.",
                    criticality=2,
                    risk_score=30,
                    tags=["graph", "entra", "group"],
                )
            )
            known_entity_ids.add(group_id)

        for user in users:
            principal_id = _stable_id("graph_principal", user["id"])
            principal_name = str(user.get("userPrincipalName") or user.get("displayName") or user["id"])
            kind = "service_account" if "service" in principal_name.lower() or "#ext#" in principal_name.lower() else "user"
            entities.append(
                Entity(
                    id=principal_id,
                    name=principal_name,
                    kind=kind,
                    source="Microsoft Graph",
                    environment="cloud",
                    description="Entra ID principal discovered through Microsoft Graph.",
                    criticality=3 if kind == "service_account" else 2,
                    risk_score=48 if kind == "service_account" else 34,
                    tags=["graph", "entra", user.get("userType", "member").lower()],
                )
            )
            known_entity_ids.add(principal_id)

        membership_requests = [
            {
                "id": str(index),
                "method": "GET",
                "url": (
                    f"/users/{user['id']}/transitiveMemberOf/microsoft.graph.group"
                    "?$select=id,displayName&$top=50"
                ),
                "headers": {"ConsistencyLevel": "eventual"},
            }
            for index, user in enumerate(users, start=1)
        ]
        membership_by_user = _graph_batch_collection(
            requests=membership_requests,
            headers={"Authorization": f"Bearer {token}"},
            limit=group_limit,
        )

        for index, user in enumerate(users, start=1):
            principal_id = _stable_id("graph_principal", user["id"])
            principal_name = str(user.get("userPrincipalName") or user.get("displayName") or user["id"])
            membership_url = (
                f"https://graph.microsoft.com/v1.0/users/{user['id']}/transitiveMemberOf/microsoft.graph.group"
                "?$select=id,displayName&$top=50"
            )
            groups_payload = membership_by_user.get(str(index))
            if groups_payload is None:
                groups_payload = _paginated_get(membership_url, headers=headers, limit=group_limit)
            for group in groups_payload:
                target_id = group_names.get(str(group["id"])) or _stable_id("graph_group", group["id"])
                if target_id not in known_entity_ids:
                    entities.append(
                        Entity(
                            id=target_id,
                            name=str(group.get("displayName") or group["id"]),
                            kind="group",
                            source="Microsoft Graph",
                            environment="cloud",
                            description="Entra ID group discovered through transitiveMemberOf expansion.",
                            criticality=2,
                            risk_score=30,
                            tags=["graph", "entra", "group"],
                        )
                    )
                    known_entity_ids.add(target_id)
                relationships.append(
                    Relationship(
                        id=_stable_id("rel", f"{principal_id}:{target_id}:member_of"),
                        kind="member_of",
                        source=principal_id,
                        target=target_id,
                        label=f"{principal_name} transitive member of {group.get('displayName') or group['id']}",
                        rationale="Server-side transitiveMemberOf expansion returned this group path.",
                        removable=True,
                        metadata={"origin": "graph-transitiveMemberOf"},
                    )
                )

        for site_id in site_ids:
            site = _graph_get(
                f"https://graph.microsoft.com/v1.0/sites/{site_id}?$select=id,displayName,webUrl",
                headers=headers,
            )
            site_entity_id = _stable_id("graph_resource", str(site["id"]))
            entities.append(
                Entity(
                    id=site_entity_id,
                    name=str(site.get("displayName") or site["id"]),
                    kind="resource",
                    source="SharePoint Online",
                    environment="cloud",
                    description=str(site.get("webUrl") or "SharePoint site discovered through Microsoft Graph."),
                    criticality=4,
                    risk_score=66,
                    tags=["graph", "sharepoint", "site"],
                )
            )
            permissions = _paginated_get(
                f"https://graph.microsoft.com/v1.0/sites/{site_id}/permissions?$top=50",
                headers=headers,
                limit=200,
            )
            for permission in permissions:
                roles = [str(role).title() for role in permission.get("roles", [])]
                for identity in permission.get("grantedToIdentitiesV2", []) or permission.get("grantedToIdentities", []):
                    user_payload = identity.get("user") or identity.get("siteUser") or {}
                    group_payload = identity.get("group") or identity.get("siteGroup") or {}
                    principal_payload = user_payload or group_payload
                    if not principal_payload:
                        continue
                    raw_id = str(principal_payload.get("id") or principal_payload.get("displayName"))
                    principal_entity_id = _stable_id("graph_permission_principal", raw_id)
                    entities.append(
                        Entity(
                            id=principal_entity_id,
                            name=str(principal_payload.get("displayName") or raw_id),
                            kind="group" if group_payload else "user",
                            source="Microsoft Graph",
                            environment="cloud",
                            description="SharePoint permission principal discovered through Graph site permissions.",
                            criticality=2,
                            risk_score=35,
                            tags=["graph", "sharepoint", "principal"],
                        )
                    )
                    relationships.append(
                        Relationship(
                            id=_stable_id("rel", f"{principal_entity_id}:{site_entity_id}:direct_acl:{','.join(roles)}"),
                            kind="direct_acl",
                            source=principal_entity_id,
                            target=site_entity_id,
                            label=f"SharePoint permission on {site.get('displayName') or site_id}",
                            rationale="Graph site permissions enumerated this access grant.",
                            permissions=roles or ["Read"],
                            removable=True,
                            metadata={"origin": "graph-site-permissions"},
                        )
            )

        duration_ms = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
        if len(users) >= user_limit:
            notes.append("Graph user collection reached the configured cap; raise EIP_GRAPH_USER_LIMIT for wider coverage.")
        if len(groups) >= group_limit:
            notes.append("Graph group collection reached the configured cap; raise EIP_GRAPH_GROUP_LIMIT for wider coverage.")
        if site_ids:
            notes.append(
                "SharePoint site permissions are only collected for the explicit Graph site IDs configured in EIP_GRAPH_SITE_IDS."
            )
        return _successful_bundle(
            connector_id=connector_id,
            name="Microsoft Graph / Entra ID",
            source="Microsoft",
            surface="Microsoft Graph / Entra ID",
            description="Graph-powered cloud identity and optional SharePoint permissions collection.",
            collection_mode="incremental",
            required_env=required_env,
            entities=entities,
            relationships=relationships,
            coverage=f"{len(users)} users, {len(groups)} groups, {len(site_ids)} sites",
            latency_ms=duration_ms,
            notes=notes,
        )
    except Exception as exc:
        return _failed_bundle(connector_id, "Microsoft Graph / Entra ID", "Microsoft", "incremental", required_env, str(exc))


def _collect_azure_rbac_bundle() -> CollectionBundle:
    connector_id = "azure-rbac"
    required_env = _required_env_for_connector(connector_id)
    if not _has_env_values(required_env):
        return _not_configured_bundle(
            connector_id,
            "Azure RBAC",
            "Microsoft",
            "hybrid",
            required_env,
        )
    validation_errors = _validation_errors_for_connector(connector_id)
    if validation_errors:
        return _not_configured_bundle(
            connector_id,
            "Azure RBAC",
            "Microsoft",
            "hybrid",
            required_env,
            notes=validation_errors,
        )

    tenant_id = os.getenv("EIP_GRAPH_TENANT_ID", "")
    client_id = os.getenv("EIP_GRAPH_CLIENT_ID", "")
    client_secret = os.getenv("EIP_GRAPH_CLIENT_SECRET", "")
    subscription_ids = [item.strip() for item in os.getenv("EIP_AZURE_SUBSCRIPTION_IDS", "").split(",") if item.strip()]

    started = datetime.now(tz=UTC)
    try:
        token = _client_credentials_token(
            token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            client_id=client_id,
            client_secret=client_secret,
            scope="https://management.azure.com/.default",
        )
        headers = {"Authorization": f"Bearer {token}"}
        entities: list[Entity] = []
        relationships: list[Relationship] = []

        for subscription_id in subscription_ids:
            resource_id = _stable_id("azure_resource", f"/subscriptions/{subscription_id}")
            entities.append(
                Entity(
                    id=resource_id,
                    name=f"Subscription {subscription_id}",
                    kind="resource",
                    source="Azure RBAC",
                    environment="cloud",
                    description=f"Azure subscription scope /subscriptions/{subscription_id}.",
                    criticality=5,
                    risk_score=88,
                    tags=["azure", "subscription"],
                )
            )
            definitions = _paginated_get(
                (
                    f"https://management.azure.com/subscriptions/{subscription_id}/providers/"
                    "Microsoft.Authorization/roleDefinitions?api-version=2022-04-01"
                ),
                headers=headers,
                limit=500,
                value_key="value",
            )
            definition_map = {item["id"].lower(): item for item in definitions}
            assignments = _paginated_get(
                (
                    f"https://management.azure.com/subscriptions/{subscription_id}/providers/"
                    "Microsoft.Authorization/roleAssignments?api-version=2022-04-01&$filter=atScope()"
                ),
                headers=headers,
                limit=500,
                value_key="value",
            )
            for assignment in assignments:
                properties = assignment.get("properties", {})
                principal_object_id = str(properties.get("principalId"))
                if not principal_object_id:
                    continue
                principal_type = str(properties.get("principalType", "User")).lower()
                principal_id = _stable_id("cloud_principal", principal_object_id)
                entities.append(
                    Entity(
                        id=principal_id,
                        name=principal_object_id,
                        kind="group" if principal_type == "group" else "service_account" if principal_type in {"serviceprincipal", "managedidentity"} else "user",
                        source="Azure RBAC",
                        environment="cloud",
                        description="Azure principal observed in a role assignment.",
                        criticality=3,
                        risk_score=54,
                        tags=["azure", principal_type],
                    )
                )
                scope = str(properties.get("scope") or f"/subscriptions/{subscription_id}")
                scope_resource_id = _stable_id("azure_resource", scope)
                entities.append(
                    Entity(
                        id=scope_resource_id,
                        name=scope,
                        kind="resource",
                        source="Azure RBAC",
                        environment="cloud",
                        description=f"Azure RBAC scope {scope}.",
                        criticality=5 if "/subscriptions/" in scope else 4,
                        risk_score=86 if "/subscriptions/" in scope else 72,
                        tags=["azure", "scope"],
                    )
                )
                role_definition_id = str(properties.get("roleDefinitionId", "")).lower()
                role_definition = definition_map.get(role_definition_id, {})
                role_name = str(role_definition.get("properties", {}).get("roleName") or role_definition_id or "Azure Role")
                permissions = []
                for permission_block in role_definition.get("properties", {}).get("permissions", []):
                    actions = permission_block.get("actions", [])
                    permissions.extend(str(action) for action in actions[:12])
                permissions = permissions[:12]

                role_entity_id = _stable_id("azure_role_instance", str(assignment["id"]))
                entities.append(
                    Entity(
                        id=role_entity_id,
                        name=f"{role_name} @ {scope}",
                        kind="role",
                        source="Azure RBAC",
                        environment="cloud",
                        description="Role assignment materialized as a role instance for explainable scope analysis.",
                        criticality=4,
                        risk_score=70 if _looks_privileged_permissions(permissions) else 46,
                        tags=["azure", "rbac", "role-assignment"],
                    )
                )
                relationships.append(
                    Relationship(
                        id=_stable_id("rel", f"{principal_id}:{role_entity_id}:assigned_role"),
                        kind="assigned_role",
                        source=principal_id,
                        target=role_entity_id,
                        label=f"{principal_object_id} assigned {role_name}",
                        rationale="Azure RBAC role assignment at the configured scope.",
                        removable=True,
                        metadata={"origin": "azure-rbac", "scope": scope},
                    )
                )
                relationships.append(
                    Relationship(
                        id=_stable_id("rel", f"{role_entity_id}:{scope_resource_id}:role_grant"),
                        kind="role_grant",
                        source=role_entity_id,
                        target=scope_resource_id,
                        label=f"{role_name} effective on {scope}",
                        rationale="The Azure role assignment grants permissions at this scope and descendants.",
                        permissions=permissions or [role_name],
                        inherits=True,
                        metadata={"origin": "azure-rbac", "subscription_id": subscription_id},
                    )
                )

        duration_ms = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
        return _successful_bundle(
            connector_id=connector_id,
            name="Azure RBAC",
            source="Microsoft",
            surface="Azure RBAC",
            description="Subscription-scope Azure RBAC inventory based on the configured subscriptions.",
            collection_mode="hybrid",
            required_env=required_env,
            entities=entities,
            relationships=relationships,
            coverage=f"{len(subscription_ids)} subscriptions",
            latency_ms=duration_ms,
            notes=[
                "The current Azure RBAC collector uses subscription-scope reads and doesn't yet traverse management groups.",
                "Role assignments are collected with $filter=atScope(), so inherited assignments above the configured subscription still need a broader scope crawl.",
            ],
        )
    except Exception as exc:
        return _failed_bundle(connector_id, "Azure RBAC", "Microsoft", "hybrid", required_env, str(exc))


def _collect_okta_bundle() -> CollectionBundle:
    connector_id = "okta-ud"
    required_env = _required_env_for_connector(connector_id)
    if not _has_env_values(required_env):
        return _not_configured_bundle(
            connector_id,
            "Okta Universal Directory",
            "Okta",
            "incremental",
            required_env,
        )
    validation_errors = _validation_errors_for_connector(connector_id)
    if validation_errors:
        return _not_configured_bundle(
            connector_id,
            "Okta Universal Directory",
            "Okta",
            "incremental",
            required_env,
            notes=validation_errors,
        )

    base_url = os.getenv("EIP_OKTA_BASE_URL", "").rstrip("/")
    api_token = os.getenv("EIP_OKTA_API_TOKEN", "")
    group_limit = int(os.getenv("EIP_OKTA_GROUP_LIMIT", "100"))
    user_limit = int(os.getenv("EIP_OKTA_USER_LIMIT", "100"))
    started = datetime.now(tz=UTC)

    headers = {
        "Authorization": f"SSWS {api_token}",
        "Accept": "application/json",
    }
    try:
        entities: list[Entity] = []
        relationships: list[Relationship] = []
        groups = _okta_paginated_get(f"{base_url}/api/v1/groups?limit=200", headers=headers, limit=group_limit)
        users = _okta_paginated_get(f"{base_url}/api/v1/users?limit=200", headers=headers, limit=user_limit)

        group_ids: dict[str, str] = {}
        for group in groups:
            current_id = _stable_id("okta_group", str(group["id"]))
            group_ids[str(group["id"])] = current_id
            entities.append(
                Entity(
                    id=current_id,
                    name=str(group.get("profile", {}).get("name") or group["id"]),
                    kind="group",
                    source="Okta",
                    environment="cloud",
                    description="Okta group discovered from the Groups API.",
                    criticality=2,
                    risk_score=28,
                    tags=["okta", "group"],
                )
            )

        user_ids: dict[str, str] = {}
        for user in users:
            current_id = _stable_id("okta_principal", str(user["id"]))
            user_ids[str(user["id"])] = current_id
            entities.append(
                Entity(
                    id=current_id,
                    name=str(user.get("profile", {}).get("login") or user["id"]),
                    kind="user",
                    source="Okta",
                    environment="cloud",
                    description="Okta user discovered from the Users API.",
                    criticality=2,
                    risk_score=31,
                    tags=["okta", "user"],
                )
            )

        for group in groups:
            target_id = group_ids[str(group["id"])]
            members = _okta_paginated_get(
                f"{base_url}/api/v1/groups/{group['id']}/users?limit=200",
                headers=headers,
                limit=user_limit,
            )
            for member in members:
                member_id = user_ids.get(str(member["id"])) or _stable_id("okta_principal", str(member["id"]))
                relationships.append(
                    Relationship(
                        id=_stable_id("rel", f"{member_id}:{target_id}:member_of"),
                        kind="member_of",
                        source=member_id,
                        target=target_id,
                        label=f"{member.get('profile', {}).get('login') or member['id']} member of {group.get('profile', {}).get('name') or group['id']}",
                        rationale="Okta group membership discovered through the Groups API.",
                        removable=True,
                        metadata={"origin": "okta-groups-api"},
                    )
                )

        duration_ms = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
        return _successful_bundle(
            connector_id=connector_id,
            name="Okta Universal Directory",
            source="Okta",
            surface="Okta Universal Directory",
            description="Users, groups and group memberships collected from Okta.",
            collection_mode="incremental",
            required_env=required_env,
            entities=entities,
            relationships=relationships,
            coverage=f"{len(users)} users, {len(groups)} groups",
            latency_ms=duration_ms,
            notes=[
                "The default Okta users list omits DEPROVISIONED users, so leaver reconciliation still needs a dedicated pass.",
            ],
        )
    except Exception as exc:
        return _failed_bundle(connector_id, "Okta Universal Directory", "Okta", "incremental", required_env, str(exc))


def _collect_cyberark_bundle() -> CollectionBundle:
    connector_id = "cyberark-privileged"
    required_env = _required_env_for_connector(connector_id)
    if not _has_env_values(required_env):
        return _not_configured_bundle(
            connector_id,
            "CyberArk Privileged Access",
            "CyberArk",
            "snapshot",
            required_env,
        )
    validation_errors = _validation_errors_for_connector(connector_id)
    if validation_errors:
        return _not_configured_bundle(
            connector_id,
            "CyberArk Privileged Access",
            "CyberArk",
            "snapshot",
            required_env,
            notes=validation_errors,
        )

    base_url = os.getenv("EIP_CYBERARK_BASE_URL", "").rstrip("/")
    username = os.getenv("EIP_CYBERARK_USERNAME", "")
    password = os.getenv("EIP_CYBERARK_PASSWORD", "")
    auth_type = os.getenv("EIP_CYBERARK_AUTH_TYPE", "cyberark")
    safe_limit = int(os.getenv("EIP_CYBERARK_SAFE_LIMIT", "100"))
    started = datetime.now(tz=UTC)
    token: str | None = None

    try:
        with httpx.Client(timeout=30.0) as client:
            auth_response = client.post(
                f"{base_url}/PasswordVault/API/Auth/{auth_type}/Logon",
                json={"username": username, "password": password},
            )
            auth_response.raise_for_status()
            token_payload = auth_response.json()
            token = token_payload if isinstance(token_payload, str) else str(token_payload)
            headers = {"Authorization": token}

            safes_payload = client.get(
                f"{base_url}/PasswordVault/API/Safes",
                params={"limit": safe_limit},
                headers=headers,
            )
            safes_payload.raise_for_status()
            safes = safes_payload.json().get("value", [])

            entities: list[Entity] = []
            relationships: list[Relationship] = []
            for safe in safes[:safe_limit]:
                safe_name = str(safe.get("safeName") or safe.get("safeUrlId") or safe.get("id"))
                safe_id = _stable_id("cyberark_safe", safe_name)
                entities.append(
                    Entity(
                        id=safe_id,
                        name=safe_name,
                        kind="resource",
                        source="CyberArk",
                        environment="hybrid",
                        description="CyberArk safe discovered from the REST API.",
                        criticality=5,
                        risk_score=90,
                        tags=["cyberark", "safe", "privileged"],
                    )
                )
                members_response = client.get(
                    f"{base_url}/PasswordVault/API/Safes/{safe_name}/Members",
                    headers=headers,
                )
                members_response.raise_for_status()
                members = members_response.json().get("value", [])
                for member in members:
                    member_name = str(member.get("memberName") or member.get("username") or member.get("id"))
                    principal_id = _stable_id("cyberark_principal", member_name)
                    entities.append(
                        Entity(
                            id=principal_id,
                            name=member_name,
                            kind="group" if str(member.get("memberType", "")).lower() == "group" else "user",
                            source="CyberArk",
                            environment="hybrid",
                            description="Privileged member discovered from CyberArk safe membership.",
                            criticality=4,
                            risk_score=78,
                            tags=["cyberark", "privileged"],
                        )
                    )
                    permissions = [
                        key
                        for key, value in member.items()
                        if isinstance(value, bool) and value and key.lower() not in {"useaccounts", "retrieveaccounts"}
                    ]
                    relationships.append(
                        Relationship(
                            id=_stable_id("rel", f"{principal_id}:{safe_id}:direct_acl:{','.join(permissions)}"),
                            kind="direct_acl",
                            source=principal_id,
                            target=safe_id,
                            label=f"CyberArk safe membership on {safe_name}",
                            rationale="Safe membership enumerated through the CyberArk API hub surface.",
                            permissions=permissions or ["Member"],
                            removable=True,
                            metadata={"origin": "cyberark-safe-members"},
                        )
                    )

            duration_ms = int((datetime.now(tz=UTC) - started).total_seconds() * 1000)
            return _successful_bundle(
                connector_id=connector_id,
                name="CyberArk Privileged Access",
                source="CyberArk",
                surface="CyberArk Privileged Access / Secure Infrastructure Access",
                description="Privileged safe membership inventory from CyberArk.",
                collection_mode="snapshot",
                required_env=required_env,
                entities=entities,
                relationships=relationships,
                coverage=f"{len(safes)} safes",
                latency_ms=duration_ms,
            )
    except Exception as exc:
        return _failed_bundle(connector_id, "CyberArk Privileged Access", "CyberArk", "snapshot", required_env, str(exc))
    finally:
        if token:
            with httpx.Client(timeout=15.0) as client:
                try:
                    client.post(
                        f"{base_url}/PasswordVault/API/Auth/Logoff",
                        headers={"Authorization": token},
                    )
                except Exception:
                    logger.warning("CyberArk API logoff failed during collector cleanup.", exc_info=True)


def _stable_id(prefix: str, value: str) -> str:
    token = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{prefix}_{token[:42]}"


def _ldap_transitive_group_dns(
    *,
    connection: Connection,
    base_dn: str,
    principal_dn: str,
    size_limit: int,
) -> list[str] | None:
    filter_value = escape_filter_chars(principal_dn)
    search_filter = f"(member:1.2.840.113556.1.4.1941:={filter_value})"
    try:
        success = connection.search(
            base_dn,
            search_filter,
            attributes=["distinguishedName"],
            size_limit=size_limit,
        )
    except Exception:
        logger.info("LDAP_MATCHING_RULE_IN_CHAIN lookup failed; falling back to direct memberOf.", exc_info=True)
        return None
    if not success:
        description = str(connection.result.get("description", "")).lower()
        if description in {"inappropriatematching", "unwillingtoperform", "protocolerror"}:
            return None
        return []
    return [str(entry.distinguishedName) for entry in connection.entries]


def _parse_graph_site_ids(raw_value: str) -> list[str]:
    values = [item.strip() for item in re.split(r"[;\r\n]+", raw_value) if item.strip()]
    return values


def _graph_site_id_is_valid(value: str) -> bool:
    parts = [item.strip() for item in value.split(",") if item.strip()]
    return len(parts) == 3


def _has_env_values(required_env: list[str]) -> bool:
    return all(os.getenv(item) for item in required_env)


def _required_env_for_connector(connector_id: str) -> list[str]:
    blueprint = _blueprint(connector_id)
    return list(blueprint.configuration_env) if blueprint is not None else []


def _successful_bundle(
    *,
    connector_id: str,
    name: str,
    source: str,
    surface: str,
    description: str,
    collection_mode: str,
    required_env: list[str],
    entities: list[Entity],
    relationships: list[Relationship],
    coverage: str,
    latency_ms: int,
    notes: list[str] | None = None,
) -> CollectionBundle:
    notes = notes or []
    blueprint = _blueprint(connector_id)
    connector_status = ConnectorStatus(
        name=name,
        source=source,
        status="warning" if notes else "healthy",
        latency_ms=max(latency_ms, 1),
        last_sync=utc_now_iso(),
        coverage=coverage,
    )
    runtime_status = ConnectorRuntimeStatus(
        id=connector_id,
        name=name,
        source=source,
        surface=surface,
        implementation_status=blueprint.implementation_status if blueprint else "partial",
        configured=True,
        enabled=True,
        status="warning" if notes else "healthy",
        collection_mode=collection_mode,  # type: ignore[arg-type]
        description=description,
        required_env=required_env,
        required_permissions=blueprint.required_permissions if blueprint else [],
        supported_entities=blueprint.supported_entities if blueprint else [],
        tenant_requirements=blueprint.tenant_requirements if blueprint else [],
        official_limitations=blueprint.official_limitations if blueprint else [],
        current_runtime_coverage=blueprint.current_runtime_coverage if blueprint else [],
        documentation_links=blueprint.documentation_links if blueprint else [],
        notes=notes,
        last_sync=connector_status.last_sync,
        entity_count=len(entities),
        relationship_count=len(relationships),
    )
    insights = [
        InsightNote(
            title=f"{name} connector active",
            body=f"{coverage}.",
            tone="good" if not notes else "warn",
        )
    ]
    return CollectionBundle(
        entities=entities,
        relationships=relationships,
        connectors=[connector_status],
        insights=insights,
        notes=notes,
        runtime_status=runtime_status,
    )


def _not_configured_bundle(
    connector_id: str,
    surface: str,
    source: str,
    collection_mode: str,
    required_env: list[str],
    notes: list[str] | None = None,
) -> CollectionBundle:
    blueprint = _blueprint(connector_id)
    notes = list(notes or [])
    if blueprint and blueprint.implementation_status == "partial":
        notes.append("Current runtime coverage is partial compared with the full official target model.")
    return CollectionBundle(
        runtime_status=ConnectorRuntimeStatus(
            id=connector_id,
            name=surface,
            source=source,
            surface=surface,
            implementation_status=blueprint.implementation_status if blueprint else "partial",
            configured=False,
            enabled=False,
            status="needs_config",
            collection_mode=collection_mode,  # type: ignore[arg-type]
            description="Connector available but not configured with the required environment variables.",
            required_env=required_env,
            required_permissions=blueprint.required_permissions if blueprint else [],
            supported_entities=blueprint.supported_entities if blueprint else [],
            tenant_requirements=blueprint.tenant_requirements if blueprint else [],
            official_limitations=blueprint.official_limitations if blueprint else [],
            current_runtime_coverage=blueprint.current_runtime_coverage if blueprint else [],
            documentation_links=blueprint.documentation_links if blueprint else [],
            notes=notes,
        )
    )


def _failed_bundle(
    connector_id: str,
    surface: str,
    source: str,
    collection_mode: str,
    required_env: list[str],
    error: str,
) -> CollectionBundle:
    blueprint = _blueprint(connector_id)
    return CollectionBundle(
        connectors=[
            ConnectorStatus(
                name=surface,
                source=source,
                status="degraded",
                latency_ms=1,
                last_sync=utc_now_iso(),
                coverage="Collection failed",
            )
        ],
        insights=[
            InsightNote(
                title=f"{surface} connector failed",
                body=error,
                tone="warn",
            )
        ],
        notes=[error],
        runtime_status=ConnectorRuntimeStatus(
            id=connector_id,
            name=surface,
            source=source,
            surface=surface,
            implementation_status=blueprint.implementation_status if blueprint else "partial",
            configured=True,
            enabled=True,
            status="failed",
            collection_mode=collection_mode,  # type: ignore[arg-type]
            description="The connector is configured but the latest collection attempt failed.",
            required_env=required_env,
            required_permissions=blueprint.required_permissions if blueprint else [],
            supported_entities=blueprint.supported_entities if blueprint else [],
            tenant_requirements=blueprint.tenant_requirements if blueprint else [],
            official_limitations=blueprint.official_limitations if blueprint else [],
            current_runtime_coverage=blueprint.current_runtime_coverage if blueprint else [],
            documentation_links=blueprint.documentation_links if blueprint else [],
            notes=[error],
            last_sync=utc_now_iso(),
        ),
    )


def _blueprint(connector_id: str):
    for blueprint in build_connector_blueprints().blueprints:
        if blueprint.id == connector_id:
            return blueprint
    return None


def _validation_errors_for_connector(connector_id: str) -> list[str]:
    errors: list[str] = []
    if connector_id in {"entra-graph", "azure-rbac"}:
        if not _is_guid(os.getenv("EIP_GRAPH_TENANT_ID", "")):
            errors.append("EIP_GRAPH_TENANT_ID must be a GUID.")
        if not _is_guid(os.getenv("EIP_GRAPH_CLIENT_ID", "")):
            errors.append("EIP_GRAPH_CLIENT_ID must be a GUID.")
    if connector_id == "entra-graph":
        site_ids = _parse_graph_site_ids(os.getenv("EIP_GRAPH_SITE_IDS", ""))
        invalid_site_ids = [item for item in site_ids if not _graph_site_id_is_valid(item)]
        if invalid_site_ids:
            errors.append(
                "EIP_GRAPH_SITE_IDS must use semicolon-separated Graph site IDs; each site ID should keep its three comma-separated components intact."
            )
    if connector_id == "azure-rbac":
        subscription_ids = [item.strip() for item in os.getenv("EIP_AZURE_SUBSCRIPTION_IDS", "").split(",") if item.strip()]
        if not subscription_ids:
            errors.append("EIP_AZURE_SUBSCRIPTION_IDS must include at least one subscription GUID.")
        invalid_subscriptions = [item for item in subscription_ids if not _is_guid(item)]
        if invalid_subscriptions:
            errors.append("EIP_AZURE_SUBSCRIPTION_IDS must contain only GUID subscription IDs.")
    if connector_id == "ad-ldap":
        server_uri = os.getenv("EIP_LDAP_SERVER_URI", "")
        if server_uri and not server_uri.startswith(("ldap://", "ldaps://")):
            errors.append("EIP_LDAP_SERVER_URI must start with ldap:// or ldaps://.")
        base_dn = os.getenv("EIP_LDAP_BASE_DN", "")
        if base_dn and "=" not in base_dn:
            errors.append("EIP_LDAP_BASE_DN should look like a distinguished name, for example DC=example,DC=com.")
    if connector_id == "okta-ud":
        base_url = os.getenv("EIP_OKTA_BASE_URL", "")
        if base_url and not _is_https_url(base_url):
            errors.append("EIP_OKTA_BASE_URL must be an https URL.")
        if "-admin." in base_url.lower():
            errors.append("EIP_OKTA_BASE_URL should be the Okta org base URL, not the -admin console URL.")
    if connector_id == "aws-iam":
        account_ids = [item.strip() for item in os.getenv("EIP_AWS_ACCOUNT_IDS", "").split(",") if item.strip()]
        invalid_account_ids = [item for item in account_ids if not ACCOUNT_ID_PATTERN.match(item)]
        if invalid_account_ids:
            errors.append("EIP_AWS_ACCOUNT_IDS must contain only 12-digit AWS account IDs.")
    if connector_id in {"google-directory", "google-drive-collaboration"}:
        customer_id = os.getenv("EIP_GOOGLE_CUSTOMER_ID", "").strip()
        if customer_id and customer_id != "my_customer" and not customer_id.startswith("C"):
            errors.append("EIP_GOOGLE_CUSTOMER_ID should be my_customer or a Google customer ID such as C0123abc.")
        admin_subject = os.getenv("EIP_GOOGLE_ADMIN_SUBJECT", "").strip()
        if admin_subject and not EMAIL_PATTERN.match(admin_subject):
            errors.append("EIP_GOOGLE_ADMIN_SUBJECT must be an administrator email address.")
        service_account_json = os.getenv("EIP_GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if service_account_json:
            parsed_json = _json_env_value(service_account_json)
            required_keys = {"client_email", "private_key", "token_uri"}
            if not isinstance(parsed_json, dict) or not required_keys.issubset(parsed_json):
                errors.append(
                    "EIP_GOOGLE_SERVICE_ACCOUNT_JSON must be a JSON object or file path containing client_email, private_key and token_uri."
                )
    if connector_id == "cyberark-privileged":
        base_url = os.getenv("EIP_CYBERARK_BASE_URL", "")
        if base_url and not _is_https_url(base_url):
            errors.append("EIP_CYBERARK_BASE_URL should use https.")
    return errors


def _is_guid(value: str) -> bool:
    return bool(GUID_PATTERN.match(value.strip()))


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and bool(parsed.netloc)


def _json_env_value(value: str) -> dict[str, Any] | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        if candidate.startswith("{"):
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        if os.path.exists(candidate):
            with open(candidate, encoding="utf-8") as handle:
                parsed = json.load(handle)
                return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
    return None


def _client_credentials_token(*, token_url: str, client_id: str, client_secret: str, scope: str) -> str:
    response = httpx.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": scope,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def _graph_get(url: str, *, headers: dict[str, str]) -> dict[str, Any]:
    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def _graph_batch_collection(
    *,
    requests: list[dict[str, Any]],
    headers: dict[str, str],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    if not requests:
        return {}
    results: dict[str, list[dict[str, Any]]] = {}
    with httpx.Client(timeout=30.0) as client:
        for index in range(0, len(requests), 20):
            chunk = requests[index : index + 20]
            response = client.post(
                "https://graph.microsoft.com/v1.0/$batch",
                headers={**headers, "Content-Type": "application/json"},
                json={"requests": chunk},
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("responses", []):
                if item.get("status") != 200:
                    continue
                body = item.get("body", {})
                values = list(body.get("value", []))
                next_link = body.get("@odata.nextLink")
                if next_link:
                    values.extend(
                        _paginated_get(
                            next_link,
                            headers=headers,
                            limit=limit,
                        )
                    )
                results[str(item.get("id"))] = values[:limit]
    return results


def _paginated_get(
    url: str,
    *,
    headers: dict[str, str],
    limit: int,
    value_key: str = "value",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    next_url: str | None = url
    while next_url and len(items) < limit:
        response = httpx.get(next_url, headers=headers, timeout=30.0)
        response.raise_for_status()
        payload = response.json()
        page_items = payload.get(value_key, [])
        items.extend(page_items)
        next_url = payload.get("@odata.nextLink")
    return items[:limit]


def _okta_paginated_get(url: str, *, headers: dict[str, str], limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    next_url: str | None = url
    with httpx.Client(timeout=30.0) as client:
        while next_url and len(items) < limit:
            response = client.get(next_url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
            else:
                break
            next_url = _okta_next_link(response.headers.get("link"))
    return items[:limit]


def _okta_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            candidate = part.split(";", 1)[0].strip()
            return candidate.strip("<>")
    return None


def _looks_privileged_permissions(permissions: list[str]) -> bool:
    lowered = " ".join(permission.lower() for permission in permissions)
    return any(marker in lowered for marker in ("write", "delete", "owner", "*", "roleassignments"))
