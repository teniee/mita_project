"""scripts/mcp/check_leaked_secrets.py finds committed values and never prints one."""

import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "check_leaked_secrets", ROOT / "scripts/mcp/check_leaked_secrets.py"
)
check_leaked_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_leaked_secrets)

LEAKED_VALUE = "synthetic-leaked-secret-value-0123456789"
FP = hashlib.sha256(LEAKED_VALUE.encode()).hexdigest()[:12]


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setitem(
        check_leaked_secrets.LEAKED,
        FP,
        check_leaked_secrets.Leak("TEST item", "secret"),
    )


def run(monkeypatch, capsys, stdin: str, *argv: str):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = check_leaked_secrets.main(["--source", "svc", *argv])
    out, err = capsys.readouterr()
    return code, out + err


@pytest.mark.parametrize(
    "value,form",
    [
        (LEAKED_VALUE, "value"),
        (f"redis://default:{LEAKED_VALUE}@cache.example.test:6379", "URL password"),
        (f"Bearer {LEAKED_VALUE}", "bearer token"),
    ],
)
def test_every_form_matches_and_no_value_is_printed(
    table, monkeypatch, capsys, value, form
):
    code, out = run(monkeypatch, capsys, json.dumps({"API_SECRET": value}))
    assert code == 1
    assert f"MATCH   API_SECRET ({form}) = TEST item [secret]" in out
    assert LEAKED_VALUE not in out and value not in out


def test_list_and_nested_shapes_are_read(table, monkeypatch, capsys):
    shape = {"services": [{"name": "JWT_SECRET", "value": LEAKED_VALUE}]}
    code, out = run(monkeypatch, capsys, json.dumps(shape))
    assert code == 1 and "MATCH   JWT_SECRET (value)" in out
    nested = {"mcpServers": {"redis": {"env": {"URL": LEAKED_VALUE}}}}
    code, out = run(monkeypatch, capsys, json.dumps(nested))
    assert code == 1 and "mcpServers.redis.env.URL" in out


def test_clean_input_passes_and_empty_input_is_an_error(table, monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, json.dumps({"A": "fresh-value-xyz-123456"}))
    assert code == 0 and "0 match(es)" in out
    assert run(monkeypatch, capsys, "{}")[0] == 2
    code, out = run(monkeypatch, capsys, f'{{"broken": "{LEAKED_VALUE}"')
    assert code == 2 and LEAKED_VALUE not in out


def test_env_file(table, monkeypatch, capsys, tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"# comment\nexport SECRET_KEY='{LEAKED_VALUE}'\nOTHER=x\n")
    code, out = run(monkeypatch, capsys, "", "--env-file", str(env))
    assert code == 1 and "MATCH   SECRET_KEY (value)" in out
    assert LEAKED_VALUE not in out


def test_table_covers_every_fingerprint_in_the_security_findings():
    findings = (ROOT / "docs/chatgpt-app/security-findings.md").read_text()
    published = set(re.findall(r"`([0-9a-f]{12})`", findings))
    assert published, "security-findings.md lists no fingerprints"
    assert published <= set(check_leaked_secrets.LEAKED), sorted(
        published - set(check_leaked_secrets.LEAKED)
    )
