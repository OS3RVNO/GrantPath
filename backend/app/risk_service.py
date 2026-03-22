from __future__ import annotations

from collections.abc import Callable

from app.models import RiskFinding, RiskFindingsResponse
from app.storage import AppStorage

_SEVERITY_WEIGHT = {"critical": 3, "warn": 2, "neutral": 1, "good": 0}


class RiskService:
    def __init__(self, engine_getter: Callable[[], object], storage: AppStorage, platform_services) -> None:
        self._engine_getter = engine_getter
        self._storage = storage
        self._platform_services = platform_services

    def list_findings(self, limit: int = 25) -> RiskFindingsResponse:
        engine = self._engine_getter()
        cache_key = f"risks:{engine.snapshot.generated_at}:{max(1, int(limit))}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return RiskFindingsResponse.model_validate(cached)
        overview = engine.get_overview()
        access_rows = self._storage.list_materialized_access_index(engine.snapshot.generated_at)
        if not access_rows:
            access_rows = engine.materialized_access_index()

        findings: list[RiskFinding] = []
        seen_ids: set[str] = set()

        for hotspot in overview.hotspots:
            severity = "critical" if hotspot.exposure_score >= 85 else "warn"
            finding = RiskFinding(
                id=f"risk_hotspot_{hotspot.resource.id}",
                category="overexposed-resource",
                severity=severity,
                headline=f"{hotspot.resource.name} is broadly exposed",
                detail=hotspot.headline,
                recommended_action="Review direct and inherited grants, then narrow the broadest group path.",
                affected_principal_count=hotspot.privileged_principal_count,
                affected_resource_count=1,
                resource=hotspot.resource,
                source="risk-engine",
            )
            findings.append(finding)
            seen_ids.add(finding.id)
            if len(findings) >= limit:
                break

        for row in access_rows:
            if len(findings) >= limit:
                break
            permissions = [str(permission) for permission in row["permissions"]]
            path_count = int(row["path_count"])
            path_complexity = int(row.get("path_complexity", 0))
            risk_score = int(row["risk_score"])
            if not engine._is_privileged_permission_set(permissions) and risk_score < 70:
                continue
            category = "indirect-privileged-access" if path_count > 1 else "direct-privileged-access"
            finding_id = f"risk_access_{row['principal_id']}_{row['resource_id']}_{category}"
            if finding_id in seen_ids:
                continue
            principal = engine._summary(str(row["principal_id"]))
            resource = engine._summary(str(row["resource_id"]))
            findings.append(
                RiskFinding(
                    id=finding_id,
                    category=category,
                    severity="critical" if risk_score >= 85 else "warn",
                    headline=f"{principal.name} reaches {resource.name} with privileged rights",
                    detail=str(row["why"]),
                    recommended_action=(
                        "Inspect nested group paths and direct ACL overlays before approving the entitlement."
                    ),
                    affected_principal_count=1,
                    affected_resource_count=1,
                    resource=resource,
                    principal=principal,
                    source="materialized-access-index",
                )
            )
            seen_ids.add(finding_id)

            if len(findings) >= limit:
                break
            if path_complexity < 34:
                continue
            opaque_finding_id = f"risk_complexity_{row['principal_id']}_{row['resource_id']}"
            if opaque_finding_id in seen_ids:
                continue
            findings.append(
                RiskFinding(
                    id=opaque_finding_id,
                    category="opaque-access-path",
                    severity="critical" if path_complexity >= 50 else "warn",
                    headline=f"{principal.name} reaches {resource.name} through a hard-to-explain path",
                    detail=(
                        f"The best materialized path currently scores {path_complexity} on complexity, "
                        f"with {path_count} path(s) contributing to the effective entitlement."
                    ),
                    recommended_action=(
                        "Reduce nested groups, delegated hops or inherited grant overlays until the explain path becomes simpler to defend."
                    ),
                    affected_principal_count=1,
                    affected_resource_count=1,
                    resource=resource,
                    principal=principal,
                    source="materialized-access-index",
                )
            )
            seen_ids.add(opaque_finding_id)

        direct_members_by_group: dict[str, set[str]] = {}
        for relationship in engine.snapshot.relationships:
            if relationship.kind not in {"member_of", "nested_group"}:
                continue
            group_id = relationship.target
            source_entity = engine.entities.get(relationship.source)
            target_entity = engine.entities.get(group_id)
            if source_entity is None or target_entity is None or target_entity.kind != "group":
                continue
            direct_members_by_group.setdefault(group_id, set()).add(source_entity.id)

        for group_id, member_ids in direct_members_by_group.items():
            if len(findings) >= limit:
                break
            group_entity = engine.entities.get(group_id)
            if group_entity is None:
                continue
            privileged_grants = [
                relationship
                for relationship in engine.grant_relationships_by_source.get(group_id, [])
                if engine.is_privileged_permissions(relationship.permissions)
            ]
            if len(member_ids) < 5 or not privileged_grants:
                continue
            impacted_resources = {relationship.target for relationship in privileged_grants}
            finding_id = f"risk_group_{group_id}_broad-privileged-group"
            if finding_id in seen_ids:
                continue
            findings.append(
                RiskFinding(
                    id=finding_id,
                    category="broad-privileged-group",
                    severity="critical" if len(member_ids) >= 10 else "warn",
                    headline=f"{group_entity.name} grants privileged access to a broad membership",
                    detail=(
                        f"{group_entity.name} currently has {len(member_ids)} direct member(s) and "
                        f"{len(privileged_grants)} privileged grant edge(s)."
                    ),
                    recommended_action=(
                        "Split the group scope or move privileged permissions to a narrower administrative group."
                    ),
                    affected_principal_count=len(member_ids),
                    affected_resource_count=len(impacted_resources),
                    principal=engine._summary(group_id),
                    source="risk-engine",
                )
            )
            seen_ids.add(finding_id)

        effective_map = engine._effective_access_map()
        for (principal_id, resource_id), entry in effective_map.items():
            if len(findings) >= limit:
                break
            principal = engine._summary(principal_id)
            resource = engine._summary(resource_id)
            for path in entry["paths"]:
                membership_depth = sum(
                    1 for relationship in path.relationships if relationship.kind in {"member_of", "nested_group"}
                )
                if membership_depth < 3:
                    continue
                finding_id = f"risk_nesting_{principal_id}_{resource_id}_{membership_depth}"
                if finding_id in seen_ids:
                    continue
                findings.append(
                    RiskFinding(
                        id=finding_id,
                        category="excessive-nesting",
                        severity="warn" if membership_depth == 3 else "critical",
                        headline=f"{principal.name} reaches {resource.name} through deep nesting",
                        detail=(
                            f"The access path to {resource.name} depends on {membership_depth} nested group "
                            "transitions before the effective grant is applied."
                        ),
                        recommended_action=(
                            "Review nested groups in the path and flatten the deepest chain where possible."
                        ),
                        affected_principal_count=1,
                        affected_resource_count=1,
                        principal=principal,
                        resource=resource,
                        source="risk-engine",
                    )
                )
                seen_ids.add(finding_id)
                break

        findings.sort(
            key=lambda item: (
                _SEVERITY_WEIGHT[item.severity],
                item.affected_principal_count,
                item.affected_resource_count,
                item.headline.lower(),
            ),
            reverse=True,
        )
        response = RiskFindingsResponse(
            generated_at=engine.snapshot.generated_at,
            total_findings=len(findings[:limit]),
            findings=findings[:limit],
        )
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=300,
        )
        return response
