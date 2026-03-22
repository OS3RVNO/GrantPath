from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class AppConfig:
    environment: str
    runtime_role: str
    database_url: str | None
    app_secret_key: str
    default_scan_root: str | None
    session_cookie_name: str
    session_lifetime_hours: int
    secure_cookies: bool
    cookie_samesite: str
    allowed_origins: list[str]
    trusted_hosts: list[str]
    expose_bootstrap_details: bool
    enforce_csrf: bool
    csrf_header_name: str
    login_rate_limit_window_seconds: int
    login_max_failures: int
    login_lockout_seconds: int
    snapshot_retention: int
    enable_materialized_access_index: bool
    ssh_known_hosts_path: str | None
    allow_insecure_ssh_host_keys: bool
    opensearch_url: str | None
    opensearch_index: str
    opensearch_username: str | None
    opensearch_password: str | None
    opensearch_verify_tls: bool
    clickhouse_url: str | None
    clickhouse_database: str
    clickhouse_username: str | None
    clickhouse_password: str | None
    clickhouse_verify_tls: bool
    valkey_url: str | None
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    kafka_bootstrap_servers: str | None
    temporal_address: str | None
    langfuse_base_url: str | None
    background_heartbeat_interval_seconds: int
    background_stale_after_seconds: int


_DEFAULT_SECRET_SENTINELS = {
    "",
    "change-me-in-production",
    "replace-with-a-long-random-secret",
    "replace-me",
    "changeme",
}

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "testserver"}


def _is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in _DEFAULT_SECRET_SENTINELS or normalized.startswith("replace-with-")


def _validate_config(config: AppConfig) -> AppConfig:
    if config.runtime_role not in {"all", "api", "worker"}:
        raise RuntimeError(
            "EIP_RUNTIME_ROLE must be one of: all, api, worker."
        )
    if config.environment != "production":
        return config

    errors: list[str] = []
    if not config.database_url or not config.database_url.startswith("postgres"):
        errors.append("Production requires EIP_DATABASE_URL pointing to PostgreSQL.")
    if len(config.app_secret_key) < 32 or _is_placeholder_secret(config.app_secret_key):
        errors.append("Production requires a strong non-default EIP_APP_SECRET_KEY.")
    if not config.secure_cookies:
        errors.append("Production requires EIP_SECURE_COOKIES=1.")
    if config.expose_bootstrap_details:
        errors.append("Production must keep EIP_EXPOSE_BOOTSTRAP_DETAILS disabled.")
    if config.allow_insecure_ssh_host_keys:
        errors.append("Production must not allow insecure SSH host keys.")
    if not config.default_scan_root:
        errors.append("Production requires EIP_DEFAULT_SCAN_ROOT so the scan scope is explicit.")
    if not config.allowed_origins or any(origin.startswith("http://") for origin in config.allowed_origins):
        errors.append("Production requires HTTPS-only EIP_ALLOWED_ORIGINS.")
    if not config.trusted_hosts or any(host in _LOCAL_HOSTS for host in config.trusted_hosts):
        errors.append("Production requires explicit non-localhost EIP_TRUSTED_HOSTS.")

    if errors:
        raise RuntimeError("Invalid production configuration:\n- " + "\n- ".join(errors))
    return config


def load_config() -> AppConfig:
    environment = os.getenv("EIP_ENV", "development").strip().lower() or "development"
    development_origins = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    development_hosts = ["127.0.0.1", "localhost", "testserver"]
    config = AppConfig(
        environment=environment,
        runtime_role=os.getenv("EIP_RUNTIME_ROLE", "all").strip().lower() or "all",
        database_url=os.getenv("EIP_DATABASE_URL"),
        app_secret_key=os.getenv("EIP_APP_SECRET_KEY", secrets.token_urlsafe(32)),
        default_scan_root=os.getenv("EIP_DEFAULT_SCAN_ROOT"),
        session_cookie_name=os.getenv("EIP_SESSION_COOKIE", "eip_session"),
        session_lifetime_hours=max(1, int(os.getenv("EIP_SESSION_LIFETIME_HOURS", "12"))),
        secure_cookies=_env_flag("EIP_SECURE_COOKIES", environment == "production"),
        cookie_samesite=os.getenv("EIP_COOKIE_SAMESITE", "lax").strip().lower() or "lax",
        allowed_origins=_env_list("EIP_ALLOWED_ORIGINS", development_origins),
        trusted_hosts=_env_list("EIP_TRUSTED_HOSTS", development_hosts),
        expose_bootstrap_details=_env_flag(
            "EIP_EXPOSE_BOOTSTRAP_DETAILS",
            environment != "production",
        ),
        enforce_csrf=_env_flag("EIP_ENFORCE_CSRF", True),
        csrf_header_name=os.getenv("EIP_CSRF_HEADER_NAME", "X-EIP-CSRF-Token"),
        login_rate_limit_window_seconds=max(
            60,
            int(os.getenv("EIP_LOGIN_WINDOW_SECONDS", "600")),
        ),
        login_max_failures=max(3, int(os.getenv("EIP_LOGIN_MAX_FAILURES", "5"))),
        login_lockout_seconds=max(
            60,
            int(os.getenv("EIP_LOGIN_LOCKOUT_SECONDS", "900")),
        ),
        snapshot_retention=max(1, int(os.getenv("EIP_SNAPSHOT_RETENTION", "25"))),
        enable_materialized_access_index=_env_flag("EIP_ENABLE_MATERIALIZED_ACCESS_INDEX", True),
        ssh_known_hosts_path=os.getenv("EIP_SSH_KNOWN_HOSTS"),
        allow_insecure_ssh_host_keys=_env_flag("EIP_ALLOW_INSECURE_SSH_HOST_KEYS", False),
        opensearch_url=os.getenv("EIP_OPENSEARCH_URL"),
        opensearch_index=os.getenv("EIP_OPENSEARCH_INDEX", "eip-entities"),
        opensearch_username=os.getenv("EIP_OPENSEARCH_USERNAME"),
        opensearch_password=os.getenv("EIP_OPENSEARCH_PASSWORD"),
        opensearch_verify_tls=_env_flag("EIP_OPENSEARCH_VERIFY_TLS", environment == "production"),
        clickhouse_url=os.getenv("EIP_CLICKHOUSE_URL"),
        clickhouse_database=os.getenv("EIP_CLICKHOUSE_DATABASE", "eip"),
        clickhouse_username=os.getenv("EIP_CLICKHOUSE_USERNAME"),
        clickhouse_password=os.getenv("EIP_CLICKHOUSE_PASSWORD"),
        clickhouse_verify_tls=_env_flag("EIP_CLICKHOUSE_VERIFY_TLS", environment == "production"),
        valkey_url=os.getenv("EIP_VALKEY_URL"),
        neo4j_uri=os.getenv("EIP_NEO4J_URI"),
        neo4j_username=os.getenv("EIP_NEO4J_USERNAME"),
        neo4j_password=os.getenv("EIP_NEO4J_PASSWORD"),
        kafka_bootstrap_servers=os.getenv("EIP_KAFKA_BOOTSTRAP_SERVERS"),
        temporal_address=os.getenv("EIP_TEMPORAL_ADDRESS"),
        langfuse_base_url=os.getenv("EIP_LANGFUSE_BASE_URL"),
        background_heartbeat_interval_seconds=max(
            10,
            int(os.getenv("EIP_BACKGROUND_HEARTBEAT_INTERVAL_SECONDS", "30")),
        ),
        background_stale_after_seconds=max(
            30,
            int(os.getenv("EIP_BACKGROUND_STALE_AFTER_SECONDS", "120")),
        ),
    )
    return _validate_config(config)


settings = load_config()
