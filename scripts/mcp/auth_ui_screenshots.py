"""Review screenshots of the ChatGPT sign-in / sign-up / consent pages.

    python scripts/mcp/auth_ui_screenshots.py --base-url http://localhost:8765 \\
        --out docs/chatgpt-app/review/auth-ui

Drives the real pages the way ChatGPT does: registers a client (DCR), opens
/authorize with PKCE and follows it to /oauth/login. Desktop shots use
Chromium, mobile shots WebKit (the engine of ChatGPT's in-app browser on
iOS). Only fictional addresses are typed and no valid credentials are ever
submitted, so nothing redirects to ChatGPT. Refuses production hosts
(scripts/_target_guard.py). The one state that cannot be produced on demand —
the database being down — is rendered by the same ``pages.problem_page`` the
service uses and served on the page's own origin.

Dev-only dependencies (not in requirements-mcp*): playwright==1.49.1 (with
``playwright install chromium webkit``), httpx, and Pillow for ``--webp``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from _target_guard import assert_writable_target  # noqa: E402

REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
SCOPES = "profile:read finance:read finance:write feedback:write profile:write"
DESKTOP = {"width": 1440, "height": 900}
IPHONE = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    ),
}


def is_local(base: str) -> bool:
    """A local review server may use a self-signed certificate (the CSRF
    cookie is ``__Host-``/``Secure``, so the flow needs HTTPS even locally)."""
    return urlparse(base).hostname in ("localhost", "127.0.0.1")


def login_url(base: str) -> str:
    with httpx.Client(base_url=base, timeout=20, verify=not is_local(base)) as http:
        client = http.post(
            "/register",
            json={
                "redirect_uris": [REDIRECT],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "client_name": "ChatGPT",
            },
        )
        client.raise_for_status()
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client.json()["client_id"],
                "redirect_uri": REDIRECT,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": secrets.token_urlsafe(8),
                "scope": SCOPES,
                "resource": f"{base}/mcp",
            }
        )
        authorized = http.get(f"/authorize?{query}")
        if authorized.status_code != 302:
            raise SystemExit(f"/authorize answered {authorized.status_code}")
        return authorized.headers[
            "location"
        ]  # absolute: <public url>/oauth/login?req=…


def settle(page) -> None:
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(300)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="local or staging origin")
    parser.add_argument("--out", default=str(ROOT / "docs/chatgpt-app/review/auth-ui"))
    parser.add_argument(
        "--webp",
        action="store_true",
        help="convert to lossless WebP (needs Pillow): exact colors, about half the size",
    )
    args = parser.parse_args()
    base = assert_writable_target(args.base_url, purpose="auth UI screenshots").rstrip(
        "/"
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    url = login_url(base)

    from app.mcp.auth import pages  # same renderer the service uses

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        tls = {"ignore_https_errors": is_local(base)}
        desktop = chromium.new_context(viewport=DESKTOP, reduced_motion="reduce", **tls)
        page = desktop.new_page()

        page.goto(url)
        settle(page)
        page.screenshot(path=out / "01-sign-in-desktop.png", full_page=True)
        page.locator(".auth-card").screenshot(path=out / "04-consent.png")
        page.locator(".demo").screenshot(path=out / "07-product-demo.png")
        page.locator(".ask").screenshot(path=out / "08-what-can-i-ask.png")

        page.goto(url + "&mode=register")
        settle(page)
        page.screenshot(path=out / "02-create-account-desktop.png", full_page=True)

        page.fill("#email", "alex.demo@example.com")
        page.fill("#password", "Fresh-Start-2026!")
        page.fill("#password_confirm", "Fresh-Start-2025!")
        page.click("button[value=register]")
        settle(page)
        page.locator(".auth-card").screenshot(path=out / "05-validation-error.png")

        page.goto(url)
        settle(page)
        page.fill("#email", "nobody.demo@example.com")
        page.fill("#password", "Not-The-Password-1!")
        page.click("button[value=allow]")
        settle(page)
        page.locator(".auth-card").screenshot(path=out / "06-sign-in-failed.png")

        page.goto(base + "/oauth/login?req=expired.0")
        settle(page)
        page.screenshot(path=out / "09-expired-link.png")

        page.goto(base + "/authorize?client_id=unknown-client&response_type=code")
        settle(page)
        page.screenshot(path=out / "10-connection-error.png")

        unavailable = pages.problem_page(
            pages.UNAVAILABLE_TITLE,
            pages.UNAVAILABLE,
            icon_name="clock",
            retry_url="/oauth/login",
        )
        page.route(
            base + "/review-unavailable",
            lambda route: route.fulfill(
                status=503, content_type="text/html; charset=utf-8", body=unavailable
            ),
        )
        page.goto(base + "/review-unavailable")
        settle(page)
        page.screenshot(path=out / "11-temporarily-unavailable.png")
        chromium.close()

        webkit = p.webkit.launch()
        phone = webkit.new_context(**IPHONE, reduced_motion="reduce", **tls)
        page = phone.new_page()
        page.goto(url + "&mode=register")
        settle(page)
        page.screenshot(path=out / "03-create-account-mobile.png", full_page=True)
        page.goto(url)
        settle(page)
        page.screenshot(path=out / "12-sign-in-mobile-first-screen.png")
        webkit.close()

    if args.webp:
        from PIL import Image

        for path in sorted(out.glob("*.png")):
            with Image.open(path) as image:
                image.save(path.with_suffix(".webp"), "WEBP", lossless=True, method=6)
            path.unlink()
    for path in sorted(out.glob("*.png")) + sorted(out.glob("*.webp")):
        print(f"{path}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
