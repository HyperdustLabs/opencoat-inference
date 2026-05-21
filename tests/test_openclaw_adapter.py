import json

import httpx

from opencoat_inference.openclaw import OpenClawProviderAdapter, OpenClawProviderConfig


def json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=data)


def request_json(request: httpx.Request) -> dict | None:
    return json.loads(request.content) if request.content else None


def test_openclaw_provider_config_normalizes_v1_base_url():
    config = OpenClawProviderConfig(
        sidecar_url="http://127.0.0.1:7888/v1",
        consumer_agent_id="openclaw-local",
        model="opencoat-stub",
    )

    assert config.model_config() == {
        "provider": "openai-compatible",
        "base_url": "http://127.0.0.1:7888/v1",
        "model": "opencoat-stub",
        "api_key": "not-required",
        "headers": {"x-opencoat-consumer-agent-id": "openclaw-local"},
    }


def test_openclaw_bootstrap_installs_wallets_and_grants_credit():
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request_json(request)
        seen.append((request.method, request.url.path, body))
        if request.url.path == "/health":
            return json_response({"ok": True})
        if request.url.path == "/v1/wallet/privy":
            return json_response({"status": "installed", "owner_id": "opencoat-provider"})
        if request.url.path == "/v1/agents/openclaw-local/wallet/install":
            return json_response({"status": "installed", "agent_id": "openclaw-local"})
        if request.url.path == "/v1/trial-credit":
            return json_response({"consumer_id": "openclaw-local", "balance_usdc": 0.1})
        return json_response({"error": "not found"}, status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = OpenClawProviderAdapter(
        OpenClawProviderConfig(consumer_agent_id="openclaw-local"),
        client=client,
    )

    result = adapter.bootstrap()

    assert result["status"] == "ready"
    assert [step["name"] for step in result["steps"]] == [
        "health",
        "provider_wallet",
        "consumer_wallet",
        "trial_credit",
    ]
    assert (
        "POST",
        "/v1/agents/openclaw-local/wallet/install",
        {
            "role": "consumer",
            "display_name": "OpenCOAT consumer wallet for openclaw-local",
        },
    ) in seen


def test_openclaw_bootstrap_reports_missing_privy_without_hiding_provider_config():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return json_response({"ok": True})
        if request.url.path in {
            "/v1/wallet/privy",
            "/v1/agents/openclaw-local/wallet/install",
        }:
            return json_response(
                {"detail": "OPENCOAT_PRIVY_APP_ID and OPENCOAT_PRIVY_APP_SECRET are required"},
                status_code=400,
            )
        if request.url.path == "/v1/trial-credit":
            return json_response({"consumer_id": "openclaw-local", "balance_usdc": 0.1})
        return json_response({"error": "not found"}, status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = OpenClawProviderAdapter(client=client)

    result = adapter.bootstrap()

    assert result["status"] == "ready_needs_wallet_configuration"
    assert result["provider_config"]["base_url"] == "http://127.0.0.1:7888/v1"
    wallet_steps = [step for step in result["steps"] if step["name"].endswith("_wallet")]
    assert {step["status"] for step in wallet_steps} == {"needs_configuration"}


def test_openclaw_smoke_test_sends_consumer_header():
    captured_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        assert request.url.path == "/v1/chat/completions"
        assert request_json(request)["provider_agent_id"] == "agent_opencoat_stub"
        return json_response({"id": "chatcmpl_123", "choices": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = OpenClawProviderAdapter(client=client)

    result = adapter.chat_completion("hello")

    assert result["id"] == "chatcmpl_123"
    assert captured_headers["x-opencoat-consumer-agent-id"] == "openclaw-local"
