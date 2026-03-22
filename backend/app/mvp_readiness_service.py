from __future__ import annotations

from datetime import datetime

from app.auth import utc_now, utc_now_iso
from app.models import (
    MvpReadinessAction,
    MvpReadinessFreshness,
    MvpReadinessItem,
    MvpReadinessResponse,
)
from app.storage import AppStorage


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class MvpReadinessService:
    def __init__(self, storage: AppStorage, runtime_getter) -> None:
        self._storage = storage
        self._runtime_getter = runtime_getter

    def status(self) -> MvpReadinessResponse:
        runtime = self._runtime_getter()
        setup = runtime.setup_status()
        snapshot = self._storage.load_latest_snapshot()
        scans = self._storage.list_scan_runs(limit=10)
        latest_successful_scan = next((scan for scan in scans if scan.status == "healthy"), None)
        latest_scan_at = latest_successful_scan.finished_at if latest_successful_scan else None
        active_targets = [target for target in self._storage.list_targets() if target.enabled]
        imported_sources = [source for source in self._storage.list_imported_sources() if source.enabled]
        auth_providers = self._storage.list_auth_providers()
        reviews = self._storage.list_access_review_campaigns()
        admin_users = self._storage.list_admin_users()
        local_admins = [
            admin for admin in admin_users if str(admin.get("auth_source") or "local") == "local"
        ]
        local_mfa_ready = all(bool(admin.get("mfa_enabled")) for admin in local_admins) if local_admins else False
        snapshot_generated_at = snapshot.generated_at if snapshot else None
        access_index_stats = self._storage.materialized_access_index_stats(
            snapshot_generated_at or runtime.engine.snapshot.generated_at
        )
        freshness = self._freshness(snapshot_generated_at, latest_scan_at)

        checklist = [
            MvpReadinessItem(
                id="bootstrap-admin",
                title="Local administrator and tenant bootstrap",
                status="ready" if not setup.setup_required else "action_required",
                summary=(
                    "A local break-glass administrator is configured."
                    if not setup.setup_required
                    else "The application still needs its first local administrator."
                ),
                why_it_matters=(
                    "The MVP needs a stable break-glass account so setup, scans and reports stay operable even before federation is configured."
                ),
                recommended_action=(
                    "Keep the local admin available and rotate the password regularly."
                    if not setup.setup_required
                    else "Complete the initial setup and create the first local administrator."
                ),
                workspace="sources",
                section="auth",
            ),
            MvpReadinessItem(
                id="identity-plane",
                title="Operator sign-in plane",
                status="ready" if auth_providers else "in_progress",
                required=False,
                summary=(
                    f"{len(auth_providers)} federated sign-in provider(s) configured."
                    if auth_providers
                    else "Only local application sign-in is configured."
                ),
                why_it_matters=(
                    "Federated sign-in is not mandatory for the MVP, but it makes pilot adoption easier for operators and auditors."
                ),
                recommended_action=(
                    "Validate the configured provider scopes and MFA policy."
                    if auth_providers
                    else "Optionally add LDAP or OIDC after the first pilot scan is working."
                ),
                workspace="sources",
                section="auth",
            ),
            MvpReadinessItem(
                id="local-mfa",
                title="Local admin MFA",
                status="ready" if local_mfa_ready else "action_required",
                summary=(
                    f"{len(local_admins)} local administrator account(s) protected with built-in TOTP."
                    if local_mfa_ready
                    else "At least one local administrator is still missing built-in TOTP MFA."
                ),
                why_it_matters=(
                    "Even in an MVP, the break-glass path must be defendable. Local MFA reduces the chance of a weak operational path undermining the pilot."
                ),
                recommended_action=(
                    "Keep recovery steps documented and monitored."
                    if local_mfa_ready
                    else "Enable built-in TOTP MFA for the local administrator."
                ),
                workspace="sources",
                section="auth",
            ),
            MvpReadinessItem(
                id="target-coverage",
                title="Live collection scope",
                status="ready" if active_targets or imported_sources else "action_required",
                summary=(
                    f"{len(active_targets)} active target(s) and {len(imported_sources)} imported source(s) are available."
                    if active_targets or imported_sources
                    else "No live target or imported source is currently active."
                ),
                why_it_matters=(
                    "The MVP only becomes useful when it watches a real filesystem scope or a real offline entitlement dataset."
                ),
                recommended_action=(
                    "Review target depth and leave at least one real production-like source enabled."
                    if active_targets or imported_sources
                    else "Add at least one monitored target or import one offline bundle."
                ),
                workspace="sources",
                section="collection",
            ),
            MvpReadinessItem(
                id="first-successful-scan",
                title="Successful scan and normalized snapshot",
                status="ready" if snapshot and latest_successful_scan else "action_required",
                summary=(
                    f"Latest successful scan finished at {latest_scan_at}."
                    if snapshot and latest_successful_scan
                    else "No successful scan has produced a normalized snapshot yet."
                ),
                why_it_matters=(
                    "Search, explain, exposure and what-if depend on a completed collection and normalization cycle."
                ),
                recommended_action=(
                    "Keep scan cadence aligned with the sensitivity of the target."
                    if snapshot and latest_successful_scan
                    else "Run a full scan and confirm it completes without blocking errors."
                ),
                workspace="operations",
                section="status",
            ),
            MvpReadinessItem(
                id="effective-access-index",
                title="Effective access index",
                status="ready" if access_index_stats["row_count"] else "action_required",
                summary=(
                    f"{access_index_stats['row_count']} indexed entitlement row(s) are ready for fast queries."
                    if access_index_stats["row_count"]
                    else "The materialized access index is still empty."
                ),
                why_it_matters=(
                    "The MVP promise is speed and explainability. Without the materialized index, the control plane cannot feel instant."
                ),
                recommended_action=(
                    "Use indexed explain and exposure queries for the pilot."
                    if access_index_stats["row_count"]
                    else "Complete a scan so the compiler can populate effective access."
                ),
                workspace="operations",
                section="status",
            ),
            MvpReadinessItem(
                id="evidence-loop",
                title="Governance and export evidence",
                status="ready" if reviews else "in_progress",
                required=False,
                summary=(
                    f"{len(reviews)} access review campaign(s) already recorded."
                    if reviews
                    else "No review campaign has been executed yet."
                ),
                why_it_matters=(
                    "The MVP becomes more convincing when an admin can both explain access and export a professional evidence package."
                ),
                recommended_action=(
                    "Use the first campaign as pilot evidence."
                    if reviews
                    else "Create one access review campaign to exercise the full evidence loop."
                ),
                workspace="govern",
                section="reviews",
            ),
        ]

        ready_count = sum(1 for item in checklist if item.status == "ready")
        blockers = [item.title for item in checklist if item.required and item.status == "action_required"]
        overall_status = (
            "action_required"
            if blockers
            else "ready"
            if ready_count == len(checklist)
            else "in_progress"
        )
        completion_percent = int(round((ready_count / len(checklist)) * 100)) if checklist else 100
        next_actions = [item.recommended_action for item in checklist if item.status != "ready"][:4]
        actions = [
            MvpReadinessAction(
                id=item.id,
                label=item.title,
                detail=item.recommended_action,
                workspace=item.workspace,
                section=item.section,
            )
            for item in checklist
            if item.status != "ready"
        ][:4]

        return MvpReadinessResponse(
            generated_at=utc_now_iso(),
            overall_status=overall_status,
            completion_percent=completion_percent,
            primary_scope="Filesystem live monitoring with explain, exposure, what-if and export evidence.",
            checklist=checklist,
            blockers=blockers,
            next_actions=next_actions,
            actions=actions,
            freshness=freshness,
        )

    def _freshness(
        self,
        snapshot_generated_at: str | None,
        latest_successful_scan_at: str | None,
    ) -> MvpReadinessFreshness:
        snapshot_dt = _parse_iso(snapshot_generated_at)
        scan_dt = _parse_iso(latest_successful_scan_at)
        reference = max([point for point in [snapshot_dt, scan_dt] if point is not None], default=None)
        if reference is None:
            return MvpReadinessFreshness(
                status="missing",
                summary="No successful scan has produced a snapshot yet.",
                snapshot_generated_at=snapshot_generated_at,
                latest_successful_scan_at=latest_successful_scan_at,
                age_minutes=None,
            )

        age_minutes = max(0, int((utc_now() - reference).total_seconds() // 60))
        if age_minutes <= 30:
            status = "fresh"
            summary = "The latest snapshot is fresh enough for interactive investigation."
        elif age_minutes <= 240:
            status = "aging"
            summary = "The latest snapshot is still usable, but it should be refreshed before a serious review."
        else:
            status = "stale"
            summary = "The latest snapshot is stale; run a scan before trusting the current exposure view."

        return MvpReadinessFreshness(
            status=status,
            summary=summary,
            snapshot_generated_at=snapshot_generated_at,
            latest_successful_scan_at=latest_successful_scan_at,
            age_minutes=age_minutes,
        )
