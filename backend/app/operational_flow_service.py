from __future__ import annotations

from app.auth import utc_now_iso
from app.models import OperationalFlowResponse, OperationalFlowStep
from app.storage import AppStorage


class OperationalFlowService:
    def __init__(self, storage: AppStorage, runtime_getter) -> None:
        self._storage = storage
        self._runtime_getter = runtime_getter

    def status(self) -> OperationalFlowResponse:
        runtime = self._runtime_getter()
        setup = runtime.setup_status()
        targets = self._storage.list_targets()
        active_targets = [target for target in targets if target.enabled]
        snapshot = self._storage.load_latest_snapshot()
        raw_stats = self._storage.raw_snapshot_stats()
        snapshot_generated_at = snapshot.generated_at if snapshot else runtime.engine.snapshot.generated_at
        access_index = self._storage.materialized_access_index_stats(snapshot_generated_at)
        auth_providers = self._storage.list_auth_providers()
        admin_users = self._storage.list_admin_users()
        local_admins = [admin for admin in admin_users if str(admin.get("auth_source") or "local") == "local"]
        local_mfa_ready = all(bool(admin.get("mfa_enabled")) for admin in local_admins) if local_admins else False
        imported_sources = [source for source in self._storage.list_imported_sources() if source.enabled]
        reviews = self._storage.list_access_review_campaigns()
        connector_inventory = runtime.connector_inventory()
        live_or_partial = [
            connector
            for connector in connector_inventory.connectors
            if connector.implementation_status in {"live", "partial"}
        ]
        configured_collectors = [connector for connector in live_or_partial if connector.configured]

        steps = [
            OperationalFlowStep(
                id="bootstrap-admin",
                title="Bootstrap administrator",
                status="ready" if not setup.setup_required else "action_required",
                detail=(
                    "Local administrator exists and the platform can be operated."
                    if not setup.setup_required
                    else "Initial administrator creation is still required."
                ),
                recommended_action=(
                    "Proceed with the current administrator account."
                    if not setup.setup_required
                    else "Create the first local administrator from the setup screen."
                ),
            ),
            OperationalFlowStep(
                id="sign-in-plane",
                title="Authentication plane",
                status="ready" if auth_providers else "in_progress",
                detail=(
                    f"{len(auth_providers)} federated sign-in provider(s) configured."
                    if auth_providers
                    else "Only the local application administrator is active."
                ),
                recommended_action=(
                    "Keep local admin as break-glass and review provider scopes periodically."
                    if auth_providers
                    else "Optionally configure LDAP or OAuth2/OIDC for delegated operator access."
                ),
            ),
            OperationalFlowStep(
                id="local-mfa",
                title="Local administrator MFA",
                status="ready" if local_mfa_ready else "action_required",
                detail=(
                    f"{len(local_admins)} local administrator account(s) protected with built-in TOTP MFA."
                    if local_mfa_ready
                    else "At least one local administrator exists without built-in TOTP MFA enabled."
                ),
                recommended_action=(
                    "Keep a monitored break-glass account and review MFA recovery procedures."
                    if local_mfa_ready
                    else "Enable built-in TOTP MFA for local administrators, or rely on Keycloak/OIDC MFA for federated operators."
                ),
            ),
            OperationalFlowStep(
                id="target-coverage",
                title="Target coverage",
                status="ready" if active_targets or imported_sources else "action_required",
                detail=(
                    f"{len(active_targets)} live target(s) and {len(imported_sources)} imported source(s) active."
                    if active_targets or imported_sources
                    else "No active monitored target or imported source is currently available."
                ),
                recommended_action=(
                    "Review target depth and connector coverage."
                    if active_targets or imported_sources
                    else "Add at least one monitored filesystem target or import an offline source bundle."
                ),
            ),
            OperationalFlowStep(
                id="raw-ingestion",
                title="Raw ingestion and normalization",
                status="ready" if raw_stats["row_count"] and snapshot else "in_progress",
                detail=(
                    f"{raw_stats['row_count']} raw batch(es) captured; latest normalized snapshot: {snapshot_generated_at}."
                    if raw_stats["row_count"] and snapshot
                    else "The normalization pipeline is configured but still waiting for a completed collection cycle."
                ),
                recommended_action=(
                    "Monitor snapshot freshness and raw retention."
                    if raw_stats["row_count"] and snapshot
                    else "Run a scan to populate raw ingestion and normalized entities."
                ),
            ),
            OperationalFlowStep(
                id="materialized-index",
                title="Materialized access index",
                status="ready" if access_index["row_count"] else "in_progress",
                detail=(
                    f"{access_index['row_count']} entitlement row(s) indexed across {access_index['resource_count']} resources."
                    if access_index["row_count"]
                    else "Effective access compilation is enabled but the index is still empty."
                ),
                recommended_action=(
                    "Use indexed access APIs for fast explain and exposure queries."
                    if access_index["row_count"]
                    else "Complete a scan so the entitlement compiler can populate the access index."
                ),
            ),
            OperationalFlowStep(
                id="connector-readiness",
                title="Connector readiness",
                status="ready" if configured_collectors else "in_progress",
                detail=(
                    f"{len(configured_collectors)} configured live/partial connector(s) available out of {len(live_or_partial)} runtime-capable surfaces."
                    if live_or_partial
                    else "No runtime-capable connector surface is currently registered."
                ),
                recommended_action=(
                    "Keep connector credentials rotated and monitor failures."
                    if configured_collectors
                    else "Configure official connector environments for the identity or cloud surfaces you need."
                ),
            ),
            OperationalFlowStep(
                id="governance-loop",
                title="Governance and evidence",
                status="ready" if reviews else "in_progress",
                detail=(
                    f"{len(reviews)} access review campaign(s) recorded and exportable."
                    if reviews
                    else "The platform can generate reviews, but no campaign has been recorded yet."
                ),
                recommended_action=(
                    "Use review campaigns and remediation plans as the operational decision loop."
                    if reviews
                    else "Create a first review campaign so the evidence and remediation workflow is exercised."
                ),
            ),
        ]

        ready_count = sum(1 for step in steps if step.status == "ready")
        action_required = any(step.status == "action_required" for step in steps)
        overall_status = (
            "action_required"
            if action_required
            else "ready"
            if ready_count == len(steps)
            else "in_progress"
        )
        next_actions = [step.recommended_action for step in steps if step.status != "ready"][:4]
        completion_percent = int(round((ready_count / len(steps)) * 100)) if steps else 100
        return OperationalFlowResponse(
            generated_at=utc_now_iso(),
            overall_status=overall_status,
            completion_percent=completion_percent,
            steps=steps,
            next_actions=next_actions,
        )
