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

from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp

from app.mcp import MCP_SERVER_NAME, MCP_SERVER_VERSION
from app.mcp.auth.keys import SigningKeys, load_signing_keys
from app.mcp.auth.login import ConsentPage
from app.mcp.auth.provider import MitaAuthorizationProvider, PendingRequestCodec
from app.mcp.auth.scopes import SUPPORTED_SCOPES
from app.mcp.auth.tokens import JwtTokenVerifier
from app.mcp.config import McpSettings
from app.mcp.db import SessionScope, read_only_session, write_session
from app.mcp.observability import RequestLogMiddleware, metrics
from app.mcp.ratelimit import SlidingWindowLimiter
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

    return McpService(
        app=RequestLogMiddleware(app),
        server=server,
        runtime=runtime,
        provider=provider,
        keys=keys,
    )
