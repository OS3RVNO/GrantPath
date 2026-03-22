from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from ldap3 import ALL, Connection, Server
from ldap3.utils.conv import escape_filter_chars

from app.auth import AuthService, AuthenticationError
from app.models import (
    AuthProviderConfig,
    AuthProviderCreateRequest,
    AuthProviderDetailResponse,
    AuthProviderListResponse,
    AuthProviderSummary,
    AuthProviderUpdateRequest,
    PublicAuthProviderListResponse,
    PublicAuthProviderSummary,
)
from app.storage import AppStorage


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


class FederatedAuthService:
    def __init__(self, storage: AppStorage, auth_service: AuthService) -> None:
        self.storage = storage
        self.auth_service = auth_service

    def list_providers(self) -> AuthProviderListResponse:
        return AuthProviderListResponse(
            generated_at=utc_now_iso(),
            providers=self.storage.list_auth_providers(),
        )

    def list_public_providers(self) -> PublicAuthProviderListResponse:
        providers = []
        for provider in self.storage.list_auth_providers():
            if not provider.enabled:
                continue
            providers.append(
                PublicAuthProviderSummary(
                    id=provider.id,
                    name=provider.name,
                    kind=provider.kind,
                    preset=provider.preset,
                    sign_in_label=(
                        f"Sign in with {provider.name}"
                        if provider.uses_redirect
                        else f"Use {provider.name} credentials"
                    ),
                    accepts_password=provider.accepts_password,
                    uses_redirect=provider.uses_redirect,
                    login_path=(
                        f"/api/auth/oidc/{provider.id}/login"
                        if provider.uses_redirect
                        else None
                    ),
                )
            )
        return PublicAuthProviderListResponse(generated_at=utc_now_iso(), providers=providers)

    def create_provider(self, payload: AuthProviderCreateRequest) -> AuthProviderDetailResponse:
        self._validate_provider_config(payload.config)
        return self.storage.create_auth_provider(payload, timestamp=utc_now_iso())

    def update_provider(
        self,
        provider_id: str,
        payload: AuthProviderUpdateRequest,
    ) -> AuthProviderDetailResponse | None:
        if payload.config is not None:
            self._validate_provider_config(payload.config)
        return self.storage.update_auth_provider(provider_id, payload, timestamp=utc_now_iso())

    def delete_provider(self, provider_id: str) -> bool:
        return self.storage.delete_auth_provider(provider_id)

    def password_login(self, provider_id: str, username: str, password: str) -> dict[str, object]:
        provider = self._require_provider(provider_id, expected_kind="ldap")
        profile = self._ldap_authenticate(provider.config, username, password)
        auth_source = f"ldap:{provider.summary.id}"
        return self.auth_service.login_external_identity(
            username=profile["username"],
            auth_source=auth_source,
            external_subject=profile["subject"],
            display_name=profile["display_name"],
        )

    def begin_oauth_login(self, provider_id: str, redirect_uri: str) -> str:
        provider = self._require_provider(provider_id, expected_kind="oidc")
        metadata = self._provider_metadata(provider.config)
        state = secrets.token_urlsafe(24)
        code_verifier = self._pkce_verifier() if provider.summary.preset != "github" else ""
        self.storage.create_auth_flow_state(
            state=state,
            provider_id=provider_id,
            code_verifier=code_verifier or None,
            created_at=utc_now_iso(),
            expires_at=(utc_now() + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        )
        scopes = provider.config.scopes or self._default_scopes(provider.summary.preset)
        params = {
            "client_id": provider.config.client_id or "",
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
        }
        if code_verifier:
            params["code_challenge"] = self._pkce_challenge(code_verifier)
            params["code_challenge_method"] = "S256"
        return f"{metadata['authorize_url']}?{urlencode(params)}"

    def complete_oauth_login(
        self,
        provider_id: str,
        *,
        state: str,
        code: str,
        redirect_uri: str,
    ) -> dict[str, object]:
        flow_state = self.storage.consume_auth_flow_state(state)
        if flow_state is None or flow_state["provider_id"] != provider_id:
            raise AuthenticationError("Invalid or expired OAuth state.")
        expires_at = datetime.fromisoformat(flow_state["expires_at"].replace("Z", "+00:00"))
        if expires_at <= utc_now():
            raise AuthenticationError("The OAuth state has expired. Start the sign-in flow again.")

        provider = self._require_provider(provider_id, expected_kind="oidc")
        metadata = self._provider_metadata(provider.config)
        access_token = self._exchange_oauth_code(
            provider=provider,
            metadata=metadata,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=flow_state.get("code_verifier") or None,
        )
        profile = self._fetch_oauth_profile(provider, metadata, access_token)
        auth_source = f"oidc:{provider.summary.id}"
        return self.auth_service.login_external_identity(
            username=profile["username"],
            auth_source=auth_source,
            external_subject=profile["subject"],
            display_name=profile["display_name"],
        )

    def _validate_provider_config(self, config: AuthProviderConfig) -> None:
        if config.kind == "ldap":
            if not config.ldap_server_uri or not config.ldap_base_dn:
                raise ValueError("LDAP providers require server URI and base DN.")
            return
        if not config.client_id:
            raise ValueError("OIDC providers require a client ID.")
        if config.preset not in {"github", "microsoft", "google"} and not (
            config.discovery_url or config.issuer_url
        ):
            raise ValueError("OIDC providers require a discovery URL or issuer URL.")

    def _require_provider(self, provider_id: str, *, expected_kind: str) -> AuthProviderDetailResponse:
        provider = self.storage.get_auth_provider(provider_id)
        if provider is None or not provider.summary.enabled:
            raise AuthenticationError("The selected sign-in provider is unavailable.")
        if provider.config.kind != expected_kind:
            raise AuthenticationError("The selected sign-in provider does not support this flow.")
        return provider

    def _ldap_authenticate(self, config: AuthProviderConfig, username: str, password: str) -> dict[str, str]:
        server = Server(str(config.ldap_server_uri), get_info=ALL)
        if config.ldap_bind_dn:
            bind_password = os.getenv(config.ldap_bind_password_env or "", "")
            service_connection = Connection(server, user=config.ldap_bind_dn, password=bind_password, auto_bind=True)
            search_filter = (
                config.ldap_user_search_filter
                or "(|(userPrincipalName={username})(sAMAccountName={username})(uid={username})(mail={username}))"
            )
            safe_username = escape_filter_chars(username)
            service_connection.search(
                str(config.ldap_base_dn),
                search_filter.replace("{username}", safe_username),
                attributes=["cn", "displayName", "mail", "userPrincipalName", "memberOf", "distinguishedName"],
                size_limit=5,
            )
            if not service_connection.entries:
                raise AuthenticationError("The domain account could not be found.")
            entry = service_connection.entries[0]
            memberships = []
            member_of = getattr(entry, "memberOf", None)
            if member_of:
                memberships = member_of.values if hasattr(member_of, "values") else [str(member_of)]
            if config.allowed_groups:
                allowed = {item.lower() for item in config.allowed_groups}
                if not any(str(group).lower() in allowed for group in memberships):
                    raise AuthenticationError("The domain identity is not allowed to access the platform.")
            user_dn = str(getattr(entry, "distinguishedName"))
            Connection(server, user=user_dn, password=password, auto_bind=True)
            display_name = str(getattr(entry, "displayName", None) or getattr(entry, "cn", username))
            principal_name = str(getattr(entry, "userPrincipalName", None) or getattr(entry, "mail", None) or username)
            return {
                "subject": user_dn,
                "username": principal_name,
                "display_name": display_name,
            }

        try:
            Connection(server, user=username, password=password, auto_bind=True)
        except Exception as exc:  # pragma: no cover - depends on external directory
            raise AuthenticationError("Invalid domain credentials.") from exc
        return {
            "subject": username,
            "username": username,
            "display_name": username,
        }

    def _provider_metadata(self, config: AuthProviderConfig) -> dict[str, str]:
        if config.preset == "github":
            return {
                "authorize_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "emails_url": "https://api.github.com/user/emails",
            }
        if config.preset == "microsoft" and not (config.discovery_url or config.issuer_url):
            discovery_url = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
        elif config.preset == "google" and not (config.discovery_url or config.issuer_url):
            discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
        else:
            discovery_url = config.discovery_url or self._issuer_discovery_url(config.issuer_url or "")
        response = httpx.get(discovery_url, timeout=20)
        response.raise_for_status()
        payload = response.json()
        return {
            "authorize_url": str(payload["authorization_endpoint"]),
            "token_url": str(payload["token_endpoint"]),
            "userinfo_url": str(payload["userinfo_endpoint"]),
        }

    def _exchange_oauth_code(
        self,
        *,
        provider: AuthProviderDetailResponse,
        metadata: dict[str, str],
        code: str,
        redirect_uri: str,
        code_verifier: str | None,
    ) -> str:
        client_secret = os.getenv(provider.config.client_secret_env or "", "")
        data: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.config.client_id or "",
        }
        if client_secret:
            data["client_secret"] = client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        headers = {"Accept": "application/json"}
        response = httpx.post(metadata["token_url"], data=data, headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise AuthenticationError("The OAuth provider did not return an access token.")
        return str(access_token)

    def _fetch_oauth_profile(
        self,
        provider: AuthProviderDetailResponse,
        metadata: dict[str, str],
        access_token: str,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if provider.summary.preset == "github":
            profile_response = httpx.get(metadata["userinfo_url"], headers=headers, timeout=20)
            profile_response.raise_for_status()
            profile = profile_response.json()
            emails_response = httpx.get(metadata["emails_url"], headers=headers, timeout=20)
            emails_response.raise_for_status()
            emails = emails_response.json()
            email = next(
                (
                    item.get("email")
                    for item in emails
                    if item.get("primary") and item.get("verified") and item.get("email")
                ),
                profile.get("email"),
            )
            username = str(profile.get("login") or email or profile.get("id"))
            if email:
                self._validate_external_identity(provider.config, str(email))
            return {
                "subject": str(profile.get("id") or username),
                "username": str(email or username),
                "display_name": str(profile.get("name") or username),
            }

        response = httpx.get(metadata["userinfo_url"], headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
        email_key = provider.config.email_attribute or "email"
        username_key = provider.config.username_attribute or "preferred_username"
        email = str(payload.get(email_key) or "")
        username = str(payload.get(username_key) or email or payload.get("sub") or "")
        self._validate_external_identity(provider.config, email or username)
        return {
            "subject": str(payload.get("sub") or username),
            "username": username,
            "display_name": str(payload.get("name") or payload.get("given_name") or username),
        }

    def _validate_external_identity(self, config: AuthProviderConfig, identifier: str) -> None:
        normalized = identifier.strip().lower()
        if config.allowed_emails and normalized not in {item.strip().lower() for item in config.allowed_emails}:
            raise AuthenticationError("The external identity is not allowed to access the platform.")
        if config.allowed_domains and "@" in normalized:
            domain = normalized.split("@", 1)[1]
            if domain not in {item.strip().lower() for item in config.allowed_domains}:
                raise AuthenticationError("The external identity domain is not allowed.")

    def _default_scopes(self, preset: str) -> list[str]:
        if preset == "github":
            return ["read:user", "user:email"]
        return ["openid", "profile", "email"]

    def _issuer_discovery_url(self, issuer_url: str) -> str:
        normalized = issuer_url.rstrip("/")
        return f"{normalized}/.well-known/openid-configuration"

    def _pkce_verifier(self) -> str:
        return secrets.token_urlsafe(48)

    def _pkce_challenge(self, verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
