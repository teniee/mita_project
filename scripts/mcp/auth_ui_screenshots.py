"""Review screenshots of the ChatGPT sign-in / sign-up / consent pages.

    python scripts/mcp/auth_ui_screenshots.py --base-url http://localhost:8765 \\
        --out docs/chatgpt-app/review/auth-ui-v3

Drives the real pages the way ChatGPT does: registers a client (DCR), opens
/authorize with PKCE and follows it to /oauth/login. Phone and tablet shots
use WebKit (the engine of ChatGPT's in-app browser on iOS), desktop shots
Chromium. The phone comes first: the page is designed for it. Only fictional
addresses are typed and no valid credentials are ever submitted, so nothing
redirects to ChatGPT. Refuses production hosts (scripts/_target_guard.py).
The one state that cannot be produced on demand — the database being down —
is rendered by the same ``pages.problem_page`` the service uses and served on
the page's own origin.

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
IOS_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
IPHONE = {
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": IOS_UA,
}
IPHONE_PRO = dict(IPHONE, viewport={"width": 393, "height": 852})
IPHONE_MAX = dict(IPHONE, viewport={"width": 430, "height": 932})
TABLET = {
    "viewport": {"width": 768, "height": 1024},
    "device_scale_factor": 2,
    "has_touch": True,
}
DESKTOPS = ((1280, 800), (1440, 900), (1440, 1000))


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
    parser.add_argument(
        "--out", default=str(ROOT / "docs/chatgpt-app/review/auth-ui-v3")
    )
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
    register = url + "&mode=register"

    from app.mcp.auth import pages  # same renderer the service uses

    with sync_playwright() as p:
        tls = {"ignore_https_errors": is_local(base), "reduced_motion": "reduce"}
        webkit = p.webkit.launch()

        page = webkit.new_context(**IPHONE, **tls).new_page()
        page.goto(url)
        settle(page)
        page.screenshot(path=out / "01-mobile-390x844-first-screen.png")
        page.locator(".consent").screenshot(path=out / "03-mobile-consent.png")
        page.locator(".perm summary").click()
        page.locator(".consent").screenshot(path=out / "04-mobile-consent-details.png")
        page.locator(".snap").screenshot(path=out / "05-mobile-example.png")
        page.locator(".calc summary").click()
        page.locator(".hero").screenshot(path=out / "06-mobile-example-calculation.png")
        page.goto(url)
        settle(page)
        page.screenshot(path=out / "07-mobile-full-page.png", full_page=True)
        page.goto(register)
        settle(page)
        page.screenshot(
            path=out / "02-mobile-390x844-create-account.png", full_page=True
        )

        for number, preset in ((8, IPHONE_PRO), (9, IPHONE_MAX)):
            page = webkit.new_context(**preset, **tls).new_page()
            page.goto(url)
            settle(page)
            size = "{width}x{height}".format(**preset["viewport"])
            page.screenshot(path=out / f"{number:02d}-mobile-{size}-first-screen.png")

        page = webkit.new_context(**TABLET, **tls).new_page()
        page.goto(url)
        settle(page)
        page.screenshot(path=out / "10-tablet-768x1024-first-screen.png")
        webkit.close()

        chromium = p.chromium.launch()
        for index, (width, height) in enumerate(DESKTOPS):
            page = chromium.new_context(
                viewport={"width": width, "height": height}, **tls
            ).new_page()
            page.goto(url)
            settle(page)
            number = (11, 12, 14)[index]
            page.screenshot(
                path=out / f"{number}-desktop-{width}x{height}-first-screen.png"
            )
        # The last context is 1440×1000; the rest of the desktop set is 1440×900.
        page = chromium.new_context(
            viewport={"width": 1440, "height": 900}, **tls
        ).new_page()
        page.goto(register)
        settle(page)
        page.screenshot(path=out / "13-desktop-1440x900-create-account.png")
        page.goto(url)
        settle(page)
        page.screenshot(path=out / "16-desktop-full-page.png", full_page=True)
        for summary in page.locator(".more summary").all():
            summary.click()
        page.locator(".more").screenshot(path=out / "15-desktop-more-details.png")

        page.goto(register)
        settle(page)
        page.fill("#email", "alex.demo@example.com")
        page.fill("#password", "Fresh-Start-2026!")
        page.fill("#password_confirm", "Fresh-Start-2025!")
        page.click("button[value=register]")
        settle(page)
        page.locator(".auth-card").screenshot(path=out / "17-validation-error.png")

        page.goto(url)
        settle(page)
        page.fill("#email", "nobody.demo@example.com")
        page.fill("#password", "Not-The-Password-1!")
        page.click("button[value=allow]")
        settle(page)
        page.locator(".auth-card").screenshot(path=out / "18-sign-in-failed.png")

        page.goto(base + "/oauth/login?req=expired.0")
        settle(page)
        page.screenshot(path=out / "19-expired-link.png")

        page.goto(base + "/authorize?client_id=unknown-client&response_type=code")
        settle(page)
        page.screenshot(path=out / "20-connection-error.png")

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
        page.screenshot(path=out / "21-temporarily-unavailable.png")
        chromium.close()

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
