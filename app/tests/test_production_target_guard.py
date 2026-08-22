"""The production-write guard must fail closed.

Production accumulated 78+ synthetic accounts and irreversible daily_plan drift
because scripts/production_e2e_test.py defaulted to the live Railway host and
.github/workflows/deployed-smoke.yml both defaulted to it and auto-ran on a push.
These tests pin every part of that not happening again.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _target_guard import (  # noqa: E402
    PRODUCTION_HOSTS,
    ProductionTargetError,
    assert_writable_target,
    is_production,
)

PROD_URLS = [
    "https://mita-production-production.up.railway.app",
    "https://mita-production-production.up.railway.app/",
    "http://mita-production-production.up.railway.app",
    "https://MITA-Production-Production.UP.RAILWAY.APP",
    "https://mita-production-production.up.railway.app./api",
    "https://mita-production.up.railway.app",
    "https://mitafinance.com",
    "https://www.mitafinance.com",
    "https://api.mitafinance.com",
]

SAFE_URLS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://mita-staging.up.railway.app",
    "https://pr-142-mita.up.railway.app",
    "http://backend:8000",
]

MISSING = [None, "", "   "]
MALFORMED = ["not-a-url", "ftp://mita.example", "://nope", "https://"]


class TestProductionIsRefused:
    @pytest.mark.parametrize("url", PROD_URLS)
    def test_assert_writable_target_rejects_production(self, url):
        with pytest.raises(ProductionTargetError) as exc:
            assert_writable_target(url, purpose="unit test")
        assert "production" in str(exc.value).lower()

    @pytest.mark.parametrize("url", PROD_URLS)
    def test_is_production_detects_every_alias_form(self, url):
        assert is_production(url) is True

    def test_case_and_trailing_dot_cannot_evade_the_block(self):
        # A hostname is case-insensitive and may carry a root-zone dot; neither
        # may be a way past the guard.
        with pytest.raises(ProductionTargetError):
            assert_writable_target(
                "https://MiTa-Production-Production.up.railway.app.",
                purpose="unit test",
            )

    def test_substring_lookalikes_are_not_blocked(self):
        # The guard matches the parsed host exactly. A staging host that merely
        # contains the production name must still be usable.
        url = "https://mita-production-production.up.railway.app.staging.example"
        assert is_production(url) is False
        assert assert_writable_target(url, purpose="unit test") == url


class TestFailsClosed:
    @pytest.mark.parametrize("url", MISSING)
    def test_missing_target_is_refused(self, url):
        with pytest.raises(ProductionTargetError) as exc:
            assert_writable_target(url, purpose="unit test")
        assert "explicit target" in str(exc.value)

    @pytest.mark.parametrize("url", MALFORMED)
    def test_malformed_target_is_refused(self, url):
        with pytest.raises(ProductionTargetError):
            assert_writable_target(url, purpose="unit test")

    def test_the_error_names_the_calling_suite(self):
        with pytest.raises(ProductionTargetError) as exc:
            assert_writable_target(None, purpose="onboarding_suite")
        assert "onboarding_suite" in str(exc.value)


class TestSafeTargetsPass:
    @pytest.mark.parametrize("url", SAFE_URLS)
    def test_disposable_target_is_accepted(self, url):
        assert assert_writable_target(url, purpose="unit test") == url

    def test_trailing_slash_is_normalised(self):
        assert (
            assert_writable_target("http://localhost:8000/", purpose="unit test")
            == "http://localhost:8000"
        )


class TestScriptsRefuseProduction:
    """End-to-end: the actual scripts must exit non-zero, before any request."""

    @pytest.mark.parametrize(
        "script", ["production_e2e_test.py", "remote_smoke_test.py"]
    )
    def test_script_refuses_production_url(self, script):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / script), "--base-url", PROD_URLS[0]],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert proc.returncode != 0, f"{script} did not refuse production"
        assert "REFUSED" in proc.stderr, proc.stderr[:400]

    @pytest.mark.parametrize(
        "script", ["production_e2e_test.py", "remote_smoke_test.py"]
    )
    def test_script_refuses_when_no_target_given(self, script, monkeypatch):
        env = {
            k: v
            for k, v in __import__("os").environ.items()
            if k != "MITA_TEST_BASE_URL"
        }
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
        assert proc.returncode != 0, f"{script} ran with no target"
        assert "REFUSED" in proc.stderr, proc.stderr[:400]

    def test_guard_cli_refuses_production_and_accepts_local(self):
        bad = subprocess.run(
            [sys.executable, str(SCRIPTS / "_target_guard_cli.py"), PROD_URLS[0]],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert bad.returncode == 2
        good = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "_target_guard_cli.py"),
                "http://localhost:8000",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert good.returncode == 0


class TestNoScriptCarriesAProductionDefault:
    def test_account_creating_scripts_have_no_production_default(self):
        """A default target is how this happened. There must not be one."""
        for name in ("production_e2e_test.py", "remote_smoke_test.py"):
            src = (SCRIPTS / name).read_text()
            for host in PRODUCTION_HOSTS:
                assert (
                    f'default="https://{host}"' not in src
                ), f"{name} reintroduced a production default"
                assert (
                    f"default='https://{host}'" not in src
                ), f"{name} reintroduced a production default"


class TestSmokeWorkflowCannotTouchProduction:
    @property
    def workflow(self):
        path = REPO / ".github" / "workflows" / "deployed-smoke.yml"
        return path.read_text(), yaml.safe_load(path.read_text())

    def test_no_production_host_anywhere_in_the_workflow(self):
        text, _ = self.workflow
        for host in PRODUCTION_HOSTS:
            assert (
                host not in text
            ), f"deployed-smoke.yml references production host {host}"

    def test_base_url_input_is_required_and_has_no_default(self):
        _, doc = self.workflow
        # PyYAML parses the bare `on:` key as boolean True.
        triggers = doc.get("on", doc.get(True))
        inputs = triggers["workflow_dispatch"]["inputs"]
        assert inputs["base_url"]["required"] is True
        assert (
            "default" not in inputs["base_url"]
        ), "a default target is how production got written to"

    def test_workflow_cannot_be_triggered_by_a_push(self):
        _, doc = self.workflow
        triggers = doc.get("on", doc.get(True))
        assert (
            "push" not in triggers
        ), "a push trigger ran the account-creating smoke suite automatically"
        assert set(triggers) == {"workflow_dispatch"}

    def test_workflow_runs_the_guard_before_the_suite(self):
        text, doc = self.workflow
        steps = doc["jobs"]["smoke"]["steps"]
        runs = [s.get("run", "") for s in steps]
        guard_at = next(i for i, r in enumerate(runs) if "_target_guard_cli" in r)
        suite_at = next(i for i, r in enumerate(runs) if "remote_smoke_test" in r)
        assert guard_at < suite_at, "guard must run before the account-creating step"


class TestDartLiveSuitesShareTheGuard:
    def test_dart_guard_lists_the_same_hosts_as_python(self):
        dart = (
            REPO / "mobile_app" / "integration_test" / "target_guard.dart"
        ).read_text()
        for host in PRODUCTION_HOSTS:
            assert f"'{host}'" in dart, f"Dart guard is missing {host}"

    @pytest.mark.parametrize(
        "name",
        ["mobile_backend_journey_live_test.dart", "comprehensive_api_live_test.dart"],
    )
    def test_live_suites_delegate_to_the_shared_guard(self, name):
        src = (REPO / "mobile_app" / "integration_test" / name).read_text()
        assert "import 'target_guard.dart';" in src
        # the old single-host contains() check must be gone
        assert "_e2eBaseUrl.contains(" not in src
        assert "fail(_e2eTargetProblem)" in src
