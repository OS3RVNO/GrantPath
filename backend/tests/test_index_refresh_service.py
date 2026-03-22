from pathlib import Path

from app.demo_data import build_demo_snapshot
from app.engine import AccessGraphEngine
from app.index_refresh_service import IndexRefreshService
from app.models import Relationship
from app.storage import AppStorage


def _storage_for(tmp_path: Path) -> AppStorage:
    storage = AppStorage(tmp_path / "eip.db")
    storage.initialize()
    return storage


def _normalize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda item: (
            str(item["principal_id"]),
            str(item["resource_id"]),
            str(item["access_mode"]),
            int(item["risk_score"]),
            int(item["path_count"]),
        ),
    )


def test_index_refresh_carries_forward_when_snapshot_graph_is_unchanged(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    service = IndexRefreshService(storage)

    previous_snapshot = build_demo_snapshot().model_copy(
        update={"generated_at": "2026-03-21T00:00:00Z"}
    )
    storage.save_snapshot(previous_snapshot)
    previous_engine = AccessGraphEngine(previous_snapshot)

    first_summary = service.ensure_indexes(previous_snapshot, previous_engine)
    assert first_summary.mode == "full"

    current_snapshot = previous_snapshot.model_copy(
        update={"generated_at": "2026-03-21T01:00:00Z"}
    )
    storage.save_snapshot(current_snapshot)
    current_engine = AccessGraphEngine(current_snapshot)

    summary = service.ensure_indexes(current_snapshot, current_engine)

    assert summary.mode == "carry_forward"
    assert summary.reused_access_rows > 0
    assert summary.recomputed_access_rows == 0
    assert _normalize_rows(
        storage.list_materialized_access_index(current_snapshot.generated_at)
    ) == _normalize_rows(current_engine.materialized_access_index())


def test_index_refresh_recomputes_only_impacted_scope_for_safe_delta_change(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    service = IndexRefreshService(storage)

    previous_snapshot = build_demo_snapshot().model_copy(
        update={"generated_at": "2026-03-21T00:00:00Z"}
    )
    storage.save_snapshot(previous_snapshot)
    previous_engine = AccessGraphEngine(previous_snapshot)
    service.ensure_indexes(previous_snapshot, previous_engine)

    current_snapshot = previous_snapshot.model_copy(
        update={
            "generated_at": "2026-03-21T01:00:00Z",
            "relationships": previous_snapshot.relationships
            + [
                Relationship(
                    id="rel_omar_direct_payroll",
                    kind="direct_acl",
                    source="user_omar",
                    target="res_folder_payroll",
                    label="Direct Read on Payroll Folder",
                    rationale="Added to validate incremental access index refresh.",
                    permissions=["Read"],
                    removable=True,
                )
            ],
        }
    )
    storage.save_snapshot(current_snapshot)
    current_engine = AccessGraphEngine(current_snapshot)

    summary = service.ensure_indexes(current_snapshot, current_engine)

    assert summary.mode == "delta"
    assert summary.reused_access_rows > 0
    assert summary.recomputed_access_rows > 0
    assert summary.impacted_principals >= 1
    assert summary.impacted_resources >= 1
    assert _normalize_rows(
        storage.list_materialized_access_index(current_snapshot.generated_at)
    ) == _normalize_rows(current_engine.materialized_access_index())
