from __future__ import annotations

from app.engine import AccessGraphEngine
from app.auth import utc_now_iso
from app.models import ChangeRecord, ChangesResponse
from app.storage import AppStorage


class ChangeService:
    def __init__(self, storage: AppStorage) -> None:
        self._storage = storage

    def list_changes(self, limit: int = 20) -> ChangesResponse:
        scans = self._storage.list_scan_runs(limit=limit)
        metrics_by_started_at = {
            str(metric["started_at"]): metric
            for metric in self._storage.list_scan_run_metrics(limit=max(limit * 2, 20))
        }
        changes = [
            ChangeRecord(
                id=scan.id,
                occurred_at=scan.finished_at or scan.started_at,
                change_type="scan_completed",
                status=scan.status,
                summary=(
                    f"{scan.status.title()} scan processed {scan.resource_count} resources "
                    f"and {scan.relationship_count} relationships across {len(scan.target_ids)} targets."
                ),
                target_count=len(scan.target_ids),
                resource_count=scan.resource_count,
                relationship_count=scan.relationship_count,
                warning_count=scan.warning_count,
                privileged_path_count=int(
                    metrics_by_started_at.get(scan.started_at, {}).get("privileged_path_count", 0)
                ),
                broad_access_count=int(
                    metrics_by_started_at.get(scan.started_at, {}).get("broad_access_count", 0)
                ),
            )
            for scan in scans
        ]
        changes.extend(self._snapshot_drift_changes(limit=max(2, limit // 2)))
        changes.sort(key=lambda item: item.occurred_at, reverse=True)
        return ChangesResponse(generated_at=utc_now_iso(), changes=changes)

    def _snapshot_drift_changes(self, limit: int) -> list[ChangeRecord]:
        snapshots = self._storage.list_recent_snapshot_generated_at(limit=max(limit + 1, 3))
        changes: list[ChangeRecord] = []
        for index in range(len(snapshots) - 1):
            current_snapshot_at = snapshots[index]
            previous_snapshot_at = snapshots[index + 1]
            drift_change = self._drift_change_for_pair(
                current_snapshot_at=current_snapshot_at,
                previous_snapshot_at=previous_snapshot_at,
            )
            if drift_change is not None:
                changes.append(drift_change)
            if len(changes) >= limit:
                break
        return changes

    def _drift_change_for_pair(
        self,
        *,
        current_snapshot_at: str,
        previous_snapshot_at: str,
    ) -> ChangeRecord | None:
        current_rows = self._load_access_index_rows(current_snapshot_at)
        previous_rows = self._load_access_index_rows(previous_snapshot_at)
        if not current_rows or not previous_rows:
            return None

        current_map = {self._row_key(row): row for row in current_rows}
        previous_map = {self._row_key(row): row for row in previous_rows}
        added_keys = [key for key in current_map if key not in previous_map]
        removed_keys = [key for key in previous_map if key not in current_map]
        changed_keys = [
            key
            for key in current_map.keys() & previous_map.keys()
            if self._row_signature(current_map[key]) != self._row_signature(previous_map[key])
        ]
        if not added_keys and not removed_keys and not changed_keys:
            return None

        affected_principals = {key[0] for key in [*added_keys, *removed_keys, *changed_keys]}
        affected_resources = {key[1] for key in [*added_keys, *removed_keys, *changed_keys]}
        privileged_added = sum(
            1
            for key in [*added_keys, *changed_keys]
            if self._is_privileged_permissions(current_map[key]["permissions"])
        )
        risk_score = min(99, 42 + privileged_added * 8 + len(changed_keys) * 2 + len(added_keys))
        summary = (
            f"Detected {len(added_keys)} added, {len(removed_keys)} removed and "
            f"{len(changed_keys)} changed effective entitlements between the latest snapshots."
        )
        return ChangeRecord(
            id=f"drift_{current_snapshot_at}_{previous_snapshot_at}",
            occurred_at=current_snapshot_at,
            change_type="access_drift_detected",
            status="warning" if privileged_added else "healthy",
            summary=summary,
            previous_snapshot_at=previous_snapshot_at,
            current_snapshot_at=current_snapshot_at,
            warning_count=1 if privileged_added else 0,
            added_access_count=len(added_keys),
            removed_access_count=len(removed_keys),
            changed_access_count=len(changed_keys),
            affected_principal_count=len(affected_principals),
            affected_resource_count=len(affected_resources),
            broad_access_count=0,
            privileged_path_count=privileged_added,
            relationship_count=len(added_keys) + len(removed_keys) + len(changed_keys),
            resource_count=len(affected_resources),
            target_count=0,
        )

    def _load_access_index_rows(self, snapshot_generated_at: str) -> list[dict[str, object]]:
        rows = self._storage.list_materialized_access_index(snapshot_generated_at)
        if rows:
            return rows
        snapshot = self._storage.load_snapshot_by_generated_at(snapshot_generated_at)
        if snapshot is None:
            return []
        engine = AccessGraphEngine(snapshot)
        return engine.materialized_access_index()

    def _row_key(self, row: dict[str, object]) -> tuple[str, str]:
        return (str(row["principal_id"]), str(row["resource_id"]))

    def _row_signature(self, row: dict[str, object]) -> tuple[tuple[str, ...], str, int]:
        permissions = tuple(sorted(str(permission) for permission in row["permissions"]))
        return (
            permissions,
            str(row["access_mode"]),
            int(row.get("path_count", 0)),
        )

    def _is_privileged_permissions(self, permissions: list[object]) -> bool:
        privileged_markers = {"admin", "fullcontrol", "delete", "write", "modify", "takeownership", "changepermissions"}
        normalized = {str(permission).strip().lower() for permission in permissions}
        return any(marker in normalized for marker in privileged_markers)
