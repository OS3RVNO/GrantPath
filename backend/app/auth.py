from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.branding import PRODUCT_DEFAULT_TENANT_NAME
from app.config import settings
from app.models import (
    AdminUserListResponse,
    AdminUserSummary,
    AppRole,
    BootstrapStatusResponse,
    MfaSetupResponse,
    MfaStatusResponse,
)
from app.storage import AppStorage


class AuthenticationError(ValueError):
    pass


class RateLimitError(ValueError):
    pass


APP_ROLE_VALUES: tuple[AppRole, ...] = (
    "viewer",
    "investigator",
    "admin",
    "connector_admin",
    "auditor",
    "executive_read_only",
)

ROLE_CAPABILITIES: dict[AppRole, set[str]] = {
    "viewer": {"read"},
    "executive_read_only": {"read"},
    "investigator": {"read", "investigate.simulate"},
    "auditor": {"read", "investigate.simulate", "governance.manage"},
    "connector_admin": {"read", "sources.manage"},
    "admin": {
        "read",
        "investigate.simulate",
        "governance.manage",
        "sources.manage",
        "admin.manage",
    },
}


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    return base64.b64encode(digest).decode("ascii")


def create_password_record(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return _hash_password(password, salt), base64.b64encode(salt).decode("ascii")


def verify_password(password: str, password_hash: str, salt_b64: str) -> bool:
    salt = base64.b64decode(salt_b64.encode("ascii"))
    return secrets.compare_digest(_hash_password(password, salt), password_hash)


def normalize_roles(
    roles: list[str] | None,
    *,
    default: list[AppRole] | None = None,
) -> list[AppRole]:
    desired = roles or default or ["viewer"]
    normalized: list[AppRole] = []
    for value in desired:
        role = str(value).strip()
        if role not in APP_ROLE_VALUES:
            continue
        typed_role = role  # type: ignore[assignment]
        if typed_role not in normalized:
            normalized.append(typed_role)
    if normalized:
        return normalized
    if default is not None:
        return list(default)
    return ["viewer"]


def expand_capabilities(roles: list[str] | None) -> list[str]:
    normalized = normalize_roles(roles)
    capabilities: set[str] = set()
    for role in normalized:
        capabilities.update(ROLE_CAPABILITIES.get(role, {"read"}))
    return sorted(capabilities)


def session_has_capability(session: dict[str, object], capability: str) -> bool:
    capabilities = {str(item) for item in session.get("capabilities", []) if str(item)}
    return capability in capabilities or "admin.manage" in capabilities


class AuthService:
    def __init__(self, storage: AppStorage, data_dir: Path) -> None:
        self.storage = storage
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.bootstrap_file = self.data_dir / "bootstrap-admin-password.txt"
        self._mfa_cipher = Fernet(
            base64.urlsafe_b64encode(hashlib.sha256(settings.app_secret_key.encode("utf-8")).digest())
        )

    def ensure_bootstrap_admin(self) -> BootstrapStatusResponse:
        existing = self.storage.list_admin_users()
        if existing:
            admin = existing[0]
            bootstrap = self.bootstrap_status()
            return bootstrap.model_copy(
                update={
                    "setup_required": False,
                    "admin_username": str(admin["username"]),
                    "must_change_password": bool(admin["must_change_password"]),
                }
            )

        username = os.getenv("EIP_ADMIN_USERNAME", "admin")
        password = os.getenv("EIP_ADMIN_PASSWORD")
        if not password:
            return BootstrapStatusResponse(
                setup_required=True,
                admin_username=username,
                must_change_password=False,
                password_generated=False,
                password_file=None,
            )

        password_hash, salt = create_password_record(password)
        self.storage.save_admin_user(
            username=username,
            password_hash=password_hash,
            salt=salt,
            created_at=utc_now_iso(),
            must_change_password=False,
            auth_source="local",
            external_subject=None,
            display_name=username,
            roles=["admin"],
        )
        bootstrap_payload = {
            "setup_required": False,
            "admin_username": username,
            "must_change_password": False,
            "password_generated": False,
            "password_file": None,
        }
        self.storage.set_setting("bootstrap_admin", json.dumps(bootstrap_payload))
        return BootstrapStatusResponse(**bootstrap_payload)

    def bootstrap_status(self, *, include_sensitive: bool = False) -> BootstrapStatusResponse:
        raw = self.storage.get_setting("bootstrap_admin")
        if raw:
            payload = BootstrapStatusResponse.model_validate_json(raw)
            return self._sanitize_bootstrap(payload, include_sensitive=include_sensitive)

        existing = self.storage.list_admin_users()
        if existing:
            admin = existing[0]
            payload = BootstrapStatusResponse(
                setup_required=False,
                admin_username=str(admin["username"]),
                must_change_password=bool(admin["must_change_password"]),
                password_generated=False,
                password_file=str(self.bootstrap_file) if self.bootstrap_file.exists() else None,
            )
            return self._sanitize_bootstrap(payload, include_sensitive=include_sensitive)

        return self._sanitize_bootstrap(
            self.ensure_bootstrap_admin(),
            include_sensitive=include_sensitive,
        )

    def setup_required(self) -> bool:
        return not bool(self.storage.list_admin_users())

    def create_initial_admin(
        self,
        *,
        username: str,
        password: str,
        tenant_name: str | None = None,
    ) -> BootstrapStatusResponse:
        if self.storage.list_admin_users():
            raise ValueError("Initial setup has already been completed.")
        password_hash, salt = create_password_record(password)
        self.storage.save_admin_user(
            username=username,
            password_hash=password_hash,
            salt=salt,
            created_at=utc_now_iso(),
            must_change_password=False,
            auth_source="local",
            external_subject=None,
            display_name=username,
            roles=["admin"],
        )
        if tenant_name:
            self.storage.set_setting("tenant_name", tenant_name)
        payload = BootstrapStatusResponse(
            setup_required=False,
            admin_username=username,
            must_change_password=False,
            password_generated=False,
            password_file=None,
        )
        self.storage.set_setting("bootstrap_admin", payload.model_dump_json())
        return payload

    def login(self, username: str, password: str, client_address: str | None = None) -> dict[str, object]:
        if self.setup_required():
            raise AuthenticationError("Initial setup required before login.")
        scopes = self._login_scopes(username, client_address)
        self._assert_login_allowed(scopes)
        admin = self.storage.get_admin_user(username)
        if admin is None:
            self._record_failed_login(scopes)
            raise AuthenticationError("Invalid administrator credentials.")
        if str(admin.get("auth_source") or "local") != "local":
            self._record_failed_login(scopes)
            raise AuthenticationError("This account uses an external sign-in provider.")
        if not verify_password(password, str(admin["password_hash"]), str(admin["salt"])):
            self._record_failed_login(scopes)
            raise AuthenticationError("Invalid administrator credentials.")
        if bool(admin.get("mfa_enabled")):
            challenge_token = self._create_mfa_challenge(
                username=str(admin["username"]),
                auth_source="local",
                must_change_password=bool(admin["must_change_password"]),
            )
            self._clear_login_attempts(scopes)
            return {
                "username": str(admin["username"]),
                "auth_source": "local",
                "must_change_password": bool(admin["must_change_password"]),
                "mfa_required": True,
                "mfa_enabled": True,
                "mfa_challenge_token": challenge_token,
            }
        session_payload = self.issue_session(
            username=username,
            must_change_password=bool(admin["must_change_password"]),
            auth_source=str(admin.get("auth_source") or "local"),
        )
        self._clear_login_attempts(scopes)
        return session_payload

    def issue_session(
        self,
        *,
        username: str,
        must_change_password: bool,
        auth_source: str,
    ) -> dict[str, object]:
        now = utc_now()
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        self.storage.create_session(
            token=token,
            username=username,
            csrf_token=csrf_token,
            created_at=now.isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(hours=settings.session_lifetime_hours)).isoformat().replace(
                "+00:00", "Z"
            ),
        )
        admin = self.storage.get_admin_user(username)
        roles = normalize_roles(admin.get("roles") if admin else None, default=["viewer"])
        return {
            "token": token,
            "csrf_token": csrf_token,
            "username": username,
            "must_change_password": must_change_password,
            "auth_source": auth_source,
            "roles": roles,
            "capabilities": expand_capabilities(roles),
            "mfa_enabled": bool(admin.get("mfa_enabled")) if admin else False,
        }

    def session(self, token: str | None) -> dict[str, object] | None:
        if not token:
            return None
        record = self.storage.get_session(token)
        if record is None:
            return None
        expires_at = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
        if expires_at <= utc_now():
            self.storage.delete_session(token)
            return None

        self.storage.touch_session(token, utc_now_iso())
        admin = self.storage.get_admin_user(str(record["username"]))
        if admin is None:
            self.storage.delete_session(token)
            return None
        return {
            "username": str(admin["username"]),
            "auth_source": str(admin.get("auth_source") or "local"),
            "roles": normalize_roles(admin.get("roles")),
            "capabilities": expand_capabilities(admin.get("roles")),
            "must_change_password": bool(admin["must_change_password"]),
            "csrf_token": str(record["csrf_token"]),
            "mfa_enabled": bool(admin.get("mfa_enabled")),
        }

    def logout(self, token: str | None) -> None:
        if token:
            self.storage.delete_session(token)

    def change_password(self, username: str, current_password: str, new_password: str) -> None:
        admin = self._require_local_admin(username)
        if not verify_password(current_password, str(admin["password_hash"]), str(admin["salt"])):
            raise ValueError("Current password is incorrect.")
        password_hash, salt = create_password_record(new_password)
        self.storage.set_admin_password(
            username=username,
            password_hash=password_hash,
            salt=salt,
            must_change_password=False,
        )
        if self.bootstrap_file.exists():
            self.bootstrap_file.unlink(missing_ok=True)
        bootstrap = self.bootstrap_status().model_copy(
            update={  # nosec B105
                "setup_required": False,
                "admin_username": username,
                "must_change_password": False,
                "password_generated": False,
                "password_file": None,
            }
        )
        self.storage.set_setting("bootstrap_admin", bootstrap.model_dump_json())
        self.storage.delete_all_sessions(username)
        self.storage.delete_mfa_challenges_for_user(username)

    def login_external_identity(
        self,
        *,
        username: str,
        auth_source: str,
        external_subject: str,
        display_name: str | None,
    ) -> dict[str, object]:
        admin = self.storage.get_admin_user_by_external(auth_source, external_subject)
        if admin is None:
            existing_username = self.storage.get_admin_user(username)
            resolved_username = username
            if existing_username is not None and str(existing_username.get("auth_source") or "local") != auth_source:
                resolved_username = f"{username} ({auth_source})"
            self.storage.save_external_admin(
                username=resolved_username,
                auth_source=auth_source,
                external_subject=external_subject,
                display_name=display_name,
                created_at=utc_now_iso(),
                roles=["viewer"],
            )
            admin = self.storage.get_admin_user_by_external(auth_source, external_subject)
        if admin is None:
            raise AuthenticationError("Unable to provision the external administrator identity.")
        return self.issue_session(
            username=str(admin["username"]),
            must_change_password=False,
            auth_source=auth_source,
        )

    def list_admin_users(self) -> AdminUserListResponse:
        users = [
            self._admin_summary(admin)
            for admin in self.storage.list_admin_users()
        ]
        return AdminUserListResponse(generated_at=utc_now_iso(), users=users)

    def update_admin_roles(self, username: str, roles: list[str]) -> AdminUserSummary:
        admin = self.storage.get_admin_user(username)
        if admin is None:
            raise ValueError(f"Unknown administrator: {username}")
        normalized_roles = normalize_roles(roles, default=[])
        if not normalized_roles:
            raise ValueError("At least one application role must remain assigned.")

        current_users = self.storage.list_admin_users()
        current_admin_usernames = {
            str(user["username"])
            for user in current_users
            if "admin" in normalize_roles(user.get("roles"))
        }
        if username in current_admin_usernames and "admin" not in normalized_roles and len(current_admin_usernames) <= 1:
            raise ValueError("At least one administrator with the admin role must remain assigned.")

        self.storage.set_admin_roles(username=username, roles=normalized_roles)
        updated = self.storage.get_admin_user(username)
        if updated is None:
            raise ValueError(f"Unknown administrator: {username}")
        return self._admin_summary(updated)

    def mfa_status(self, username: str) -> MfaStatusResponse:
        admin = self.storage.get_admin_user(username)
        if admin is None:
            raise ValueError("Administrator not found.")
        is_local = str(admin.get("auth_source") or "local") == "local"
        return MfaStatusResponse(
            available=is_local,
            enabled=bool(admin.get("mfa_enabled")) if is_local else False,
            pending_setup=self.storage.get_mfa_pending_setup(username) is not None if is_local else False,
            issuer=self._mfa_issuer(),
            provider_hint=(
                "Local application accounts use built-in TOTP. Federated providers such as Keycloak, Okta or Entra ID should enforce MFA upstream."
                if is_local
                else "This administrator uses a federated provider. Enforce MFA in the identity provider, for example in Keycloak or your OIDC platform."
            ),
        )

    def begin_mfa_setup(self, username: str) -> MfaSetupResponse:
        admin = self._require_local_admin(username)
        secret = pyotp.random_base32()
        self.storage.upsert_mfa_pending_setup(
            username=username,
            secret_ciphertext=self._encrypt_mfa_secret(secret),
            created_at=utc_now_iso(),
        )
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=str(admin["username"]), issuer_name=self._mfa_issuer())
        return MfaSetupResponse(
            issuer=self._mfa_issuer(),
            account_name=str(admin["username"]),
            manual_entry_key=secret,
            provisioning_uri=provisioning_uri,
        )

    def confirm_mfa_setup(self, username: str, code: str) -> None:
        admin = self._require_local_admin(username)
        pending = self.storage.get_mfa_pending_setup(username)
        if pending is None:
            raise ValueError("No pending MFA setup was found for this administrator.")
        secret = self._decrypt_mfa_secret(str(pending["secret_ciphertext"]))
        if not self._verify_totp(secret, code):
            raise ValueError("Invalid MFA code. Verify the authenticator clock and try again.")
        self.storage.set_admin_mfa(
            username=str(admin["username"]),
            secret_ciphertext=str(pending["secret_ciphertext"]),
            enabled=True,
        )
        self.storage.delete_mfa_pending_setup(username)
        self.storage.delete_mfa_challenges_for_user(username)

    def disable_mfa(self, username: str, current_password: str, code: str) -> None:
        admin = self._require_local_admin(username)
        if not bool(admin.get("mfa_enabled")) or not admin.get("mfa_secret"):
            raise ValueError("MFA is not enabled for this administrator.")
        if not verify_password(current_password, str(admin["password_hash"]), str(admin["salt"])):
            raise ValueError("Current password is incorrect.")
        secret = self._decrypt_mfa_secret(str(admin["mfa_secret"]))
        if not self._verify_totp(secret, code):
            raise ValueError("Invalid MFA code. Verify the authenticator clock and try again.")
        self.storage.set_admin_mfa(username=username, secret_ciphertext=None, enabled=False)
        self.storage.delete_mfa_pending_setup(username)
        self.storage.delete_all_sessions(username)
        self.storage.delete_mfa_challenges_for_user(username)

    def verify_mfa_challenge(self, challenge_token: str, code: str) -> dict[str, object]:
        challenge = self.storage.get_mfa_challenge(challenge_token)
        if challenge is None:
            raise AuthenticationError("Invalid or expired MFA challenge.")
        expires_at = datetime.fromisoformat(str(challenge["expires_at"]).replace("Z", "+00:00"))
        if expires_at <= utc_now():
            self.storage.delete_mfa_challenge(challenge_token)
            raise AuthenticationError("The MFA challenge has expired. Sign in again.")
        admin = self.storage.get_admin_user(str(challenge["username"]))
        if admin is None or not bool(admin.get("mfa_enabled")) or not admin.get("mfa_secret"):
            self.storage.delete_mfa_challenge(challenge_token)
            raise AuthenticationError("MFA is no longer available for this administrator.")
        secret = self._decrypt_mfa_secret(str(admin["mfa_secret"]))
        if not self._verify_totp(secret, code):
            raise AuthenticationError("Invalid MFA code.")
        self.storage.delete_mfa_challenge(challenge_token)
        return self.issue_session(
            username=str(challenge["username"]),
            must_change_password=bool(challenge["must_change_password"]),
            auth_source=str(challenge["auth_source"]),
        )

    def validate_csrf(self, session: dict[str, object], csrf_token: str | None) -> None:
        if not settings.enforce_csrf:
            return
        expected = str(session.get("csrf_token") or "")
        provided = csrf_token or ""
        if not expected or not provided or not secrets.compare_digest(expected, provided):
            raise AuthenticationError("CSRF validation failed.")

    def _sanitize_bootstrap(
        self,
        payload: BootstrapStatusResponse,
        *,
        include_sensitive: bool,
    ) -> BootstrapStatusResponse:
        if include_sensitive or settings.expose_bootstrap_details:
            return payload
        return payload.model_copy(update={"password_file": None})  # nosec B105

    def _login_scopes(self, username: str, client_address: str | None) -> list[str]:
        scopes = [f"user:{username.strip().lower()}"]
        if client_address:
            scopes.append(f"ip:{client_address.strip().lower()}")
        return scopes

    def _assert_login_allowed(self, scopes: list[str]) -> None:
        now = utc_now()
        for scope in scopes:
            attempt = self.storage.get_login_attempt(scope)
            if attempt is None or not attempt.get("locked_until"):
                continue
            locked_until = datetime.fromisoformat(str(attempt["locked_until"]).replace("Z", "+00:00"))
            if locked_until > now:
                raise RateLimitError("Too many login attempts. Please retry later.")
            self.storage.delete_login_attempt(scope)

    def _record_failed_login(self, scopes: list[str]) -> None:
        now = utc_now()
        now_iso = now.isoformat().replace("+00:00", "Z")
        window = timedelta(seconds=settings.login_rate_limit_window_seconds)
        for scope in scopes:
            attempt = self.storage.get_login_attempt(scope)
            if attempt is None:
                failure_count = 1
                first_failure_at_raw = now_iso
            else:
                first_failure_at_raw = str(attempt["first_failure_at"])
                first_failure_at = datetime.fromisoformat(first_failure_at_raw.replace("Z", "+00:00"))
                if now - first_failure_at > window:
                    failure_count = 1
                    first_failure_at_raw = now_iso
                else:
                    failure_count = int(attempt["failure_count"]) + 1
            locked_until = None
            if failure_count >= settings.login_max_failures:
                locked_until = (now + timedelta(seconds=settings.login_lockout_seconds)).isoformat().replace(
                    "+00:00",
                    "Z",
                )
            self.storage.upsert_login_attempt(
                scope=scope,
                failure_count=failure_count,
                first_failure_at=first_failure_at_raw,
                locked_until=locked_until,
                updated_at=now_iso,
            )

    def _clear_login_attempts(self, scopes: list[str]) -> None:
        for scope in scopes:
            self.storage.delete_login_attempt(scope)

    def _generate_bootstrap_password(self) -> str:
        return secrets.token_urlsafe(18)

    def _require_local_admin(self, username: str) -> dict[str, object]:
        admin = self.storage.get_admin_user(username)
        if admin is None:
            raise ValueError("Administrator not found.")
        if str(admin.get("auth_source") or "local") != "local":
            raise ValueError("Built-in MFA is available only for local application administrators.")
        return admin

    def _admin_summary(self, admin: dict[str, object]) -> AdminUserSummary:
        roles = normalize_roles(admin.get("roles"))
        return AdminUserSummary(
            username=str(admin["username"]),
            display_name=None if not admin.get("display_name") else str(admin["display_name"]),
            auth_source=str(admin.get("auth_source") or "local"),
            roles=roles,
            capabilities=expand_capabilities(roles),
            mfa_enabled=bool(admin.get("mfa_enabled")),
            created_at=str(admin["created_at"]),
            must_change_password=bool(admin.get("must_change_password")),
        )

    def _mfa_issuer(self) -> str:
        return self.storage.get_setting("tenant_name") or PRODUCT_DEFAULT_TENANT_NAME

    def _encrypt_mfa_secret(self, secret: str) -> str:
        return self._mfa_cipher.encrypt(secret.encode("utf-8")).decode("ascii")

    def _decrypt_mfa_secret(self, ciphertext: str) -> str:
        try:
            return self._mfa_cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise AuthenticationError("The stored MFA secret could not be decrypted.") from exc

    def _verify_totp(self, secret: str, code: str) -> bool:
        normalized = "".join(char for char in code if char.isdigit())
        if len(normalized) < 6:
            return False
        return bool(pyotp.TOTP(secret).verify(normalized, valid_window=1))

    def _create_mfa_challenge(self, *, username: str, auth_source: str, must_change_password: bool) -> str:
        challenge_token = secrets.token_urlsafe(32)
        now = utc_now()
        self.storage.delete_mfa_challenges_for_user(username)
        self.storage.create_mfa_challenge(
            challenge_token=challenge_token,
            username=username,
            auth_source=auth_source,
            must_change_password=must_change_password,
            created_at=now.isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        )
        return challenge_token
