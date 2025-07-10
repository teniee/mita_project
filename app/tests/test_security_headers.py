import os
import sys
import types

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.mita.finance"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=63072000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
        response.headers[
            "Content-Security-Policy"
        ] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

client = TestClient(app)


def test_security_headers_present():
    r = client.get("/docs")
    assert r.headers.get("Strict-Transport-Security")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src" in csp
    assert "unsafe-inline" in csp
    assert r.headers.get("Permissions-Policy") == "geolocation=(), microphone=()"
    assert r.headers.get("Referrer-Policy") == "same-origin"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"


def test_cors_restricted():
    r = client.options(
        "/docs",
        headers={
            "Origin": "https://app.mita.finance",
            "Access-Control-Request-Method": "GET",
        },
    )
    origin = r.headers.get("access-control-allow-origin")
    assert origin == "https://app.mita.finance"
