"""Environment configuration for the MCP service.

Kept separate from ``app.core.config.Settings`` on purpose: the MCP service has
its own secrets (signing key, CSRF secret) and must not need the API's
``OPENAI_API_KEY`` or SMTP settings to start. It still imports
``app.core.config`` indirectly for ``DATABASE_URL``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Tuple
from urllib.parse import urlparse

AuthMode = Literal["builtin", "external"]

# Redirect URIs ChatGPT uses (developers.openai.com/apps-sdk/build/auth).
DEFAULT_ALLOWED_REDIRECT_PREFIXES: Tuple[str, ...] = (
    "https://chatgpt.com/connector/oauth/",
    "https://chatgpt.com/connector_platform_oauth_redirect",
)

PRODUCTION_ENVIRONMENTS = {"production", "prod"}


class McpConfigError(ValueError):
    """Raised when the MCP service is misconfigured; startup must fail."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise McpConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise McpConfigError(f"{name} must be positive")
    return value


def _multiline_env(name: str) -> str:
    """PEM values pasted into Railway often arrive with literal ``\\n``."""
    value = os.environ.get(name, "")
    if "\\n" in value and "\n" not in value:
        value = value.replace("\\n", "\n")
    return value.strip()


@dataclass(frozen=True)
class McpSettings:
    environment: str
    public_url: str
    auth_mode: AuthMode
    # Built-in authorization server
    private_key_pem: str = ""
    previous_public_key_pem: str = ""
    login_csrf_secret: str = ""
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 30 * 24 * 3600
    authorization_code_ttl_seconds: int = 300
    pending_authorization_ttl_seconds: int = 600
    allowed_redirect_prefixes: Tuple[str, ...] = DEFAULT_ALLOWED_REDIRECT_PREFIXES
    # External authorization server (resource-server-only mode)
    external_issuer: str = ""
    external_jwks_url: str = ""
    external_user_claim: str = "https://mitafinance.com/user_id"
    # Publication
    apps_challenge_token: str = ""
    support_url: str = ""
    metrics_token: str = ""
    # Abuse controls
    tool_calls_per_minute: int = 60
    login_attempts_per_minute: int = 10
    trusted_proxy_hops: int = 1

    @property
    def is_production(self) -> bool:
        return self.environment in PRODUCTION_ENVIRONMENTS

    @property
    def resource_url(self) -> str:
        """RFC 8707 resource identifier — also the access-token audience."""
        return f"{self.public_url}/mcp"

    @property
    def issuer_url(self) -> str:
        if self.auth_mode == "external":
            return self.external_issuer
        return self.public_url

    @property
    def resource_metadata_url(self) -> str:
        return f"{self.public_url}/.well-known/oauth-protected-resource/mcp"


def _normalize_public_url(raw: str, *, production: bool) -> str:
    if not raw:
        raise McpConfigError(
            "MCP_PUBLIC_URL is required (e.g. https://mcp.example.com)"
        )
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise McpConfigError("MCP_PUBLIC_URL must be an absolute http(s) URL")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise McpConfigError("MCP_PUBLIC_URL must be an origin without path or query")
    if production and parsed.scheme != "https":
        raise McpConfigError("MCP_PUBLIC_URL must use https in production")
    return f"{parsed.scheme}://{parsed.netloc}"


def load_settings() -> McpSettings:
    environment = _env("ENVIRONMENT", "development").lower()
    production = environment in PRODUCTION_ENVIRONMENTS
    public_url = _normalize_public_url(_env("MCP_PUBLIC_URL"), production=production)

    auth_mode = _env("MCP_AUTH_MODE", "builtin").lower()
    if auth_mode not in ("builtin", "external"):
        raise McpConfigError("MCP_AUTH_MODE must be 'builtin' or 'external'")

    prefixes_raw = _env("MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES")
    prefixes = (
        tuple(p.strip() for p in prefixes_raw.split(",") if p.strip())
        if prefixes_raw
        else DEFAULT_ALLOWED_REDIRECT_PREFIXES
    )
    for prefix in prefixes:
        parsed = urlparse(prefix)
        local = parsed.hostname in {"localhost", "127.0.0.1"}
        if parsed.scheme != "https" and not (local and not production):
            raise McpConfigError(
                "MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES entries must be https "
                "(http://localhost is accepted outside production only)"
            )

    settings = McpSettings(
        environment=environment,
        public_url=public_url,
        auth_mode=auth_mode,  # type: ignore[arg-type]
        private_key_pem=_multiline_env("MCP_OAUTH_PRIVATE_KEY"),
        previous_public_key_pem=_multiline_env("MCP_OAUTH_PREVIOUS_PUBLIC_KEY"),
        login_csrf_secret=_env("MCP_LOGIN_CSRF_SECRET"),
        access_token_ttl_seconds=_int_env("MCP_ACCESS_TOKEN_TTL_SECONDS", 900),
        refresh_token_ttl_seconds=_int_env(
            "MCP_REFRESH_TOKEN_TTL_SECONDS", 30 * 24 * 3600
        ),
        allowed_redirect_prefixes=prefixes,
        external_issuer=_env("MCP_EXTERNAL_ISSUER"),
        external_jwks_url=_env("MCP_EXTERNAL_JWKS_URL"),
        external_user_claim=_env(
            "MCP_EXTERNAL_USER_CLAIM", "https://mitafinance.com/user_id"
        ),
        apps_challenge_token=_env("OPENAI_APPS_CHALLENGE_TOKEN"),
        support_url=_env("MCP_SUPPORT_URL"),
        metrics_token=_env("MCP_METRICS_TOKEN"),
        tool_calls_per_minute=_int_env("MCP_TOOL_CALLS_PER_MINUTE", 60),
        login_attempts_per_minute=_int_env("MCP_LOGIN_ATTEMPTS_PER_MINUTE", 10),
        trusted_proxy_hops=_int_env("MCP_TRUSTED_PROXY_HOPS", 1),
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: McpSettings) -> None:
    if settings.access_token_ttl_seconds > 3600:
        raise McpConfigError("MCP_ACCESS_TOKEN_TTL_SECONDS must be at most 3600")
    if settings.auth_mode == "builtin":
        if not settings.private_key_pem:
            raise McpConfigError(
                "MCP_OAUTH_PRIVATE_KEY is required in builtin auth mode "
                "(generate with scripts/mcp/generate_keys.py)"
            )
        if len(settings.login_csrf_secret) < 32:
            raise McpConfigError("MCP_LOGIN_CSRF_SECRET must be at least 32 characters")
    else:
        if not settings.external_issuer or not settings.external_jwks_url:
            raise McpConfigError(
                "MCP_EXTERNAL_ISSUER and MCP_EXTERNAL_JWKS_URL are required "
                "in external auth mode"
            )
        if urlparse(settings.external_jwks_url).scheme != "https":
            raise McpConfigError("MCP_EXTERNAL_JWKS_URL must be https")
