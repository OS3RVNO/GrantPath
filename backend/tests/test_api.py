import os
from pathlib import Path

import pyotp
from fastapi.testclient import TestClient

os.environ.setdefault("EIP_ADMIN_PASSWORD", "TestAdminPassword!2026")
os.environ.setdefault("EIP_DISABLE_AUTOSCAN", "1")
os.environ.setdefault("EIP_ENABLE_SCHEDULER", "0")
os.environ.setdefault("EIP_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data-test"))

from app.connector_blueprints import build_connector_blueprints
from app.auth import create_password_record
from app.demo_data import build_demo_snapshot
from app.engine import AccessGraphEngine
from app.integration_collectors import _parse_graph_site_ids, _validation_errors_for_connector
from app.main import app, runtime
from app.models import Entity, Relationship


client = TestClient(app)
_CONTEXT: dict[str, str] | None = None
_AUTH_HEADERS: dict[str, str] = {}


def _login(username: str = "admin", password: str = "TestAdminPassword!2026") -> dict[str, object]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()
    csrf_token = payload.get("csrf_token")
    assert csrf_token
    _AUTH_HEADERS["X-EIP-CSRF-Token"] = csrf_token
    return payload


def _ensure_local_admin(username: str, password: str, roles: list[str]) -> None:
    password_hash, salt = create_password_record(password)
    runtime.control_storage.save_admin_user(
        username=username,
        password_hash=password_hash,
        salt=salt,
        created_at="2026-03-21T00:00:00Z",
        must_change_password=False,
        auth_source="local",
        external_subject=None,
        display_name=username,
        roles=roles,
    )


def _headers() -> dict[str, str]:
    return dict(_AUTH_HEADERS)


def _seed_demo_runtime_snapshot() -> None:
    snapshot = build_demo_snapshot()
    runtime.storage.save_snapshot(snapshot)
    runtime.engine = AccessGraphEngine(snapshot)
    runtime._refresh_enterprise_indexes(snapshot)


def _ensure_materialized_indexes() -> int:
    snapshot = runtime.storage.load_latest_snapshot()
    if snapshot is None:
        return 0
    stats = runtime.storage.materialized_access_index_stats(snapshot.generated_at)
    if stats["row_count"] >= 1:
        return int(stats["row_count"])

    rows = runtime.engine.materialized_access_index()
    if rows:
        runtime.storage.save_materialized_access_index(snapshot.generated_at, rows)
        runtime.storage.save_resource_exposure_index(
            snapshot.generated_at,
            runtime.engine.resource_exposure_index_from_rows(rows),
        )
        runtime.storage.save_principal_access_summary(
            snapshot.generated_at,
            runtime.engine.principal_access_summary_index_from_rows(rows),
        )
    return len(rows)


def _context_matches_runtime(context: dict[str, str]) -> bool:
    snapshot = runtime.storage.load_latest_snapshot()
    if snapshot is None:
        return False
    entity_ids = {entity.id for entity in snapshot.entities}
    relationship_ids = {relationship.id for relationship in snapshot.relationships}
    if context.get("principal_id") not in entity_ids:
        return False
    if context.get("resource_id") not in entity_ids:
        return False
    if context.get("scenario_edge_id") not in relationship_ids:
        return False
    return _ensure_materialized_indexes() >= 1


def _live_context() -> dict[str, str]:
    global _CONTEXT
    if _CONTEXT is not None and _context_matches_runtime(_CONTEXT):
        return _CONTEXT

    _CONTEXT = None
    _login()
    scan_response = client.post("/api/scans/run", headers=_headers())
    assert scan_response.status_code == 200

    overview_response = client.get("/api/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    catalog_response = client.get("/api/catalog")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()

    principal_id = overview.get("default_principal_id")
    if not principal_id and catalog.get("principals"):
        principal_id = catalog["principals"][0]["id"]

    resource_id = overview.get("default_resource_id")
    if not resource_id and catalog.get("resources"):
        resource_id = catalog["resources"][0]["id"]

    scenario_edge_id = overview.get("default_scenario_edge_id")
    if not scenario_edge_id and catalog.get("scenarios"):
        scenario_edge_id = catalog["scenarios"][0]["edge_id"]
    if not scenario_edge_id:
        removable_relationship = next(
            (
                relationship
                for relationship in runtime.engine.relationships
                if relationship.removable
            ),
            None,
        )
        scenario_edge_id = None if removable_relationship is None else removable_relationship.id

    row_count = _ensure_materialized_indexes()
    if row_count >= 1:
        first_row = runtime.storage.list_materialized_access_index(
            runtime.engine.snapshot.generated_at,
            limit=1,
        )[0]
        principal_id = str(first_row["principal_id"])
        resource_id = str(first_row["resource_id"])

    if not principal_id or not resource_id or not scenario_edge_id or row_count < 1:
        _seed_demo_runtime_snapshot()
        overview_response = client.get("/api/overview")
        assert overview_response.status_code == 200
        overview = overview_response.json()
        catalog_response = client.get("/api/catalog")
        assert catalog_response.status_code == 200
        catalog = catalog_response.json()
        _ensure_materialized_indexes()
        first_row = runtime.storage.list_materialized_access_index(
            runtime.engine.snapshot.generated_at,
            limit=1,
        )[0]
        principal_id = str(first_row["principal_id"])
        resource_id = str(first_row["resource_id"])
        scenario_edge_id = overview.get("default_scenario_edge_id") or catalog["scenarios"][0]["edge_id"]

    assert principal_id
    assert resource_id
    assert scenario_edge_id

    _CONTEXT = {
        "principal_id": principal_id,
        "resource_id": resource_id,
        "scenario_edge_id": scenario_edge_id,
    }
    return _CONTEXT


def test_session_and_runtime_require_admin_login() -> None:
    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False
    assert session_response.json()["setup_required"] is False

    payload = _login()
    assert "admin" in payload["roles"]
    assert "admin.manage" in payload["capabilities"]
    runtime_response = client.get("/api/runtime")

    assert runtime_response.status_code == 200
    payload = runtime_response.json()
    assert payload["admin_username"] == "admin"
    assert payload["target_count"] >= 1


def test_access_endpoints_support_pagination() -> None:
    context = _live_context()
    _login()

    resource_response = client.get(
        f"/api/resources/{context['resource_id']}/exposure?limit=2&offset=1"
    )
    assert resource_response.status_code == 200
    resource_payload = resource_response.json()
    assert resource_payload["limit"] == 2
    assert resource_payload["offset"] == 1
    assert resource_payload["returned_count"] <= 2
    assert resource_payload["total_principals"] >= resource_payload["returned_count"]

    principal_response = client.get(
        f"/api/users/{context['principal_id']}/access?limit=3&offset=0"
    )
    assert principal_response.status_code == 200
    principal_payload = principal_response.json()
    assert principal_payload["limit"] == 3
    assert principal_payload["offset"] == 0
    assert principal_payload["returned_count"] <= 3
    assert principal_payload["total_resources"] >= principal_payload["returned_count"]


def test_graph_subgraph_supports_density_caps() -> None:
    context = _live_context()
    _login()

    response = client.get(
        f"/api/graph/subgraph?entity_id={context['principal_id']}&depth=2&max_nodes=40&max_edges=60"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["node_limit"] == 40
    assert payload["edge_limit"] == 60
    assert len(payload["graph"]["nodes"]) <= 40
    assert len(payload["graph"]["edges"]) <= 60


def test_rbac_restricts_mutating_operations_for_viewer_accounts() -> None:
    context = _live_context()
    _ensure_local_admin("viewer-user", "ViewerPassword!2026", ["viewer"])
    _login("viewer-user", "ViewerPassword!2026")

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["roles"] == ["viewer"]
    assert session_payload["capabilities"] == ["read"]

    overview_response = client.get("/api/overview")
    assert overview_response.status_code == 200

    what_if_response = client.post(
        "/api/what-if",
        json={"edge_id": context["scenario_edge_id"], "focus_resource_id": context["resource_id"]},
    )
    assert what_if_response.status_code == 403

    scan_response = client.post("/api/scans/run", headers=_headers())
    assert scan_response.status_code == 403


def test_admin_can_update_application_roles() -> None:
    _ensure_local_admin("analyst-user", "AnalystPassword!2026", ["viewer"])
    _login()

    list_response = client.get("/api/admin-users")
    assert list_response.status_code == 200
    assert any(item["username"] == "analyst-user" for item in list_response.json()["users"])

    update_response = client.patch(
        "/api/admin-users/analyst-user/roles",
        json={"roles": ["investigator", "viewer"]},
        headers=_headers(),
    )
    assert update_response.status_code == 200
    assert set(update_response.json()["roles"]) == {"viewer", "investigator"}


def test_workspace_management_updates_session_and_control_plane() -> None:
    session_payload = _login()
    original_workspace_id = session_payload["active_workspace_id"]
    assert original_workspace_id

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    assert list_response.json()["active_workspace_id"] == original_workspace_id

    create_response = client.post(
        "/api/workspaces",
        json={
            "name": "Pilot Workspace",
            "slug": "pilot-workspace",
            "description": "Workspace isolated for pilot validation.",
            "environment": "hybrid",
        },
        headers=_headers(),
    )
    assert create_response.status_code == 200
    workspace_payload = create_response.json()
    workspace_id = workspace_payload["id"]
    assert workspace_payload["slug"] == "pilot-workspace"

    update_response = client.patch(
        f"/api/workspaces/{workspace_id}",
        json={"name": "Pilot Workspace Updated", "environment": "cloud"},
        headers=_headers(),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Pilot Workspace Updated"
    assert update_response.json()["environment"] == "cloud"

    activate_response = client.post(
        f"/api/workspaces/{workspace_id}/activate",
        json={},
        headers=_headers(),
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["id"] == workspace_id

    switched_session = client.get("/api/auth/session")
    assert switched_session.status_code == 200
    assert switched_session.json()["active_workspace_id"] == workspace_id
    assert switched_session.json()["active_workspace_name"] == "Pilot Workspace Updated"

    restore_response = client.post(
        f"/api/workspaces/{original_workspace_id}/activate",
        json={},
        headers=_headers(),
    )
    assert restore_response.status_code == 200
    restored_session = client.get("/api/auth/session")
    assert restored_session.status_code == 200
    assert restored_session.json()["active_workspace_id"] == original_workspace_id


def test_runtime_status_exposes_pilot_operational_signals() -> None:
    _live_context()
    _login()

    runtime_response = client.get("/api/runtime")
    assert runtime_response.status_code == 200
    payload = runtime_response.json()
    assert payload["freshness_status"] in {"fresh", "stale", "empty"}
    assert payload["raw_batch_count"] >= 1
    assert payload["materialized_access_rows"] >= 1
    assert payload["latest_scan_status"] in {"healthy", "warning"}
    assert payload["last_successful_scan_at"] is not None
    assert payload["report_scheduler_enabled"] in {True, False}
    assert payload["runtime_role"] in {"all", "api", "worker"}
    assert payload["background_worker_state"] in {"local", "remote", "standby", "missing"}
    assert payload["index_refresh"]["mode"] in {"full", "delta", "carry_forward", "existing"}

    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json()["runtime_role"] == payload["runtime_role"]


def test_connector_blueprints_endpoint_exposes_official_profiles() -> None:
    _login()
    response = client.get("/api/connector-blueprints")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["blueprints"]) >= 8
    assert any(item["surface"] == "Microsoft Graph / Entra ID" for item in payload["blueprints"])
    assert any(item["id"] == "aws-iam" for item in payload["blueprints"])
    assert any(item["id"] == "google-directory" for item in payload["blueprints"])
    assert all("implementation_status" in item for item in payload["blueprints"])


def test_connector_runtime_endpoint_exposes_configuration_state() -> None:
    _login()
    response = client.get("/api/connectors/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["connectors"]) >= 8
    assert any(item["id"] == "entra-graph" for item in payload["connectors"])
    assert any(item["id"] == "aws-iam" and item["status"] == "disabled" for item in payload["connectors"])
    assert any(item["status"] in {"needs_config", "disabled", "configured"} for item in payload["connectors"])
    assert all("official_limitations" in item for item in payload["connectors"])


def test_connector_support_matrix_exposes_trust_levels() -> None:
    _live_context()
    _login()
    response = client.get("/api/connectors/support-matrix")

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary_scope"]
    entry_ids = {item["id"] for item in payload["entries"]}
    assert "native-filesystem" in entry_ids
    assert "ad-ldap" in entry_ids
    native_filesystem = next(item for item in payload["entries"] if item["id"] == "native-filesystem")
    assert native_filesystem["support_tier"] in {"supported", "pilot"}
    assert native_filesystem["validation_level"] in {"runtime_verified", "config_validated", "planned"}


def test_cloud_connector_blueprints_reflect_official_constraints() -> None:
    blueprints = {item.id: item for item in build_connector_blueprints().blueprints}

    assert "20 requests per batch" in " ".join(blueprints["entra-graph"].official_limitations)
    assert "DEPROVISIONED" in " ".join(blueprints["okta-ud"].official_limitations)
    assert "supportsAllDrives" in " ".join(blueprints["google-drive-collaboration"].official_limitations)


def test_cloud_connector_validation_catches_graph_google_and_aws_shape_errors(monkeypatch) -> None:
    monkeypatch.setenv("EIP_GRAPH_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("EIP_GRAPH_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("EIP_GRAPH_SITE_IDS", "tenant.sharepoint.com,siteCollectionId,webId;tenant.sharepoint.com,bad")
    graph_errors = _validation_errors_for_connector("entra-graph")
    assert any("semicolon-separated Graph site IDs" in error for error in graph_errors)
    assert _parse_graph_site_ids(
        "tenant.sharepoint.com,siteCollectionId,webId;tenant.sharepoint.com,otherSiteCollectionId,otherWebId"
    ) == [
        "tenant.sharepoint.com,siteCollectionId,webId",
        "tenant.sharepoint.com,otherSiteCollectionId,otherWebId",
    ]

    monkeypatch.setenv("EIP_AWS_ACCOUNT_IDS", "12345678901,222222222222")
    aws_errors = _validation_errors_for_connector("aws-iam")
    assert any("12-digit AWS account IDs" in error for error in aws_errors)

    monkeypatch.setenv("EIP_GOOGLE_CUSTOMER_ID", "tenant123")
    monkeypatch.setenv("EIP_GOOGLE_ADMIN_SUBJECT", "not-an-email")
    monkeypatch.setenv("EIP_GOOGLE_SERVICE_ACCOUNT_JSON", '{"type":"service_account"}')
    google_errors = _validation_errors_for_connector("google-directory")
    assert any("my_customer or a Google customer ID" in error for error in google_errors)
    assert any("administrator email address" in error for error in google_errors)
    assert any("client_email, private_key and token_uri" in error for error in google_errors)


def test_platform_posture_endpoint_exposes_enterprise_component_state() -> None:
    _live_context()
    response = client.get("/api/platform/posture")

    assert response.status_code == 200
    payload = response.json()
    component_ids = {item["id"] for item in payload["components"]}
    assert {
        "storage",
        "raw-snapshot-store",
        "materialized-access-index",
        "resource-exposure-index",
        "principal-access-summary",
        "opensearch",
        "valkey",
        "clickhouse",
    }.issubset(
        component_ids
    )
    materialized = next(
        item for item in payload["components"] if item["id"] == "materialized-access-index"
    )
    assert materialized["configured"] is True
    assert any("Rows:" in detail for detail in materialized["details"])


def test_query_layer_architecture_endpoints_work() -> None:
    context = _live_context()
    _login()

    principal_access = client.get(f"/api/users/{context['principal_id']}/access")
    assert principal_access.status_code == 200
    assert principal_access.json()["principal"]["id"] == context["principal_id"]
    assert "path_complexity" in principal_access.json()["records"][0]

    resource_exposure = client.get(f"/api/resources/{context['resource_id']}/exposure")
    assert resource_exposure.status_code == 200
    assert resource_exposure.json()["resource"]["id"] == context["resource_id"]
    assert "path_complexity" in resource_exposure.json()["records"][0]

    explain_response = client.post(
        "/api/explain",
        json={
            "principal_id": context["principal_id"],
            "resource_id": context["resource_id"],
        },
    )
    assert explain_response.status_code == 200
    assert explain_response.json()["path_count"] >= 1

    whatif_response = client.post(
        "/api/whatif",
        json={"edge_id": context["scenario_edge_id"], "focus_resource_id": context["resource_id"]},
    )
    assert whatif_response.status_code == 200
    assert "narrative" in whatif_response.json()
    assert whatif_response.json()["recomputed_principals"] >= whatif_response.json()["impacted_principals"]
    assert whatif_response.json()["recomputed_resources"] >= whatif_response.json()["impacted_resources"]

    risk_response = client.get("/api/risks")
    assert risk_response.status_code == 200
    assert "findings" in risk_response.json()

    changes_response = client.get("/api/changes")
    assert changes_response.status_code == 200
    assert isinstance(changes_response.json()["changes"], list)

    subgraph_response = client.get(
        "/api/graph/subgraph",
        params={"entity_id": context["principal_id"], "depth": 2},
    )
    assert subgraph_response.status_code == 200
    assert subgraph_response.json()["focus"]["id"] == context["principal_id"]

    entity_response = client.get(f"/api/entities/{context['principal_id']}")
    assert entity_response.status_code == 200
    entity_payload = entity_response.json()
    assert "group_closure" in entity_payload
    assert isinstance(entity_payload["group_closure"], list)

    resource_entity_response = client.get(f"/api/entities/{context['resource_id']}")
    assert resource_entity_response.status_code == 200
    resource_entity_payload = resource_entity_response.json()
    assert "resource_hierarchy" in resource_entity_payload
    assert isinstance(resource_entity_payload["resource_hierarchy"], list)


def test_operational_flow_and_audit_endpoints_return_coherent_state() -> None:
    _live_context()
    _login()

    flow_response = client.get("/api/operational-flow")
    assert flow_response.status_code == 200
    flow_payload = flow_response.json()
    assert "steps" in flow_payload
    assert flow_payload["completion_percent"] >= 0
    assert any(step["id"] == "materialized-index" for step in flow_payload["steps"])

    audit_response = client.get("/api/audit/events")
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert "events" in audit_payload
    assert isinstance(audit_payload["events"], list)
    assert len(audit_payload["events"]) >= 1

    mvp_response = client.get("/api/mvp/readiness")
    assert mvp_response.status_code == 200
    mvp_payload = mvp_response.json()
    assert "checklist" in mvp_payload
    assert "freshness" in mvp_payload
    assert any(item["id"] == "effective-access-index" for item in mvp_payload["checklist"])

    inventory_response = client.get("/api/mvp/inventory")
    assert inventory_response.status_code == 200
    inventory_payload = inventory_response.json()
    assert "categories" in inventory_payload
    assert inventory_payload["present_count"] >= 1
    assert any(category["id"] == "analysis-and-explainability" for category in inventory_payload["categories"])
    assert any(
        item["id"] == "explain-path"
        for category in inventory_payload["categories"]
        for item in category["items"]
    )

    jobs_response = client.get("/api/jobs/center")
    assert jobs_response.status_code == 200
    jobs_payload = jobs_response.json()
    assert jobs_payload["overall_status"] in {"healthy", "watch", "attention"}
    assert any(item["id"] == "scan-runner" for item in jobs_payload["lanes"])
    assert any(item["id"] == "report-delivery" for item in jobs_payload["lanes"])
    assert all(
        lane["execution_mode"] in {"local", "remote", "standby", "missing"}
        for lane in jobs_payload["lanes"]
    )

    analytics_response = client.get("/api/analytics/exposure")
    assert analytics_response.status_code == 200
    analytics_payload = analytics_response.json()
    assert isinstance(analytics_payload["resource_summaries"], list)
    assert isinstance(analytics_payload["principal_summaries"], list)

    query_performance_response = client.get("/api/analytics/query-performance")
    assert query_performance_response.status_code == 200
    query_performance_payload = query_performance_response.json()
    assert isinstance(query_performance_payload["metrics"], list)
    assert any(item["operation"] == "overview" for item in query_performance_payload["metrics"])


def test_access_review_governance_flow_works() -> None:
    _live_context()
    _login()

    create_response = client.post(
        "/api/access-reviews",
        headers=_headers(),
        json={
            "name": "Quarterly privileged access review",
            "description": "Target the highest-risk access paths.",
            "min_risk_score": 60,
            "privileged_only": True,
            "max_items": 8,
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["summary"]["total_items"] >= 1
    campaign_id = payload["summary"]["id"]
    item_id = payload["items"][0]["id"]

    list_response = client.get("/api/access-reviews")
    assert list_response.status_code == 200
    assert any(item["id"] == campaign_id for item in list_response.json()["campaigns"])

    detail_response = client.get(f"/api/access-reviews/{campaign_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["summary"]["id"] == campaign_id

    decision_response = client.post(
        f"/api/access-reviews/{campaign_id}/items/{item_id}/decision",
        headers=_headers(),
        json={"decision": "revoke"},
    )
    assert decision_response.status_code == 200
    assert any(item["decision"] == "revoke" for item in decision_response.json()["items"])

    remediation_response = client.get(
        f"/api/access-reviews/{campaign_id}/items/{item_id}/remediation"
    )
    assert remediation_response.status_code == 200
    remediation = remediation_response.json()
    assert "summary" in remediation
    assert isinstance(remediation["steps"], list)
    assert len(remediation["steps"]) >= 1

    html_report = client.get(
        "/api/reports/review-campaign.html",
        params={"campaign_id": campaign_id, "locale": "it"},
    )
    assert html_report.status_code == 200
    assert html_report.headers["content-type"].startswith("text/html")
    assert "report-table" in html_report.text
    assert "section-copy" in html_report.text
    assert "Campagna di revisione accessi" in html_report.text


def test_review_campaign_report_survives_stale_entities() -> None:
    _live_context()
    _login()

    create_response = client.post(
        "/api/access-reviews",
        headers=_headers(),
        json={
            "name": "Historical review resilience",
            "description": "Ensure reports still render when the current snapshot no longer contains a reviewed entity.",
            "min_risk_score": 0,
            "privileged_only": False,
            "max_items": 5,
        },
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    campaign_id = payload["summary"]["id"]
    principal_id = payload["items"][0]["principal_id"]

    removed = runtime.engine.entities.pop(principal_id, None)
    assert removed is not None
    try:
        html_report = client.get(
            "/api/reports/review-campaign.html",
            params={"campaign_id": campaign_id, "locale": "it"},
        )
        assert html_report.status_code == 200
        assert "report-table" in html_report.text
    finally:
        runtime.engine.entities[principal_id] = removed


def test_access_review_report_supports_locale_parameter() -> None:
    context = _live_context()
    _login()

    response = client.get(
        "/api/reports/access-review.html",
        params={
            "principal_id": context["principal_id"],
            "resource_id": context["resource_id"],
            "scenario_edge_id": context["scenario_edge_id"],
            "locale": "it",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Report di revisione accessi" in response.text
    assert "Perche esiste questo accesso" in response.text


def test_report_schedule_can_be_created_and_run() -> None:
    context = _live_context()
    _login()
    archive_dir = Path(os.environ["EIP_DATA_DIR"]) / "scheduled-report-tests"
    archive_dir.mkdir(parents=True, exist_ok=True)

    create_response = client.post(
        "/api/report-schedules",
        headers=_headers(),
        json={
            "name": "Daily finance access report",
            "description": "Deliver the finance explain report every morning.",
            "enabled": True,
            "cadence": "daily",
            "timezone": "Europe/Rome",
            "hour": 7,
            "minute": 30,
            "day_of_week": None,
            "day_of_month": None,
            "config": {
                "kind": "access_review",
                "locale": "it",
                "formats": ["html", "pdf"],
                "principal_id": context["principal_id"],
                "resource_id": context["resource_id"],
                "scenario_edge_id": context["scenario_edge_id"],
            },
            "delivery": {
                "archive": {
                    "enabled": True,
                    "directory": str(archive_dir),
                    "filename_prefix": "finance-daily",
                },
                "email": {
                    "enabled": False,
                    "smtp_host": None,
                    "smtp_port": 587,
                    "security": "starttls",
                    "username": None,
                    "password_env": None,
                    "from_address": None,
                    "reply_to": None,
                    "to": [],
                    "cc": [],
                    "bcc": [],
                    "subject_template": "Finance report",
                    "message_body": "Attached.",
                    "attach_formats": ["pdf"],
                    "include_html_body": True,
                },
                "webhook": {
                    "enabled": False,
                    "url": None,
                    "secret_env": None,
                    "secret_header": "X-EIP-Webhook-Secret",
                    "include_summary": True,
                },
            },
        },
    )
    assert create_response.status_code == 200
    schedule_id = create_response.json()["summary"]["id"]
    assert create_response.json()["summary"]["next_run_at"]

    list_response = client.get("/api/report-schedules")
    assert list_response.status_code == 200
    assert any(item["id"] == schedule_id for item in list_response.json()["schedules"])

    run_response = client.post(f"/api/report-schedules/{schedule_id}/run", headers=_headers())
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["summary"]["last_status"] == "success"
    assert payload["recent_runs"]
    assert "archive" in payload["recent_runs"][0]["delivered_channels"]
    assert any(path.endswith(".pdf") for path in payload["recent_runs"][0]["artifact_paths"])
    assert all(Path(path).exists() for path in payload["recent_runs"][0]["artifact_paths"])


def test_report_schedule_without_archive_does_not_persist_artifacts(monkeypatch) -> None:
    context = _live_context()
    _login()
    archive_dir = Path(os.environ["EIP_DATA_DIR"]) / "scheduled-report-no-archive"

    monkeypatch.setattr(
        runtime.report_schedule_service,
        "_send_email",
        lambda schedule, html_content, attachments, generated_at: None,
    )

    create_response = client.post(
        "/api/report-schedules",
        headers=_headers(),
        json={
            "name": "Email-only report",
            "description": "Deliver an explain report without local archive retention.",
            "enabled": True,
            "cadence": "daily",
            "timezone": "Europe/Rome",
            "hour": 7,
            "minute": 30,
            "day_of_week": None,
            "day_of_month": None,
            "config": {
                "kind": "access_review",
                "locale": "it",
                "formats": ["html", "pdf"],
                "principal_id": context["principal_id"],
                "resource_id": context["resource_id"],
                "scenario_edge_id": context["scenario_edge_id"],
            },
            "delivery": {
                "archive": {
                    "enabled": False,
                    "directory": str(archive_dir),
                    "filename_prefix": "email-only",
                },
                "email": {
                    "enabled": True,
                    "smtp_host": "smtp.example.test",
                    "smtp_port": 587,
                    "security": "starttls",
                    "username": "reporter",
                    "password_env": None,
                    "from_address": "reports@example.test",
                    "reply_to": None,
                    "to": ["security@example.test"],
                    "cc": [],
                    "bcc": [],
                    "subject_template": "Access review report",
                    "message_body": "Attached.",
                    "attach_formats": ["pdf"],
                    "include_html_body": True,
                },
                "webhook": {
                    "enabled": False,
                    "url": None,
                    "secret_env": None,
                    "secret_header": "X-EIP-Webhook-Secret",
                    "include_summary": True,
                },
            },
        },
    )
    assert create_response.status_code == 200
    schedule_id = create_response.json()["summary"]["id"]

    run_response = client.post(f"/api/report-schedules/{schedule_id}/run", headers=_headers())
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["summary"]["last_status"] == "success"
    assert payload["recent_runs"][0]["artifact_paths"] == []
    assert "email" in payload["recent_runs"][0]["delivered_channels"]
    assert "archive" not in payload["recent_runs"][0]["delivered_channels"]
    assert not archive_dir.exists()


def test_storage_schema_version_is_tracked() -> None:
    assert runtime.storage.schema_version() >= 1


def test_public_auth_providers_endpoint_and_provider_lifecycle() -> None:
    _login()
    create_response = client.post(
        "/api/auth/providers",
        headers=_headers(),
        json={
            "name": "Contoso Entra ID",
            "enabled": True,
            "config": {
                "kind": "oidc",
                "preset": "microsoft",
                "description": "External administrator login through Entra ID.",
                "issuer_url": "https://login.microsoftonline.com/common/v2.0",
                "client_id": "client-id-placeholder",
                "client_secret_env": "EIP_OIDC_CLIENT_SECRET",
                "scopes": ["openid", "profile", "email"],
                "allowed_domains": ["contoso.com"],
                "allowed_emails": [],
                "username_attribute": None,
                "email_attribute": None,
                "ldap_server_uri": None,
                "ldap_base_dn": None,
                "ldap_bind_dn": None,
                "ldap_bind_password_env": None,
                "ldap_user_search_filter": None,
                "allowed_groups": [],
                "start_tls": False,
                "discovery_url": None,
            },
        },
    )
    assert create_response.status_code == 200
    provider_id = create_response.json()["summary"]["id"]

    public_response = client.get("/api/auth/providers/public")
    assert public_response.status_code == 200
    assert any(item["id"] == provider_id for item in public_response.json()["providers"])

    toggle_response = client.patch(
        f"/api/auth/providers/{provider_id}",
        headers=_headers(),
        json={"enabled": False},
    )
    assert toggle_response.status_code == 200
    assert toggle_response.json()["summary"]["enabled"] is False

    delete_response = client.delete(f"/api/auth/providers/{provider_id}", headers=_headers())
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True


def test_local_mfa_flow_requires_second_factor() -> None:
    _login()

    status_response = client.get("/api/auth/mfa/status")
    assert status_response.status_code == 200
    assert status_response.json()["available"] is True

    setup_response = client.post("/api/auth/mfa/setup", headers=_headers())
    assert setup_response.status_code == 200
    setup_payload = setup_response.json()
    secret = setup_payload["manual_entry_key"]

    enable_response = client.post(
        "/api/auth/mfa/enable",
        headers=_headers(),
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert enable_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "TestAdminPassword!2026"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["authenticated"] is False
    assert login_payload["mfa_required"] is True
    assert login_payload["mfa_challenge_token"]

    verify_response = client.post(
        "/api/auth/mfa/verify",
        json={
            "challenge_token": login_payload["mfa_challenge_token"],
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert verify_response.status_code == 200
    verify_payload = verify_response.json()
    assert verify_payload["authenticated"] is True
    assert verify_payload["mfa_enabled"] is True
    _AUTH_HEADERS["X-EIP-CSRF-Token"] = verify_payload["csrf_token"]

    disable_response = client.post(
        "/api/auth/mfa/disable",
        headers=_headers(),
        json={
            "current_password": "TestAdminPassword!2026",
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert disable_response.status_code == 200

    _login()


def test_identity_cluster_endpoints_return_valid_payloads() -> None:
    _login()
    response = client.get("/api/identity-clusters")

    assert response.status_code == 200
    payload = response.json()
    assert "total_clusters" in payload
    assert isinstance(payload["clusters"], list)

    if payload["clusters"]:
        detail = client.get(f"/api/identity-clusters/{payload['clusters'][0]['id']}")
        assert detail.status_code == 200
        assert "members" in detail.json()


def test_imported_source_lifecycle_and_runtime_merge() -> None:
    _login()
    create_response = client.post(
        "/api/imported-sources",
        headers=_headers(),
        json={
            "name": "Offline Entra Export",
            "source": "JSON import",
            "environment": "cloud",
            "description": "Imported without external credentials.",
            "entities": [
                {
                    "id": "alice_cloud",
                    "name": "alice.wong@contoso.com",
                    "kind": "user",
                    "source": "Microsoft Graph",
                    "environment": "cloud",
                    "description": "Cloud identity for Alice Wong.",
                    "criticality": 2,
                    "risk_score": 35,
                    "tags": ["graph", "entra", "user"],
                },
                {
                    "id": "payroll_export",
                    "name": "Payroll Export Folder",
                    "kind": "resource",
                    "source": "Microsoft Graph",
                    "environment": "cloud",
                    "description": "Imported resource from offline bundle.",
                    "criticality": 3,
                    "risk_score": 41,
                    "tags": ["graph", "resource"],
                }
            ],
            "relationships": [
                {
                    "id": "alice_cloud_acl",
                    "kind": "direct_acl",
                    "source": "alice_cloud",
                    "target": "payroll_export",
                    "label": "Read on Payroll Folder",
                    "rationale": "Imported permission from offline bundle.",
                    "permissions": ["Read"],
                    "inherits": False,
                    "temporary": False,
                    "expires_at": None,
                    "removable": True,
                    "metadata": {},
                }
            ],
            "connectors": [],
            "insights": [],
        },
    )

    assert create_response.status_code == 200
    source_id = create_response.json()["summary"]["id"]

    list_response = client.get("/api/imported-sources")
    assert list_response.status_code == 200
    assert any(item["id"] == source_id for item in list_response.json()["sources"])

    clusters_response = client.get("/api/identity-clusters")
    assert clusters_response.status_code == 200
    assert isinstance(clusters_response.json()["clusters"], list)

    disable_response = client.patch(
        f"/api/imported-sources/{source_id}",
        headers=_headers(),
        json={"enabled": False},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["summary"]["enabled"] is False

    delete_response = client.delete(f"/api/imported-sources/{source_id}", headers=_headers())
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True


def test_target_api_accepts_remote_ssh_configuration() -> None:
    _login()
    response = client.post(
        "/api/targets",
        headers=_headers(),
        json={
            "name": "Remote Linux share",
            "path": "/srv/data",
            "platform": "linux",
            "connection_mode": "ssh",
            "host": "server01.internal",
            "port": 22,
            "username": "scanner",
            "secret_env": "EIP_SSH_REMOTE_PASSWORD",
            "key_path": "/home/scanner/.ssh/id_ed25519",
            "recursive": True,
            "max_depth": 1,
            "max_entries": 50,
            "include_hidden": False,
            "enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["connection_mode"] == "ssh"
    assert payload["host"] == "server01.internal"
    assert payload["username"] == "scanner"


def test_benchmark_endpoint_returns_real_latency_metrics() -> None:
    _live_context()
    response = client.get("/api/benchmark?mode=real&iterations=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["mode"] == "real"
    assert payload["snapshot"]["target_count"] >= 1
    assert len(payload["metrics"]) >= 3
    assert all(metric["average_ms"] >= 0 for metric in payload["metrics"])


def test_html_report_download_works() -> None:
    params = _live_context()
    response = client.get("/api/reports/access-review.html", params=params)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "GrantPath Access Intelligence Report" in response.text


def test_pdf_and_excel_report_downloads_work() -> None:
    params = _live_context()

    pdf_response = client.get("/api/reports/access-review.pdf", params=params)
    xlsx_response = client.get("/api/reports/access-review.xlsx", params=params)

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert len(pdf_response.content) > 1000

    assert xlsx_response.status_code == 200
    assert (
        xlsx_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(xlsx_response.content) > 1000


def test_mutating_routes_require_csrf() -> None:
    _login()
    response = client.post(
        "/api/targets",
        json={
            "name": "No CSRF target",
            "path": "C:\\\\",
            "platform": "windows",
            "connection_mode": "local",
            "port": 22,
            "recursive": True,
            "max_depth": 1,
            "max_entries": 50,
            "include_hidden": False,
            "enabled": True,
        },
    )

    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_changes_endpoint_surfaces_access_drift_between_snapshots() -> None:
    context = _live_context()
    _login()

    latest_snapshot = runtime.storage.load_latest_snapshot()
    assert latest_snapshot is not None
    principal = next(entity for entity in latest_snapshot.entities if entity.id == context["principal_id"])
    generated_at = "2026-12-31T23:59:59Z"
    drift_resource = Entity(
        id="drift_resource_finance_archive",
        name="Finance Archive",
        kind="resource",
        source=principal.source,
        environment=principal.environment,
        description="Synthetic resource used to validate snapshot drift reporting.",
        criticality=4,
        risk_score=66,
        tags=["drift-test", "filesystem"],
    )
    drift_relationship = Relationship(
        id="drift_relationship_finance_archive",
        kind="direct_acl",
        source=principal.id,
        target=drift_resource.id,
        label="Read",
        rationale="Synthetic entitlement added to validate historical drift detection.",
        permissions=["Read"],
        removable=True,
    )
    drift_snapshot = latest_snapshot.model_copy(
        update={
            "generated_at": generated_at,
            "entities": [*latest_snapshot.entities, drift_resource],
            "relationships": [*latest_snapshot.relationships, drift_relationship],
        }
    )
    runtime.storage.save_snapshot(drift_snapshot)

    response = client.get("/api/changes")
    assert response.status_code == 200
    payload = response.json()
    drift_records = [item for item in payload["changes"] if item["change_type"] == "access_drift_detected"]
    assert drift_records
    assert drift_records[0]["added_access_count"] >= 1
