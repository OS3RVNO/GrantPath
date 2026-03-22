from __future__ import annotations

from pathlib import Path

from app.auth import utc_now_iso
from app.models import (
    FeatureInventoryCategory,
    FeatureInventoryItem,
    FeatureInventoryResponse,
)
from app.storage import AppStorage


class FeatureInventoryService:
    def __init__(self, storage: AppStorage, runtime_getter) -> None:
        self._storage = storage
        self._runtime_getter = runtime_getter

    def status(self) -> FeatureInventoryResponse:
        runtime = self._runtime_getter()
        setup = runtime.setup_status()
        snapshot = self._storage.load_latest_snapshot()
        scans = self._storage.list_scan_runs(limit=10)
        latest_successful_scan = next((scan for scan in scans if scan.status == "healthy"), None)
        targets = self._storage.list_targets()
        active_targets = [target for target in targets if target.enabled]
        ssh_targets = [target for target in active_targets if target.connection_mode == "ssh"]
        imported_sources = [source for source in self._storage.list_imported_sources() if source.enabled]
        auth_providers = self._storage.list_auth_providers()
        reviews = self._storage.list_access_review_campaigns()
        schedules = self._storage.list_report_schedules()
        admin_users = self._storage.list_admin_users()
        local_admins = [
            admin for admin in admin_users if str(admin.get("auth_source") or "local") == "local"
        ]
        local_mfa_ready = all(bool(admin.get("mfa_enabled")) for admin in local_admins) if local_admins else False
        snapshot_generated_at = snapshot.generated_at if snapshot else runtime.engine.snapshot.generated_at
        raw_stats = self._storage.raw_snapshot_stats()
        access_index_stats = self._storage.materialized_access_index_stats(snapshot_generated_at)
        has_index = access_index_stats["row_count"] > 0
        scenarios = runtime.engine.get_overview().scenarios
        data_ready = bool(snapshot and latest_successful_scan)
        root = runtime.project_root

        categories = [
            self._build_category(
                "identity-access",
                "Identity and access plane",
                "How operators enter the platform and whether the break-glass path is defensible.",
                [
                    FeatureInventoryItem(
                        id="local-admin-bootstrap",
                        title="Local break-glass administrator",
                        status="present" if not setup.setup_required else "missing",
                        summary=(
                            "A local administrator account already exists for this deployment."
                            if not setup.setup_required
                            else "The first local administrator has not been created yet."
                        ),
                        gap=(
                            "No local break-glass administrator is available yet."
                            if setup.setup_required
                            else "No blocker remains for the local administrator bootstrap path."
                        ),
                        recommended_action=(
                            "Complete the initial setup and create the first administrator."
                            if setup.setup_required
                            else "Keep the break-glass account documented and monitored."
                        ),
                        workspace="sources",
                        section="auth",
                    ),
                    FeatureInventoryItem(
                        id="local-admin-mfa",
                        title="Local administrator MFA",
                        status=(
                            "present"
                            if local_mfa_ready
                            else "partial"
                            if local_admins
                            else "missing"
                        ),
                        summary=(
                            f"{len(local_admins)} local administrator account(s) are protected with built-in TOTP."
                            if local_mfa_ready
                            else "Built-in TOTP MFA is available for local admins but not fully enabled."
                            if local_admins
                            else "No local administrator exists yet, so MFA cannot be exercised."
                        ),
                        gap=(
                            "At least one local admin still lacks built-in MFA."
                            if local_admins and not local_mfa_ready
                            else "The platform still needs a local administrator before MFA can be enabled."
                            if not local_admins
                            else "No critical MFA gap remains on the local admin path."
                        ),
                        recommended_action=(
                            "Enable built-in TOTP for the local administrator."
                            if local_admins and not local_mfa_ready
                            else "Create a local admin first, then enable TOTP."
                            if not local_admins
                            else "Review recovery codes and MFA runbooks periodically."
                        ),
                        workspace="sources",
                        section="auth",
                    ),
                    FeatureInventoryItem(
                        id="federated-sign-in",
                        title="Federated operator sign-in",
                        status="present" if auth_providers else "partial",
                        required_for_mvp=False,
                        summary=(
                            f"{len(auth_providers)} LDAP/OIDC provider(s) are configured."
                            if auth_providers
                            else "LDAP and OIDC are implemented, but this deployment is still local-sign-in only."
                        ),
                        gap=(
                            "Federated sign-in is available in product but not yet configured here."
                            if not auth_providers
                            else "No immediate gap remains for delegated operator access."
                        ),
                        recommended_action=(
                            "Validate scopes, group filters and MFA enforcement in the configured provider."
                            if auth_providers
                            else "Optionally add LDAP or OIDC once the pilot scan is stable."
                        ),
                        workspace="sources",
                        section="auth",
                    ),
                ],
            ),
            self._build_category(
                "collection-pipeline",
                "Collection and normalization",
                "Whether the product is collecting real data, retaining raw evidence and compiling a usable snapshot.",
                [
                    FeatureInventoryItem(
                        id="live-filesystem-collection",
                        title="Live filesystem collection",
                        status="present" if active_targets else "missing",
                        summary=(
                            f"{len(active_targets)} active filesystem target(s) are configured."
                            if active_targets
                            else "No active live filesystem target is configured."
                        ),
                        gap=(
                            "The app cannot behave like a real control plane without at least one active target."
                            if not active_targets
                            else "No blocker remains for live collection scope."
                        ),
                        recommended_action=(
                            "Add at least one monitored path, share or mounted target."
                            if not active_targets
                            else "Review target depth, size and operational boundaries."
                        ),
                        workspace="sources",
                        section="collection",
                    ),
                    FeatureInventoryItem(
                        id="normalized-snapshot",
                        title="Normalized snapshot pipeline",
                        status=(
                            "present"
                            if data_ready and raw_stats["row_count"]
                            else "partial"
                            if active_targets or imported_sources
                            else "missing"
                        ),
                        summary=(
                            f"{raw_stats['row_count']} raw batch(es) and a successful normalized snapshot are available."
                            if data_ready and raw_stats["row_count"]
                            else "Targets exist, but the collection pipeline has not yet produced a healthy snapshot."
                            if active_targets or imported_sources
                            else "The normalization pipeline has nothing real to process yet."
                        ),
                        gap=(
                            "A successful scan is still missing, so explain and exposure remain untrustworthy."
                            if active_targets or imported_sources and not data_ready
                            else "No raw or normalized data exists yet."
                            if not active_targets and not imported_sources
                            else "The collection pipeline is producing usable normalized data."
                        ),
                        recommended_action=(
                            "Run a full scan and confirm the latest run completes as healthy."
                            if not data_ready
                            else "Monitor freshness and raw retention during the pilot."
                        ),
                        workspace="operations",
                        section="status",
                    ),
                    FeatureInventoryItem(
                        id="remote-linux-ssh",
                        title="Remote Linux collection over SSH",
                        status="present" if ssh_targets else "partial",
                        required_for_mvp=False,
                        summary=(
                            f"{len(ssh_targets)} SSH-based Linux target(s) are configured."
                            if ssh_targets
                            else "SSH-based Linux collection is implemented but not configured in this deployment."
                        ),
                        gap=(
                            "Remote Linux collection is not yet exercised in this environment."
                            if not ssh_targets
                            else "No meaningful gap remains for the SSH Linux collector."
                        ),
                        recommended_action=(
                            "Add one SSH Linux target if the pilot includes remote Linux hosts."
                            if not ssh_targets
                            else "Keep host key verification and least-privilege SSH accounts enforced."
                        ),
                        workspace="sources",
                        section="collection",
                    ),
                    FeatureInventoryItem(
                        id="offline-import-bundles",
                        title="Offline entitlement bundle import",
                        status="present" if imported_sources else "partial",
                        required_for_mvp=False,
                        summary=(
                            f"{len(imported_sources)} imported source bundle(s) are active."
                            if imported_sources
                            else "Offline bundle import is implemented but not yet exercised here."
                        ),
                        gap=(
                            "The fallback path for external entitlement bundles has not been tested in this deployment."
                            if not imported_sources
                            else "No major gap remains for offline source onboarding."
                        ),
                        recommended_action=(
                            "Import one JSON bundle if the pilot needs non-filesystem evidence."
                            if not imported_sources
                            else "Keep bundle schemas versioned and documented."
                        ),
                        workspace="sources",
                        section="imports",
                    ),
                ],
            ),
            self._build_category(
                "analysis-and-explainability",
                "Analysis and explainability",
                "Whether the app can answer who has access, why it exists and what changes would do fast enough for a pilot.",
                [
                    FeatureInventoryItem(
                        id="materialized-index",
                        title="Materialized access index",
                        status="present" if has_index else "missing",
                        summary=(
                            f"{access_index_stats['row_count']} entitlement row(s) are materialized for fast queries."
                            if has_index
                            else "The effective access index is still empty."
                        ),
                        gap=(
                            "Fast explain and exposure queries are not credible until the index is populated."
                            if not has_index
                            else "The index is available and query acceleration is in place."
                        ),
                        recommended_action=(
                            "Complete a healthy scan so the index can be compiled."
                            if not has_index
                            else "Use the indexed APIs during pilot validation."
                        ),
                        workspace="operations",
                        section="status",
                    ),
                    FeatureInventoryItem(
                        id="explain-path",
                        title="Explain path for effective access",
                        status="present" if has_index else "missing",
                        summary=(
                            "Explain responses are available from the materialized access graph."
                            if has_index
                            else "Explain exists in product but there is no indexed data to explain yet."
                        ),
                        gap=(
                            "Without indexed access data, the core MVP question cannot be answered reliably."
                            if not has_index
                            else "No major gap remains for explain path in this deployment."
                        ),
                        recommended_action=(
                            "Generate a healthy snapshot and validate one principal-resource explain path."
                            if not has_index
                            else "Validate the most important pilot path and export it as evidence."
                        ),
                        workspace="investigate",
                        section="explain",
                    ),
                    FeatureInventoryItem(
                        id="resource-exposure",
                        title="Who-has-access resource exposure",
                        status="present" if has_index else "missing",
                        summary=(
                            "The exposure view can enumerate effective principals for indexed resources."
                            if has_index
                            else "The exposure API is implemented but has no indexed data to query."
                        ),
                        gap=(
                            "The product cannot demonstrate who-has-access without a compiled access index."
                            if not has_index
                            else "No major gap remains for the exposure view."
                        ),
                        recommended_action=(
                            "Run a scan before using the exposure tab."
                            if not has_index
                            else "Validate one exposed resource during pilot sign-off."
                        ),
                        workspace="investigate",
                        section="exposure",
                    ),
                    FeatureInventoryItem(
                        id="whatif-simulation",
                        title="What-if simulation",
                        status="present" if scenarios else "partial" if has_index else "missing",
                        summary=(
                            f"{len(scenarios)} scenario edge(s) are available for blast-radius simulation."
                            if scenarios
                            else "What-if exists, but the current snapshot does not expose any scenario candidates."
                            if has_index
                            else "What-if is implemented but waiting for indexed data."
                        ),
                        gap=(
                            "The simulation engine has no candidate edge to test in this deployment."
                            if has_index and not scenarios
                            else "The platform needs indexed data before what-if can be demonstrated."
                            if not has_index
                            else "No major gap remains for what-if simulation."
                        ),
                        recommended_action=(
                            "Collect richer access data or choose a more privileged target to generate scenarios."
                            if has_index and not scenarios
                            else "Run a scan and repopulate the access index."
                            if not has_index
                            else "Use one simulation as part of the pilot evidence loop."
                        ),
                        workspace="investigate",
                        section="whatif",
                    ),
                    FeatureInventoryItem(
                        id="risk-and-change-signals",
                        title="Risk findings and change history",
                        status="present" if has_index and scans else "partial" if has_index or scans else "missing",
                        summary=(
                            "Risk and recent-change services are populated for the current deployment."
                            if has_index and scans
                            else "At least one of the risk or change feeds is available, but not both are fully useful yet."
                            if has_index or scans
                            else "Neither risk findings nor change history have enough runtime data yet."
                        ),
                        gap=(
                            "The operational signal layer is still too thin for a convincing MVP dashboard."
                            if has_index or scans and not (has_index and scans)
                            else "The platform still lacks the basic data needed for risk and change signals."
                            if not has_index and not scans
                            else "No major gap remains for risk and change signals."
                        ),
                        recommended_action=(
                            "Complete a healthy scan and verify the risk dashboard after index compilation."
                            if not (has_index and scans)
                            else "Use the dashboard as the executive summary layer for the pilot."
                        ),
                        workspace="operations",
                        section="status",
                    ),
                ],
            ),
            self._build_category(
                "governance-and-delivery",
                "Governance and delivery",
                "Whether an administrator can close the loop with review, remediation and deliverable evidence.",
                [
                    FeatureInventoryItem(
                        id="evidence-export",
                        title="Evidence export in HTML, PDF and XLSX",
                        status="present" if snapshot else "partial",
                        summary=(
                            "Professional export formats are available and backed by the current snapshot."
                            if snapshot
                            else "The export engine is implemented, but there is no real snapshot to export yet."
                        ),
                        gap=(
                            "The reporting engine needs a real snapshot before it can prove value."
                            if not snapshot
                            else "No major gap remains for evidence export."
                        ),
                        recommended_action=(
                            "Run a scan, then export one explain report and one review report as pilot evidence."
                            if not snapshot
                            else "Use exported evidence in the first pilot walkthrough."
                        ),
                        workspace="govern",
                        section="reviews",
                    ),
                    FeatureInventoryItem(
                        id="access-reviews",
                        title="Access reviews with deterministic remediation",
                        status="present" if reviews else "partial" if has_index else "missing",
                        summary=(
                            f"{len(reviews)} access review campaign(s) have already been recorded."
                            if reviews
                            else "Review campaigns are available, but none has been executed in this deployment yet."
                            if has_index
                            else "The governance loop is implemented but cannot start without indexed access data."
                        ),
                        gap=(
                            "The review flow exists but has not yet been exercised by an operator."
                            if has_index and not reviews
                            else "A healthy indexed snapshot is still required before review campaigns can start."
                            if not has_index
                            else "No major gap remains for review and remediation."
                        ),
                        recommended_action=(
                            "Create one review campaign and record at least one keep/revoke decision."
                            if has_index and not reviews
                            else "Run a scan first so review candidates can be generated."
                            if not has_index
                            else "Use the first completed campaign as pilot governance evidence."
                        ),
                        workspace="govern",
                        section="reviews",
                    ),
                    FeatureInventoryItem(
                        id="scheduled-reports",
                        title="Scheduled report delivery",
                        status="present" if schedules else "partial",
                        required_for_mvp=False,
                        summary=(
                            f"{len(schedules)} scheduled report job(s) are configured."
                            if schedules
                            else "Scheduled reporting is implemented, but this deployment has no active schedule."
                        ),
                        gap=(
                            "Report scheduling has not yet been exercised in this environment."
                            if not schedules
                            else "No major gap remains for scheduled delivery."
                        ),
                        recommended_action=(
                            "Create one daily or weekly schedule if the pilot includes recurring reporting."
                            if not schedules
                            else "Validate SMTP or webhook delivery before calling the pilot complete."
                        ),
                        workspace="govern",
                        section="schedules",
                    ),
                ],
            ),
            self._build_category(
                "packaging-and-operations",
                "Packaging and operations",
                "Whether the current codebase is packaged well enough to be installed and exercised by a real pilot team.",
                [
                    FeatureInventoryItem(
                        id="docker-production-build",
                        title="Docker production packaging",
                        status="present" if (root / "docker-compose.production.yml").exists() else "missing",
                        summary=(
                            "A production-oriented Docker deployment is present in the repository."
                            if (root / "docker-compose.production.yml").exists()
                            else "No production Docker packaging is currently available."
                        ),
                        gap=(
                            "The pilot cannot be deployed consistently through containers yet."
                            if not (root / "docker-compose.production.yml").exists()
                            else "No major packaging gap remains for Docker delivery."
                        ),
                        recommended_action=(
                            "Keep production secrets and mounts documented for operators."
                            if (root / "docker-compose.production.yml").exists()
                            else "Add a production Docker compose profile before pilot distribution."
                        ),
                        workspace="operations",
                        section="platform",
                    ),
                    FeatureInventoryItem(
                        id="windows-distribution",
                        title="Windows executable packaging",
                        status="present"
                        if (root / "scripts" / "build-windows.ps1").exists()
                        else "missing",
                        required_for_mvp=False,
                        summary=(
                            "A Windows packaging script is available for rebuilding the executable."
                            if (root / "scripts" / "build-windows.ps1").exists()
                            else "No Windows packaging script is available."
                        ),
                        gap=(
                            "Windows packaging is not wired for distribution yet."
                            if not (root / "scripts" / "build-windows.ps1").exists()
                            else "No major gap remains for Windows packaging."
                        ),
                        recommended_action=(
                            "Rebuild the executable after every release candidate."
                            if (root / "scripts" / "build-windows.ps1").exists()
                            else "Add a reproducible Windows packaging workflow."
                        ),
                        workspace="operations",
                        section="platform",
                    ),
                    FeatureInventoryItem(
                        id="linux-installer",
                        title="Linux installation script",
                        status="present" if (root / "scripts" / "install-linux.sh").exists() else "missing",
                        required_for_mvp=False,
                        summary=(
                            "A Linux installation script is available for self-hosted deployment."
                            if (root / "scripts" / "install-linux.sh").exists()
                            else "No Linux installer script is available."
                        ),
                        gap=(
                            "Linux self-hosted installation is not yet scripted."
                            if not (root / "scripts" / "install-linux.sh").exists()
                            else "No major gap remains for Linux installation."
                        ),
                        recommended_action=(
                            "Validate the installer on the target Linux family before pilot rollout."
                            if (root / "scripts" / "install-linux.sh").exists()
                            else "Add a reproducible Linux installation path."
                        ),
                        workspace="operations",
                        section="platform",
                    ),
                ],
            ),
        ]

        all_items = [item for category in categories for item in category.items]
        present_count = sum(1 for item in all_items if item.status == "present")
        partial_count = sum(1 for item in all_items if item.status == "partial")
        missing_count = sum(1 for item in all_items if item.status == "missing")
        required_missing = [
            item.title for item in all_items if item.required_for_mvp and item.status == "missing"
        ]
        overall_status = (
            "action_required"
            if required_missing
            else "ready"
            if partial_count == 0 and missing_count == 0
            else "in_progress"
        )

        return FeatureInventoryResponse(
            generated_at=utc_now_iso(),
            primary_scope="Filesystem live monitoring with explain, exposure, what-if, evidence export and access review.",
            overall_status=overall_status,
            categories=categories,
            present_count=present_count,
            partial_count=partial_count,
            missing_count=missing_count,
            required_missing=required_missing,
        )

    def _build_category(
        self,
        category_id: str,
        title: str,
        summary: str,
        items: list[FeatureInventoryItem],
    ) -> FeatureInventoryCategory:
        return FeatureInventoryCategory(
            id=category_id,
            title=title,
            summary=summary,
            items=items,
            present_count=sum(1 for item in items if item.status == "present"),
            partial_count=sum(1 for item in items if item.status == "partial"),
            missing_count=sum(1 for item in items if item.status == "missing"),
        )
