"""Build the self-hosted WOFF2 fonts for the ChatGPT sign-in page.

The sign-in page (``app/mcp/auth/pages.py``) loads no third-party resource,
so the three brand fonts from the MITA Brand Guidelines (Figma) are served by
the MCP service itself from ``app/mcp/auth/static/fonts/``:

* Manrope (primary: UI, body)          — repo copy used by the mobile app
* Sora (secondary: marketing headlines) — repo copy used by the mobile app
* Space Mono (financial figures)       — google/fonts, pinned by SHA-256

Each is cut to the Latin range the page uses and, for the variable fonts, to
the weight range it uses. All three are SIL OFL 1.1 without Reserved Font
Names, so subsetting is allowed; the licences are copied next to the files.

Dev-only tooling (not in the MCP image)::

    python -m venv /tmp/fontvenv
    /tmp/fontvenv/bin/pip install fonttools==4.55.3 brotli==1.1.0
    /tmp/fontvenv/bin/python scripts/mcp/build_auth_fonts.py
"""

from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[2]
FONTS_IN = ROOT / "mobile_app" / "assets" / "fonts"
OUT = ROOT / "app" / "mcp" / "auth" / "static" / "fonts"

SPACE_MONO = "https://raw.githubusercontent.com/google/fonts/main/ofl/spacemono/"
SPACE_MONO_SHA256 = {
    "SpaceMono-Regular.ttf": "95837e182baeeada83368f7748db28357f0a1b75c6b84ff7065b5edf933c8e18",
    "SpaceMono-Bold.ttf": "405e73d41afb7e5906efce206a326af5c956f38e255f35421c260e861e599c59",
}

# Google Fonts' "latin" range plus arrows: everything the page's copy and an
# e-mail address typed in Latin script can contain.
UNICODES = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2190-2193,U+2212,"
    "U+2215,U+FEFF,U+FFFD"
)


def _subset(font: TTFont, dest: Path) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.notdef_outline = True
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=subset.parse_unicodes(UNICODES))
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(dest)
    print(f"{dest.relative_to(ROOT)}: {dest.stat().st_size} bytes")


def _variable(src: Path, dest: Path, low: int, high: int) -> None:
    font = instancer.instantiateVariableFont(TTFont(src), {"wght": (low, high)})
    # Round-trip before subsetting: the instanced gvar is still lazily loaded
    # and the subsetter would look up glyphs it no longer has.
    buffer = io.BytesIO()
    font.save(buffer)
    buffer.seek(0)
    _subset(TTFont(buffer), dest)


def _space_mono(workdir: Path) -> dict:
    files = {}
    for name, digest in SPACE_MONO_SHA256.items():
        path = workdir / name
        with urllib.request.urlopen(
            SPACE_MONO + name, timeout=30
        ) as response:  # nosec B310 - pinned https URL
            path.write_bytes(response.read())
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"{name}: sha256 {actual} != pinned {digest}")
        files[name] = path
    licence = workdir / "OFL.txt"
    with urllib.request.urlopen(
        SPACE_MONO + "OFL.txt", timeout=30
    ) as response:  # nosec B310 - pinned https URL
        licence.write_bytes(response.read())
    files["OFL"] = licence
    return files


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _variable(
        FONTS_IN / "Manrope" / "Manrope-VariableFont_wght.ttf",
        OUT / "manrope.woff2",
        400,
        700,
    )
    _variable(
        FONTS_IN / "Sora" / "Sora-VariableFont_wght.ttf", OUT / "sora.woff2", 400, 700
    )
    with tempfile.TemporaryDirectory() as tmp:
        mono = _space_mono(Path(tmp))
        _subset(TTFont(mono["SpaceMono-Regular.ttf"]), OUT / "space-mono-400.woff2")
        _subset(TTFont(mono["SpaceMono-Bold.ttf"]), OUT / "space-mono-700.woff2")
        # ".license", not ".txt": .dockerignore drops *.txt from the image.
        shutil.copyfile(mono["OFL"], OUT / "SpaceMono-OFL.license")
    shutil.copyfile(FONTS_IN / "Manrope" / "OFL.txt", OUT / "Manrope-OFL.license")
    shutil.copyfile(FONTS_IN / "Sora" / "OFL.txt", OUT / "Sora-OFL.license")


if __name__ == "__main__":
    main()
