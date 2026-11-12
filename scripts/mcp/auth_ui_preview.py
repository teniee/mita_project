#!/usr/bin/env python3
"""Review the ChatGPT connect page locally — no OAuth server, no database.

    python scripts/mcp/auth_ui_preview.py --serve            # http://127.0.0.1:8770
    python scripts/mcp/auth_ui_preview.py --shots docs/chatgpt-app/review/auth-ui-v5.2 \\
        [--axe path/to/axe.min.js] [--webp --quality 88]

Renders the page with the same code the service uses (``pages.login_page`` /
``pages.problem_page``) and serves it from 127.0.0.1 only, with the service's
security headers (the CSP blocks any script) and the self-hosted assets. The
form posts nowhere useful: this is for looking, not signing in. The figures are
the fictional month MITA computes in ``demo.py``.

``--shots`` renders the reference viewports (phones in WebKit — the engine of
ChatGPT's iOS in-app browser — tablet and desktop in Chromium), first screen and
full page, still (reduced motion) plus motion frames, and prints per viewport:
horizontal overflow, clipped text and undersized tap targets. ``--axe`` runs
axe-core (WCAG 2.2 AA) on the sign-in and sign-up pages.

Dev-only dependencies: playwright (``playwright install chromium webkit``),
Pillow for ``--webp``.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.mcp.auth import pages  # noqa: E402
from app.mcp.auth.scopes import SUPPORTED_SCOPES  # noqa: E402

HOST, PORT = "127.0.0.1", 8770
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
# login.GENERIC_FAILURE (not imported: login.py needs the service's settings).
SIGN_IN_FAILED = (
    "Sign-in failed. Check your email and password and try again. After "
    "several failed attempts, sign-in is paused for 30 minutes."
)
VIEWPORTS = (  # (name, width, height, engine)
    ("320x640", 320, 640, "webkit"),
    ("360x800", 360, 800, "webkit"),
    ("390x844", 390, 844, "webkit"),
    ("430x932", 430, 932, "webkit"),
    ("768x1024", 768, 1024, "chromium"),
    ("1280x800", 1280, 800, "chromium"),
    ("1440x900", 1440, 900, "chromium"),
)


def view(register: bool = False, error: str = "") -> pages.LoginView:
    return pages.LoginView(
        req="preview",
        csrf="0" * 64,
        client_name="ChatGPT",
        redirect_host="chatgpt.com",
        scopes=tuple(SUPPORTED_SCOPES),
        register=register,
        email="",
        error=SIGN_IN_FAILED if error else None,
        error_field="credentials" if error else None,
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        return

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path.startswith(pages.ASSET_PREFIX):
            found = pages.ASSETS.get(url.path[len(pages.ASSET_PREFIX) :])
            if found is None:
                self.send_error(404)
                return
            data, content_type = found
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/problem":
            html = pages.problem_page(
                "This sign-in link has expired",
                "For your security, MITA sign-in links work for 10 minutes and only "
                "in the browser where you opened them. Return to ChatGPT and "
                "connect MITA again.",
                icon_name="clock",
            )
            headers = pages.security_headers()
        else:
            html = pages.login_page(
                view(
                    register=query.get("mode") == ["register"],
                    error=query.get("state", [""])[0],
                )
            )
            headers = pages.security_headers(REDIRECT)
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


MEASURE = """() => {
  const doc = document.documentElement;
  const clipped = [];
  for (const el of document.querySelectorAll('body *')) {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || el.closest('.vh,[aria-hidden=true]')) continue;
    if (el.childElementCount === 0 && el.textContent.trim() && el.scrollWidth > el.clientWidth + 1 && s.overflow !== 'visible') {
      clipped.push((el.className || el.tagName) + ': ' + el.textContent.trim().slice(0, 32));
    }
  }
  const small = [];
  for (const el of document.querySelectorAll('a, button, input, summary')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.height && (r.height < 24 || r.width < 24)) small.push((el.id || el.className || el.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  const first = window.innerHeight;
  const seen = (sel) => { const n = document.querySelector(sel); if (!n) return null; const r = n.getBoundingClientRect(); return Math.round(r.top + window.scrollY); };
  return {overflow: doc.scrollWidth - doc.clientWidth, height: doc.scrollHeight, viewport: first,
          clipped: clipped.slice(0, 10), small: small.slice(0, 10),
          top_of: {proof: seen('.proof'), cta: seen('.cta'), ask: seen('#ask'), form: seen('#auth form'), trust: seen('#trust'), month: seen('#month'), more: seen('#more'), close: seen('.close')}};
}"""

# The form in view: scrolled to only when it is not already on screen.
TO_FORM = """() => { const f = document.querySelector('#auth');
  if (f.getBoundingClientRect().top > innerHeight / 2) f.scrollIntoView({block: 'start'}); }"""


# Lazy images load only near the viewport: scroll once, then wait for them.
LOAD_LAZY = """async () => {
  for (let y = 0; y < document.documentElement.scrollHeight; y += innerHeight / 2) {
    scrollTo(0, y); await new Promise(r => setTimeout(r, 30));
  }
  await Promise.all([...document.images].map(i => i.complete ? null : new Promise(r => { i.onload = i.onerror = r; })));
  scrollTo(0, 0);
}"""


def shots(out: Path, axe: str = "", webp: bool = False, quality: int = 88) -> dict:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    server = serve()
    base = f"http://{HOST}:{server.server_port}/oauth/login"
    report: dict = {"viewports": {}, "axe": {}}
    try:
        with sync_playwright() as p:
            engines = {"webkit": p.webkit.launch(), "chromium": p.chromium.launch()}
            for name, width, height, engine in VIEWPORTS:
                mobile = width < 560
                context = engines[engine].new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=2,
                    is_mobile=mobile and engine == "webkit",
                    has_touch=mobile,
                    reduced_motion="reduce",
                )
                page = context.new_page()
                page.goto(base)
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(250)
                report["viewports"][name] = page.evaluate(MEASURE)
                page.screenshot(path=str(out / f"{name}-first-screen.png"))
                page.evaluate(LOAD_LAZY)
                page.screenshot(path=str(out / f"{name}-full-page.png"), full_page=True)
                if name in ("390x844", "1440x900"):
                    page.evaluate(TO_FORM)
                    page.wait_for_timeout(150)
                    page.screenshot(path=str(out / f"{name}-sign-in.png"))
                    page.goto(base + "?mode=register")
                    page.evaluate("document.fonts.ready")
                    page.evaluate(LOAD_LAZY)
                    page.wait_for_timeout(200)
                    page.screenshot(
                        path=str(out / f"{name}-create-account-full-page.png"),
                        full_page=True,
                    )
                    page.evaluate(TO_FORM)
                    page.wait_for_timeout(150)
                    page.screenshot(path=str(out / f"{name}-create-account.png"))
                    page.goto(base + "?state=error")
                    page.evaluate("document.fonts.ready")
                    page.locator("#auth").scroll_into_view_if_needed()
                    page.wait_for_timeout(150)
                    page.screenshot(path=str(out / f"{name}-sign-in-failed.png"))
                context.close()
            # Motion: the question, MITA typing, the answer settling (phone).
            context = engines["webkit"].new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
                reduced_motion="no-preference",
            )
            page = context.new_page()
            page.goto(base)
            elapsed = 0
            for at in (600, 1100, 1900, 3400):
                page.wait_for_timeout(at - elapsed)
                elapsed = at
                page.screenshot(path=str(out / f"390x844-motion-{at}ms.png"))
            context.close()
            if axe:
                source = Path(axe).read_text()
                for engine, width, height in (
                    ("webkit", 390, 844),
                    ("chromium", 1280, 800),
                ):
                    for mode in ("", "?mode=register", "?state=error"):
                        # The CSP blocks every script, axe included: it is
                        # injected into this test browser only.
                        context = engines[engine].new_context(
                            viewport={"width": width, "height": height},
                            reduced_motion="reduce",
                            bypass_csp=True,
                        )
                        page = context.new_page()
                        page.goto(base + mode)
                        page.evaluate("document.fonts.ready")
                        page.add_script_tag(content=source)
                        result = page.evaluate(
                            """async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});
                               return r.violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, target: v.nodes.slice(0,3).map(n => n.target.join(' '))})); }"""
                        )
                        report["axe"][f"{engine} {width} {mode or 'sign-in'}"] = result
                        context.close()
            for browser in engines.values():
                browser.close()
    finally:
        server.shutdown()
    if webp:
        from PIL import Image

        for path in sorted(out.glob("*.png")):
            with Image.open(path) as image:
                image.convert("RGB").save(
                    path.with_suffix(".webp"), "WEBP", quality=quality, method=6
                )
            path.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--shots")
    parser.add_argument("--axe", default="")
    parser.add_argument("--webp", action="store_true")
    parser.add_argument("--quality", type=int, default=88)
    args = parser.parse_args()
    if args.serve:
        server = serve()
        print(
            f"http://{HOST}:{server.server_port}/oauth/login  (and ?mode=register, ?state=error, /problem)"
        )
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            server.shutdown()
        return
    if args.shots:
        print(
            json.dumps(
                shots(Path(args.shots), args.axe, args.webp, args.quality), indent=1
            )
        )


if __name__ == "__main__":
    main()
