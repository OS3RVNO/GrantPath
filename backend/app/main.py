from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import sys
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.benchmark import run_local_benchmark
from app.branding import PRODUCT_API_TITLE, PRODUCT_CATEGORY
from app.config import settings
from app.connector_blueprints import build_connector_blueprints
from app.auth import AuthenticationError, RateLimitError, session_has_capability
from app.models import (
    AccessReviewCampaignCreateRequest,
    AccessReviewDecisionRequest,
    AdminUserRolesUpdateRequest,
    AuthProviderCreateRequest,
    AuthProviderUpdateRequest,
    ChangePasswordRequest,
    ExplainRequest,
    ImportedSourceBundle,
    ImportedSourceUpdateRequest,
    LoginRequest,
    MfaChallengeVerifyRequest,
    MfaDisableRequest,
    MfaSetupConfirmRequest,
    ReportScheduleCreateRequest,
    ReportScheduleUpdateRequest,
    ScanTargetCreateRequest,
    ScanTargetUpdateRequest,
    SessionResponse,
    SetupLocalAdminRequest,
    WhatIfRequest,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)
from app.reporting import (
    build_report_context,
    review_campaign_report_filename,
    render_excel_report,
    render_html_report,
    render_pdf_report,
    render_review_campaign_excel_report,
    render_review_campaign_html_report,
    render_review_campaign_pdf_report,
    report_filename,
)
from app.runtime import runtime
from app.telemetry import setup_telemetry

logger = logging.getLogger(__name__)
SESSION_COOKIE = settings.session_cookie_name


def _frontend_dist_dir() -> Path | None:
    candidates: list[Path] = []
    configured = os.getenv("EIP_FRONTEND_DIST_DIR")
    if configured:
        candidates.append(Path(configured))

    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "frontend" / "dist")

    bundle_root = Path(getattr(sys, "_MEIPASS", repo_root))
    candidates.append(bundle_root / "frontend_dist")

    for candidate in candidates:
        if candidate.exists() and (candidate / "index.html").exists():
            return candidate
    return None


FRONTEND_DIST_DIR = _frontend_dist_dir()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        runtime.shutdown()


app = FastAPI(
    title=PRODUCT_API_TITLE,
    version="0.5.0",
    summary=f"Self-hosted {PRODUCT_CATEGORY.lower()} with explainable paths, review workflows and enterprise-ready setup.",
    lifespan=lifespan,
)
setup_telemetry(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    operation = _query_metric_operation(request.url.path, request.method)
    started = perf_counter() if operation else None
    response: Response | None = None
    try:
        response = await call_next(request)
    except Exception:
        if operation and started is not None:
            runtime.record_query_metric(
                operation=operation,
                duration_ms=round((perf_counter() - started) * 1000, 4),
                status_code=500,
                request_path=request.url.path,
            )
        raise

    if operation and started is not None:
        runtime.record_query_metric(
            operation=operation,
            duration_ms=round((perf_counter() - started) * 1000, 4),
            status_code=response.status_code,
            request_path=request.url.path,
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


def _session_from_request(request: Request) -> dict[str, object] | None:
    return runtime.auth.session(request.cookies.get(SESSION_COOKIE))


def _session_response_payload(session: dict[str, object] | None) -> SessionResponse:
    active_workspace = runtime.active_workspace() if session is not None else None
    authenticated = session is not None and not bool(session.get("mfa_required"))
    return SessionResponse(
        authenticated=authenticated,
        username=str(session["username"]) if session else None,
        auth_source=str(session["auth_source"]) if session else None,
        roles=[str(role) for role in (session.get("roles") or [])] if session else [],
        capabilities=[str(item) for item in (session.get("capabilities") or [])] if session else [],
        must_change_password=bool(session["must_change_password"]) if session else False,
        csrf_token=str(session["csrf_token"]) if session and session.get("csrf_token") else None,
        mfa_required=bool(session.get("mfa_required")) if session else False,
        mfa_enabled=bool(session["mfa_enabled"]) if session else False,
        mfa_challenge_token=(
            str(session["mfa_challenge_token"])
            if session and session.get("mfa_challenge_token")
            else None
        ),
        setup_required=runtime.auth.setup_required(),
        bootstrap=runtime.auth.bootstrap_status(include_sensitive=session is not None),
        active_workspace_id=active_workspace.id if active_workspace is not None else None,
        active_workspace_name=active_workspace.name if active_workspace is not None else None,
    )


def _query_metric_operation(path: str, method: str) -> str | None:
    normalized_method = method.upper()
    if normalized_method == "GET" and path == "/api/overview":
        return "overview"
    if normalized_method == "GET" and path == "/api/catalog":
        return "catalog"
    if normalized_method == "GET" and path == "/api/search":
        return "search"
    if normalized_method == "POST" and path == "/api/explain":
        return "explain"
    if normalized_method == "POST" and path in {"/api/what-if", "/api/whatif"}:
        return "what-if"
    if normalized_method == "GET" and path == "/api/risks":
        return "risk-findings"
    if normalized_method == "GET" and path == "/api/graph/subgraph":
        return "graph-subgraph"
    if normalized_method == "GET" and path.startswith("/api/users/") and path.endswith("/access"):
        return "principal-access"
    if normalized_method == "GET" and path.startswith("/api/resources/") and path.endswith("/access"):
        return "resource-access"
    if normalized_method == "GET" and path.startswith("/api/resources/") and path.endswith("/exposure"):
        return "resource-exposure"
    return None


def require_admin(request: Request) -> dict[str, object]:
    session = _session_from_request(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator authentication required.",
        )
    return session


def require_operational_admin(session: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    if bool(session.get("must_change_password")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator password rotation is required before accessing the platform.",
        )
    return session


def _require_capability(
    session: dict[str, object],
    capability: str,
    detail: str,
) -> dict[str, object]:
    if not session_has_capability(session, capability):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return session


def require_mutating_admin(
    request: Request,
    session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    try:
        runtime.auth.validate_csrf(session, request.headers.get(settings.csrf_header_name))
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return session


def require_operational_mutating_admin(
    request: Request,
    session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    session = require_mutating_admin(request, session)
    return require_operational_admin(session)


def require_simulation_admin(
    session: dict[str, object] = Depends(require_operational_admin),
) -> dict[str, object]:
    return _require_capability(
        session,
        "investigate.simulate",
        "Your application role does not allow running what-if simulations.",
    )


def require_sources_mutating_admin(
    request: Request,
    session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    session = require_operational_mutating_admin(request, session)
    return _require_capability(
        session,
        "sources.manage",
        "Your application role does not allow managing collection sources.",
    )


def require_governance_mutating_admin(
    request: Request,
    session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    session = require_operational_mutating_admin(request, session)
    return _require_capability(
        session,
        "governance.manage",
        "Your application role does not allow changing governance decisions or report schedules.",
    )


def require_admin_management(
    request: Request,
    session: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    session = require_operational_mutating_admin(request, session)
    return _require_capability(
        session,
        "admin.manage",
        "Your application role does not allow managing administrator roles.",
    )


def require_admin_role_view(
    session: dict[str, object] = Depends(require_operational_admin),
) -> dict[str, object]:
    return _require_capability(
        session,
        "admin.manage",
        "Your application role does not allow viewing administrator roles.",
    )


@app.get("/api/health")
def health() -> dict[str, str | bool | None]:
    status_payload = runtime.runtime_status()
    return {
        "status": "ok",
        "tenant": runtime.engine.snapshot.tenant,
        "generated_at": runtime.engine.snapshot.generated_at,
        "runtime_role": status_payload.runtime_role,
        "scan_in_progress": status_payload.scan_in_progress,
        "background_worker_state": status_payload.background_worker_state,
    }


@app.get("/api/setup/status")
def setup_status():
    return runtime.setup_status()


@app.post("/api/setup/local-admin")
def setup_local_admin(payload: SetupLocalAdminRequest):
    try:
        return runtime.complete_initial_setup(payload)
    except ValueError as exc:
        runtime.audit(
            actor_username=payload.username,
            action="initial_setup_completed",
            status="failed",
            target_type="setup",
            target_id=payload.username,
            summary="Initial application administrator setup failed.",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/auth/bootstrap-status")
def bootstrap_status() -> dict[str, object]:
    return runtime.auth.bootstrap_status(include_sensitive=False).model_dump()


@app.get("/api/auth/session")
def session_status(request: Request) -> SessionResponse:
    return _session_response_payload(_session_from_request(request))


@app.get("/api/workspaces")
def workspace_list(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_workspaces()


@app.post("/api/workspaces")
def create_workspace(
    payload: WorkspaceCreateRequest,
    session: dict[str, object] = Depends(require_admin_management),
):
    try:
        workspace = runtime.create_workspace(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="workspace_created",
        status="success",
        target_type="workspace",
        target_id=workspace.id,
        summary=f"Workspace {workspace.name} created.",
        details={"slug": workspace.slug, "environment": workspace.environment},
    )
    return workspace


@app.patch("/api/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdateRequest,
    session: dict[str, object] = Depends(require_admin_management),
):
    workspace = runtime.update_workspace(workspace_id, payload)
    if workspace is None:
        raise HTTPException(status_code=404, detail=f"Unknown workspace: {workspace_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="workspace_updated",
        status="success",
        target_type="workspace",
        target_id=workspace.id,
        summary=f"Workspace {workspace.name} updated.",
        details={"environment": workspace.environment},
    )
    return workspace


@app.post("/api/workspaces/{workspace_id}/activate")
def activate_workspace(
    workspace_id: str,
    session: dict[str, object] = Depends(require_admin_management),
):
    try:
        workspace = runtime.activate_workspace(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workspace: {workspace_id}") from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="workspace_activated",
        status="success",
        target_type="workspace",
        target_id=workspace.id,
        summary=f"Workspace {workspace.name} activated.",
        details={"environment": workspace.environment},
    )
    return workspace


@app.get("/api/auth/providers/public")
def public_auth_providers():
    return runtime.list_public_auth_providers()


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> SessionResponse:
    try:
        if payload.provider_id:
            session = runtime.federated_auth.password_login(
                payload.provider_id,
                payload.username,
                payload.password,
            )
        else:
            session = runtime.auth.login(
                payload.username,
                payload.password,
                client_address=request.client.host if request.client else None,
            )
    except RateLimitError as exc:
        runtime.audit(
            actor_username=payload.username,
            action="login",
            status="rate_limited",
            target_type="session",
            summary="Administrator login was rate limited.",
            details={"provider_id": payload.provider_id or "", "error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthenticationError as exc:
        runtime.audit(
            actor_username=payload.username,
            action="login",
            status="failed",
            target_type="session",
            summary="Administrator login failed.",
            details={"provider_id": payload.provider_id or "", "error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    runtime.audit(
        actor_username=str(session["username"]),
        action="login" if not session.get("mfa_required") else "mfa_challenge_issued",
        status="success",
        target_type="session" if not session.get("mfa_required") else "authentication",
        target_id=str(session["username"]),
        summary=(
            "Administrator session established."
            if not session.get("mfa_required")
            else "MFA challenge issued for the administrator sign-in."
        ),
        details={"auth_source": str(session.get("auth_source") or "local")},
    )
    if session.get("token"):
        response.set_cookie(
            key=SESSION_COOKIE,
            value=str(session["token"]),
            httponly=True,
            samesite=settings.cookie_samesite,
            secure=settings.secure_cookies,
            max_age=60 * 60 * settings.session_lifetime_hours,
        )
    return _session_response_payload(session)


@app.post("/api/auth/mfa/verify")
def verify_mfa(payload: MfaChallengeVerifyRequest, response: Response) -> SessionResponse:
    try:
        session = runtime.auth.verify_mfa_challenge(payload.challenge_token, payload.code)
    except AuthenticationError as exc:
        runtime.audit(
            actor_username="unknown",
            action="mfa_verify",
            status="failed",
            target_type="authentication",
            summary="MFA verification failed.",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    runtime.audit(
        actor_username=str(session["username"]),
        action="mfa_verify",
        status="success",
        target_type="session",
        target_id=str(session["username"]),
        summary="Administrator session established after MFA verification.",
        details={"auth_source": str(session.get("auth_source") or "local")},
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=str(session["token"]),
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.secure_cookies,
        max_age=60 * 60 * settings.session_lifetime_hours,
    )
    return _session_response_payload(session)


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    session: dict[str, object] = Depends(require_mutating_admin),
) -> dict[str, bool]:
    runtime.auth.logout(request.cookies.get(SESSION_COOKIE))
    runtime.audit(
        actor_username=str(session["username"]),
        action="logout",
        status="success",
        target_type="session",
        target_id=str(session["username"]),
        summary="Administrator session terminated.",
    )
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    session: dict[str, object] = Depends(require_mutating_admin),
) -> dict[str, bool]:
    try:
        runtime.auth.change_password(
            str(session["username"]),
            payload.current_password,
            payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    runtime.auth.logout(request.cookies.get(SESSION_COOKIE))
    runtime.audit(
        actor_username=str(session["username"]),
        action="password_changed",
        status="success",
        target_type="admin_user",
        target_id=str(session["username"]),
        summary="Administrator password was rotated successfully.",
    )
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/mfa/status")
def mfa_status(session: dict[str, object] = Depends(require_admin)):
    try:
        return runtime.auth.mfa_status(str(session["username"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/mfa/setup")
def mfa_setup(
    session: dict[str, object] = Depends(require_operational_mutating_admin),
):
    try:
        setup = runtime.auth.begin_mfa_setup(str(session["username"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="mfa_setup_started",
        status="success",
        target_type="admin_user",
        target_id=str(session["username"]),
        summary="Administrator MFA setup was initiated.",
    )
    return setup


@app.post("/api/auth/mfa/enable")
def mfa_enable(
    payload: MfaSetupConfirmRequest,
    session: dict[str, object] = Depends(require_operational_mutating_admin),
):
    try:
        runtime.auth.confirm_mfa_setup(str(session["username"]), payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="mfa_enabled",
        status="success",
        target_type="admin_user",
        target_id=str(session["username"]),
        summary="Administrator MFA was enabled.",
    )
    return {"ok": True}


@app.post("/api/auth/mfa/disable")
def mfa_disable(
    payload: MfaDisableRequest,
    request: Request,
    response: Response,
    session: dict[str, object] = Depends(require_operational_mutating_admin),
):
    try:
        runtime.auth.disable_mfa(str(session["username"]), payload.current_password, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.auth.logout(request.cookies.get(SESSION_COOKIE))
    runtime.audit(
        actor_username=str(session["username"]),
        action="mfa_disabled",
        status="success",
        target_type="admin_user",
        target_id=str(session["username"]),
        summary="Administrator MFA was disabled.",
    )
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/providers")
def auth_providers(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_auth_providers()


@app.get("/api/admin-users")
def admin_users(_: dict[str, object] = Depends(require_admin_role_view)):
    return runtime.list_admin_users()


@app.patch("/api/admin-users/{username}/roles")
def update_admin_user_roles(
    username: str,
    payload: AdminUserRolesUpdateRequest,
    session: dict[str, object] = Depends(require_admin_management),
):
    try:
        admin_user = runtime.update_admin_user_roles(username, list(payload.roles))
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail.startswith("Unknown administrator:") else 400
        runtime.audit(
            actor_username=str(session["username"]),
            action="admin_user_roles_updated",
            status="failed",
            target_type="admin_user",
            target_id=username,
            summary=f"Administrator role update failed for {username}.",
            details={"error": detail},
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="admin_user_roles_updated",
        status="success",
        target_type="admin_user",
        target_id=username,
        summary=f"Administrator roles updated for {username}.",
        details={"roles": ", ".join(admin_user.roles)},
    )
    return admin_user


@app.post("/api/auth/providers")
def create_auth_provider(
    payload: AuthProviderCreateRequest,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    try:
        provider = runtime.create_auth_provider(payload)
    except ValueError as exc:
        runtime.audit(
            actor_username=str(session["username"]),
            action="auth_provider_created",
            status="failed",
            target_type="auth_provider",
            summary=f"Auth provider creation failed for {payload.name}.",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="auth_provider_created",
        status="success",
        target_type="auth_provider",
        target_id=provider.summary.id,
        summary=f"Auth provider {provider.summary.name} created.",
        details={"kind": provider.summary.kind, "preset": provider.summary.preset},
    )
    return provider


@app.patch("/api/auth/providers/{provider_id}")
def update_auth_provider(
    provider_id: str,
    payload: AuthProviderUpdateRequest,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    try:
        provider = runtime.update_auth_provider(provider_id, payload)
    except ValueError as exc:
        runtime.audit(
            actor_username=str(session["username"]),
            action="auth_provider_updated",
            status="failed",
            target_type="auth_provider",
            target_id=provider_id,
            summary=f"Auth provider update failed for {provider_id}.",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown auth provider: {provider_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="auth_provider_updated",
        status="success",
        target_type="auth_provider",
        target_id=provider_id,
        summary=f"Auth provider {provider.summary.name} updated.",
    )
    return provider


@app.delete("/api/auth/providers/{provider_id}")
def delete_auth_provider(
    provider_id: str,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    if not runtime.delete_auth_provider(provider_id):
        raise HTTPException(status_code=404, detail=f"Unknown auth provider: {provider_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="auth_provider_deleted",
        status="success",
        target_type="auth_provider",
        target_id=provider_id,
        summary=f"Auth provider {provider_id} deleted.",
    )
    return {"ok": True}


@app.get("/api/auth/oidc/{provider_id}/login", name="oidc_login")
def oidc_login(provider_id: str, request: Request):
    redirect_uri = str(request.url_for("oidc_callback", provider_id=provider_id))
    try:
        target_url = runtime.federated_auth.begin_oauth_login(provider_id, redirect_uri)
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(target_url, status_code=302)


@app.get("/api/auth/oidc/{provider_id}/callback", name="oidc_callback")
def oidc_callback(
    provider_id: str,
    request: Request,
    response: Response,
):
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not state or not code:
        raise HTTPException(status_code=400, detail="Missing OAuth callback parameters.")
    try:
        session = runtime.federated_auth.complete_oauth_login(
            provider_id,
            state=state,
            code=code,
            redirect_uri=str(request.url_for("oidc_callback", provider_id=provider_id)),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    redirect = RedirectResponse("/", status_code=302)
    redirect.set_cookie(
        key=SESSION_COOKIE,
        value=str(session["token"]),
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.secure_cookies,
        max_age=60 * 60 * settings.session_lifetime_hours,
    )
    return redirect


@app.get("/api/runtime")
def runtime_status(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.runtime_status()


@app.get("/api/targets")
def targets(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_targets()


@app.post("/api/targets")
def create_target(
    payload: ScanTargetCreateRequest,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    target = runtime.create_target(payload)
    runtime.audit(
        actor_username=str(session["username"]),
        action="target_created",
        status="success",
        target_type="scan_target",
        target_id=target.id,
        summary=f"Monitoring target {target.name} created.",
        details={"path": target.path, "connection_mode": target.connection_mode},
    )
    return target


@app.patch("/api/targets/{target_id}")
def update_target(
    target_id: str,
    payload: ScanTargetUpdateRequest,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    target = runtime.update_target(target_id, payload)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Unknown target: {target_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="target_updated",
        status="success",
        target_type="scan_target",
        target_id=target_id,
        summary=f"Monitoring target {target.name} updated.",
        details={"path": target.path, "enabled": str(target.enabled)},
    )
    return target


@app.get("/api/scans")
def scans(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.scan_runs()


@app.post("/api/scans/run")
def run_scan(session: dict[str, object] = Depends(require_sources_mutating_admin)):
    try:
        run = runtime.run_scan()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="scan_requested",
        status="success",
        target_type="scan",
        target_id=run.id,
        summary="Full scan requested by an administrator.",
        details={"target_count": str(len(run.target_ids))},
    )
    return run


@app.post("/api/targets/{target_id}/scan")
def run_target_scan(
    target_id: str,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    try:
        run = runtime.run_scan([target_id])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="scan_requested",
        status="success",
        target_type="scan_target",
        target_id=target_id,
        summary=f"Targeted scan requested for {target_id}.",
        details={"run_id": run.id},
    )
    return run


@app.get("/api/overview")
def overview(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.overview()


@app.get("/api/catalog")
def catalog(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.catalog()


@app.get("/api/connector-blueprints")
def connector_blueprints(_: dict[str, object] = Depends(require_operational_admin)):
    return build_connector_blueprints()


@app.get("/api/connectors/runtime")
def connectors_runtime(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.connector_inventory()


@app.get("/api/connectors/support-matrix")
def connector_support_matrix(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.connector_support_matrix()


@app.get("/api/platform/posture")
def platform_posture(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.platform_posture()


@app.get("/api/jobs/center")
def jobs_center(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.job_center()


@app.get("/api/analytics/exposure")
def exposure_analytics(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.exposure_analytics()


@app.get("/api/analytics/query-performance")
def query_performance(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.query_performance()


@app.get("/api/operational-flow")
def operational_flow(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.operational_flow()


@app.get("/api/mvp/readiness")
def mvp_readiness(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.mvp_readiness()


@app.get("/api/mvp/inventory")
def mvp_inventory(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.feature_inventory()


@app.get("/api/audit/events")
def audit_events(
    limit: int = Query(50, ge=1, le=200),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return runtime.audit_events(limit)


@app.get("/api/imported-sources")
def imported_sources(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_imported_sources()


@app.get("/api/access-reviews")
def access_reviews(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_access_reviews()


@app.post("/api/access-reviews")
def create_access_review(
    payload: AccessReviewCampaignCreateRequest,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    try:
        detail = runtime.create_access_review(payload, actor_username=str(session["username"]))
    except ValueError as exc:
        runtime.audit(
            actor_username=str(session["username"]),
            action="access_review_created",
            status="failed",
            target_type="access_review",
            summary=f"Access review creation failed for {payload.name}.",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="access_review_created",
        status="success",
        target_type="access_review",
        target_id=detail.summary.id,
        summary=f"Access review campaign {detail.summary.name} created.",
        details={"item_count": str(detail.summary.total_items)},
    )
    return detail


@app.get("/api/access-reviews/{campaign_id}")
def access_review_detail(
    campaign_id: str,
    _: dict[str, object] = Depends(require_operational_admin),
):
    detail = runtime.get_access_review(campaign_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown access review campaign: {campaign_id}")
    return detail


@app.post("/api/access-reviews/{campaign_id}/items/{item_id}/decision")
def access_review_decision(
    campaign_id: str,
    item_id: str,
    payload: AccessReviewDecisionRequest,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    detail = runtime.update_access_review_decision(campaign_id, item_id, payload)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown access review campaign: {campaign_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="access_review_decision",
        status="success",
        target_type="access_review_item",
        target_id=item_id,
        summary=f"Decision {payload.decision} recorded for review item {item_id}.",
        details={"campaign_id": campaign_id},
    )
    return detail


@app.get("/api/access-reviews/{campaign_id}/items/{item_id}/remediation")
def access_review_remediation(
    campaign_id: str,
    item_id: str,
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.access_review_remediation(campaign_id, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/report-schedules")
def report_schedules(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.list_report_schedules()


@app.post("/api/report-schedules")
def create_report_schedule(
    payload: ReportScheduleCreateRequest,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    try:
        detail = runtime.create_report_schedule(payload, actor_username=str(session["username"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="report_schedule_created",
        status="success",
        target_type="report_schedule",
        target_id=detail.summary.id,
        summary=f"Scheduled report {detail.summary.name} created.",
        details={"cadence": detail.summary.cadence, "channels": ", ".join(detail.summary.channels)},
    )
    return detail


@app.get("/api/report-schedules/{schedule_id}")
def report_schedule_detail(
    schedule_id: str,
    _: dict[str, object] = Depends(require_operational_admin),
):
    detail = runtime.get_report_schedule(schedule_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown report schedule: {schedule_id}")
    return detail


@app.patch("/api/report-schedules/{schedule_id}")
def update_report_schedule(
    schedule_id: str,
    payload: ReportScheduleUpdateRequest,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    try:
        detail = runtime.update_report_schedule(schedule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown report schedule: {schedule_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="report_schedule_updated",
        status="success",
        target_type="report_schedule",
        target_id=schedule_id,
        summary=f"Scheduled report {detail.summary.name} updated.",
        details={"enabled": str(detail.summary.enabled), "next_run_at": detail.summary.next_run_at or ""},
    )
    return detail


@app.delete("/api/report-schedules/{schedule_id}")
def delete_report_schedule(
    schedule_id: str,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    deleted = runtime.delete_report_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unknown report schedule: {schedule_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="report_schedule_deleted",
        status="success",
        target_type="report_schedule",
        target_id=schedule_id,
        summary=f"Scheduled report {schedule_id} deleted.",
    )
    return {"ok": True}


@app.post("/api/report-schedules/{schedule_id}/run")
def run_report_schedule(
    schedule_id: str,
    session: dict[str, object] = Depends(require_governance_mutating_admin),
):
    try:
        detail, run = runtime.run_report_schedule(schedule_id, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime.audit(
        actor_username=str(session["username"]),
        action="report_schedule_run",
        status=run.status,
        target_type="report_schedule",
        target_id=schedule_id,
        summary=f"Scheduled report {detail.summary.name} executed manually.",
        details={"channels": ", ".join(run.delivered_channels), "message": run.message or ""},
    )
    return detail


@app.post("/api/imported-sources")
def create_imported_source(
    payload: ImportedSourceBundle,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    detail = runtime.create_imported_source(payload)
    runtime.audit(
        actor_username=str(session["username"]),
        action="imported_source_created",
        status="success",
        target_type="imported_source",
        target_id=detail.summary.id,
        summary=f"Imported source {detail.summary.name} created.",
        details={"source": detail.summary.source},
    )
    return detail


@app.patch("/api/imported-sources/{source_id}")
def update_imported_source(
    source_id: str,
    payload: ImportedSourceUpdateRequest,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    source = runtime.update_imported_source(source_id, payload)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown imported source: {source_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="imported_source_updated",
        status="success",
        target_type="imported_source",
        target_id=source_id,
        summary=f"Imported source {source.summary.name} updated.",
        details={"enabled": str(source.summary.enabled)},
    )
    return source


@app.delete("/api/imported-sources/{source_id}")
def delete_imported_source(
    source_id: str,
    session: dict[str, object] = Depends(require_sources_mutating_admin),
):
    if not runtime.delete_imported_source(source_id):
        raise HTTPException(status_code=404, detail=f"Unknown imported source: {source_id}")
    runtime.audit(
        actor_username=str(session["username"]),
        action="imported_source_deleted",
        status="success",
        target_type="imported_source",
        target_id=source_id,
        summary=f"Imported source {source_id} deleted.",
    )
    return {"ok": True}


@app.get("/api/identity-clusters")
def identity_clusters(_: dict[str, object] = Depends(require_operational_admin)):
    return runtime.engine.identity_clusters()


@app.get("/api/identity-clusters/{cluster_id}")
def identity_cluster_detail(
    cluster_id: str,
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.engine.identity_cluster_detail(cluster_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/benchmark")
def benchmark(
    mode: str = Query("real", pattern="^(real|synthetic)$"),
    scale: int = Query(1, ge=1, le=100),
    iterations: int = Query(2, ge=1, le=50),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return run_local_benchmark(mode=mode, scale=scale, iterations=iterations)


@app.get("/api/search")
def search(
    q: str = Query("", min_length=0, max_length=100),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return runtime.search(q)


@app.get("/api/resources/{resource_id}/access")
def resource_access(
    resource_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=5000),
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.get_resource_access(resource_id, limit=limit, offset=offset)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/resources/{resource_id}/exposure")
def resource_exposure(
    resource_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=5000),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return resource_access(resource_id, limit=limit, offset=offset)


@app.get("/api/principals/{principal_id}/resources")
def principal_access(
    principal_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=5000),
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.get_principal_access(principal_id, limit=limit, offset=offset)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/users/{principal_id}/access")
def user_access(
    principal_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=5000),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return principal_access(principal_id, limit=limit, offset=offset)


@app.get("/api/entities/{entity_id}")
def entity_detail(entity_id: str, _: dict[str, object] = Depends(require_operational_admin)):
    try:
        return runtime.entity_detail(entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/graph/subgraph")
def graph_subgraph(
    entity_id: str = Query(..., min_length=1),
    depth: int = Query(1, ge=1, le=4),
    max_nodes: int = Query(160, ge=20, le=800),
    max_edges: int = Query(320, ge=20, le=2000),
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.graph_subgraph(entity_id, depth, max_nodes=max_nodes, max_edges=max_edges)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/risks")
def risks(
    limit: int = Query(25, ge=1, le=100),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return runtime.risk_findings(limit)


@app.get("/api/changes")
def changes(
    limit: int = Query(20, ge=1, le=100),
    _: dict[str, object] = Depends(require_operational_admin),
):
    return runtime.recent_changes(limit)


@app.post("/api/explain")
def explain(
    payload: ExplainRequest,
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        return runtime.explain(payload.principal_id, payload.resource_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/what-if")
def what_if(
    payload: WhatIfRequest,
    _: dict[str, object] = Depends(require_simulation_admin),
):
    try:
        return runtime.what_if(payload.edge_id, payload.focus_resource_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/whatif")
def whatif_alias(
    payload: WhatIfRequest,
    _: dict[str, object] = Depends(require_simulation_admin),
):
    return what_if(payload, _)


@app.get("/api/reports/access-review.{fmt}")
def access_review_report(
    fmt: str,
    principal_id: str = Query(..., min_length=1),
    resource_id: str = Query(..., min_length=1),
    scenario_edge_id: str = Query(..., min_length=1),
    focus_resource_id: str | None = Query(default=None),
    locale: str = Query(default="en", min_length=2, max_length=5),
    _: dict[str, object] = Depends(require_operational_admin),
):
    try:
        context = build_report_context(
            runtime.engine,
            principal_id=principal_id,
            resource_id=resource_id,
            scenario_edge_id=scenario_edge_id,
            focus_resource_id=focus_resource_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if fmt == "html":
        html = render_html_report(context, locale=locale)
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'inline; filename="{report_filename(context, "html", locale=locale)}"'
            },
        )

    if fmt == "pdf":
        pdf_bytes = render_pdf_report(context, locale=locale)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{report_filename(context, "pdf", locale=locale)}"'
            },
        )

    if fmt == "xlsx":
        excel_bytes = render_excel_report(context, locale=locale)
        return StreamingResponse(
            iter([excel_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{report_filename(context, "xlsx", locale=locale)}"'
            },
        )

    raise HTTPException(status_code=400, detail="Supported formats: html, pdf, xlsx")


@app.get("/api/reports/review-campaign.{fmt}")
def review_campaign_report(
    fmt: str,
    campaign_id: str = Query(..., min_length=1),
    locale: str = Query(default="en", min_length=2, max_length=5),
    _: dict[str, object] = Depends(require_operational_admin),
):
    campaign = runtime.get_access_review(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Unknown access review campaign: {campaign_id}")

    if fmt == "html":
        html = render_review_campaign_html_report(campaign, locale=locale)
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'inline; filename="{review_campaign_report_filename(campaign, "html", locale=locale)}"'
            },
        )

    if fmt == "pdf":
        pdf_bytes = render_review_campaign_pdf_report(campaign, locale=locale)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{review_campaign_report_filename(campaign, "pdf", locale=locale)}"'
            },
        )

    if fmt == "xlsx":
        excel_bytes = render_review_campaign_excel_report(campaign, locale=locale)
        return StreamingResponse(
            iter([excel_bytes]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{review_campaign_report_filename(campaign, "xlsx", locale=locale)}"'
            },
        )

    raise HTTPException(status_code=400, detail="Supported formats: html, pdf, xlsx")


if FRONTEND_DIST_DIR is not None and (FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")),
        name="frontend-assets",
    )


@app.get("/", include_in_schema=False)
def frontend_index():
    if FRONTEND_DIST_DIR is None:
        raise HTTPException(status_code=404, detail="Frontend build assets are not available.")
    return FileResponse(FRONTEND_DIST_DIR / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Unknown API route.")
    if FRONTEND_DIST_DIR is None:
        raise HTTPException(status_code=404, detail="Frontend build assets are not available.")
    candidate = FRONTEND_DIST_DIR / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIST_DIR / "index.html")
