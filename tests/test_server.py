from fastapi.testclient import TestClient

from opencoat_inference.ledger import Ledger
from opencoat_inference.server import create_app


def test_chat_completion_charges_trial_credit(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.grant_trial()
    client = TestClient(create_app(ledger))

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "opencoat-stub",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["choices"][0]["message"]["content"].endswith("hello")
    assert body["opencoat"]["cost_usdc"] > 0
    assert ledger.balance() < 0.10


def test_chat_completion_returns_402_without_credit(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    client = TestClient(create_app(ledger))

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "opencoat-stub",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 402
    assert response.json()["detail"]["payment"] == "x402-placeholder"

