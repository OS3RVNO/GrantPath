from __future__ import annotations

from collections import Counter

from app.auth import utc_now_iso
from app.models import (
    ConnectorRecommendedUsage,
    ConnectorRuntimeStatus,
    ConnectorSupportMatrixEntry,
    ConnectorSupportMatrixResponse,
    ConnectorSupportTier,
    ConnectorValidationLevel,
)


class ConnectorSupportService:
    def __init__(self, storage, runtime_getter) -> None:
        self._storage = storage
        self._runtime_getter = runtime_getter

    def status(self) -> ConnectorSupportMatrixResponse:
        runtime = self._runtime_getter()
        targets = self._storage.list_targets()
        active_targets = [target for target in targets if target.enabled]
        ssh_targets = [target for target in active_targets if target.connection_mode == "ssh"]
        imported_sources = [source for source in self._storage.list_imported_sources() if source.enabled]
        scan_runs = self._storage.list_scan_runs(limit=10)
        latest_successful_scan = next(
            (run for run in scan_runs if run.status in {"healthy", "warning"} and run.finished_at),
            None,
        )
        connector_inventory = runtime.connector_inventory()

        entries = [
            self._native_filesystem_entry(active_targets, latest_successful_scan is not None),
            self._native_linux_ssh_entry(ssh_targets, latest_successful_scan is not None),
            self._offline_bundle_entry(imported_sources),
        ]
        entries.extend(
            self._runtime_connector_entry(connector)
            for connector in connector_inventory.connectors
        )

        counts_by_tier = Counter(entry.support_tier for entry in entries)
        counts_by_validation = Counter(entry.validation_level for entry in entries)
        return ConnectorSupportMatrixResponse(
            generated_at=utc_now_iso(),
            primary_scope=(
                "Filesystem-first control plane with explicit support tiers for native collectors and documented enterprise connectors."
            ),
            entries=entries,
            counts_by_tier=dict(counts_by_tier),
            counts_by_validation=dict(counts_by_validation),
        )

    def _native_filesystem_entry(
        self,
        active_targets,
        has_successful_scan: bool,
    ) -> ConnectorSupportMatrixEntry:
        configured = bool(active_targets)
        validation_level: ConnectorValidationLevel = (
            "runtime_verified"
            if configured and has_successful_scan
            else "config_validated"
            if configured
            else "planned"
        )
        support_tier: ConnectorSupportTier = "supported" if configured else "pilot"
        recommended_usage: ConnectorRecommendedUsage = (
            "production"
            if validation_level == "runtime_verified"
            else "pilot"
            if configured
            else "lab"
        )
        evidence = [
            f"{len(active_targets)} active filesystem target(s) configured." if configured else "No live target configured yet.",
            "Native collector supports local Windows/Linux scans and mounted or reachable filesystem paths.",
        ]
        current_gaps = (
            ["Add at least one live target before using the platform as an operational control plane."]
            if not configured
            else []
        )
        next_actions = (
            ["Add and validate a live filesystem target."]
            if not configured
            else ["Keep target boundaries, depth and retention aligned with pilot scope."]
        )
        return ConnectorSupportMatrixEntry(
            id="native-filesystem",
            name="Native filesystem collection",
            category="Native runtime",
            vendor="EIP",
            support_tier=support_tier,
            validation_level=validation_level,
            recommended_usage=recommended_usage,
            runtime_configured=configured,
            runtime_enabled=configured,
            implementation_status="live",
            summary=(
                "Production-capable first-party collection for the filesystem surfaces exercised by this deployment."
                if configured
                else "First-party filesystem collector is implemented, but the current deployment has not enabled any live target."
            ),
            evidence=evidence,
            current_gaps=current_gaps,
            next_actions=next_actions,
            documentation_links=[],
        )

    def _native_linux_ssh_entry(
        self,
        ssh_targets,
        has_successful_scan: bool,
    ) -> ConnectorSupportMatrixEntry:
        configured = bool(ssh_targets)
        validation_level: ConnectorValidationLevel = (
            "runtime_verified"
            if configured and has_successful_scan
            else "config_validated"
            if configured
            else "planned"
        )
        return ConnectorSupportMatrixEntry(
            id="native-linux-ssh",
            name="Linux collection over SSH",
            category="Native runtime",
            vendor="EIP",
            support_tier="pilot" if configured else "experimental",
            validation_level=validation_level,
            recommended_usage=(
                "pilot"
                if configured and validation_level == "runtime_verified"
                else "lab"
            ),
            runtime_configured=configured,
            runtime_enabled=configured,
            implementation_status="live",
            summary=(
                "Remote Linux collection over SSH is wired and currently exercised by this deployment."
                if configured
                else "Remote Linux collection exists in the runtime but is not configured here."
            ),
            evidence=[
                f"{len(ssh_targets)} SSH target(s) configured." if configured else "No SSH target configured.",
                "Host key verification is enforced and collection stays read-only.",
            ],
            current_gaps=(
                []
                if configured
                else ["Add at least one SSH Linux target before treating this surface as pilot-ready."]
            ),
            next_actions=(
                ["Keep SSH credentials least-privileged and review host trust material."]
                if configured
                else ["Configure one Linux SSH target if the rollout includes remote Linux hosts."]
            ),
            documentation_links=[],
        )

    def _offline_bundle_entry(self, imported_sources) -> ConnectorSupportMatrixEntry:
        configured = bool(imported_sources)
        return ConnectorSupportMatrixEntry(
            id="native-offline-bundles",
            name="Offline entitlement bundle import",
            category="Native runtime",
            vendor="EIP",
            support_tier="supported" if configured else "pilot",
            validation_level="runtime_verified" if configured else "planned",
            recommended_usage="production" if configured else "pilot",
            runtime_configured=configured,
            runtime_enabled=configured,
            implementation_status="live",
            summary=(
                "Offline JSON bundle import is active and can extend the evidence plane without live connectors."
                if configured
                else "Offline bundle import is implemented and available as a fallback source onboarding path."
            ),
            evidence=[
                f"{len(imported_sources)} imported source(s) enabled." if configured else "No imported source enabled.",
                "Useful when a live connector is not available but raw entitlement evidence still exists.",
            ],
            current_gaps=[],
            next_actions=(
                ["Keep import schemas versioned and document the provenance of every bundle."]
                if configured
                else ["Use an import bundle whenever a pilot source cannot be collected live."]
            ),
            documentation_links=[],
        )

    def _runtime_connector_entry(
        self,
        connector: ConnectorRuntimeStatus,
    ) -> ConnectorSupportMatrixEntry:
        support_tier = self._support_tier(connector)
        validation_level = self._validation_level(connector)
        recommended_usage = self._recommended_usage(support_tier, validation_level)
        evidence = []
        if connector.last_sync:
            evidence.append(f"Last successful runtime sync: {connector.last_sync}.")
        if connector.entity_count or connector.relationship_count:
            evidence.append(
                f"Runtime observed {connector.entity_count} entities and {connector.relationship_count} relationships."
            )
        if connector.current_runtime_coverage:
            evidence.append(connector.current_runtime_coverage[0])
        if not evidence:
            evidence.append("No runtime evidence is recorded yet for this connector in the current deployment.")

        current_gaps = list(connector.notes[:2])
        if connector.official_limitations:
            current_gaps.append(connector.official_limitations[0])
        current_gaps = current_gaps[:3]

        next_actions = []
        if not connector.configured and connector.required_env:
            next_actions.append(
                f"Set the required environment and secrets for {connector.surface.lower()}."
            )
        if connector.implementation_status == "partial":
            next_actions.append(
                "Validate the documented runtime coverage against the pilot scope before treating it as authoritative."
            )
        if connector.implementation_status == "blueprint":
            next_actions.append(
                "Keep this surface in documentation-only mode until a live collector is wired."
            )
        if validation_level == "runtime_verified":
            next_actions.append(
                "Monitor sync freshness, rotate credentials and keep the documented limitations visible to operators."
            )
        if not next_actions:
            next_actions.append("Review connector scope and permissions periodically.")

        return ConnectorSupportMatrixEntry(
            id=connector.id,
            name=connector.surface,
            category=self._connector_category(connector.id),
            vendor=connector.source,
            support_tier=support_tier,
            validation_level=validation_level,
            recommended_usage=recommended_usage,
            runtime_configured=connector.configured,
            runtime_enabled=connector.enabled,
            implementation_status=connector.implementation_status,
            summary=self._summary_for_connector(connector, support_tier, validation_level),
            evidence=evidence,
            current_gaps=current_gaps,
            next_actions=next_actions,
            documentation_links=connector.documentation_links,
        )

    def _support_tier(self, connector: ConnectorRuntimeStatus) -> ConnectorSupportTier:
        if connector.implementation_status == "blueprint":
            return "blueprint"
        if connector.implementation_status == "partial":
            return "pilot"
        if connector.configured and connector.enabled:
            return "supported"
        return "experimental"

    def _validation_level(
        self,
        connector: ConnectorRuntimeStatus,
    ) -> ConnectorValidationLevel:
        if connector.last_sync or connector.entity_count or connector.relationship_count:
            return "runtime_verified"
        if connector.configured:
            return "config_validated"
        if connector.implementation_status in {"live", "partial"}:
            return "doc_aligned"
        return "planned"

    def _recommended_usage(
        self,
        support_tier: ConnectorSupportTier,
        validation_level: ConnectorValidationLevel,
    ) -> ConnectorRecommendedUsage:
        if support_tier == "supported" and validation_level == "runtime_verified":
            return "production"
        if support_tier in {"supported", "pilot"}:
            return "pilot"
        if support_tier == "experimental":
            return "lab"
        return "design_only"

    def _connector_category(self, connector_id: str) -> str:
        if connector_id in {"ad-ldap", "entra-graph", "okta-ud", "google-directory"}:
            return "Identity and directory"
        if connector_id in {"azure-rbac", "aws-iam"}:
            return "Cloud control plane"
        if connector_id in {"m365-collaboration", "google-drive-collaboration"}:
            return "Collaboration"
        if connector_id == "cyberark":
            return "Privileged access"
        return "Other enterprise"

    def _summary_for_connector(
        self,
        connector: ConnectorRuntimeStatus,
        support_tier: ConnectorSupportTier,
        validation_level: ConnectorValidationLevel,
    ) -> str:
        if support_tier == "blueprint":
            return (
                f"{connector.surface} is documented and modeled, but this runtime does not ship a live collector for it yet."
            )
        if validation_level == "runtime_verified":
            return (
                f"{connector.surface} is configured and has produced runtime evidence in this deployment."
            )
        if connector.configured:
            return (
                f"{connector.surface} is configured, but the current deployment has not produced live evidence for it yet."
            )
        return (
            f"{connector.surface} is present in the product model, but configuration and validation are still pending."
        )
