from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
import hashlib
import re

from app.demo_data import build_demo_snapshot
from app.models import (
    AccessPath,
    CatalogResponse,
    Entity,
    EntityDetailResponse,
    EntitySummary,
    ExplainResponse,
    FlowEdge,
    FlowNode,
    FlowPayload,
    GraphEdge,
    GraphNode,
    GraphPayload,
    GroupClosureRecord,
    Hotspot,
    IdentityClusterDetailResponse,
    IdentityClusterMember,
    IdentityClusterResource,
    IdentityClustersResponse,
    IdentityClusterSummary,
    MetricCard,
    OverviewResponse,
    PathStep,
    PrincipalAccessResponse,
    PrincipalResourceRecord,
    Relationship,
    ResourceHierarchyRecord,
    ResourceAccessRecord,
    ResourceAccessResponse,
    ResourceImpact,
    ScenarioChoice,
    SearchResult,
    Snapshot,
    WhatIfDiffItem,
    WhatIfResponse,
)

PRINCIPAL_KINDS = {"user", "service_account", "group"}
CORRELATABLE_PRINCIPAL_KINDS = {"user", "service_account"}
TRAVERSABLE_RELATIONSHIPS = {
    "member_of",
    "nested_group",
    "delegated_access",
    "assigned_role",
}
GRANT_RELATIONSHIPS = {"direct_acl", "role_grant"}
PRIVILEGED_KEYWORDS = (
    "write",
    "delete",
    "fullaccess",
    "fullcontrol",
    "modify",
    "setsecret",
    "deploy",
    "owner",
    "share",
    "admin",
    "takeownership",
    "changepermissions",
)
GENERIC_IDENTITY_ALIASES = {
    "admin",
    "administrator",
    "root",
    "guest",
    "system",
    "service",
    "daemon",
    "users",
}


@dataclass(frozen=True)
class ResolvedPath:
    principal_id: str
    resource_id: str
    permissions: tuple[str, ...]
    relationships: tuple[Relationship, ...]
    access_mode: str
    narrative: str
    risk_score: int


class AccessGraphEngine:
    def __init__(self, snapshot: Snapshot | None = None) -> None:
        self.snapshot = snapshot or build_demo_snapshot()
        self.entities = {entity.id: entity for entity in self.snapshot.entities}
        self.relationships = self.snapshot.relationships
        self.relationships_by_id = {relationship.id: relationship for relationship in self.relationships}
        self.actor_adjacency: dict[str, list[Relationship]] = defaultdict(list)
        self.resource_children: dict[str, list[Relationship]] = defaultdict(list)
        self.resource_parent: dict[str, Relationship] = {}
        self.grant_relationships: list[Relationship] = []
        self.grant_relationships_by_source: dict[str, list[Relationship]] = defaultdict(list)
        self.deny_relationships_by_resource: dict[str, list[Relationship]] = defaultdict(list)
        self._resource_ancestor_cache: dict[str, tuple[str, ...]] = {}
        self._resource_chain_cache: dict[tuple[str, str], tuple[Relationship, ...]] = {}
        self._actor_reachability_cache: dict[
            tuple[str, frozenset[str]], dict[str, list[tuple[Relationship, ...]]]
        ] = {}
        self._effective_access_cache: dict[frozenset[str], dict[tuple[str, str], dict[str, object]]] = {}
        self._impact_surface_cache: dict[str, list[str]] = {}
        self._impacted_principal_cache: dict[str, list[str]] = {}
        self._overview_cache: OverviewResponse | None = None
        self._catalog_cache: CatalogResponse | None = None
        self._resource_access_cache: dict[str, ResourceAccessResponse] = {}
        self._principal_access_cache: dict[str, PrincipalAccessResponse] = {}
        self._explain_cache: dict[tuple[str, str], ExplainResponse] = {}
        self._simulation_cache: dict[tuple[str, str | None], WhatIfResponse] = {}
        self._identity_clusters_cache: IdentityClustersResponse | None = None
        self._identity_cluster_detail_cache: dict[str, IdentityClusterDetailResponse] = {}
        self._identity_cluster_index: dict[str, dict[str, object]] | None = None
        self._principal_group_closure_cache: dict[str, list[GroupClosureRecord]] = {}
        self._resource_hierarchy_closure_cache: dict[str, list[ResourceHierarchyRecord]] = {}

        for relationship in self.relationships:
            if relationship.kind in TRAVERSABLE_RELATIONSHIPS:
                self.actor_adjacency[relationship.source].append(relationship)
            elif relationship.kind == "contains":
                self.resource_children[relationship.source].append(relationship)
                self.resource_parent[relationship.target] = relationship
            elif relationship.kind in GRANT_RELATIONSHIPS:
                self.grant_relationships.append(relationship)
                self.grant_relationships_by_source[relationship.source].append(relationship)
            elif relationship.kind == "deny_acl":
                self.deny_relationships_by_resource[relationship.target].append(relationship)

        self.principal_ids = [
            entity.id for entity in self.entities.values() if entity.kind in PRINCIPAL_KINDS
        ]
        self.resource_ids = [
            entity.id for entity in self.entities.values() if entity.kind == "resource"
        ]
        self.resource_descendants: dict[str, list[str]] = defaultdict(list)
        for resource_id in self.resource_ids:
            for ancestor_id in self._resource_ancestors(resource_id):
                self.resource_descendants[ancestor_id].append(resource_id)
        self._search_index = [
            (
                entity,
                " ".join(
                    [
                        entity.name.lower(),
                        entity.description.lower(),
                        entity.source.lower(),
                        " ".join(tag.lower() for tag in entity.tags),
                        entity.kind.lower(),
                    ]
                ),
            )
            for entity in self.entities.values()
        ]

    def get_overview(self) -> OverviewResponse:
        if self._overview_cache is not None:
            return self._overview_cache

        effective_map = self._effective_access_map()
        all_paths = [path for entry in effective_map.values() for path in entry["paths"]]
        principals = [entity for entity in self.entities.values() if entity.kind in PRINCIPAL_KINDS]
        resources = [entity for entity in self.entities.values() if entity.kind == "resource"]

        privileged_path_count = sum(
            1 for path in all_paths if self._is_privileged_permission_set(path.permissions)
        )
        delegated_path_count = sum(
            1 for path in all_paths if any(rel.kind == "delegated_access" for rel in path.relationships)
        )

        metrics = [
            MetricCard(
                title="Principals in scope",
                value=str(len(principals)),
                delta=f"{sum(1 for entity in principals if entity.kind == 'group')} groups included",
                tone="good" if principals else "warn",
                description="Users, service identities and access groups materialized from the live snapshot.",
            ),
            MetricCard(
                title="Resources modeled",
                value=str(len(resources)),
                delta=f"{len(self.snapshot.connectors)} active collectors",
                tone="neutral",
                description="Live filesystem objects normalized into one explainable access graph.",
            ),
            MetricCard(
                title="Effective access paths",
                value=str(len(effective_map)),
                delta=f"{delegated_path_count} delegated",
                tone="warn" if delegated_path_count else "good",
                description="Unique principal-to-resource entitlements after membership, ACL and deny evaluation.",
            ),
            MetricCard(
                title="Privileged paths",
                value=str(privileged_path_count),
                delta=f"{sum(1 for rel in self.relationships if rel.kind == 'deny_acl')} deny entries modeled",
                tone="critical" if privileged_path_count >= 8 else "warn" if privileged_path_count else "good",
                description="Paths containing modify, write, delete or stronger permissions.",
            ),
        ]

        hotspots = self._build_hotspots(effective_map)
        scenarios = self._build_scenarios()
        default_principal_id, default_resource_id = self._default_selection(effective_map)
        default_scenario_edge_id = scenarios[0].edge_id if scenarios else None

        self._overview_cache = OverviewResponse(
            tenant=self.snapshot.tenant,
            generated_at=self.snapshot.generated_at,
            metrics=metrics,
            connectors=self.snapshot.connectors,
            hotspots=hotspots,
            scenarios=scenarios,
            history=self.snapshot.history,
            insights=self.snapshot.insights,
            default_principal_id=default_principal_id,
            default_resource_id=default_resource_id,
            default_scenario_edge_id=default_scenario_edge_id,
        )
        return self._overview_cache

    def get_catalog(self) -> CatalogResponse:
        if self._catalog_cache is not None:
            return self._catalog_cache

        principals = sorted(
            (self._summary(entity.id) for entity in self.entities.values() if entity.kind in PRINCIPAL_KINDS),
            key=lambda item: item.name,
        )
        resources = sorted(
            (self._summary(entity.id) for entity in self.entities.values() if entity.kind == "resource"),
            key=lambda item: item.name,
        )
        scenarios = self._build_scenarios()
        self._catalog_cache = CatalogResponse(
            principals=principals,
            resources=resources,
            scenarios=scenarios,
        )
        return self._catalog_cache

    def search(self, query: str) -> list[SearchResult]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        matches: list[tuple[int, SearchResult]] = []
        for entity, haystack in self._search_index:
            if normalized_query not in haystack:
                continue

            score = 20
            if entity.name.lower().startswith(normalized_query):
                score += 40
            if normalized_query in entity.name.lower():
                score += 20
            if entity.kind == "resource":
                score += 5
            matches.append(
                (
                    score,
                    SearchResult(
                        entity=self._summary(entity.id),
                        headline=f"{entity.kind.replace('_', ' ').title()} via {entity.source}",
                        keywords=entity.tags[:4],
                    ),
                )
            )

        matches.sort(key=lambda item: (-item[0], item[1].entity.name))
        return [result for _, result in matches[:8]]

    def materialized_access_index(self) -> list[dict[str, object]]:
        effective_map = self._effective_access_map()
        return self._materialized_rows_from_access_map(effective_map)

    def materialized_access_index_for_scope(
        self,
        principal_ids,
        resource_ids,
    ) -> list[dict[str, object]]:
        effective_map = self._effective_access_subset(principal_ids, resource_ids)
        return self._materialized_rows_from_access_map(effective_map)

    def _materialized_rows_from_access_map(
        self,
        effective_map: dict[tuple[str, str], dict[str, object]],
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for (principal_id, resource_id), entry in effective_map.items():
            paths = entry["paths"]
            best_path = paths[0]
            rows.append(
                {
                    "principal_id": principal_id,
                    "resource_id": resource_id,
                    "permissions": self._flatten_permissions(paths),
                    "path_count": len(paths),
                    "path_complexity": self._path_complexity_score(best_path),
                    "access_mode": self._combine_access_modes(path.access_mode for path in paths),
                    "risk_score": max(path.risk_score for path in paths),
                    "why": best_path.narrative,
                }
            )
        rows.sort(key=lambda item: (-int(item["risk_score"]), str(item["principal_id"]), str(item["resource_id"])))
        return rows

    def impacted_principal_ids_for_relationship(self, relationship: Relationship) -> list[str]:
        return self._impacted_principal_ids_for_relationship(relationship)

    def impacted_resource_ids_for_relationship(self, relationship: Relationship) -> list[str]:
        return self._impact_surface_for_relationship(relationship)

    def impacted_principal_ids_for_actor(self, actor_id: str) -> list[str]:
        if actor_id not in self.entities:
            return []
        impacted = [
            principal_id
            for principal_id in self.principal_ids
            if actor_id in self._actor_reachability(principal_id, frozenset())
        ]
        impacted.sort(key=lambda principal_id: self.entities[principal_id].name.lower())
        return impacted

    def impacted_resource_ids_for_actor(self, actor_id: str) -> list[str]:
        if actor_id not in self.entities:
            return []
        impacted = self._impact_surface_from_actor(actor_id)
        return sorted(
            set(impacted),
            key=lambda resource_id: self.entities[resource_id].name.lower(),
        )

    def affected_resource_ids_for_resource(self, resource_id: str) -> list[str]:
        if resource_id not in self.entities or self.entities[resource_id].kind != "resource":
            return []
        affected = set(self.resource_descendants.get(resource_id, [resource_id]))
        affected.add(resource_id)
        return sorted(
            affected,
            key=lambda affected_resource_id: self.entities[affected_resource_id].name.lower(),
        )

    def resource_exposure_index(self) -> list[dict[str, object]]:
        rows = self.materialized_access_index()
        return self.resource_exposure_index_from_rows(rows)

    def resource_exposure_index_from_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        buckets: dict[str, dict[str, object]] = {}
        for row in rows:
            resource_id = str(row["resource_id"])
            bucket = buckets.setdefault(
                resource_id,
                {
                    "resource_id": resource_id,
                    "principal_count": 0,
                    "privileged_principal_count": 0,
                    "max_risk_score": 0,
                    "path_complexity_total": 0,
                },
            )
            bucket["principal_count"] = int(bucket["principal_count"]) + 1
            if self._is_privileged_permission_set(row["permissions"]):
                bucket["privileged_principal_count"] = int(bucket["privileged_principal_count"]) + 1
            bucket["max_risk_score"] = max(int(bucket["max_risk_score"]), int(row["risk_score"]))
            bucket["path_complexity_total"] = int(bucket["path_complexity_total"]) + int(
                row.get("path_complexity", 0)
            )

        materialized = []
        for bucket in buckets.values():
            principal_count = max(1, int(bucket["principal_count"]))
            average_path_complexity = round(int(bucket["path_complexity_total"]) / principal_count)
            exposure_score = min(
                99,
                int(bucket["max_risk_score"])
                + int(bucket["privileged_principal_count"]) * 6
                + average_path_complexity // 3,
            )
            materialized.append(
                {
                    "resource_id": str(bucket["resource_id"]),
                    "principal_count": int(bucket["principal_count"]),
                    "privileged_principal_count": int(bucket["privileged_principal_count"]),
                    "max_risk_score": int(bucket["max_risk_score"]),
                    "average_path_complexity": average_path_complexity,
                    "exposure_score": exposure_score,
                }
            )
        materialized.sort(
            key=lambda item: (
                int(item["exposure_score"]),
                int(item["principal_count"]),
                self.entities[str(item["resource_id"])].name,
            ),
            reverse=True,
        )
        return materialized

    def principal_access_summary_index(self) -> list[dict[str, object]]:
        rows = self.materialized_access_index()
        return self.principal_access_summary_index_from_rows(rows)

    def principal_access_summary_index_from_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        buckets: dict[str, dict[str, object]] = {}
        for row in rows:
            principal_id = str(row["principal_id"])
            bucket = buckets.setdefault(
                principal_id,
                {
                    "principal_id": principal_id,
                    "resource_count": 0,
                    "privileged_resource_count": 0,
                    "max_risk_score": 0,
                    "path_complexity_total": 0,
                },
            )
            bucket["resource_count"] = int(bucket["resource_count"]) + 1
            if self._is_privileged_permission_set(row["permissions"]):
                bucket["privileged_resource_count"] = int(bucket["privileged_resource_count"]) + 1
            bucket["max_risk_score"] = max(int(bucket["max_risk_score"]), int(row["risk_score"]))
            bucket["path_complexity_total"] = int(bucket["path_complexity_total"]) + int(
                row.get("path_complexity", 0)
            )

        materialized = []
        for bucket in buckets.values():
            resource_count = max(1, int(bucket["resource_count"]))
            average_path_complexity = round(int(bucket["path_complexity_total"]) / resource_count)
            exposure_score = min(
                99,
                int(bucket["max_risk_score"])
                + int(bucket["privileged_resource_count"]) * 5
                + average_path_complexity // 4,
            )
            materialized.append(
                {
                    "principal_id": str(bucket["principal_id"]),
                    "resource_count": int(bucket["resource_count"]),
                    "privileged_resource_count": int(bucket["privileged_resource_count"]),
                    "max_risk_score": int(bucket["max_risk_score"]),
                    "average_path_complexity": average_path_complexity,
                    "exposure_score": exposure_score,
                }
            )
        materialized.sort(
            key=lambda item: (
                int(item["exposure_score"]),
                int(item["resource_count"]),
                self.entities[str(item["principal_id"])].name,
            ),
            reverse=True,
        )
        return materialized

    def get_resource_access(self, resource_id: str) -> ResourceAccessResponse:
        cached = self._resource_access_cache.get(resource_id)
        if cached is not None:
            return cached

        resource = self._entity(resource_id)
        records: list[ResourceAccessRecord] = []

        for principal in self._principal_entities():
            paths = self._resolve_paths(principal.id, resource_id)
            if not paths:
                continue

            records.append(
                ResourceAccessRecord(
                    principal=self._summary(principal.id),
                    permissions=self._flatten_permissions(paths),
                    path_count=len(paths),
                    path_complexity=self._path_complexity_score(paths[0]),
                    access_mode=self._combine_access_modes(path.access_mode for path in paths),
                    risk_score=max(path.risk_score for path in paths),
                    why=paths[0].narrative,
                )
            )

        records.sort(key=lambda item: (-item.risk_score, item.principal.name))
        privileged_principal_count = sum(
            1 for record in records if self._is_privileged_permission_set(record.permissions)
        )
        response = ResourceAccessResponse(
            resource=self._summary(resource.id),
            total_principals=len(records),
            privileged_principal_count=privileged_principal_count,
            offset=0,
            limit=max(1, len(records)) if records else 1,
            returned_count=len(records),
            has_more=False,
            records=records,
        )
        self._resource_access_cache[resource_id] = response
        return response

    def get_principal_access(self, principal_id: str) -> PrincipalAccessResponse:
        cached = self._principal_access_cache.get(principal_id)
        if cached is not None:
            return cached

        principal = self._entity(principal_id)
        records: list[PrincipalResourceRecord] = []

        for resource in self._resource_entities():
            paths = self._resolve_paths(principal_id, resource.id)
            if not paths:
                continue

            records.append(
                PrincipalResourceRecord(
                    resource=self._summary(resource.id),
                    permissions=self._flatten_permissions(paths),
                    path_count=len(paths),
                    path_complexity=self._path_complexity_score(paths[0]),
                    access_mode=self._combine_access_modes(path.access_mode for path in paths),
                    risk_score=max(path.risk_score for path in paths),
                    why=paths[0].narrative,
                )
            )

        records.sort(key=lambda item: (-item.risk_score, item.resource.name))
        privileged_resources = sum(
            1 for record in records if self._is_privileged_permission_set(record.permissions)
        )
        response = PrincipalAccessResponse(
            principal=self._summary(principal.id),
            total_resources=len(records),
            privileged_resources=privileged_resources,
            offset=0,
            limit=max(1, len(records)) if records else 1,
            returned_count=len(records),
            has_more=False,
            records=records,
        )
        self._principal_access_cache[principal_id] = response
        return response

    def explain(self, principal_id: str, resource_id: str) -> ExplainResponse:
        cache_key = (principal_id, resource_id)
        cached = self._explain_cache.get(cache_key)
        if cached is not None:
            return cached

        principal = self._entity(principal_id)
        resource = self._entity(resource_id)
        paths = self._resolve_paths(principal_id, resource_id)
        if not paths:
            raise KeyError(f"No effective access between {principal_id} and {resource_id}")

        response_paths = [self._to_access_path(path) for path in paths]
        response = ExplainResponse(
            principal=self._summary(principal.id),
            resource=self._summary(resource.id),
            permissions=self._flatten_permissions(paths),
            path_count=len(paths),
            risk_score=max(path.risk_score for path in paths),
            paths=response_paths,
            graph=self._build_graph(paths),
        )
        self._explain_cache[cache_key] = response
        return response

    def entity_detail(self, entity_id: str) -> EntityDetailResponse:
        entity = self._entity(entity_id)
        inbound = [
            self._to_path_step(relationship)
            for relationship in self.relationships
            if relationship.target == entity_id
        ]
        outbound = [
            self._to_path_step(relationship)
            for relationship in self.relationships
            if relationship.source == entity_id
        ]
        perspective = (
            "resource"
            if entity.kind == "resource"
            else "principal"
            if entity.kind in PRINCIPAL_KINDS
            else "supporting"
        )
        return EntityDetailResponse(
            entity=entity,
            perspective=perspective,
            inbound=inbound,
            outbound=outbound,
        )

    def summary(self, entity_id: str) -> EntitySummary:
        return self._summary(entity_id)

    def is_privileged_permissions(self, permissions) -> bool:
        return self._is_privileged_permission_set(permissions)

    def simulate_edge_removal(
        self, edge_id: str, focus_resource_id: str | None = None
    ) -> WhatIfResponse:
        cache_key = (edge_id, focus_resource_id)
        cached = self._simulation_cache.get(cache_key)
        if cached is not None:
            return cached

        edge = self.relationships_by_id.get(edge_id)
        if edge is None:
            raise KeyError(f"Unknown relationship: {edge_id}")
        if not edge.removable:
            raise ValueError(f"Relationship is not marked removable: {edge_id}")

        before_map = self._effective_access_map()
        impacted_principal_ids = self._impacted_principal_ids_for_relationship(edge)
        impacted_resource_ids = self._impact_surface_for_relationship(edge)
        relevant_before = {
            key: entry
            for key, entry in before_map.items()
            if key[0] in impacted_principal_ids and key[1] in impacted_resource_ids
        }
        after_map = self._effective_access_subset(
            impacted_principal_ids,
            impacted_resource_ids,
            ignored_edge_ids={edge_id},
        )
        diff = self._diff_effective_access(relevant_before, after_map)

        impacted_principals = {item.principal.id for item in diff}
        impacted_resources = {item.resource.id for item in diff}
        removed_paths = self._removed_path_count(relevant_before, after_map)
        privileged_paths_removed = sum(
            1
            for item in diff
            if self._is_privileged_permission_set(item.removed_permissions)
        )

        resource_impact: dict[str, dict[str, int]] = {}
        for item in diff:
            stats = resource_impact.setdefault(
                item.resource.id,
                {"principals": 0, "permissions": 0},
            )
            stats["principals"] += 1
            stats["permissions"] += len(item.removed_permissions)

        blast_radius = [
            ResourceImpact(
                resource=self._summary(resource_id),
                removed_principal_count=stats["principals"],
                removed_permission_count=stats["permissions"],
                severity=self._severity_for_resource_impact(resource_id, stats["permissions"]),
            )
            for resource_id, stats in resource_impact.items()
        ]
        blast_radius.sort(
            key=lambda item: (
                self.entities[item.resource.id].criticality,
                item.removed_permission_count,
                item.resource.name,
            ),
            reverse=True,
        )

        if focus_resource_id is None:
            focus_resource_id = blast_radius[0].resource.id if blast_radius else None

        focus_before = (
            self.get_resource_access(focus_resource_id).records if focus_resource_id else []
        )
        focus_after = (
            self._resource_access_for_map(
                focus_resource_id,
                self._effective_access_subset(
                    self.principal_ids,
                    [focus_resource_id],
                    ignored_edge_ids={edge_id},
                ),
            )
            if focus_resource_id
            else []
        )

        narrative = self._simulate_narrative(edge, diff, blast_radius)
        flow = self._build_flow(edge, diff)

        response = WhatIfResponse(
            edge=edge,
            narrative=narrative,
            impacted_principals=len(impacted_principals),
            impacted_resources=len(impacted_resources),
            removed_paths=removed_paths,
            privileged_paths_removed=privileged_paths_removed,
            recomputed_principals=len(impacted_principal_ids),
            recomputed_resources=len(impacted_resource_ids),
            recomputed_pairs=len(impacted_principal_ids) * len(impacted_resource_ids),
            diff=diff[:10],
            blast_radius=blast_radius[:6],
            focus_resource_id=focus_resource_id,
            focus_before=focus_before,
            focus_after=focus_after,
            flow=flow,
        )
        self._simulation_cache[cache_key] = response
        return response

    def identity_clusters(self) -> IdentityClustersResponse:
        if self._identity_clusters_cache is not None:
            return self._identity_clusters_cache

        cluster_index = self._materialize_identity_clusters()
        clusters = [
            item["summary"]
            for item in sorted(
                cluster_index.values(),
                key=lambda item: (
                    item["summary"].source_count,
                    item["summary"].combined_resource_count,
                    item["summary"].max_risk_score,
                    item["summary"].display_name,
                ),
                reverse=True,
            )
        ]
        self._identity_clusters_cache = IdentityClustersResponse(
            generated_at=self.snapshot.generated_at,
            total_clusters=len(clusters),
            clusters=clusters,
        )
        return self._identity_clusters_cache

    def identity_cluster_detail(self, cluster_id: str) -> IdentityClusterDetailResponse:
        cached = self._identity_cluster_detail_cache.get(cluster_id)
        if cached is not None:
            return cached

        cluster_index = self._materialize_identity_clusters()
        cluster_payload = cluster_index.get(cluster_id)
        if cluster_payload is None:
            raise KeyError(f"Unknown identity cluster: {cluster_id}")

        detail = IdentityClusterDetailResponse(
            cluster=cluster_payload["summary"],
            members=cluster_payload["members"],
            top_resources=cluster_payload["resources"],
        )
        self._identity_cluster_detail_cache[cluster_id] = detail
        return detail

    def _materialize_identity_clusters(self) -> dict[str, dict[str, object]]:
        if self._identity_cluster_index is not None:
            return self._identity_cluster_index

        principal_entities = [
            entity
            for entity in self._principal_entities()
            if entity.kind in CORRELATABLE_PRINCIPAL_KINDS
        ]
        if len(principal_entities) < 2:
            self._identity_cluster_index = {}
            return self._identity_cluster_index

        key_buckets: dict[str, set[str]] = defaultdict(set)
        entity_keys: dict[str, list[str]] = {}
        for entity in principal_entities:
            keys = self._identity_match_keys(entity)
            entity_keys[entity.id] = keys
            for key in keys:
                key_buckets[key].add(entity.id)

        parents = {entity.id: entity.id for entity in principal_entities}

        def find(entity_id: str) -> str:
            root = parents[entity_id]
            while root != parents[root]:
                root = parents[root]
            while entity_id != root:
                parent = parents[entity_id]
                parents[entity_id] = root
                entity_id = parent
            return root

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for key, entity_ids in key_buckets.items():
            if len(entity_ids) < 2:
                continue
            if len(entity_ids) > 12:
                continue
            bucket_entities = [self.entities[entity_id] for entity_id in entity_ids]
            distinct_sources = {entity.source for entity in bucket_entities}
            distinct_names = {entity.name.lower() for entity in bucket_entities}
            if len(distinct_sources) < 2 and len(distinct_names) < 2:
                continue
            ordered_ids = sorted(entity_ids)
            anchor = ordered_ids[0]
            for entity_id in ordered_ids[1:]:
                union(anchor, entity_id)

        grouped_entities: dict[str, list[Entity]] = defaultdict(list)
        for entity in principal_entities:
            root = find(entity.id)
            grouped_entities[root].append(entity)

        cluster_index: dict[str, dict[str, object]] = {}
        for members in grouped_entities.values():
            if len(members) < 2:
                continue

            shared_keys = sorted(
                key
                for key, entity_ids in key_buckets.items()
                if len(entity_ids.intersection({member.id for member in members})) >= 2
            )
            if not shared_keys:
                continue

            members.sort(key=lambda item: (item.source, item.name))
            cluster_id = self._stable_cluster_id(member.id for member in members)
            summary = self._build_identity_cluster_summary(cluster_id, members, shared_keys)
            member_payload = self._build_identity_cluster_members(members, entity_keys, shared_keys)
            resource_payload = self._build_identity_cluster_resources(members)
            cluster_index[cluster_id] = {
                "summary": summary.model_copy(
                    update={
                        "combined_resource_count": len(resource_payload),
                        "max_risk_score": max((resource.max_risk_score for resource in resource_payload), default=0),
                    }
                ),
                "members": member_payload,
                "resources": resource_payload[:8],
            }

        self._identity_cluster_index = cluster_index
        return self._identity_cluster_index

    def _build_identity_cluster_summary(
        self,
        cluster_id: str,
        members: list[Entity],
        shared_keys: list[str],
    ) -> IdentityClusterSummary:
        preferred_names = sorted(members, key=lambda entity: (self._display_name_rank(entity), entity.name))
        display_name = preferred_names[0].name if preferred_names else cluster_id
        sources = sorted({member.source for member in members})
        return IdentityClusterSummary(
            id=cluster_id,
            display_name=display_name,
            entity_count=len(members),
            source_count=len(sources),
            sources=sources,
            match_keys=[self._humanize_match_key(key) for key in shared_keys[:4]],
        )

    def _build_identity_cluster_members(
        self,
        members: list[Entity],
        entity_keys: dict[str, list[str]],
        shared_keys: list[str],
    ) -> list[IdentityClusterMember]:
        shared_key_set = set(shared_keys)
        payload: list[IdentityClusterMember] = []
        for member in members:
            matching_keys = [key for key in entity_keys.get(member.id, []) if key in shared_key_set]
            confidence = min(98, 68 + len(matching_keys) * 10)
            evidence = [self._humanize_match_key(key) for key in matching_keys[:3]]
            payload.append(
                IdentityClusterMember(
                    entity=self._summary(member.id),
                    confidence=confidence,
                    evidence=evidence,
                    match_keys=evidence,
                )
            )
        payload.sort(key=lambda item: (-item.confidence, item.entity.source, item.entity.name))
        return payload

    def _build_identity_cluster_resources(
        self,
        members: list[Entity],
    ) -> list[IdentityClusterResource]:
        resource_stats: dict[str, dict[str, object]] = {}
        for member in members:
            for record in self.get_principal_access(member.id).records:
                stats = resource_stats.setdefault(
                    record.resource.id,
                    {
                        "permissions": set(),
                        "contributors": {},
                        "max_risk_score": 0,
                        "path_count": 0,
                    },
                )
                stats["permissions"].update(record.permissions)
                stats["contributors"][member.id] = self._summary(member.id)
                stats["max_risk_score"] = max(int(stats["max_risk_score"]), record.risk_score)
                stats["path_count"] = int(stats["path_count"]) + record.path_count

        resources = [
            IdentityClusterResource(
                resource=self._summary(resource_id),
                permissions=sorted(stats["permissions"], key=str.lower),
                contributing_identities=sorted(
                    stats["contributors"].values(),
                    key=lambda item: (item.source, item.name),
                ),
                max_risk_score=int(stats["max_risk_score"]),
                path_count=int(stats["path_count"]),
            )
            for resource_id, stats in resource_stats.items()
        ]
        resources.sort(
            key=lambda item: (
                item.max_risk_score,
                len(item.contributing_identities),
                item.path_count,
                item.resource.name,
            ),
            reverse=True,
        )
        return resources

    def _identity_match_keys(self, entity: Entity) -> list[str]:
        raw_name = entity.name.strip().lower()
        candidates: set[str] = set()

        def add_candidate(prefix: str, value: str) -> None:
            normalized = re.sub(r"[^a-z0-9._@-]+", "", value.lower())
            if not normalized or normalized in GENERIC_IDENTITY_ALIASES or len(normalized) < 3:
                return
            candidates.add(f"{prefix}:{normalized}")

        add_candidate("name", raw_name)
        if "\\" in raw_name:
            add_candidate("account", raw_name.split("\\", 1)[1])
        if "/" in raw_name:
            add_candidate("account", raw_name.rsplit("/", 1)[-1])
        if "@" in raw_name:
            local_part, domain = raw_name.split("@", 1)
            add_candidate("email", raw_name)
            add_candidate("account", local_part)
            if "." in local_part:
                add_candidate("collapsed", local_part.replace(".", ""))
            add_candidate("domain", domain)
        else:
            add_candidate("account", raw_name)
            dotted = raw_name.replace(" ", ".")
            if dotted != raw_name:
                add_candidate("account", dotted)
                add_candidate("collapsed", dotted.replace(".", ""))
            collapsed = re.sub(r"[^a-z0-9]+", "", raw_name)
            if collapsed and collapsed != raw_name:
                add_candidate("collapsed", collapsed)

        return sorted(candidates)

    def _display_name_rank(self, entity: Entity) -> tuple[int, int]:
        lowered = entity.name.lower()
        looks_like_email = 0 if "@" in lowered else 1
        looks_like_host_alias = 1 if "\\" in lowered or "/" in lowered else 0
        return (looks_like_email, looks_like_host_alias)

    def _humanize_match_key(self, match_key: str) -> str:
        kind, _, value = match_key.partition(":")
        if kind == "email":
            return f"shared email {value}"
        if kind == "account":
            return f"shared account alias {value}"
        if kind == "collapsed":
            return f"shared normalized username {value}"
        return f"shared {value}"

    def _stable_cluster_id(self, member_ids) -> str:
        seed = "|".join(sorted(member_ids))
        digest = hashlib.blake2s(seed.encode("utf-8"), digest_size=6).hexdigest()
        return f"cluster_{digest}"

    def _principal_entities(self) -> list[Entity]:
        return [self.entities[entity_id] for entity_id in self.principal_ids]

    def _resource_entities(self) -> list[Entity]:
        return [self.entities[entity_id] for entity_id in self.resource_ids]

    def _entity(self, entity_id: str) -> Entity:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise KeyError(f"Unknown entity: {entity_id}")
        return entity

    def _summary(self, entity_id: str) -> EntitySummary:
        entity = self._entity(entity_id)
        return EntitySummary(
            id=entity.id,
            name=entity.name,
            kind=entity.kind,
            source=entity.source,
            environment=entity.environment,
        )

    def _default_selection(
        self, effective_map: dict[tuple[str, str], dict[str, object]]
    ) -> tuple[str | None, str | None]:
        if effective_map:
            principal_id, resource_id = max(
                effective_map,
                key=lambda key: (
                    int(effective_map[key]["risk_score"]),
                    int(effective_map[key]["path_count"]),
                    self.entities[key[1]].criticality,
                ),
            )
            return principal_id, resource_id

        principal_id = self.principal_ids[0] if self.principal_ids else None
        resource_id = self.resource_ids[0] if self.resource_ids else None
        return principal_id, resource_id

    def _build_hotspots(self, effective_map: dict[tuple[str, str], dict[str, object]]) -> list[Hotspot]:
        stats: dict[str, dict[str, int]] = defaultdict(lambda: {"privileged": 0, "delegated": 0})

        for (_, resource_id), entry in effective_map.items():
            permissions = entry["permissions"]
            if self._is_privileged_permission_set(permissions):
                stats[resource_id]["privileged"] += 1
            if any(
                any(rel.kind == "delegated_access" for rel in path.relationships)
                for path in entry["paths"]
            ):
                stats[resource_id]["delegated"] += 1

        hotspots = []
        for resource_id, counts in stats.items():
            resource = self.entities[resource_id]
            exposure_score = (
                resource.risk_score + counts["privileged"] * 12 + counts["delegated"] * 9
            )
            hotspots.append(
                Hotspot(
                    resource=self._summary(resource_id),
                    privileged_principal_count=counts["privileged"],
                    delegated_path_count=counts["delegated"],
                    exposure_score=exposure_score,
                    headline=(
                        f"{counts['privileged']} privileged principals, "
                        f"{counts['delegated']} delegated paths"
                    ),
                )
            )

        hotspots.sort(key=lambda item: (-item.exposure_score, item.resource.name))
        return hotspots[:5]

    def _build_scenarios(self) -> list[ScenarioChoice]:
        scenarios: list[ScenarioChoice] = []
        for relationship in self.relationships:
            if not relationship.removable:
                continue
            impacted_principals = self._estimate_impacted_principals(relationship)
            if impacted_principals == 0:
                continue

            impacted_resources = self._impact_surface_for_relationship(relationship)
            focus_resource_id = (
                max(
                    impacted_resources,
                    key=lambda resource_id: (
                        self.entities[resource_id].criticality,
                        self.entities[resource_id].risk_score,
                    ),
                )
                if impacted_resources
                else None
            )

            scenarios.append(
                ScenarioChoice(
                    edge_id=relationship.id,
                    label=relationship.label,
                    reason=relationship.rationale,
                    focus_resource_id=focus_resource_id,
                    estimated_impacted_principals=impacted_principals,
                )
            )

        scenarios.sort(
            key=lambda item: (-item.estimated_impacted_principals, item.label)
        )
        return scenarios[:6]

    def _estimate_impacted_principals(self, relationship: Relationship) -> int:
        return len(self._impacted_principal_ids_for_relationship(relationship))

    def _impact_surface_for_relationship(self, relationship: Relationship) -> list[str]:
        cached = self._impact_surface_cache.get(relationship.id)
        if cached is not None:
            return cached

        if relationship.kind in {"direct_acl", "role_grant"}:
            impacted_resources = (
                self.resource_descendants.get(relationship.target, [relationship.target])
                if relationship.inherits
                else [relationship.target]
            )
        else:
            impacted_resources = self._impact_surface_from_actor(relationship.target)

        materialized = sorted(
            set(impacted_resources),
            key=lambda resource_id: (
                self.entities[resource_id].criticality,
                self.entities[resource_id].risk_score,
                self.entities[resource_id].name,
            ),
            reverse=True,
        )
        self._impact_surface_cache[relationship.id] = materialized
        return materialized

    def _impact_surface_from_actor(self, actor_id: str) -> list[str]:
        impacted_resources: list[str] = []
        queue = deque([actor_id])
        visited = {actor_id}

        while queue:
            current_id = queue.popleft()
            for grant in self.grant_relationships_by_source.get(current_id, []):
                if grant.inherits:
                    impacted_resources.extend(
                        self.resource_descendants.get(grant.target, [grant.target])
                    )
                else:
                    impacted_resources.append(grant.target)

            for relationship in self.actor_adjacency.get(current_id, []):
                next_id = relationship.target
                if next_id in visited:
                    continue
                visited.add(next_id)
                queue.append(next_id)

        return impacted_resources

    def _effective_access_map(
        self, ignored_edge_ids: set[str] | None = None
    ) -> dict[tuple[str, str], dict[str, object]]:
        ignored_key = frozenset(ignored_edge_ids or set())
        cached = self._effective_access_cache.get(ignored_key)
        if cached is not None:
            return cached
        access_map = self._materialize_effective_access_map(self.principal_ids, None, ignored_key)
        self._effective_access_cache[ignored_key] = access_map
        return access_map

    def _effective_access_subset(
        self,
        principal_ids,
        resource_ids,
        ignored_edge_ids: set[str] | None = None,
    ) -> dict[tuple[str, str], dict[str, object]]:
        principal_scope = sorted(set(principal_ids))
        resource_scope = {resource_id for resource_id in resource_ids if resource_id}
        if not principal_scope or not resource_scope:
            return {}
        ignored_key = frozenset(ignored_edge_ids or set())
        return self._materialize_effective_access_map(principal_scope, resource_scope, ignored_key)

    def _materialize_effective_access_map(
        self,
        principal_ids,
        resource_scope: set[str] | None,
        ignored_key: frozenset[str],
    ) -> dict[tuple[str, str], dict[str, object]]:
        reachability = {
            principal_id: self._actor_reachability(principal_id, ignored_key)
            for principal_id in principal_ids
        }
        reverse_reachability: dict[str, list[tuple[str, tuple[Relationship, ...]]]] = defaultdict(list)
        for principal_id, reachable_nodes in reachability.items():
            for actor_id, actor_paths in reachable_nodes.items():
                for actor_path in actor_paths:
                    reverse_reachability[actor_id].append((principal_id, actor_path))
        path_bucket: dict[tuple[str, str], list[ResolvedPath]] = defaultdict(list)
        seen_sequences: dict[tuple[str, str], set[tuple[str, ...]]] = defaultdict(set)
        denied_permissions_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)

        for resource_id, deny_relationships in self.deny_relationships_by_resource.items():
            if resource_scope is not None and resource_id not in resource_scope:
                continue
            for deny_relationship in deny_relationships:
                if deny_relationship.id in ignored_key:
                    continue
                normalized_permissions = {
                    permission.lower() for permission in deny_relationship.permissions
                }
                if not normalized_permissions:
                    continue
                for principal_id, _ in reverse_reachability.get(deny_relationship.source, []):
                    denied_permissions_by_pair[(principal_id, resource_id)].update(
                        normalized_permissions
                    )

        for grant in self.grant_relationships:
            if grant.id in ignored_key:
                continue

            target_resource_ids = (
                self.resource_descendants.get(grant.target, [grant.target])
                if grant.inherits
                else [grant.target]
            )
            if resource_scope is not None:
                target_resource_ids = [
                    resource_id for resource_id in target_resource_ids if resource_id in resource_scope
                ]
                if not target_resource_ids:
                    continue

            for principal_id, actor_path in reverse_reachability.get(grant.source, []):
                for resource_id in target_resource_ids:
                    resource_chain = tuple(self._resource_chain(grant.target, resource_id))
                    relationships = tuple(actor_path) + (grant,) + resource_chain
                    sequence = tuple(relationship.id for relationship in relationships)
                    key = (principal_id, resource_id)
                    if sequence in seen_sequences[key]:
                        continue
                    seen_sequences[key].add(sequence)

                    denied_permissions = denied_permissions_by_pair.get(key, set())
                    remaining_permissions = tuple(
                        sorted(
                            {
                                permission
                                for permission in grant.permissions
                                if permission.lower() not in denied_permissions
                            },
                            key=str.lower,
                        )
                    )
                    if not remaining_permissions:
                        continue
                    path_bucket[key].append(
                        ResolvedPath(
                            principal_id=principal_id,
                            resource_id=resource_id,
                            permissions=remaining_permissions,
                            relationships=relationships,
                            access_mode=self._classify_access_mode(actor_path, grant),
                            narrative=self._compose_narrative(
                                principal_id,
                                resource_id,
                                actor_path,
                                grant,
                                list(resource_chain),
                            ),
                            risk_score=self._score_path(
                                principal_id,
                                resource_id,
                                remaining_permissions,
                                actor_path,
                                grant,
                            ),
                        )
                    )

        access_map: dict[tuple[str, str], dict[str, object]] = {}
        for key, paths in path_bucket.items():
            paths.sort(key=self._path_rank_key)
            trimmed_paths = paths[:6]
            access_map[key] = {
                "permissions": self._flatten_permissions(trimmed_paths),
                "path_count": len(paths),
                "risk_score": max(path.risk_score for path in trimmed_paths),
                "access_mode": self._combine_access_modes(path.access_mode for path in trimmed_paths),
                "paths": trimmed_paths,
            }
        return access_map

    def _impacted_principal_ids_for_relationship(self, relationship: Relationship) -> list[str]:
        cached = self._impacted_principal_cache.get(relationship.id)
        if cached is not None:
            return list(cached)

        impacted = [
            principal_id
            for principal_id in self.principal_ids
            if relationship.source in self._actor_reachability(principal_id, frozenset())
        ]
        impacted.sort(key=lambda principal_id: self.entities[principal_id].name)
        self._impacted_principal_cache[relationship.id] = impacted
        return list(impacted)

    def _resolve_paths(
        self, principal_id: str, resource_id: str, ignored_edge_ids: set[str] | None = None
    ) -> list[ResolvedPath]:
        entry = self._effective_access_map(ignored_edge_ids).get((principal_id, resource_id))
        if not entry:
            return []
        return list(entry["paths"])

    def _actor_reachability(
        self, principal_id: str, ignored_key: frozenset[str], max_depth: int = 6
    ) -> dict[str, list[tuple[Relationship, ...]]]:
        cache_key = (principal_id, ignored_key)
        cached = self._actor_reachability_cache.get(cache_key)
        if cached is not None:
            return cached

        results: dict[str, list[tuple[Relationship, ...]]] = defaultdict(list)
        queue = deque([(principal_id, tuple(), {principal_id})])

        while queue:
            current_id, path, visited = queue.popleft()
            results[current_id].append(path)
            if len(path) >= max_depth:
                continue

            for relationship in self.actor_adjacency.get(current_id, []):
                if relationship.id in ignored_key:
                    continue
                next_id = relationship.target
                if next_id in visited:
                    continue
                queue.append(
                    (
                        next_id,
                        path + (relationship,),
                        visited | {next_id},
                    )
                )

        materialized = {target_id: list(paths) for target_id, paths in results.items()}
        self._actor_reachability_cache[cache_key] = materialized
        return materialized

    def _actor_paths(
        self, principal_id: str, target_id: str, ignored_edge_ids: set[str], max_depth: int = 6
    ) -> list[tuple[Relationship, ...]]:
        if principal_id not in self.entities or target_id not in self.entities:
            return []
        reachable = self._actor_reachability(principal_id, frozenset(ignored_edge_ids), max_depth)
        return reachable.get(target_id, [])

    def principal_group_closure(
        self, principal_id: str, max_depth: int = 8
    ) -> list[GroupClosureRecord]:
        cached = self._principal_group_closure_cache.get(principal_id)
        if cached is not None:
            return list(cached)

        if principal_id not in self.entities or self.entities[principal_id].kind not in PRINCIPAL_KINDS:
            return []

        queue: deque[tuple[str, tuple[Relationship, ...], frozenset[str]]] = deque(
            [(principal_id, tuple(), frozenset({principal_id}))]
        )
        stats: dict[str, dict[str, object]] = {}

        while queue:
            current_id, path, visited = queue.popleft()
            if len(path) >= max_depth:
                continue

            for relationship in self.actor_adjacency.get(current_id, []):
                if relationship.kind not in {"member_of", "nested_group"}:
                    continue
                next_id = relationship.target
                if next_id in visited:
                    continue
                next_entity = self.entities.get(next_id)
                if next_entity is None or next_entity.kind != "group":
                    continue

                next_path = path + (relationship,)
                entry = stats.get(next_id)
                if entry is None:
                    stats[next_id] = {
                        "depth": len(next_path),
                        "shortest_parent_id": current_id,
                        "path_count": 1,
                    }
                else:
                    entry["path_count"] = int(entry["path_count"]) + 1
                    if len(next_path) < int(entry["depth"]):
                        entry["depth"] = len(next_path)
                        entry["shortest_parent_id"] = current_id

                queue.append((next_id, next_path, visited | {next_id}))

        records = [
            GroupClosureRecord(
                group=self._summary(group_id),
                depth=int(entry["depth"]),
                shortest_parent=self._summary(str(entry["shortest_parent_id"])),
                path_count=int(entry["path_count"]),
            )
            for group_id, entry in stats.items()
        ]
        records.sort(key=lambda item: (item.depth, -item.path_count, item.group.name.lower()))
        self._principal_group_closure_cache[principal_id] = list(records)
        return records

    def resource_hierarchy_closure(self, resource_id: str) -> list[ResourceHierarchyRecord]:
        cached = self._resource_hierarchy_closure_cache.get(resource_id)
        if cached is not None:
            return list(cached)

        if resource_id not in self.entities or self.entities[resource_id].kind != "resource":
            return []

        records: list[ResourceHierarchyRecord] = []
        for depth, ancestor_id in enumerate(self._resource_ancestors(resource_id)):
            records.append(
                ResourceHierarchyRecord(
                    ancestor=self._summary(ancestor_id),
                    depth=depth,
                    inherits_acl=depth > 0,
                )
            )
        self._resource_hierarchy_closure_cache[resource_id] = list(records)
        return records

    def _resource_ancestors(self, resource_id: str) -> list[str]:
        cached = self._resource_ancestor_cache.get(resource_id)
        if cached is not None:
            return list(cached)

        ancestors = [resource_id]
        current_id = resource_id
        while current_id in self.resource_parent:
            relationship = self.resource_parent[current_id]
            ancestors.append(relationship.source)
            current_id = relationship.source

        self._resource_ancestor_cache[resource_id] = tuple(ancestors)
        return ancestors

    def _resource_chain(self, ancestor_id: str, descendant_id: str) -> list[Relationship]:
        cache_key = (ancestor_id, descendant_id)
        cached = self._resource_chain_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        if ancestor_id == descendant_id:
            self._resource_chain_cache[cache_key] = tuple()
            return []

        reverse_chain: list[Relationship] = []
        current_id = descendant_id
        while current_id in self.resource_parent:
            relationship = self.resource_parent[current_id]
            reverse_chain.append(relationship)
            if relationship.source == ancestor_id:
                chain = tuple(reversed(reverse_chain))
                self._resource_chain_cache[cache_key] = chain
                return list(chain)
            current_id = relationship.source

        self._resource_chain_cache[cache_key] = tuple()
        return []

    def _classify_access_mode(
        self, actor_path: tuple[Relationship, ...], grant: Relationship
    ) -> str:
        if any(relationship.kind == "delegated_access" for relationship in actor_path):
            return "Delegated"
        if grant.kind == "direct_acl" and not actor_path:
            return "Direct"
        if grant.kind == "direct_acl":
            return "Inherited"
        if not actor_path:
            return "Direct role"
        return "Role-derived"

    def _compose_narrative(
        self,
        principal_id: str,
        resource_id: str,
        actor_path: tuple[Relationship, ...],
        grant: Relationship,
        resource_chain: list[Relationship],
    ) -> str:
        principal = self.entities[principal_id]
        resource = self.entities[resource_id]
        nodes = [principal.name]
        nodes.extend(self.entities[relationship.target].name for relationship in actor_path)
        nodes.append(self.entities[grant.target].name)
        if resource_chain:
            nodes.extend(self.entities[relationship.target].name for relationship in resource_chain)

        route = " -> ".join(nodes)
        details = [relationship.rationale for relationship in actor_path]
        details.append(grant.rationale)
        if resource_chain:
            details.append(
                f"The grant propagates through the resource hierarchy until it reaches {resource.name}."
            )
        return f"{route}. {' '.join(details)}"

    def _score_path(
        self,
        principal_id: str,
        resource_id: str,
        permissions: tuple[str, ...],
        actor_path: tuple[Relationship, ...],
        grant: Relationship,
    ) -> int:
        principal = self.entities[principal_id]
        resource = self.entities[resource_id]
        score = 18 + resource.risk_score // 2 + principal.risk_score // 4
        if self._is_privileged_permission_set(permissions):
            score += 18
        if any(relationship.kind == "delegated_access" for relationship in actor_path):
            score += 12
        if grant.temporary:
            score += 6
        if "external" in principal.tags:
            score += 8
        return min(99, score)

    def _path_rank_key(self, path: ResolvedPath) -> tuple[object, ...]:
        access_mode_rank = {
            "Direct": 0,
            "Inherited": 1,
            "Direct role": 2,
            "Role-derived": 3,
            "Delegated": 4,
            "Multi-path": 5,
        }.get(path.access_mode, 6)
        nested_depth = sum(
            1 for relationship in path.relationships if relationship.kind in {"member_of", "nested_group"}
        )
        delegated_depth = sum(
            1 for relationship in path.relationships if relationship.kind == "delegated_access"
        )
        role_hops = sum(
            1 for relationship in path.relationships if relationship.kind in {"assigned_role", "role_grant"}
        )
        inherited_hops = sum(1 for relationship in path.relationships if relationship.inherits)
        fanout_penalty = sum(
            len(self.actor_adjacency.get(relationship.source, []))
            for relationship in path.relationships
            if relationship.kind in TRAVERSABLE_RELATIONSHIPS
        )
        return (
            access_mode_rank,
            len(path.relationships),
            delegated_depth,
            nested_depth,
            role_hops,
            inherited_hops,
            fanout_penalty,
            -path.risk_score,
            path.narrative.lower(),
        )

    def _path_complexity_score(self, path: ResolvedPath) -> int:
        nested_depth = sum(
            1 for relationship in path.relationships if relationship.kind in {"member_of", "nested_group"}
        )
        delegated_depth = sum(
            1 for relationship in path.relationships if relationship.kind == "delegated_access"
        )
        role_hops = sum(
            1 for relationship in path.relationships if relationship.kind in {"assigned_role", "role_grant"}
        )
        inherited_hops = sum(1 for relationship in path.relationships if relationship.inherits)
        direct_grants = sum(
            1 for relationship in path.relationships if relationship.kind in {"direct_acl", "deny_acl"}
        )
        score = (
            len(path.relationships) * 10
            + nested_depth * 4
            + delegated_depth * 8
            + role_hops * 6
            + inherited_hops * 5
            + max(0, direct_grants - 1) * 2
        )
        return max(1, score)

    def _flatten_permissions(self, paths: list[ResolvedPath]) -> list[str]:
        permissions: set[str] = set()
        for path in paths:
            permissions.update(path.permissions)
        return sorted(permissions, key=str.lower)

    def _combine_access_modes(self, modes) -> str:
        unique = sorted(set(modes))
        if len(unique) == 1:
            return unique[0]
        return "Multi-path"

    def _is_privileged_permission_set(self, permissions) -> bool:
        for permission in permissions:
            lowered = permission.lower()
            if any(keyword in lowered for keyword in PRIVILEGED_KEYWORDS):
                return True
        return False

    def _to_access_path(self, path: ResolvedPath) -> AccessPath:
        return AccessPath(
            permissions=list(path.permissions),
            access_mode=path.access_mode,
            risk_score=path.risk_score,
            narrative=path.narrative,
            steps=[self._to_path_step(relationship) for relationship in path.relationships],
        )

    def _to_path_step(self, relationship: Relationship) -> PathStep:
        return PathStep(
            edge_id=relationship.id,
            edge_kind=relationship.kind,
            source=self._summary(relationship.source),
            target=self._summary(relationship.target),
            label=relationship.label,
            rationale=relationship.rationale,
            permissions=relationship.permissions,
            inherits=relationship.inherits,
            temporary=relationship.temporary,
            removable=relationship.removable,
        )

    def _build_graph(self, paths: list[ResolvedPath]) -> GraphPayload:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        for path in paths:
            for relationship in path.relationships:
                for entity_id in (relationship.source, relationship.target):
                    entity = self.entities[entity_id]
                    nodes[entity_id] = GraphNode(
                        id=entity.id,
                        label=entity.name,
                        kind=entity.kind,
                        source=entity.source,
                        tags=entity.tags[:4],
                    )
                edges[relationship.id] = GraphEdge(
                    id=relationship.id,
                    source=relationship.source,
                    target=relationship.target,
                    label=relationship.label,
                    kind=relationship.kind,
                    highlighted=True,
                )

        return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))

    def _diff_effective_access(
        self,
        before_map: dict[tuple[str, str], dict[str, object]],
        after_map: dict[tuple[str, str], dict[str, object]],
    ) -> list[WhatIfDiffItem]:
        diff: list[WhatIfDiffItem] = []

        for key, before_entry in before_map.items():
            after_entry = after_map.get(key)
            before_permissions = set(before_entry["permissions"])
            after_permissions = set(after_entry["permissions"]) if after_entry else set()
            removed_permissions = sorted(before_permissions - after_permissions, key=str.lower)
            if not removed_permissions:
                continue

            principal_id, resource_id = key
            diff.append(
                WhatIfDiffItem(
                    principal=self._summary(principal_id),
                    resource=self._summary(resource_id),
                    removed_permissions=removed_permissions,
                    access_mode_before=str(before_entry["access_mode"]),
                )
            )

        diff.sort(
            key=lambda item: (
                self.entities[item.resource.id].criticality,
                len(item.removed_permissions),
                self.entities[item.principal.id].risk_score,
            ),
            reverse=True,
        )
        return diff

    def _removed_path_count(
        self,
        before_map: dict[tuple[str, str], dict[str, object]],
        after_map: dict[tuple[str, str], dict[str, object]],
    ) -> int:
        removed = 0
        for key, before_entry in before_map.items():
            after_entry = after_map.get(key)
            before_count = int(before_entry["path_count"])
            after_count = int(after_entry["path_count"]) if after_entry else 0
            removed += max(before_count - after_count, 0)
        return removed

    def _severity_for_resource_impact(self, resource_id: str, removed_permissions: int) -> str:
        resource = self.entities[resource_id]
        if resource.criticality >= 5 and removed_permissions >= 3:
            return "critical"
        if resource.criticality >= 4:
            return "warn"
        return "good"

    def _resource_access_for_map(
        self,
        resource_id: str,
        effective_map: dict[tuple[str, str], dict[str, object]],
    ) -> list[ResourceAccessRecord]:
        records: list[ResourceAccessRecord] = []
        for principal in self._principal_entities():
            entry = effective_map.get((principal.id, resource_id))
            if not entry:
                continue
            records.append(
                ResourceAccessRecord(
                    principal=self._summary(principal.id),
                    permissions=list(entry["permissions"]),
                    path_count=int(entry["path_count"]),
                    access_mode=str(entry["access_mode"]),
                    risk_score=int(entry["risk_score"]),
                    why=str(entry["paths"][0].narrative),
                )
            )
        records.sort(key=lambda item: (-item.risk_score, item.principal.name))
        return records

    def _simulate_narrative(
        self, edge: Relationship, diff: list[WhatIfDiffItem], blast_radius: list[ResourceImpact]
    ) -> str:
        if not diff:
            return f"Removing {edge.label} does not change any currently effective user access."

        top_impact = blast_radius[0]
        return (
            f"Removing {edge.label} affects {len({item.principal.id for item in diff})} principals. "
            f"The highest-impact target is {top_impact.resource.name}, where "
            f"{top_impact.removed_principal_count} principals lose "
            f"{top_impact.removed_permission_count} permissions."
        )

    def _build_flow(self, edge: Relationship, diff: list[WhatIfDiffItem]) -> FlowPayload:
        nodes = [
            FlowNode(id="change", label=f"Remove: {edge.label}", kind="change", x=80, y=180),
        ]
        flow_edges: list[FlowEdge] = []
        existing_node_ids = {"change"}
        principal_ids: dict[str, str] = {}
        resource_ids: dict[str, str] = {}

        for index, item in enumerate(diff[:6]):
            principal_node_id = principal_ids.setdefault(
                item.principal.id, f"principal-{len(principal_ids) + 1}"
            )
            if principal_node_id not in existing_node_ids:
                nodes.append(
                    FlowNode(
                        id=principal_node_id,
                        label=item.principal.name,
                        kind="principal",
                        x=360,
                        y=60 + len(principal_ids) * 90,
                    )
                )
                flow_edges.append(
                    FlowEdge(
                        id=f"edge-change-{principal_node_id}",
                        source="change",
                        target=principal_node_id,
                        label="path removed",
                    )
                )
                existing_node_ids.add(principal_node_id)

            resource_node_id = resource_ids.setdefault(
                item.resource.id, f"resource-{len(resource_ids) + 1}"
            )
            if resource_node_id not in existing_node_ids:
                nodes.append(
                    FlowNode(
                        id=resource_node_id,
                        label=item.resource.name,
                        kind="resource",
                        x=700,
                        y=60 + len(resource_ids) * 90,
                    )
                )
                existing_node_ids.add(resource_node_id)

            flow_edges.append(
                FlowEdge(
                    id=f"edge-{index}",
                    source=principal_node_id,
                    target=resource_node_id,
                    label=", ".join(item.removed_permissions),
                )
            )

        return FlowPayload(nodes=nodes, edges=flow_edges)
