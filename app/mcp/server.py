"""Assembles the MCP service: tools, OAuth, public endpoints, middleware.

Transport: MCP streamable HTTP at ``/mcp``, **stateless** — every request is
authenticated on its own and no MCP session object outlives it, so a
financial auth context can never be carried over to another user's request.
"""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.routes import build_metadata, cors_middleware
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp

from app.mcp import MCP_SERVER_NAME, MCP_SERVER_VERSION
from app.mcp.auth.keys import SigningKeys, load_signing_keys
from app.mcp.auth.login import ConsentPage
from app.mcp.auth.provider import (
    ALLOWED_AUTH_METHODS,
    MitaAuthorizationProvider,
    PendingRequestCodec,
    same_resource,
)
from app.mcp.auth.scopes import SUPPORTED_SCOPES
from app.mcp.auth.tokens import JwtTokenVerifier
from app.mcp.config import McpSettings
from app.mcp.db import SessionScope, read_only_session, write_session
from app.mcp.observability import RequestLogMiddleware, metrics
from app.mcp.ratelimit import OAuthEndpointRateLimit, SlidingWindowLimiter
from app.mcp.runtime import McpRuntime
from app.mcp.tools import register_tools

logger = logging.getLogger("app.mcp")

INSTRUCTIONS = (
    "MITA is a personal budgeting app. These tools read the signed-in user's own MITA "
    "data: recorded expenses, the monthly budget plan MITA generated, a month-end "
    "projection, savings goals and scheduled expenses. All tools are read-only: they "
    "cannot add, edit or delete transactions, change budgets, move money, make payments "
    "or trade. Amounts are decimal strings in the user's MITA currency. When a field is "
    "null or plan_status is 'not_generated', MITA has no such data — say so rather than "
    "estimating. MITA records expenses only; it has no bank balances or income "
    "transactions, and stated_monthly_income is what the user typed in."
)

OPENAI_CHALLENGE_PATH = "/.well-known/openai-apps-challenge"


@dataclass
class McpService:
    app: ASGIApp
    server: MCPServer
    runtime: McpRuntime
    provider: Optional[MitaAuthorizationProvider]
    keys: Optional[SigningKeys]


def _transport_security(settings: McpSettings) -> TransportSecuritySettings:
    host = urlparse(settings.public_url).netloc
    hosts = [host]
    origins = [settings.public_url, "https://chatgpt.com"]
    if not settings.is_production:
        hosts += ["127.0.0.1:*", "localhost:*", "testserver"]
        origins += ["http://127.0.0.1:*", "http://localhost:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def build_service(
    settings: McpSettings,
    *,
    session_scope: SessionScope = read_only_session,
    write_scope: SessionScope = write_session,
    readiness_check=None,
    clock=None,
) -> McpService:
    keys: Optional[SigningKeys] = None
    provider: Optional[MitaAuthorizationProvider] = None
    if settings.auth_mode == "builtin":
        keys = load_signing_keys(
            settings.private_key_pem, settings.previous_public_key_pem
        )
        verifier = JwtTokenVerifier(settings, keys=keys)
        provider = MitaAuthorizationProvider(
            settings,
            keys,
            verifier,
            write_scope,
            PendingRequestCodec(
                settings.login_csrf_secret, settings.pending_authorization_ttl_seconds
            ),
        )
        auth = AuthSettings(
            issuer_url=settings.issuer_url,
            resource_server_url=settings.resource_url,
            validate_token_resource=True,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=list(SUPPORTED_SCOPES),
                default_scopes=list(SUPPORTED_SCOPES),
            ),
            revocation_options=RevocationOptions(enabled=True),
        )
        server = MCPServer(
            MCP_SERVER_NAME,
            title="MITA Finance",
            instructions=INSTRUCTIONS,
            version=MCP_SERVER_VERSION,
            auth_server_provider=provider,
            auth=auth,
        )
    else:
        verifier = JwtTokenVerifier(settings)
        server = MCPServer(
            MCP_SERVER_NAME,
            title="MITA Finance",
            instructions=INSTRUCTIONS,
            version=MCP_SERVER_VERSION,
            token_verifier=verifier,
            auth=AuthSettings(
                issuer_url=settings.issuer_url,
                resource_server_url=settings.resource_url,
                validate_token_resource=True,
            ),
        )

    runtime = McpRuntime(
        settings=settings,
        session_scope=session_scope,
        tool_limiter=SlidingWindowLimiter(settings.tool_calls_per_minute),
    )
    if clock is not None:
        runtime.clock = clock
    register_tools(server, runtime)

    # --- public endpoints (no auth) ------------------------------------------

    @server.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(request: Request) -> Response:
        if readiness_check is not None and not await readiness_check():
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse(
            {"status": "ok", "service": "mita-mcp", "version": MCP_SERVER_VERSION}
        )

    @server.custom_route(
        OPENAI_CHALLENGE_PATH, methods=["GET"], include_in_schema=False
    )
    async def openai_challenge(request: Request) -> Response:
        if not settings.apps_challenge_token:
            return PlainTextResponse("", status_code=404)
        return PlainTextResponse(
            settings.apps_challenge_token, headers={"Cache-Control": "no-store"}
        )

    if keys is not None:
        jwks = keys.jwks

        @server.custom_route(
            "/.well-known/jwks.json", methods=["GET"], include_in_schema=False
        )
        async def jwks_endpoint(request: Request) -> Response:
            return JSONResponse(jwks, headers={"Cache-Control": "public, max-age=300"})

    if provider is not None:
        consent = ConsentPage(
            settings,
            provider,
            SlidingWindowLimiter(settings.login_attempts_per_minute),
            write_scope,
        )
        server.custom_route("/oauth/login", methods=["GET"], include_in_schema=False)(
            consent.get
        )
        server.custom_route("/oauth/login", methods=["POST"], include_in_schema=False)(
            consent.post
        )

    app: Starlette = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(settings),
        host=urlparse(settings.public_url).hostname or "0.0.0.0",  # nosec B104
    )

    if provider is not None:
        # RFC 8707 at the token endpoint: the SDK passes `resource` on to no
        # one, so a token request naming another resource would silently get
        # a token for this one. Refuse it instead (the token is always bound
        # to settings.resource_url regardless).
        sdk_token = TokenHandler(
            provider=provider, client_authenticator=ClientAuthenticator(provider)
        )

        async def strict_token(request: Request) -> Response:
            form = await request.form()  # cached on the Request; the SDK re-reads it
            requested = form.get("resource")
            if (
                isinstance(requested, str)
                and requested
                and not same_resource(requested, settings.resource_url)
            ):
                return JSONResponse(
                    {
                        "error": "invalid_target",
                        "error_description": "This authorization server only issues tokens for its MCP resource.",
                    },
                    status_code=400,
                    headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
                )
            return await sdk_token.handle(request)

        app.router.routes.insert(
            0,
            Route(
                "/token",
                endpoint=cors_middleware(strict_token, ["POST", "OPTIONS"]),
                methods=["POST", "OPTIONS"],
                include_in_schema=False,
            ),
        )

    if provider is not None:
        # RFC 8414 metadata. The SDK hard-codes token_endpoint_auth_methods to
        # the two secret-based methods, yet registration accepts public PKCE
        # clients ("none") — which is what ChatGPT registers as. Advertise the
        # methods the provider actually accepts.
        as_metadata = build_metadata(
            AnyHttpUrl(settings.issuer_url),
            None,
            ClientRegistrationOptions(
                enabled=True,
                valid_scopes=list(SUPPORTED_SCOPES),
                default_scopes=list(SUPPORTED_SCOPES),
            ),
            RevocationOptions(enabled=True),
        )
        as_metadata.token_endpoint_auth_methods_supported = sorted(ALLOWED_AUTH_METHODS)
        as_metadata_json = as_metadata.model_dump(mode="json", exclude_none=True)
        # Issuer comparison is exact string comparison (RFC 8414 §3.3); the URL
        # type would append "/" to a path-less origin.
        as_metadata_json["issuer"] = settings.issuer_url

        async def authorization_server_metadata(request: Request) -> Response:
            return JSONResponse(
                as_metadata_json, headers={"Cache-Control": "public, max-age=300"}
            )

        app.router.routes.insert(
            0,
            Route(
                "/.well-known/oauth-authorization-server",
                authorization_server_metadata,
                methods=["GET"],
                include_in_schema=False,
            ),
        )

    # RFC 9728 metadata listing both scopes (the SDK lists only required_scopes).
    async def protected_resource_metadata(request: Request) -> Response:
        return JSONResponse(
            {
                "resource": settings.resource_url,
                "authorization_servers": [settings.issuer_url],
                "scopes_supported": list(SUPPORTED_SCOPES),
                "bearer_methods_supported": ["header"],
                "resource_name": "MITA Finance",
            },
            headers={"Cache-Control": "public, max-age=300"},
        )

    for path in (
        "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-protected-resource",
    ):
        app.router.routes.insert(
            0,
            Route(
                path,
                protected_resource_metadata,
                methods=["GET"],
                include_in_schema=False,
            ),
        )

    if settings.metrics_token:

        async def metrics_endpoint(request: Request) -> Response:
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, f"Bearer {settings.metrics_token}"):
                return PlainTextResponse("", status_code=401)
            return PlainTextResponse(
                metrics.render(), media_type="text/plain; version=0.0.4"
            )

        app.router.routes.append(
            Route(
                "/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False
            )
        )

    wrapped: ASGIApp = app
    if provider is not None:
        wrapped = OAuthEndpointRateLimit(
            wrapped,
            per_minute=settings.oauth_requests_per_minute,
            trusted_hops=settings.trusted_proxy_hops,
        )
    return McpService(
        app=RequestLogMiddleware(wrapped),
        server=server,
        runtime=runtime,
        provider=provider,
        keys=keys,
    )
