from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from opencoat_inference.ledger import Ledger
from opencoat_inference.models import LedgerStatus
from opencoat_inference.privy import PrivyWallet
from opencoat_inference.server import create_app
from opencoat_inference.settings import Settings
from opencoat_inference.x402 import PAYMENT_REQUIRED_HEADER, decode_header


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
    assert body["opencoat"]["consumer_agent_id"] == "local-agent"
    assert body["opencoat"]["provider_agent_id"] == "agent_opencoat_stub"
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
    detail = response.json()["detail"]
    assert detail["error"] == "payment_required"
    assert detail["payment_protocol"] == "x402"
    assert detail["provider_agent_id"] == "agent_opencoat_stub"
    assert detail["payment_intent_id"].startswith("pi_")


def test_discovery_returns_stub_provider(tmp_path):
    client = TestClient(create_app(Ledger(tmp_path / "ledger.sqlite3")))

    response = client.get("/v1/inference-agents")

    assert response.status_code == 200
    agent = response.json()["agents"][0]
    assert agent["provider_agent_id"] == "agent_opencoat_stub"
    assert agent["models"] == ["opencoat-stub"]
    assert agent["payment"]["protocol"] == "local-ledger"


def test_consumer_header_scopes_balance_and_history(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    client = TestClient(create_app(ledger))

    headers = {"x-opencoat-consumer-agent-id": "agent_consumer_a"}
    credit = client.post("/v1/trial-credit", headers=headers)
    assert credit.status_code == 200
    assert credit.json()["consumer_id"] == "agent_consumer_a"

    response = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "opencoat-stub",
            "messages": [{"role": "user", "content": "scoped"}],
        },
    )
    assert response.status_code == 200

    history = client.get("/v1/requests", headers=headers)
    assert history.status_code == 200
    requests = history.json()["requests"]
    assert len(requests) == 1
    assert requests[0]["consumer_id"] == "agent_consumer_a"
    assert requests[0]["provider_agent_id"] == "agent_opencoat_stub"

    default_history = client.get("/v1/requests")
    assert default_history.status_code == 200
    assert default_history.json()["requests"] == []


def test_a2a_inference_uses_same_provider_runtime(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.grant_trial("agent_consumer_native")
    client = TestClient(create_app(ledger))

    response = client.post(
        "/v1/a2a/inference",
        json={
            "consumer_agent_id": "agent_consumer_native",
            "provider_agent_id": "agent_opencoat_stub",
            "model": "opencoat-stub",
            "input": "native hello",
            "max_price_usdc": 0.01,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"].endswith("native hello")
    assert body["consumer_agent_id"] == "agent_consumer_native"
    assert body["provider_agent_id"] == "agent_opencoat_stub"
    assert body["receipt"]["status"] == "settled"


def test_ledger_charge_is_atomic_for_same_consumer(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    ledger.grant_trial("agent_concurrent")

    def charge_once():
        return ledger.charge(0.01, consumer_id="agent_concurrent")

    with ThreadPoolExecutor(max_workers=8) as executor:
        decisions = list(executor.map(lambda _: charge_once(), range(20)))

    accepted = [d for d in decisions if d.status == LedgerStatus.accepted]
    rejected = [d for d in decisions if d.status == LedgerStatus.insufficient_funds]

    assert len(accepted) == 10
    assert len(rejected) == 10
    assert ledger.balance("agent_concurrent") < 0.001


def test_wallet_endpoint_reports_payment_configuration(tmp_path):
    settings = Settings(
        wallet_address="0xabc",
        x402_pay_to=None,
        payment_mode="x402",
    )
    client = TestClient(create_app(Ledger(tmp_path / "ledger.sqlite3"), settings=settings))

    response = client.get("/v1/wallet")

    assert response.status_code == 200
    assert response.json()["address"] == "0xabc"
    assert response.json()["x402_pay_to"] == "0xabc"
    assert response.json()["payment_mode"] == "x402"


def test_x402_mode_returns_payment_required_header(tmp_path):
    settings = Settings(
        payment_mode="x402",
        wallet_address="0xmerchant",
        x402_network="base-sepolia",
    )
    client = TestClient(create_app(Ledger(tmp_path / "ledger.sqlite3"), settings=settings))

    response = client.post(
        "/v1/a2a/inference",
        json={
            "provider_agent_id": "agent_opencoat_stub",
            "model": "opencoat-stub",
            "input": "paid hello",
        },
    )

    assert response.status_code == 402
    assert PAYMENT_REQUIRED_HEADER.lower() in response.headers
    payment_required = decode_header(response.headers[PAYMENT_REQUIRED_HEADER])
    assert payment_required["x402Version"] == 2
    assert payment_required["accepts"][0]["payTo"] == "0xmerchant"
    assert payment_required["accepts"][0]["network"] == "base-sepolia"


def test_configured_upstream_provider_is_discoverable(tmp_path):
    settings = Settings(
        upstream_base_url="https://llm.example",
        upstream_api_key="secret",
        upstream_model="real-model",
        upstream_provider_id="agent_real_provider",
    )
    client = TestClient(create_app(Ledger(tmp_path / "ledger.sqlite3"), settings=settings))

    response = client.get("/v1/inference-agents")

    assert response.status_code == 200
    agent_ids = {agent["provider_agent_id"] for agent in response.json()["agents"]}
    assert "agent_opencoat_stub" in agent_ids
    assert "agent_real_provider" in agent_ids


class FakePrivyClient:
    def __init__(self) -> None:
        self.wallets: list[PrivyWallet] = []

    def list_wallets(self, *, chain_type: str | None = None, external_id: str | None = None):
        return [
            wallet
            for wallet in self.wallets
            if (chain_type is None or wallet.chain_type == chain_type)
            and (external_id is None or wallet.external_id == external_id)
        ]

    def create_wallet(self, *, chain_type: str, external_id: str, display_name: str):
        wallet = PrivyWallet(
            id="wallet_123",
            address="0xprivy",
            chain_type=chain_type,
            external_id=external_id,
        )
        self.wallets.append(wallet)
        return wallet


def test_privy_wallet_can_be_provisioned_and_used_as_x402_pay_to(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    settings = Settings(
        privy_app_id="app_123",
        privy_app_secret="secret",
        payment_mode="x402",
    )
    client = TestClient(
        create_app(ledger, settings=settings, privy_client=FakePrivyClient())
    )

    provision = client.post(
        "/v1/wallet/privy",
        json={"owner_id": "opencoat-provider", "display_name": "OpenCOAT Provider"},
    )
    assert provision.status_code == 200
    assert provision.json()["address"] == "0xprivy"

    wallet = client.get("/v1/wallet")
    assert wallet.status_code == 200
    assert wallet.json()["x402_pay_to"] == "0xprivy"
    assert wallet.json()["provider"] == "privy"

    response = client.post(
        "/v1/a2a/inference",
        json={
            "provider_agent_id": "agent_opencoat_stub",
            "model": "opencoat-stub",
            "input": "paid hello",
        },
    )
    assert response.status_code == 402
    payment_required = decode_header(response.headers[PAYMENT_REQUIRED_HEADER])
    assert payment_required["accepts"][0]["payTo"] == "0xprivy"


def test_agent_can_install_privy_wallet_idempotently(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    settings = Settings(privy_app_id="app_123", privy_app_secret="secret")
    client = TestClient(
        create_app(ledger, settings=settings, privy_client=FakePrivyClient())
    )

    missing = client.get("/v1/agents/openclaw-local/wallet")
    assert missing.status_code == 200
    assert missing.json()["status"] == "not_installed"

    installed = client.post(
        "/v1/agents/openclaw-local/wallet/install",
        json={"role": "consumer"},
    )
    assert installed.status_code == 200
    assert installed.json()["agent_id"] == "openclaw-local"
    assert installed.json()["role"] == "consumer"
    assert installed.json()["status"] == "installed"
    assert installed.json()["existed"] is False
    assert installed.json()["address"] == "0xprivy"

    repeated = client.post(
        "/v1/agents/openclaw-local/wallet/install",
        json={"role": "consumer"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["existed"] is True
    assert repeated.json()["wallet_id"] == installed.json()["wallet_id"]

    status = client.get("/v1/agents/openclaw-local/wallet")
    assert status.status_code == 200
    assert status.json()["status"] == "installed"
    assert status.json()["address"] == "0xprivy"


def test_default_x402_config_uses_x402_org_solana_devnet(tmp_path):
    settings = Settings(payment_mode="x402", wallet_address="solana_merchant")
    client = TestClient(create_app(Ledger(tmp_path / "ledger.sqlite3"), settings=settings))

    response = client.post(
        "/v1/a2a/inference",
        json={
            "provider_agent_id": "agent_opencoat_stub",
            "model": "opencoat-stub",
            "input": "cdp solana devnet",
        },
    )

    assert response.status_code == 402
    payment_required = decode_header(response.headers[PAYMENT_REQUIRED_HEADER])
    accepted = payment_required["accepts"][0]
    assert accepted["network"] == "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
    assert accepted["asset"] == "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    assert accepted["amount"] == "1000"
    assert accepted["extra"]["feePayer"] == "CKPKJWNdJEqa81x7CkZ14BVPiY6y16Sxs7owznqtWYp5"
