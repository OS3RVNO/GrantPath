from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.models import (
    AccessReviewCampaignCreateRequest,
    AccessReviewCampaignDetailResponse,
    AccessReviewCampaignSummary,
    AccessReviewDecisionRequest,
    AccessReviewItem,
    AuditEventRecord,
    AuthProviderConfig,
    AuthProviderCreateRequest,
    AuthProviderDetailResponse,
    AuthProviderSummary,
    AuthProviderUpdateRequest,
    ImportedSourceBundle,
    ImportedSourceDetailResponse,
    ImportedSourceSummary,
    ImportedSourceUpdateRequest,
    ReportDeliverySettings,
    ReportScheduleConfig,
    ReportScheduleCreateRequest,
    ReportScheduleDetailResponse,
    ReportScheduleListResponse,
    ReportScheduleRunRecord,
    ReportScheduleSummary,
    ReportScheduleUpdateRequest,
    ScanRunRecord,
    ScanTarget,
    ScanTargetCreateRequest,
    ScanTargetUpdateRequest,
    Snapshot,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency for local SQLite mode
    psycopg = None
    dict_row = None


CURRENT_SCHEMA_VERSION = 4


def _as_bool(value: object) -> bool:
    return bool(int(value)) if isinstance(value, (int, float, str)) else bool(value)


def _decode_roles(value: object) -> list[str]:
    if value in {None, ""}:
        return ["admin"]
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return ["admin"]
    if not isinstance(parsed, list):
        return ["admin"]
    roles = [str(item).strip() for item in parsed if str(item).strip()]
    return roles or ["admin"]


class _CompatCursor:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return int(getattr(self._cursor, "rowcount", 0))


class _PostgresCompatConnection:
    def __init__(self, database_url: str) -> None:
        if psycopg is None or dict_row is None:  # pragma: no cover - dependency guard
            raise RuntimeError("psycopg is required for PostgreSQL support.")
        self._connection = psycopg.connect(database_url, row_factory=dict_row)

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s")

    def execute(self, query: str, params: tuple | list = ()):
        cursor = self._connection.cursor()
        try:
            cursor.execute(self._sql(query), params)
        except Exception:
            self._connection.rollback()
            raise
        return _CompatCursor(cursor)

    def executemany(self, query: str, param_sets: list[tuple] | list[list]):
        cursor = self._connection.cursor()
        try:
            cursor.executemany(self._sql(query), param_sets)
        except Exception:
            self._connection.rollback()
            raise
        return _CompatCursor(cursor)

    def executescript(self, script: str) -> None:
        statements = [statement.strip() for statement in script.split(";") if statement.strip()]
        with self._connection.cursor() as cursor:
            try:
                for statement in statements:
                    cursor.execute(statement)
            except Exception:
                self._connection.rollback()
                raise

    def commit(self) -> None:
        self._connection.commit()


class AppStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._database_url = settings.database_url
        self._is_postgres = bool(self._database_url and self._database_url.startswith("postgres"))
        if self._is_postgres:
            self._connection = _PostgresCompatConnection(str(self._database_url))
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        if not self._is_postgres:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")

    @property
    def backend_name(self) -> str:
        return "PostgreSQL" if self._is_postgres else "SQLite"

    def schema_version(self) -> int:
        with self._lock:
            self._ensure_schema_version_table()
            row = self._connection.execute(
                "SELECT version FROM schema_version WHERE id = 1"
            ).fetchone()
        return 0 if row is None else int(row["version"])

    def initialize(self) -> None:
        with self._lock:
            self._ensure_schema_version_table()
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    auth_source TEXT NOT NULL DEFAULT 'local',
                    external_subject TEXT,
                    display_name TEXT,
                    roles_json TEXT NOT NULL DEFAULT '["admin"]',
                    mfa_secret TEXT,
                    mfa_enabled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    must_change_password INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    csrf_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    scope TEXT PRIMARY KEY,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    first_failure_at TEXT NOT NULL,
                    locked_until TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    description TEXT,
                    environment TEXT NOT NULL DEFAULT 'on-prem',
                    active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_targets (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    connection_mode TEXT NOT NULL DEFAULT 'local',
                    host TEXT,
                    port INTEGER NOT NULL DEFAULT 22,
                    username TEXT,
                    secret_env TEXT,
                    key_path TEXT,
                    recursive INTEGER NOT NULL,
                    max_depth INTEGER NOT NULL,
                    max_entries INTEGER NOT NULL,
                    include_hidden INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    notes TEXT,
                    last_scan_at TEXT,
                    last_status TEXT NOT NULL DEFAULT 'idle',
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    generated_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS raw_snapshots (
                    id TEXT PRIMARY KEY,
                    snapshot_generated_at TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_raw_snapshots_generated_at
                    ON raw_snapshots(snapshot_generated_at);

                CREATE TABLE IF NOT EXISTS imported_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    description TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    bundle_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    target_ids_json TEXT NOT NULL,
                    resource_count INTEGER NOT NULL DEFAULT 0,
                    principal_count INTEGER NOT NULL DEFAULT 0,
                    relationship_count INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    privileged_path_count INTEGER NOT NULL DEFAULT 0,
                    broad_access_count INTEGER NOT NULL DEFAULT 0,
                    notes_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS query_metrics (
                    id TEXT PRIMARY KEY,
                    recorded_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    status_code INTEGER NOT NULL,
                    request_path TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_query_metrics_operation_recorded_at
                    ON query_metrics(operation, recorded_at DESC);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    actor_username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_audit_events_occurred_at
                    ON audit_events(occurred_at DESC);

                CREATE TABLE IF NOT EXISTS access_index (
                    snapshot_generated_at TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    permissions_json TEXT NOT NULL,
                    path_count INTEGER NOT NULL,
                    path_complexity INTEGER NOT NULL DEFAULT 0,
                    access_mode TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    why TEXT NOT NULL,
                    PRIMARY KEY(snapshot_generated_at, principal_id, resource_id)
                );

                CREATE INDEX IF NOT EXISTS idx_access_index_resource
                    ON access_index(snapshot_generated_at, resource_id);

                CREATE INDEX IF NOT EXISTS idx_access_index_principal
                    ON access_index(snapshot_generated_at, principal_id);

                CREATE TABLE IF NOT EXISTS principal_group_closure (
                    snapshot_generated_at TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    shortest_parent_id TEXT NOT NULL,
                    path_count INTEGER NOT NULL,
                    last_verified_at TEXT NOT NULL,
                    PRIMARY KEY(snapshot_generated_at, principal_id, group_id)
                );

                CREATE INDEX IF NOT EXISTS idx_principal_group_closure_principal
                    ON principal_group_closure(snapshot_generated_at, principal_id);

                CREATE TABLE IF NOT EXISTS resource_hierarchy_closure (
                    snapshot_generated_at TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    ancestor_resource_id TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    inherits_acl INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(snapshot_generated_at, resource_id, ancestor_resource_id)
                );

                CREATE INDEX IF NOT EXISTS idx_resource_hierarchy_closure_resource
                    ON resource_hierarchy_closure(snapshot_generated_at, resource_id);

                CREATE TABLE IF NOT EXISTS resource_exposure_index (
                    snapshot_generated_at TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    principal_count INTEGER NOT NULL,
                    privileged_principal_count INTEGER NOT NULL,
                    max_risk_score INTEGER NOT NULL,
                    average_path_complexity INTEGER NOT NULL DEFAULT 0,
                    exposure_score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(snapshot_generated_at, resource_id)
                );

                CREATE INDEX IF NOT EXISTS idx_resource_exposure_index_snapshot
                    ON resource_exposure_index(snapshot_generated_at, exposure_score DESC);

                CREATE TABLE IF NOT EXISTS principal_access_summary (
                    snapshot_generated_at TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    resource_count INTEGER NOT NULL,
                    privileged_resource_count INTEGER NOT NULL,
                    max_risk_score INTEGER NOT NULL,
                    average_path_complexity INTEGER NOT NULL DEFAULT 0,
                    exposure_score INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(snapshot_generated_at, principal_id)
                );

                CREATE INDEX IF NOT EXISTS idx_principal_access_summary_snapshot
                    ON principal_access_summary(snapshot_generated_at, exposure_score DESC);

                CREATE TABLE IF NOT EXISTS access_review_campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    snapshot_generated_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    min_risk_score INTEGER NOT NULL DEFAULT 70,
                    privileged_only INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS access_review_items (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    permissions_json TEXT NOT NULL,
                    path_count INTEGER NOT NULL,
                    access_mode TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    why TEXT NOT NULL,
                    decision TEXT NOT NULL DEFAULT 'pending',
                    decision_note TEXT,
                    reviewed_at TEXT,
                    suggested_edge_id TEXT,
                    suggested_edge_label TEXT,
                    suggested_remediation TEXT,
                    FOREIGN KEY(campaign_id) REFERENCES access_review_campaigns(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_access_review_items_campaign
                    ON access_review_items(campaign_id);

                CREATE TABLE IF NOT EXISTS report_schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    cadence TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    hour INTEGER NOT NULL DEFAULT 8,
                    minute INTEGER NOT NULL DEFAULT 0,
                    day_of_week INTEGER,
                    day_of_month INTEGER,
                    report_kind TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    delivery_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_status TEXT NOT NULL DEFAULT 'never',
                    last_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_report_schedules_next_run
                    ON report_schedules(enabled, next_run_at);

                CREATE TABLE IF NOT EXISTS report_schedule_runs (
                    id TEXT PRIMARY KEY,
                    schedule_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    trigger_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    delivered_channels_json TEXT NOT NULL DEFAULT '[]',
                    artifact_paths_json TEXT NOT NULL DEFAULT '[]',
                    message TEXT,
                    FOREIGN KEY(schedule_id) REFERENCES report_schedules(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_report_schedule_runs_schedule
                    ON report_schedule_runs(schedule_id, started_at DESC);

                CREATE TABLE IF NOT EXISTS scan_object_cache (
                    target_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(target_id, path)
                );

                CREATE TABLE IF NOT EXISTS auth_providers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    preset TEXT NOT NULL DEFAULT 'custom',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    description TEXT,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_flow_states (
                    state TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    code_verifier TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mfa_pending_setups (
                    username TEXT PRIMARY KEY,
                    secret_ciphertext TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mfa_challenges (
                    challenge_token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    auth_source TEXT NOT NULL,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column("sessions", "csrf_token", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column("scan_targets", "connection_mode", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("scan_targets", "host", "TEXT")
            self._ensure_column("scan_targets", "port", "INTEGER NOT NULL DEFAULT 22")
            self._ensure_column("scan_targets", "username", "TEXT")
            self._ensure_column("scan_targets", "secret_env", "TEXT")
            self._ensure_column("scan_targets", "key_path", "TEXT")
            self._ensure_column("access_index", "path_complexity", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("admin_users", "auth_source", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column("admin_users", "external_subject", "TEXT")
            self._ensure_column("admin_users", "display_name", "TEXT")
            self._ensure_column("admin_users", "roles_json", "TEXT NOT NULL DEFAULT '[\"admin\"]'")
            self._ensure_column("admin_users", "mfa_secret", "TEXT")
            self._ensure_column("admin_users", "mfa_enabled", "INTEGER NOT NULL DEFAULT 0")
            self._set_schema_version(CURRENT_SCHEMA_VERSION)
            self._connection.commit()

    def load_scan_caches(self, target_ids: list[str]) -> dict[str, dict[str, dict[str, object]]]:
        if not target_ids:
            return {}
        with self._lock:
            if self._is_postgres:
                rows = self._connection.execute(
                    """
                    SELECT target_id, path, fingerprint, record_json
                    FROM scan_object_cache
                    WHERE target_id = ANY(%s)
                    """,
                    (target_ids,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT target_id, path, fingerprint, record_json
                    FROM scan_object_cache
                    WHERE target_id IN (SELECT value FROM json_each(?))
                    """,
                    (json.dumps(target_ids),),
                ).fetchall()
        cache_by_target: dict[str, dict[str, dict[str, object]]] = {}
        for row in rows:
            target_cache = cache_by_target.setdefault(str(row["target_id"]), {})
            target_cache[str(row["path"])] = {
                "fingerprint": str(row["fingerprint"]),
                "record": json.loads(str(row["record_json"])),
            }
        return cache_by_target

    def replace_scan_cache(
        self,
        target_id: str,
        entries: list[dict[str, object]],
        *,
        timestamp: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM scan_object_cache WHERE target_id = ?",
                (target_id,),
            )
            self._connection.executemany(
                """
                INSERT INTO scan_object_cache(target_id, path, fingerprint, record_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        target_id,
                        str(entry["path"]),
                        str(entry["fingerprint"]),
                        json.dumps(entry["record"]),
                        timestamp,
                    )
                    for entry in entries
                ],
            )
            self._connection.commit()

    def get_setting(self, key: str) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO settings(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            self._connection.commit()

    def list_workspaces(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, name, slug, description, environment, active, created_at, updated_at
                FROM workspaces
                ORDER BY active DESC, name ASC, created_at ASC
                """
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "slug": str(row["slug"]),
                "description": None if row["description"] is None else str(row["description"]),
                "environment": str(row["environment"]),
                "active": bool(row["active"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ]

    def get_workspace(self, workspace_id: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT id, name, slug, description, environment, active, created_at, updated_at
                FROM workspaces
                WHERE id = ?
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
            "description": None if row["description"] is None else str(row["description"]),
            "environment": str(row["environment"]),
            "active": bool(row["active"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def slug_in_use(self, slug: str, *, exclude_workspace_id: str | None = None) -> bool:
        query = "SELECT id FROM workspaces WHERE slug = ?"
        params: tuple[object, ...] = (slug,)
        if exclude_workspace_id:
            query += " AND id <> ?"
            params = (slug, exclude_workspace_id)
        query += " LIMIT 1"
        with self._lock:
            row = self._connection.execute(query, params).fetchone()
        return row is not None

    def create_workspace(
        self,
        *,
        workspace_id: str,
        name: str,
        slug: str,
        description: str | None,
        environment: str,
        created_at: str,
        active: bool,
    ) -> None:
        with self._lock:
            if active:
                self._connection.execute("UPDATE workspaces SET active = 0")
            self._connection.execute(
                """
                INSERT INTO workspaces(
                    id, name, slug, description, environment, active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    name,
                    slug,
                    description,
                    environment,
                    1 if active else 0,
                    created_at,
                    created_at,
                ),
            )
            if active:
                self._connection.execute(
                    """
                    INSERT INTO settings(key, value)
                    VALUES ('active_workspace_id', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (workspace_id,),
                )
            self._connection.commit()

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        environment: str | None = None,
        updated_at: str,
    ) -> dict[str, object] | None:
        current = self.get_workspace(workspace_id)
        if current is None:
            return None
        with self._lock:
            self._connection.execute(
                """
                UPDATE workspaces
                SET name = ?, description = ?, environment = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    current["name"] if name is None else name,
                    current["description"] if description is None else description,
                    current["environment"] if environment is None else environment,
                    updated_at,
                    workspace_id,
                ),
            )
            self._connection.commit()
        return self.get_workspace(workspace_id)

    def set_active_workspace(self, workspace_id: str, *, updated_at: str) -> bool:
        with self._lock:
            existing = self._connection.execute(
                "SELECT id FROM workspaces WHERE id = ? LIMIT 1",
                (workspace_id,),
            ).fetchone()
            if existing is None:
                return False
            self._connection.execute("UPDATE workspaces SET active = 0")
            self._connection.execute(
                "UPDATE workspaces SET active = 1, updated_at = ? WHERE id = ?",
                (updated_at, workspace_id),
            )
            self._connection.execute(
                """
                INSERT INTO settings(key, value)
                VALUES ('active_workspace_id', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (workspace_id,),
            )
            self._connection.commit()
        return True

    def active_workspace_id(self) -> str | None:
        active = self.get_setting("active_workspace_id")
        if active:
            return active
        with self._lock:
            row = self._connection.execute(
                """
                SELECT id
                FROM workspaces
                ORDER BY active DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else str(row["id"])

    def list_auth_providers(self) -> list[AuthProviderSummary]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM auth_providers
                ORDER BY enabled DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_auth_provider_summary(row) for row in rows]

    def get_auth_provider(self, provider_id: str) -> AuthProviderDetailResponse | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM auth_providers WHERE id = ?",
                (provider_id,),
            ).fetchone()
        return None if row is None else self._row_to_auth_provider_detail(row)

    def create_auth_provider(
        self,
        payload: AuthProviderCreateRequest,
        *,
        timestamp: str,
    ) -> AuthProviderDetailResponse:
        provider_id = f"auth_{uuid.uuid4().hex[:12]}"
        config_payload = json.dumps(payload.config.model_dump(mode="json"))
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO auth_providers(
                    id, name, kind, preset, enabled, description, config_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    payload.name,
                    payload.config.kind,
                    payload.config.preset,
                    int(payload.enabled),
                    payload.config.description,
                    config_payload,
                    timestamp,
                    timestamp,
                ),
            )
            self._connection.commit()
        return self.get_auth_provider(provider_id)  # type: ignore[return-value]

    def update_auth_provider(
        self,
        provider_id: str,
        payload: AuthProviderUpdateRequest,
        *,
        timestamp: str,
    ) -> AuthProviderDetailResponse | None:
        current = self.get_auth_provider(provider_id)
        if current is None:
            return None
        next_summary = current.summary.model_copy(
            update={
                key: value
                for key, value in payload.model_dump(exclude_unset=True, exclude={"config"}).items()
            }
        )
        next_config = current.config if payload.config is None else payload.config
        with self._lock:
            self._connection.execute(
                """
                UPDATE auth_providers
                SET name = ?, kind = ?, preset = ?, enabled = ?, description = ?, config_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_summary.name,
                    next_config.kind,
                    next_config.preset,
                    int(next_summary.enabled),
                    next_config.description,
                    json.dumps(next_config.model_dump(mode="json")),
                    timestamp,
                    provider_id,
                ),
            )
            self._connection.commit()
        return self.get_auth_provider(provider_id)

    def delete_auth_provider(self, provider_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM auth_providers WHERE id = ?",
                (provider_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def create_auth_flow_state(
        self,
        *,
        state: str,
        provider_id: str,
        code_verifier: str | None,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO auth_flow_states(state, provider_id, code_verifier, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (state, provider_id, code_verifier, created_at, expires_at),
            )
            self._connection.commit()

    def consume_auth_flow_state(self, state: str) -> dict[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT state, provider_id, code_verifier, created_at, expires_at
                FROM auth_flow_states
                WHERE state = ?
                """,
                (state,),
            ).fetchone()
            if row is None:
                return None
            self._connection.execute("DELETE FROM auth_flow_states WHERE state = ?", (state,))
            self._connection.commit()
        return {
            "state": str(row["state"]),
            "provider_id": str(row["provider_id"]),
            "code_verifier": str(row["code_verifier"]) if row["code_verifier"] else "",
            "created_at": str(row["created_at"]),
            "expires_at": str(row["expires_at"]),
        }

    def upsert_mfa_pending_setup(
        self,
        *,
        username: str,
        secret_ciphertext: str,
        created_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO mfa_pending_setups(username, secret_ciphertext, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(username) DO UPDATE
                SET secret_ciphertext = excluded.secret_ciphertext,
                    created_at = excluded.created_at
                """,
                (username, secret_ciphertext, created_at),
            )
            self._connection.commit()

    def get_mfa_pending_setup(self, username: str) -> dict[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT username, secret_ciphertext, created_at
                FROM mfa_pending_setups
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            return None
        return {
            "username": str(row["username"]),
            "secret_ciphertext": str(row["secret_ciphertext"]),
            "created_at": str(row["created_at"]),
        }

    def delete_mfa_pending_setup(self, username: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM mfa_pending_setups WHERE username = ?", (username,))
            self._connection.commit()

    def create_mfa_challenge(
        self,
        *,
        challenge_token: str,
        username: str,
        auth_source: str,
        must_change_password: bool,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO mfa_challenges(
                    challenge_token, username, auth_source, must_change_password, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_token,
                    username,
                    auth_source,
                    int(must_change_password),
                    created_at,
                    expires_at,
                ),
            )
            self._connection.commit()

    def get_mfa_challenge(self, challenge_token: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT challenge_token, username, auth_source, must_change_password, created_at, expires_at
                FROM mfa_challenges
                WHERE challenge_token = ?
                """,
                (challenge_token,),
            ).fetchone()
        if row is None:
            return None
        return {
            "challenge_token": str(row["challenge_token"]),
            "username": str(row["username"]),
            "auth_source": str(row["auth_source"]),
            "must_change_password": _as_bool(row["must_change_password"]),
            "created_at": str(row["created_at"]),
            "expires_at": str(row["expires_at"]),
        }

    def delete_mfa_challenge(self, challenge_token: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM mfa_challenges WHERE challenge_token = ?", (challenge_token,))
            self._connection.commit()

    def delete_mfa_challenges_for_user(self, username: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM mfa_challenges WHERE username = ?", (username,))
            self._connection.commit()

    def list_admin_users(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT username, password_hash, salt, auth_source, external_subject, display_name, roles_json, mfa_secret, mfa_enabled, created_at, must_change_password
                FROM admin_users
                ORDER BY username
                """
            ).fetchall()
        return [
            {
                "username": row["username"],
                "password_hash": row["password_hash"],
                "salt": row["salt"],
                "auth_source": row["auth_source"],
                "external_subject": row["external_subject"],
                "display_name": row["display_name"],
                "roles": _decode_roles(row["roles_json"]),
                "mfa_secret": row["mfa_secret"],
                "mfa_enabled": _as_bool(row["mfa_enabled"]),
                "created_at": row["created_at"],
                "must_change_password": _as_bool(row["must_change_password"]),
            }
            for row in rows
        ]

    def get_admin_user(self, username: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT username, password_hash, salt, auth_source, external_subject, display_name, roles_json, mfa_secret, mfa_enabled, created_at, must_change_password
                FROM admin_users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            return None
        return {
            "username": row["username"],
            "password_hash": row["password_hash"],
            "salt": row["salt"],
            "auth_source": row["auth_source"],
            "external_subject": row["external_subject"],
            "display_name": row["display_name"],
            "roles": _decode_roles(row["roles_json"]),
            "mfa_secret": row["mfa_secret"],
            "mfa_enabled": _as_bool(row["mfa_enabled"]),
            "created_at": row["created_at"],
            "must_change_password": _as_bool(row["must_change_password"]),
        }

    def get_admin_user_by_external(self, auth_source: str, external_subject: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT username, password_hash, salt, auth_source, external_subject, display_name, roles_json, mfa_secret, mfa_enabled, created_at, must_change_password
                FROM admin_users
                WHERE auth_source = ? AND external_subject = ?
                """,
                (auth_source, external_subject),
            ).fetchone()
        if row is None:
            return None
        return {
            "username": row["username"],
            "password_hash": row["password_hash"],
            "salt": row["salt"],
            "auth_source": row["auth_source"],
            "external_subject": row["external_subject"],
            "display_name": row["display_name"],
            "roles": _decode_roles(row["roles_json"]),
            "mfa_secret": row["mfa_secret"],
            "mfa_enabled": _as_bool(row["mfa_enabled"]),
            "created_at": row["created_at"],
            "must_change_password": _as_bool(row["must_change_password"]),
        }

    def save_admin_user(
        self,
        *,
        username: str,
        password_hash: str,
        salt: str,
        created_at: str,
        must_change_password: bool,
        auth_source: str = "local",
        external_subject: str | None = None,
        display_name: str | None = None,
        roles: list[str] | None = None,
    ) -> None:
        serialized_roles = json.dumps(roles or ["admin"])
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO admin_users(
                    username, password_hash, salt, auth_source, external_subject, display_name, roles_json, mfa_secret, mfa_enabled, created_at, must_change_password
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE
                SET password_hash = excluded.password_hash,
                    salt = excluded.salt,
                    auth_source = excluded.auth_source,
                    external_subject = excluded.external_subject,
                    display_name = excluded.display_name,
                    roles_json = excluded.roles_json,
                    mfa_secret = CASE
                        WHEN excluded.auth_source = 'local' THEN COALESCE(excluded.mfa_secret, admin_users.mfa_secret)
                        ELSE NULL
                    END,
                    mfa_enabled = CASE
                        WHEN excluded.auth_source = 'local' THEN admin_users.mfa_enabled
                        ELSE excluded.mfa_enabled
                    END,
                    must_change_password = excluded.must_change_password
                """,
                (
                    username,
                    password_hash,
                    salt,
                    auth_source,
                    external_subject,
                    display_name,
                    serialized_roles,
                    None,
                    0,
                    created_at,
                    int(must_change_password),
                ),
            )
            self._connection.commit()

    def set_admin_password(
        self,
        *,
        username: str,
        password_hash: str,
        salt: str,
        must_change_password: bool,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE admin_users
                SET password_hash = ?, salt = ?, must_change_password = ?
                WHERE username = ?
                """,
                (password_hash, salt, int(must_change_password), username),
            )
            self._connection.commit()

    def set_admin_mfa(
        self,
        *,
        username: str,
        secret_ciphertext: str | None,
        enabled: bool,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE admin_users
                SET mfa_secret = ?, mfa_enabled = ?
                WHERE username = ?
                """,
                (secret_ciphertext, int(enabled), username),
            )
            self._connection.commit()

    def set_admin_roles(self, *, username: str, roles: list[str]) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE admin_users
                SET roles_json = ?
                WHERE username = ?
                """,
                (json.dumps(roles), username),
            )
            self._connection.commit()

    def save_external_admin(
        self,
        *,
        username: str,
        auth_source: str,
        external_subject: str,
        display_name: str | None,
        created_at: str,
        roles: list[str] | None = None,
    ) -> None:
        self.save_admin_user(
            username=username,
            password_hash="",
            salt="",
            auth_source=auth_source,
            external_subject=external_subject,
            display_name=display_name,
            created_at=created_at,
            must_change_password=False,
            roles=roles or ["viewer"],
        )

    def create_session(
        self,
        *,
        token: str,
        username: str,
        csrf_token: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO sessions(token, username, csrf_token, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (token, username, csrf_token, created_at, expires_at, created_at),
            )
            self._connection.commit()

    def get_session(self, token: str) -> dict[str, str] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT token, username, csrf_token, created_at, expires_at, last_seen_at
                FROM sessions
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
        if row is None:
            return None
        return {
            "token": row["token"],
            "username": row["username"],
            "csrf_token": row["csrf_token"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "last_seen_at": row["last_seen_at"],
        }

    def touch_session(self, token: str, timestamp: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token = ?",
                (timestamp, token),
            )
            self._connection.commit()

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
            self._connection.commit()

    def delete_all_sessions(self, username: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM sessions WHERE username = ?", (username,))
            self._connection.commit()

    def get_login_attempt(self, scope: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT scope, failure_count, first_failure_at, locked_until, updated_at
                FROM login_attempts
                WHERE scope = ?
                """,
                (scope,),
            ).fetchone()
        if row is None:
            return None
        return {
            "scope": row["scope"],
            "failure_count": int(row["failure_count"]),
            "first_failure_at": row["first_failure_at"],
            "locked_until": row["locked_until"],
            "updated_at": row["updated_at"],
        }

    def upsert_login_attempt(
        self,
        *,
        scope: str,
        failure_count: int,
        first_failure_at: str,
        locked_until: str | None,
        updated_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO login_attempts(scope, failure_count, first_failure_at, locked_until, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(scope) DO UPDATE
                SET failure_count = excluded.failure_count,
                    first_failure_at = excluded.first_failure_at,
                    locked_until = excluded.locked_until,
                    updated_at = excluded.updated_at
                """,
                (scope, failure_count, first_failure_at, locked_until, updated_at),
            )
            self._connection.commit()

    def delete_login_attempt(self, scope: str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM login_attempts WHERE scope = ?", (scope,))
            self._connection.commit()

    def list_targets(self) -> list[ScanTarget]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM scan_targets
                ORDER BY enabled DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_target(row) for row in rows]

    def get_target(self, target_id: str) -> ScanTarget | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM scan_targets WHERE id = ?",
                (target_id,),
            ).fetchone()
        return None if row is None else self._row_to_target(row)

    def create_target(self, payload: ScanTargetCreateRequest, *, timestamp: str) -> ScanTarget:
        target_id = f"target_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO scan_targets(
                    id, kind, name, path, platform, recursive, max_depth, max_entries,
                    connection_mode, host, port, username, secret_env, key_path,
                    include_hidden, enabled, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    "filesystem",
                    payload.name,
                    payload.path,
                    payload.platform,
                    int(payload.recursive),
                    payload.max_depth,
                    payload.max_entries,
                    payload.connection_mode,
                    payload.host,
                    payload.port,
                    payload.username,
                    payload.secret_env,
                    payload.key_path,
                    int(payload.include_hidden),
                    int(payload.enabled),
                    payload.notes,
                    timestamp,
                    timestamp,
                ),
            )
            self._connection.commit()
        return self.get_target(target_id)  # type: ignore[return-value]

    def update_target(
        self,
        target_id: str,
        payload: ScanTargetUpdateRequest,
        *,
        timestamp: str,
    ) -> ScanTarget | None:
        current = self.get_target(target_id)
        if current is None:
            return None

        updated = current.model_copy(
            update={
                key: value
                for key, value in payload.model_dump(exclude_unset=True).items()
            }
        )
        with self._lock:
            self._connection.execute(
                """
                UPDATE scan_targets
                SET name = ?, path = ?, platform = ?, connection_mode = ?, host = ?, port = ?,
                    username = ?, secret_env = ?, key_path = ?, recursive = ?, max_depth = ?,
                    max_entries = ?, include_hidden = ?, enabled = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.name,
                    updated.path,
                    updated.platform,
                    updated.connection_mode,
                    updated.host,
                    updated.port,
                    updated.username,
                    updated.secret_env,
                    updated.key_path,
                    int(updated.recursive),
                    updated.max_depth,
                    updated.max_entries,
                    int(updated.include_hidden),
                    int(updated.enabled),
                    updated.notes,
                    timestamp,
                    target_id,
                ),
            )
            self._connection.commit()
        return self.get_target(target_id)

    def touch_target_status(
        self,
        target_id: str,
        *,
        status: str,
        timestamp: str,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE scan_targets
                SET last_status = ?, last_scan_at = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, timestamp, error, timestamp, target_id),
            )
            self._connection.commit()

    def save_snapshot(self, snapshot: Snapshot) -> None:
        payload = json.dumps(snapshot.model_dump(mode="json"))
        snapshot_id = f"snapshot_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO snapshots(id, generated_at, snapshot_json)
                VALUES (?, ?, ?)
                """,
                (snapshot_id, snapshot.generated_at, payload),
            )
            retained_ids = self._connection.execute(
                """
                SELECT id
                FROM snapshots
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (settings.snapshot_retention,),
            ).fetchall()
            if retained_ids:
                stale_ids = self._connection.execute(
                    """
                    SELECT id
                    FROM snapshots
                    WHERE id NOT IN (
                        SELECT id
                        FROM snapshots
                        ORDER BY generated_at DESC
                        LIMIT ?
                    )
                    """,
                    (settings.snapshot_retention,),
                ).fetchall()
                self._connection.executemany(
                    "DELETE FROM snapshots WHERE id = ?",
                    [(row["id"],) for row in stale_ids],
                )
                self._connection.execute(
                    """
                    DELETE FROM access_index
                    WHERE snapshot_generated_at NOT IN (
                        SELECT generated_at
                        FROM snapshots
                        ORDER BY generated_at DESC
                        LIMIT ?
                    )
                    """,
                    (settings.snapshot_retention,),
                )
                self._connection.execute(
                    """
                    DELETE FROM raw_snapshots
                    WHERE snapshot_generated_at NOT IN (
                        SELECT generated_at
                        FROM snapshots
                        ORDER BY generated_at DESC
                        LIMIT ?
                    )
                    """,
                    (settings.snapshot_retention,),
                )
            self._connection.commit()

    def save_raw_snapshot(
        self,
        snapshot_generated_at: str,
        source: str,
        payload: dict[str, object],
        *,
        captured_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO raw_snapshots(id, snapshot_generated_at, captured_at, source, raw_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"raw_{uuid.uuid4().hex[:12]}",
                    snapshot_generated_at,
                    captured_at,
                    source,
                    json.dumps(payload),
                ),
            )
            self._connection.commit()

    def raw_snapshot_stats(self) -> dict[str, object]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count, max(captured_at) AS latest_captured_at
                FROM raw_snapshots
                """
            ).fetchone()
        return {
            "row_count": int(row["row_count"]) if row else 0,
            "latest_captured_at": None if row is None else row["latest_captured_at"],
        }

    def save_materialized_access_index(
        self,
        snapshot_generated_at: str,
        rows: list[dict[str, object]],
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM access_index WHERE snapshot_generated_at = ?",
                (snapshot_generated_at,),
            )
            if rows:
                self._connection.executemany(
                    """
                    INSERT INTO access_index(
                        snapshot_generated_at, principal_id, resource_id, permissions_json,
                        path_count, path_complexity, access_mode, risk_score, why
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_generated_at,
                            str(row["principal_id"]),
                            str(row["resource_id"]),
                            json.dumps(row["permissions"]),
                            int(row["path_count"]),
                            int(row.get("path_complexity", 0)),
                            str(row["access_mode"]),
                            int(row["risk_score"]),
                            str(row["why"]),
                        )
                        for row in rows
                    ],
                )
            self._connection.commit()

    def has_materialized_access_index(self, snapshot_generated_at: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM access_index
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return bool(row and int(row["row_count"]) > 0)

    def materialized_access_index_stats(self, snapshot_generated_at: str) -> dict[str, int]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT
                    count(*) AS row_count,
                    count(DISTINCT principal_id) AS principal_count,
                    count(DISTINCT resource_id) AS resource_count
                FROM access_index
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return {
            "row_count": int(row["row_count"]) if row else 0,
            "principal_count": int(row["principal_count"]) if row else 0,
            "resource_count": int(row["resource_count"]) if row else 0,
        }

    def has_principal_group_closure(self, snapshot_generated_at: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM principal_group_closure
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return bool(row and int(row["row_count"]) > 0)

    def save_principal_group_closure(
        self,
        snapshot_generated_at: str,
        rows: list[dict[str, object]],
        *,
        last_verified_at: str,
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM principal_group_closure WHERE snapshot_generated_at = ?",
                (snapshot_generated_at,),
            )
            if rows:
                self._connection.executemany(
                    """
                    INSERT INTO principal_group_closure(
                        snapshot_generated_at, principal_id, group_id, depth,
                        shortest_parent_id, path_count, last_verified_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_generated_at,
                            str(row["principal_id"]),
                            str(row["group_id"]),
                            int(row["depth"]),
                            str(row["shortest_parent_id"]),
                            int(row["path_count"]),
                            last_verified_at,
                        )
                        for row in rows
                    ],
                )
            self._connection.commit()

    def list_principal_group_closure(
        self,
        snapshot_generated_at: str,
        principal_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT principal_id, group_id, depth, shortest_parent_id, path_count, last_verified_at
            FROM principal_group_closure
            WHERE snapshot_generated_at = ? AND principal_id = ?
            ORDER BY depth ASC, path_count DESC, group_id ASC
        """
        params: tuple[object, ...] = (snapshot_generated_at, principal_id)
        if limit is not None:
            query += " LIMIT ?"
            params = (snapshot_generated_at, principal_id, int(limit))
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "group_id": str(row["group_id"]),
                "depth": int(row["depth"]),
                "shortest_parent_id": str(row["shortest_parent_id"]),
                "path_count": int(row["path_count"]),
                "last_verified_at": str(row["last_verified_at"]),
            }
            for row in rows
        ]

    def list_all_principal_group_closure(self, snapshot_generated_at: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT principal_id, group_id, depth, shortest_parent_id, path_count, last_verified_at
                FROM principal_group_closure
                WHERE snapshot_generated_at = ?
                ORDER BY principal_id ASC, depth ASC, path_count DESC, group_id ASC
                """,
                (snapshot_generated_at,),
            ).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "group_id": str(row["group_id"]),
                "depth": int(row["depth"]),
                "shortest_parent_id": str(row["shortest_parent_id"]),
                "path_count": int(row["path_count"]),
                "last_verified_at": str(row["last_verified_at"]),
            }
            for row in rows
        ]

    def has_resource_hierarchy_closure(self, snapshot_generated_at: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM resource_hierarchy_closure
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return bool(row and int(row["row_count"]) > 0)

    def save_resource_hierarchy_closure(
        self,
        snapshot_generated_at: str,
        rows: list[dict[str, object]],
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM resource_hierarchy_closure WHERE snapshot_generated_at = ?",
                (snapshot_generated_at,),
            )
            if rows:
                self._connection.executemany(
                    """
                    INSERT INTO resource_hierarchy_closure(
                        snapshot_generated_at, resource_id, ancestor_resource_id, depth, inherits_acl
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_generated_at,
                            str(row["resource_id"]),
                            str(row["ancestor_resource_id"]),
                            int(row["depth"]),
                            1 if bool(row["inherits_acl"]) else 0,
                        )
                        for row in rows
                    ],
                )
            self._connection.commit()

    def list_resource_hierarchy_closure(
        self,
        snapshot_generated_at: str,
        resource_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT resource_id, ancestor_resource_id, depth, inherits_acl
            FROM resource_hierarchy_closure
            WHERE snapshot_generated_at = ? AND resource_id = ?
            ORDER BY depth ASC, ancestor_resource_id ASC
        """
        params: tuple[object, ...] = (snapshot_generated_at, resource_id)
        if limit is not None:
            query += " LIMIT ?"
            params = (snapshot_generated_at, resource_id, int(limit))
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            {
                "resource_id": str(row["resource_id"]),
                "ancestor_resource_id": str(row["ancestor_resource_id"]),
                "depth": int(row["depth"]),
                "inherits_acl": bool(row["inherits_acl"]),
            }
            for row in rows
        ]

    def list_all_resource_hierarchy_closure(self, snapshot_generated_at: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT resource_id, ancestor_resource_id, depth, inherits_acl
                FROM resource_hierarchy_closure
                WHERE snapshot_generated_at = ?
                ORDER BY resource_id ASC, depth ASC, ancestor_resource_id ASC
                """,
                (snapshot_generated_at,),
            ).fetchall()
        return [
            {
                "resource_id": str(row["resource_id"]),
                "ancestor_resource_id": str(row["ancestor_resource_id"]),
                "depth": int(row["depth"]),
                "inherits_acl": bool(row["inherits_acl"]),
            }
            for row in rows
        ]

    def has_resource_exposure_index(self, snapshot_generated_at: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM resource_exposure_index
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return bool(row and int(row["row_count"]) > 0)

    def save_resource_exposure_index(
        self,
        snapshot_generated_at: str,
        rows: list[dict[str, object]],
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM resource_exposure_index WHERE snapshot_generated_at = ?",
                (snapshot_generated_at,),
            )
            if rows:
                self._connection.executemany(
                    """
                    INSERT INTO resource_exposure_index(
                        snapshot_generated_at, resource_id, principal_count, privileged_principal_count,
                        max_risk_score, average_path_complexity, exposure_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_generated_at,
                            str(row["resource_id"]),
                            int(row["principal_count"]),
                            int(row["privileged_principal_count"]),
                            int(row["max_risk_score"]),
                            int(row["average_path_complexity"]),
                            int(row["exposure_score"]),
                        )
                        for row in rows
                    ],
                )
            self._connection.commit()

    def list_resource_exposure_index(
        self,
        snapshot_generated_at: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT resource_id, principal_count, privileged_principal_count, max_risk_score,
                   average_path_complexity, exposure_score
            FROM resource_exposure_index
            WHERE snapshot_generated_at = ?
            ORDER BY exposure_score DESC, principal_count DESC, resource_id ASC
        """
        params: tuple[object, ...] = (snapshot_generated_at,)
        if limit is not None:
            query += " LIMIT ?"
            params = (snapshot_generated_at, int(limit))
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            {
                "resource_id": str(row["resource_id"]),
                "principal_count": int(row["principal_count"]),
                "privileged_principal_count": int(row["privileged_principal_count"]),
                "max_risk_score": int(row["max_risk_score"]),
                "average_path_complexity": int(row["average_path_complexity"]),
                "exposure_score": int(row["exposure_score"]),
            }
            for row in rows
        ]

    def resource_exposure_index_stats(self, snapshot_generated_at: str) -> dict[str, int]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count, max(exposure_score) AS max_exposure_score
                FROM resource_exposure_index
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return {
            "row_count": int(row["row_count"]) if row else 0,
            "max_exposure_score": int(row["max_exposure_score"]) if row and row["max_exposure_score"] is not None else 0,
        }

    def get_resource_exposure_summary(
        self,
        snapshot_generated_at: str,
        resource_id: str,
    ) -> dict[str, int] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT principal_count, privileged_principal_count, max_risk_score,
                       average_path_complexity, exposure_score
                FROM resource_exposure_index
                WHERE snapshot_generated_at = ? AND resource_id = ?
                LIMIT 1
                """,
                (snapshot_generated_at, resource_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "principal_count": int(row["principal_count"]),
            "privileged_principal_count": int(row["privileged_principal_count"]),
            "max_risk_score": int(row["max_risk_score"]),
            "average_path_complexity": int(row["average_path_complexity"]),
            "exposure_score": int(row["exposure_score"]),
        }

    def has_principal_access_summary(self, snapshot_generated_at: str) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM principal_access_summary
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return bool(row and int(row["row_count"]) > 0)

    def save_principal_access_summary(
        self,
        snapshot_generated_at: str,
        rows: list[dict[str, object]],
    ) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM principal_access_summary WHERE snapshot_generated_at = ?",
                (snapshot_generated_at,),
            )
            if rows:
                self._connection.executemany(
                    """
                    INSERT INTO principal_access_summary(
                        snapshot_generated_at, principal_id, resource_count, privileged_resource_count,
                        max_risk_score, average_path_complexity, exposure_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot_generated_at,
                            str(row["principal_id"]),
                            int(row["resource_count"]),
                            int(row["privileged_resource_count"]),
                            int(row["max_risk_score"]),
                            int(row["average_path_complexity"]),
                            int(row["exposure_score"]),
                        )
                        for row in rows
                    ],
                )
            self._connection.commit()

    def list_principal_access_summary(
        self,
        snapshot_generated_at: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT principal_id, resource_count, privileged_resource_count, max_risk_score,
                   average_path_complexity, exposure_score
            FROM principal_access_summary
            WHERE snapshot_generated_at = ?
            ORDER BY exposure_score DESC, resource_count DESC, principal_id ASC
        """
        params: tuple[object, ...] = (snapshot_generated_at,)
        if limit is not None:
            query += " LIMIT ?"
            params = (snapshot_generated_at, int(limit))
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "resource_count": int(row["resource_count"]),
                "privileged_resource_count": int(row["privileged_resource_count"]),
                "max_risk_score": int(row["max_risk_score"]),
                "average_path_complexity": int(row["average_path_complexity"]),
                "exposure_score": int(row["exposure_score"]),
            }
            for row in rows
        ]

    def principal_access_summary_stats(self, snapshot_generated_at: str) -> dict[str, int]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count, max(exposure_score) AS max_exposure_score
                FROM principal_access_summary
                WHERE snapshot_generated_at = ?
                """,
                (snapshot_generated_at,),
            ).fetchone()
        return {
            "row_count": int(row["row_count"]) if row else 0,
            "max_exposure_score": int(row["max_exposure_score"]) if row and row["max_exposure_score"] is not None else 0,
        }

    def get_principal_access_summary(
        self,
        snapshot_generated_at: str,
        principal_id: str,
    ) -> dict[str, int] | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT resource_count, privileged_resource_count, max_risk_score,
                       average_path_complexity, exposure_score
                FROM principal_access_summary
                WHERE snapshot_generated_at = ? AND principal_id = ?
                LIMIT 1
                """,
                (snapshot_generated_at, principal_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "resource_count": int(row["resource_count"]),
            "privileged_resource_count": int(row["privileged_resource_count"]),
            "max_risk_score": int(row["max_risk_score"]),
            "average_path_complexity": int(row["average_path_complexity"]),
            "exposure_score": int(row["exposure_score"]),
        }

    def list_materialized_access_by_resource(
        self,
        snapshot_generated_at: str,
        resource_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        query = """
            SELECT principal_id, resource_id, permissions_json, path_count, path_complexity, access_mode, risk_score, why
            FROM access_index
            WHERE snapshot_generated_at = ? AND resource_id = ?
            ORDER BY risk_score DESC, principal_id ASC
        """
        params: list[object] = [snapshot_generated_at, resource_id]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([int(limit), max(0, int(offset))])
        with self._lock:
            rows = self._connection.execute(query, tuple(params)).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "resource_id": str(row["resource_id"]),
                "permissions": json.loads(str(row["permissions_json"])),
                "path_count": int(row["path_count"]),
                "path_complexity": int(row["path_complexity"]) if row["path_complexity"] is not None else 0,
                "access_mode": str(row["access_mode"]),
                "risk_score": int(row["risk_score"]),
                "why": str(row["why"]),
            }
            for row in rows
        ]

    def count_materialized_access_by_resource(
        self,
        snapshot_generated_at: str,
        resource_id: str,
    ) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM access_index
                WHERE snapshot_generated_at = ? AND resource_id = ?
                """,
                (snapshot_generated_at, resource_id),
            ).fetchone()
        return int(row["row_count"]) if row else 0

    def list_materialized_access_by_principal(
        self,
        snapshot_generated_at: str,
        principal_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        query = """
            SELECT principal_id, resource_id, permissions_json, path_count, path_complexity, access_mode, risk_score, why
            FROM access_index
            WHERE snapshot_generated_at = ? AND principal_id = ?
            ORDER BY risk_score DESC, resource_id ASC
        """
        params: list[object] = [snapshot_generated_at, principal_id]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([int(limit), max(0, int(offset))])
        with self._lock:
            rows = self._connection.execute(query, tuple(params)).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "resource_id": str(row["resource_id"]),
                "permissions": json.loads(str(row["permissions_json"])),
                "path_count": int(row["path_count"]),
                "path_complexity": int(row["path_complexity"]) if row["path_complexity"] is not None else 0,
                "access_mode": str(row["access_mode"]),
                "risk_score": int(row["risk_score"]),
                "why": str(row["why"]),
            }
            for row in rows
        ]

    def count_materialized_access_by_principal(
        self,
        snapshot_generated_at: str,
        principal_id: str,
    ) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT count(*) AS row_count
                FROM access_index
                WHERE snapshot_generated_at = ? AND principal_id = ?
                """,
                (snapshot_generated_at, principal_id),
            ).fetchone()
        return int(row["row_count"]) if row else 0

    def list_materialized_access_index(
        self,
        snapshot_generated_at: str,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        query = """
            SELECT principal_id, resource_id, permissions_json, path_count, path_complexity, access_mode, risk_score, why
            FROM access_index
            WHERE snapshot_generated_at = ?
            ORDER BY risk_score DESC, path_count DESC, principal_id ASC, resource_id ASC
        """
        params: tuple[object, ...] = (snapshot_generated_at,)
        if limit is not None:
            query += " LIMIT ?"
            params = (snapshot_generated_at, int(limit))
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [
            {
                "principal_id": str(row["principal_id"]),
                "resource_id": str(row["resource_id"]),
                "permissions": json.loads(str(row["permissions_json"])),
                "path_count": int(row["path_count"]),
                "path_complexity": int(row["path_complexity"]),
                "access_mode": str(row["access_mode"]),
                "risk_score": int(row["risk_score"]),
                "why": str(row["why"]),
            }
            for row in rows
        ]

    def create_access_review_campaign(
        self,
        payload: AccessReviewCampaignCreateRequest,
        *,
        snapshot_generated_at: str,
        created_by: str,
        timestamp: str,
        items: list[dict[str, object]],
    ) -> str:
        campaign_id = f"review_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO access_review_campaigns(
                    id, name, description, snapshot_generated_at, status, created_by,
                    created_at, updated_at, min_risk_score, privileged_only
                )
                VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    payload.name,
                    payload.description,
                    snapshot_generated_at,
                    created_by,
                    timestamp,
                    timestamp,
                    payload.min_risk_score,
                    int(payload.privileged_only),
                ),
            )
            self._connection.executemany(
                """
                INSERT INTO access_review_items(
                    id, campaign_id, principal_id, resource_id, permissions_json, path_count,
                    access_mode, risk_score, why, decision, decision_note, reviewed_at,
                    suggested_edge_id, suggested_edge_label, suggested_remediation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?, ?)
                """,
                [
                    (
                        f"review_item_{uuid.uuid4().hex[:12]}",
                        campaign_id,
                        str(item["principal_id"]),
                        str(item["resource_id"]),
                        json.dumps(item["permissions"]),
                        int(item["path_count"]),
                        str(item["access_mode"]),
                        int(item["risk_score"]),
                        str(item["why"]),
                        item.get("suggested_edge_id"),
                        item.get("suggested_edge_label"),
                        item.get("suggested_remediation"),
                    )
                    for item in items
                ],
            )
            self._connection.commit()
        return campaign_id

    def list_access_review_campaigns(self) -> list[AccessReviewCampaignSummary]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM access_review_campaigns
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
        return [self._row_to_access_review_campaign_summary(row) for row in rows]

    def get_access_review_campaign(
        self,
        campaign_id: str,
    ) -> AccessReviewCampaignDetailResponse | None:
        with self._lock:
            campaign_row = self._connection.execute(
                "SELECT * FROM access_review_campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
            if campaign_row is None:
                return None
            item_rows = self._connection.execute(
                """
                SELECT *
                FROM access_review_items
                WHERE campaign_id = ?
                ORDER BY risk_score DESC, principal_id ASC, resource_id ASC
                """,
                (campaign_id,),
            ).fetchall()
        summary = self._row_to_access_review_campaign_summary(campaign_row, item_rows=item_rows)
        return AccessReviewCampaignDetailResponse(
            summary=summary,
            items=[self._row_to_access_review_item(row) for row in item_rows],
        )

    def update_access_review_decision(
        self,
        campaign_id: str,
        item_id: str,
        payload: AccessReviewDecisionRequest,
        *,
        timestamp: str,
    ) -> AccessReviewCampaignDetailResponse | None:
        with self._lock:
            campaign_row = self._connection.execute(
                "SELECT id FROM access_review_campaigns WHERE id = ?",
                (campaign_id,),
            ).fetchone()
            if campaign_row is None:
                return None
            item_exists = self._connection.execute(
                """
                UPDATE access_review_items
                SET decision = ?, decision_note = ?, reviewed_at = ?
                WHERE campaign_id = ? AND id = ?
                """,
                (
                    payload.decision,
                    payload.decision_note,
                    timestamp if payload.decision != "pending" else None,
                    campaign_id,
                    item_id,
                ),
            ).rowcount > 0
            if not item_exists:
                return None
            item_rows = self._connection.execute(
                "SELECT decision FROM access_review_items WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchall()
            decisions = [str(row["decision"]) for row in item_rows]
            status_value = "completed" if decisions and all(decision != "pending" for decision in decisions) else "open"
            self._connection.execute(
                "UPDATE access_review_campaigns SET status = ?, updated_at = ? WHERE id = ?",
                (status_value, timestamp, campaign_id),
            )
            self._connection.commit()
        return self.get_access_review_campaign(campaign_id)

    def list_report_schedules(self) -> list[ReportScheduleSummary]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM report_schedules
                ORDER BY enabled DESC, updated_at DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_report_schedule_summary(row) for row in rows]

    def get_report_schedule(self, schedule_id: str) -> ReportScheduleDetailResponse | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM report_schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()
            if row is None:
                return None
            run_rows = self._connection.execute(
                """
                SELECT *
                FROM report_schedule_runs
                WHERE schedule_id = ?
                ORDER BY started_at DESC
                LIMIT 12
                """,
                (schedule_id,),
            ).fetchall()
        return ReportScheduleDetailResponse(
            summary=self._row_to_report_schedule_summary(row),
            config=ReportScheduleConfig.model_validate(json.loads(str(row["config_json"]))),
            delivery=ReportDeliverySettings.model_validate(json.loads(str(row["delivery_json"]))),
            recent_runs=[self._row_to_report_schedule_run(run_row) for run_row in run_rows],
        )

    def create_report_schedule(
        self,
        payload: ReportScheduleCreateRequest,
        *,
        created_by: str,
        timestamp: str,
        next_run_at: str | None,
    ) -> ReportScheduleDetailResponse:
        schedule_id = f"report_schedule_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO report_schedules(
                    id, name, description, enabled, cadence, timezone, hour, minute,
                    day_of_week, day_of_month, report_kind, config_json, delivery_json,
                    created_by, created_at, updated_at, next_run_at, last_run_at, last_status, last_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'never', NULL)
                """,
                (
                    schedule_id,
                    payload.name,
                    payload.description,
                    int(payload.enabled),
                    payload.cadence,
                    payload.timezone,
                    payload.hour,
                    payload.minute,
                    payload.day_of_week,
                    payload.day_of_month,
                    payload.config.kind,
                    json.dumps(payload.config.model_dump(mode="json")),
                    json.dumps(payload.delivery.model_dump(mode="json")),
                    created_by,
                    timestamp,
                    timestamp,
                    next_run_at,
                ),
            )
            self._connection.commit()
        return self.get_report_schedule(schedule_id)  # type: ignore[return-value]

    def update_report_schedule(
        self,
        schedule_id: str,
        payload: ReportScheduleUpdateRequest,
        *,
        timestamp: str,
        next_run_at: str | None,
    ) -> ReportScheduleDetailResponse | None:
        current = self.get_report_schedule(schedule_id)
        if current is None:
            return None
        next_name = current.summary.name if payload.name is None else payload.name
        next_description = current.summary.description if payload.description is None else payload.description
        next_enabled = current.summary.enabled if payload.enabled is None else payload.enabled
        next_cadence = current.summary.cadence if payload.cadence is None else payload.cadence
        next_timezone = current.summary.timezone if payload.timezone is None else payload.timezone
        next_hour = current.summary.hour if payload.hour is None else payload.hour
        next_minute = current.summary.minute if payload.minute is None else payload.minute
        next_day_of_week = current.summary.day_of_week if payload.day_of_week is None else payload.day_of_week
        next_day_of_month = current.summary.day_of_month if payload.day_of_month is None else payload.day_of_month
        next_config = current.config if payload.config is None else payload.config
        next_delivery = current.delivery if payload.delivery is None else payload.delivery
        with self._lock:
            self._connection.execute(
                """
                UPDATE report_schedules
                SET name = ?, description = ?, enabled = ?, cadence = ?, timezone = ?, hour = ?,
                    minute = ?, day_of_week = ?, day_of_month = ?, report_kind = ?, config_json = ?,
                    delivery_json = ?, updated_at = ?, next_run_at = ?
                WHERE id = ?
                """,
                (
                    next_name,
                    next_description,
                    int(next_enabled),
                    next_cadence,
                    next_timezone,
                    next_hour,
                    next_minute,
                    next_day_of_week,
                    next_day_of_month,
                    next_config.kind,
                    json.dumps(next_config.model_dump(mode="json")),
                    json.dumps(next_delivery.model_dump(mode="json")),
                    timestamp,
                    next_run_at,
                    schedule_id,
                ),
            )
            self._connection.commit()
        return self.get_report_schedule(schedule_id)

    def delete_report_schedule(self, schedule_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM report_schedules WHERE id = ?",
                (schedule_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def record_report_schedule_run(
        self,
        schedule_id: str,
        run: ReportScheduleRunRecord,
        *,
        next_run_at: str | None,
        last_run_at: str | None,
        last_status: str,
        last_message: str | None,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO report_schedule_runs(
                    id, schedule_id, started_at, finished_at, trigger_mode, status,
                    delivered_channels_json, artifact_paths_json, message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    schedule_id,
                    run.started_at,
                    run.finished_at,
                    run.trigger,
                    run.status,
                    json.dumps(run.delivered_channels),
                    json.dumps(run.artifact_paths),
                    run.message,
                ),
            )
            self._connection.execute(
                """
                UPDATE report_schedules
                SET next_run_at = ?, last_run_at = ?, last_status = ?, last_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_run_at,
                    last_run_at,
                    last_status,
                    last_message,
                    last_run_at or run.started_at,
                    schedule_id,
                ),
            )
            self._connection.commit()

    def list_imported_sources(self) -> list[ImportedSourceSummary]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM imported_sources
                ORDER BY enabled DESC, updated_at DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_imported_source_summary(row) for row in rows]

    def get_imported_source(self, source_id: str) -> ImportedSourceDetailResponse | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM imported_sources WHERE id = ?",
                (source_id,),
            ).fetchone()
        return None if row is None else self._row_to_imported_source_detail(row)

    def create_imported_source(
        self,
        bundle: ImportedSourceBundle,
        *,
        timestamp: str,
    ) -> ImportedSourceDetailResponse:
        source_id = f"import_{uuid.uuid4().hex[:12]}"
        payload = json.dumps(bundle.model_dump(mode="json"))
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO imported_sources(
                    id, name, source, environment, description, enabled, bundle_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    bundle.name,
                    bundle.source,
                    bundle.environment,
                    bundle.description,
                    1,
                    payload,
                    timestamp,
                    timestamp,
                ),
            )
            self._connection.commit()
        return self.get_imported_source(source_id)  # type: ignore[return-value]

    def update_imported_source(
        self,
        source_id: str,
        payload: ImportedSourceUpdateRequest,
        *,
        timestamp: str,
    ) -> ImportedSourceDetailResponse | None:
        current = self.get_imported_source(source_id)
        if current is None:
            return None

        enabled = current.summary.enabled if payload.enabled is None else payload.enabled
        with self._lock:
            self._connection.execute(
                """
                UPDATE imported_sources
                SET enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(enabled), timestamp, source_id),
            )
            self._connection.commit()
        return self.get_imported_source(source_id)

    def delete_imported_source(self, source_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM imported_sources WHERE id = ?",
                (source_id,),
            )
            self._connection.commit()
        return cursor.rowcount > 0

    def load_latest_snapshot(self) -> Snapshot | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT snapshot_json
                FROM snapshots
                ORDER BY generated_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return Snapshot.model_validate(json.loads(row["snapshot_json"]))

    def list_recent_snapshot_generated_at(self, limit: int = 5) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT generated_at
                FROM snapshots
                ORDER BY generated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [str(row["generated_at"]) for row in rows]

    def load_snapshot_by_generated_at(self, generated_at: str) -> Snapshot | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT snapshot_json
                FROM snapshots
                WHERE generated_at = ?
                LIMIT 1
                """,
                (generated_at,),
            ).fetchone()
        if row is None:
            return None
        return Snapshot.model_validate(json.loads(row["snapshot_json"]))

    def record_scan_run(
        self,
        run: ScanRunRecord,
        *,
        privileged_path_count: int,
        broad_access_count: int,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO scan_runs(
                    id, started_at, finished_at, status, duration_ms, target_ids_json,
                    resource_count, principal_count, relationship_count, warning_count,
                    privileged_path_count, broad_access_count, notes_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.started_at,
                    run.finished_at,
                    run.status,
                    run.duration_ms,
                    json.dumps(run.target_ids),
                    run.resource_count,
                    run.principal_count,
                    run.relationship_count,
                    run.warning_count,
                    privileged_path_count,
                    broad_access_count,
                    json.dumps(run.notes),
                ),
            )
            self._connection.commit()

    def record_audit_event(
        self,
        *,
        actor_username: str,
        action: str,
        status: str,
        target_type: str,
        summary: str,
        occurred_at: str,
        target_id: str | None = None,
        details: dict[str, str] | None = None,
    ) -> AuditEventRecord:
        event = AuditEventRecord(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            occurred_at=occurred_at,
            actor_username=actor_username,
            action=action,
            status=status,
            target_type=target_type,
            target_id=target_id,
            summary=summary,
            details=details or {},
        )
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO audit_events(
                    id, occurred_at, actor_username, action, status, target_type, target_id, summary, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.occurred_at,
                    event.actor_username,
                    event.action,
                    event.status,
                    event.target_type,
                    event.target_id,
                    event.summary,
                    json.dumps(event.details),
                ),
            )
            self._connection.commit()
        return event

    def list_audit_events(self, limit: int = 50) -> list[AuditEventRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM audit_events
                ORDER BY occurred_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            AuditEventRecord(
                id=str(row["id"]),
                occurred_at=str(row["occurred_at"]),
                actor_username=str(row["actor_username"]),
                action=str(row["action"]),
                status=str(row["status"]),
                target_type=str(row["target_type"]),
                target_id=None if row["target_id"] is None else str(row["target_id"]),
                summary=str(row["summary"]),
                details=json.loads(str(row["details_json"])),
            )
            for row in rows
        ]

    def list_scan_runs(self, limit: int = 10) -> list[ScanRunRecord]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM scan_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_scan_run(row) for row in rows]

    def list_scan_run_metrics(self, limit: int = 20) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT started_at, privileged_path_count, broad_access_count
                FROM scan_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "started_at": row["started_at"],
                "privileged_path_count": int(row["privileged_path_count"]),
                "broad_access_count": int(row["broad_access_count"]),
            }
            for row in rows
        ]

    def record_query_metric(
        self,
        *,
        operation: str,
        duration_ms: float,
        status_code: int,
        request_path: str,
        recorded_at: str | None = None,
    ) -> None:
        timestamp = recorded_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO query_metrics(
                    id,
                    recorded_at,
                    operation,
                    duration_ms,
                    status_code,
                    request_path
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"query_metric_{uuid.uuid4().hex[:16]}",
                    timestamp,
                    operation,
                    float(duration_ms),
                    int(status_code),
                    request_path,
                ),
            )
            self._connection.commit()

    def list_query_metrics(self, limit: int = 2000) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT recorded_at, operation, duration_ms, status_code, request_path
                FROM query_metrics
                ORDER BY recorded_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "recorded_at": str(row["recorded_at"]),
                "operation": str(row["operation"]),
                "duration_ms": float(row["duration_ms"]),
                "status_code": int(row["status_code"]),
                "request_path": str(row["request_path"]),
            }
            for row in rows
        ]

    def _row_to_target(self, row: sqlite3.Row) -> ScanTarget:
        return ScanTarget(
            id=row["id"],
            kind=row["kind"],
            name=row["name"],
            path=row["path"],
            platform=row["platform"],
            connection_mode=row["connection_mode"],
            host=row["host"],
            port=int(row["port"]),
            username=row["username"],
            secret_env=row["secret_env"],
            key_path=row["key_path"],
            recursive=_as_bool(row["recursive"]),
            max_depth=int(row["max_depth"]),
            max_entries=int(row["max_entries"]),
            include_hidden=_as_bool(row["include_hidden"]),
            enabled=_as_bool(row["enabled"]),
            notes=row["notes"],
            last_scan_at=row["last_scan_at"],
            last_status=row["last_status"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_scan_run(self, row: sqlite3.Row) -> ScanRunRecord:
        return ScanRunRecord(
            id=row["id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            duration_ms=float(row["duration_ms"]) if row["duration_ms"] is not None else None,
            target_ids=json.loads(row["target_ids_json"]),
            resource_count=int(row["resource_count"]),
            principal_count=int(row["principal_count"]),
            relationship_count=int(row["relationship_count"]),
            warning_count=int(row["warning_count"]),
            notes=json.loads(row["notes_json"]),
        )

    def _row_to_imported_source_summary(self, row: sqlite3.Row) -> ImportedSourceSummary:
        bundle = ImportedSourceBundle.model_validate(json.loads(row["bundle_json"]))
        return ImportedSourceSummary(
            id=row["id"],
            name=row["name"],
            source=row["source"],
            environment=row["environment"],
            description=row["description"],
            enabled=_as_bool(row["enabled"]),
            entity_count=len(bundle.entities),
            relationship_count=len(bundle.relationships),
            connector_count=len(bundle.connectors),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_imported_source_detail(self, row: sqlite3.Row) -> ImportedSourceDetailResponse:
        bundle = ImportedSourceBundle.model_validate(json.loads(row["bundle_json"]))
        return ImportedSourceDetailResponse(
            summary=self._row_to_imported_source_summary(row),
            bundle=bundle,
        )

    def _row_to_access_review_item(self, row) -> AccessReviewItem:
        return AccessReviewItem(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            principal_id=str(row["principal_id"]),
            resource_id=str(row["resource_id"]),
            principal={
                "id": str(row["principal_id"]),
                "name": str(row["principal_id"]),
                "kind": "user",
                "source": "runtime",
                "environment": "hybrid",
            },
            resource={
                "id": str(row["resource_id"]),
                "name": str(row["resource_id"]),
                "kind": "resource",
                "source": "runtime",
                "environment": "hybrid",
            },
            permissions=json.loads(str(row["permissions_json"])),
            path_count=int(row["path_count"]),
            access_mode=str(row["access_mode"]),
            risk_score=int(row["risk_score"]),
            why=str(row["why"]),
            decision=str(row["decision"]),
            decision_note=row["decision_note"],
            reviewed_at=row["reviewed_at"],
            suggested_edge_id=row["suggested_edge_id"],
            suggested_edge_label=row["suggested_edge_label"],
            suggested_remediation=row["suggested_remediation"],
        )

    def _row_to_access_review_campaign_summary(self, row, *, item_rows=None) -> AccessReviewCampaignSummary:
        rows = item_rows
        if rows is None:
            rows = self._connection.execute(
                """
                SELECT decision
                FROM access_review_items
                WHERE campaign_id = ?
                """,
                (row["id"],),
            ).fetchall()
        decisions = [str(item["decision"]) for item in rows]
        return AccessReviewCampaignSummary(
            id=str(row["id"]),
            name=str(row["name"]),
            description=row["description"],
            snapshot_generated_at=str(row["snapshot_generated_at"]),
            status=str(row["status"]),
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            total_items=len(decisions),
            pending_items=sum(1 for decision in decisions if decision == "pending"),
            keep_count=sum(1 for decision in decisions if decision == "keep"),
            revoke_count=sum(1 for decision in decisions if decision == "revoke"),
            follow_up_count=sum(1 for decision in decisions if decision == "needs_follow_up"),
            min_risk_score=int(row["min_risk_score"]),
            privileged_only=_as_bool(row["privileged_only"]),
        )

    def _row_to_report_schedule_summary(self, row) -> ReportScheduleSummary:
        config = ReportScheduleConfig.model_validate(json.loads(str(row["config_json"])))
        delivery = ReportDeliverySettings.model_validate(json.loads(str(row["delivery_json"])))
        channels: list[str] = []
        if delivery.email.enabled:
            channels.append("email")
        if delivery.webhook.enabled:
            channels.append("webhook")
        if delivery.archive.enabled:
            channels.append("archive")
        return ReportScheduleSummary(
            id=str(row["id"]),
            name=str(row["name"]),
            description=None if row["description"] is None else str(row["description"]),
            enabled=_as_bool(row["enabled"]),
            cadence=str(row["cadence"]),
            timezone=str(row["timezone"]),
            hour=int(row["hour"]),
            minute=int(row["minute"]),
            day_of_week=None if row["day_of_week"] is None else int(row["day_of_week"]),
            day_of_month=None if row["day_of_month"] is None else int(row["day_of_month"]),
            report_kind=config.kind,
            locale=config.locale,
            formats=list(config.formats),
            channels=channels,
            created_by=str(row["created_by"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            next_run_at=None if row["next_run_at"] is None else str(row["next_run_at"]),
            last_run_at=None if row["last_run_at"] is None else str(row["last_run_at"]),
            last_status=str(row["last_status"]),
            last_message=None if row["last_message"] is None else str(row["last_message"]),
        )

    def _row_to_report_schedule_run(self, row) -> ReportScheduleRunRecord:
        return ReportScheduleRunRecord(
            id=str(row["id"]),
            schedule_id=str(row["schedule_id"]),
            started_at=str(row["started_at"]),
            finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
            trigger=str(row["trigger_mode"]),
            status=str(row["status"]),
            delivered_channels=json.loads(str(row["delivered_channels_json"])),
            artifact_paths=json.loads(str(row["artifact_paths_json"])),
            message=None if row["message"] is None else str(row["message"]),
        )

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        if self._is_postgres:
            existing = {
                row["column_name"]
                for row in self._connection.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = ? AND table_schema = current_schema()
                    """,
                    (table,),
                ).fetchall()
            }
        else:
            existing = {
                row["name"]
                for row in self._connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
        if column in existing:
            return
        self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _ensure_schema_version_table(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    def _set_schema_version(self, version: int) -> None:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self._connection.execute(
            """
            INSERT INTO schema_version(id, version, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET version = excluded.version, updated_at = excluded.updated_at
            """,
            (version, timestamp),
        )

    def _row_to_auth_provider_summary(self, row) -> AuthProviderSummary:
        config_payload = AuthProviderConfig.model_validate(json.loads(row["config_json"]))
        return AuthProviderSummary(
            id=row["id"],
            name=row["name"],
            kind=config_payload.kind,
            preset=config_payload.preset,
            enabled=_as_bool(row["enabled"]),
            description=row["description"] or config_payload.description,
            accepts_password=config_payload.kind == "ldap",
            uses_redirect=config_payload.kind == "oidc",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_auth_provider_detail(self, row) -> AuthProviderDetailResponse:
        return AuthProviderDetailResponse(
            summary=self._row_to_auth_provider_summary(row),
            config=AuthProviderConfig.model_validate(json.loads(row["config_json"])),
        )
