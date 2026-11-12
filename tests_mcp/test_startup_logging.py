"""Starting the service writes JSON log lines only.

``app.core.logging_config`` prints two plain-text lines when it is imported;
nothing else may. Importing the service computes the sign-in page's fictional
example through the forecast engine, whose INFO line used to go out as plain
text with amounts before ``configure_logging`` took over
(``scripts/mcp/e2e_http.py`` checks the same rule on a running server).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWN_STARTUP_LINES = (
    "app.core.logging_config: Logging configured",
    "app.core.logging_config: Log files",
)


def test_importing_the_service_logs_nothing_in_plain_text():
    env = dict(os.environ, PYTHONPATH=str(ROOT), ENVIRONMENT="test")
    code = (
        "from app.mcp.__main__ import import_build_service; "
        "import_build_service('INFO')"
    )
    run = subprocess.run(  # noqa: S603 - fixed interpreter and argument
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert run.returncode == 0, run.stderr[-2000:]
    stray = [
        line
        for line in (run.stdout + run.stderr).splitlines()
        if line.strip()
        and not line.startswith("{")
        and not any(known in line for known in KNOWN_STARTUP_LINES)
    ]
    assert stray == []
