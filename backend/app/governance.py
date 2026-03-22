from __future__ import annotations

from app.engine import AccessGraphEngine
from app.models import (
    AccessReviewCampaignCreateRequest,
    AccessReviewCampaignDetailResponse,
    AccessReviewItem,
    AccessReviewRemediationPlan,
    AccessReviewRemediationStep,
    EntitySummary,
)


def build_review_candidates(
    engine: AccessGraphEngine,
    access_rows: list[dict[str, object]],
    payload: AccessReviewCampaignCreateRequest,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for row in access_rows:
        permissions = list(row["permissions"])
        risk_score = int(row["risk_score"])
        if risk_score < payload.min_risk_score:
            continue
        if payload.privileged_only and not engine._is_privileged_permission_set(permissions):
            continue

        suggested_edge_id = None
        suggested_edge_label = None
        suggested_remediation = None
        try:
            explanation = engine.explain(str(row["principal_id"]), str(row["resource_id"]))
            for path in explanation.paths:
                for step in path.steps:
                    relationship = engine.relationships_by_id.get(step.edge_id)
                    if relationship and relationship.removable:
                        suggested_edge_id = relationship.id
                        suggested_edge_label = relationship.label
                        suggested_remediation = (
                            f"Review edge '{relationship.label}' to remove or reduce "
                            f"{', '.join(permissions[:3])} on {explanation.resource.name}."
                        )
                        break
                if suggested_edge_id:
                    break
        except KeyError:
            suggested_remediation = "No explainable path is currently available for this entitlement."

        candidates.append(
            {
                "id": f"item_{len(candidates) + 1:04d}",
                "principal_id": str(row["principal_id"]),
                "resource_id": str(row["resource_id"]),
                "permissions": permissions,
                "path_count": int(row["path_count"]),
                "access_mode": str(row["access_mode"]),
                "risk_score": risk_score,
                "why": str(row["why"]),
                "suggested_edge_id": suggested_edge_id,
                "suggested_edge_label": suggested_edge_label,
                "suggested_remediation": suggested_remediation,
            }
        )
        if len(candidates) >= payload.max_items:
            break
    return candidates


def enrich_campaign_detail(
    engine: AccessGraphEngine,
    detail: AccessReviewCampaignDetailResponse,
) -> AccessReviewCampaignDetailResponse:
    def _resolve_summary(
        entity_id: str,
        existing: EntitySummary,
        *,
        fallback_kind: str,
    ) -> EntitySummary:
        try:
            return engine._summary(entity_id)
        except KeyError:
            name = existing.name if existing.name and existing.name != existing.id else entity_id
            return existing.model_copy(
                update={
                    "id": entity_id,
                    "name": name,
                    "kind": existing.kind or fallback_kind,
                    "source": "historical review snapshot",
                    "environment": existing.environment or "historical",
                }
            )

    enriched_items = [
        item.model_copy(
            update={
                "principal": _resolve_summary(item.principal_id, item.principal, fallback_kind="user"),
                "resource": _resolve_summary(item.resource_id, item.resource, fallback_kind="resource"),
            }
        )
        for item in detail.items
    ]
    return detail.model_copy(update={"items": enriched_items})


def remediation_plan_for_item(
    engine: AccessGraphEngine,
    campaign_id: str,
    item: AccessReviewItem,
) -> AccessReviewRemediationPlan:
    if item.suggested_edge_id:
        simulation = engine.simulate_edge_removal(item.suggested_edge_id, item.resource_id)
        summary = (
            f"Removing '{simulation.edge.label}' would affect {simulation.impacted_principals} principal(s) "
            f"across {simulation.impacted_resources} resource(s)."
        )
        steps = [
            AccessReviewRemediationStep(
                order=1,
                title="Validate the access owner",
                detail=(
                    f"Confirm with the resource or group owner why {item.principal.name} still needs "
                    f"{', '.join(item.permissions)} on {item.resource.name}."
                ),
                impact="No technical change yet; this step reduces accidental revocation.",
            ),
            AccessReviewRemediationStep(
                order=2,
                title="Stage the entitlement change",
                detail=(
                    f"Prepare a controlled change for edge '{simulation.edge.label}'"
                    f"{' (' + item.suggested_edge_id + ')' if item.suggested_edge_id else ''}."
                ),
                impact=(
                    f"Expected blast radius: {simulation.impacted_principals} principal(s), "
                    f"{simulation.impacted_resources} resource(s)."
                ),
            ),
            AccessReviewRemediationStep(
                order=3,
                title="Re-run targeted validation",
                detail=(
                    f"Run a focused scan and explain query after the change to verify that "
                    f"{item.principal.name} lost the reviewed access and no unwanted coverage remains."
                ),
                impact="Confirms the remediation using the same deterministic engine used for review.",
            ),
        ]
        return AccessReviewRemediationPlan(
            item_id=item.id,
            campaign_id=campaign_id,
            summary=summary,
            suggested_edge_id=item.suggested_edge_id,
            suggested_edge_label=item.suggested_edge_label,
            impacted_principals=simulation.impacted_principals,
            impacted_resources=simulation.impacted_resources,
            privileged_paths_removed=simulation.privileged_paths_removed,
            steps=steps,
        )

    return AccessReviewRemediationPlan(
        item_id=item.id,
        campaign_id=campaign_id,
        summary=(
            "No removable edge was identified automatically. Manual review is required to determine "
            "whether the access comes from a provider path that is not yet fully actionable."
        ),
        steps=[
            AccessReviewRemediationStep(
                order=1,
                title="Inspect the explain path",
                detail=(
                    f"Review why {item.principal.name} reaches {item.resource.name} and identify the upstream "
                    "group, role or delegated relationship that should be changed."
                ),
                impact="Clarifies whether the entitlement is direct, inherited or synchronized from another platform.",
            ),
            AccessReviewRemediationStep(
                order=2,
                title="Coordinate with the owning platform",
                detail=(
                    "If the entitlement comes from a partially implemented cloud surface, execute the change "
                    "through the source platform and then re-import or re-sync the dataset."
                ),
                impact="Prevents unsupported direct changes against an incomplete collector surface.",
            ),
        ],
    )
