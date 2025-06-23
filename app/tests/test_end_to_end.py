import os
import subprocess
import time
import shutil
import tempfile
import pytest
import requests

BASE_URL = "http://localhost:8000"

def _wait_for_app(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{BASE_URL}/docs")
            if r.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("backend did not start")

@pytest.fixture(scope="session")
def docker_stack():
    if shutil.which("docker-compose") is None:
        pytest.skip("docker-compose not available")
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    _wait_for_app()
    yield
    subprocess.run(["docker-compose", "down", "-v"], check=True)


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token(docker_stack):
    payload = {
        "email": "e2e@example.com",
        "password": "secret123",
        "country": "US",
        "annual_income": 50000,
        "timezone": "UTC",
    }
    resp = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
    assert resp.status_code == 201
    return resp.json()["data"]["access_token"]


@pytest.fixture
def daily_budget(user_token):
    answers = {"q1": "yes"}
    resp = requests.post(
        f"{BASE_URL}/api/onboarding/submit",
        json=answers,
        headers=_auth_header(user_token),
    )
    assert resp.status_code == 200
    return True


@pytest.fixture
def ocr_receipt(user_token):
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(b"test")
        tmp.flush()
        with open(tmp.name, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/transactions/receipt",
                headers=_auth_header(user_token),
                files={"file": ("r.jpg", f, "image/jpeg")},
            )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_end_to_end_flow(user_token, daily_budget, ocr_receipt):
    txn = {
        "category": "food",
        "amount": ocr_receipt.get("amount", 10.0),
        "spent_at": "2025-01-01T00:00:00Z",
    }
    resp = requests.post(
        f"{BASE_URL}/api/transactions/",
        json=txn,
        headers=_auth_header(user_token),
    )
    assert resp.status_code == 200

    subprocess.run(
        [
            "docker-compose",
            "exec",
            "backend",
            "python",
            "-c",
            "from app.services.core.engine.cron_task_ai_advice import run_ai_advice_batch; run_ai_advice_batch()",
        ],
        check=True,
    )
    resp = requests.get(
        f"{BASE_URL}/api/insights/",
        headers=_auth_header(user_token),
    )
    assert resp.status_code == 200

    subprocess.run(
        [
            "docker-compose",
            "exec",
            "backend",
            "python",
            "-c",
            "from app.services.core.engine.cron_task_subscription_refresh import refresh_premium_status; refresh_premium_status()",
        ],
        check=True,
    )
