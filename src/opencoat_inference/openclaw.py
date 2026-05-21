from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .payer import create_payment_signature_header
from .privy import PrivyClient
from .settings import Settings
from .x402 import PAYMENT_REQUIRED_HEADER, PAYMENT_SIGNATURE_HEADER


def normalize_sidecar_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        return url[: -len("/v1")]
    return url


@dataclass(frozen=True)
class OpenClawProviderConfig:
    sidecar_url: str = "http://127.0.0.1:7888"
    model: str = "opencoat-stub"
    consumer_agent_id: str = "openclaw-local"
    provider_agent_id: str = "agent_opencoat_stub"

    @property
    def openai_base_url(self) -> str:
        return f"{normalize_sidecar_url(self.sidecar_url)}/v1"

    def model_config(self) -> dict[str, Any]:
        return {
            "provider": "openai-compatible",
            "base_url": self.openai_base_url,
            "model": self.model,
            "api_key": "not-required",
            "headers": {
                "x-opencoat-consumer-agent-id": self.consumer_agent_id,
            },
        }


class OpenClawProviderAdapter:
    def __init__(
        self,
        config: OpenClawProviderConfig | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or OpenClawProviderConfig()
        self.sidecar_url = normalize_sidecar_url(self.config.sidecar_url)
        self.client = client or httpx.Client(timeout=30)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> OpenClawProviderAdapter:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def provider_config(self) -> dict[str, Any]:
        return self.config.model_config()

    def status(self) -> dict[str, Any]:
        health = self._get("/health")
        wallet = self._get_optional("/v1/wallet")
        agent_wallet = self._get_optional(
            f"/v1/agents/{self.config.consumer_agent_id}/wallet"
        )
        balance = self._get(
            "/v1/balance",
            headers={"x-opencoat-consumer-agent-id": self.config.consumer_agent_id},
        )
        agents = self._get("/v1/inference-agents")
        return {
            "status": "ready" if health.get("ok") else "unhealthy",
            "sidecar_url": self.sidecar_url,
            "provider_config": self.provider_config(),
            "health": health,
            "wallet": wallet,
            "consumer_wallet": agent_wallet,
            "balance": balance,
            "inference_agents": agents.get("agents", []),
        }

    def bootstrap(
        self,
        *,
        install_wallets: bool = True,
        grant_trial: bool = True,
        provider_owner_id: str = "opencoat-provider",
    ) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        health = self._get("/health")
        steps.append({"name": "health", "status": "ok", "result": health})

        if install_wallets:
            steps.append(
                self._wallet_step(
                    "provider_wallet",
                    "/v1/wallet/privy",
                    {
                        "owner_id": provider_owner_id,
                        "display_name": "OpenCOAT Provider",
                    },
                )
            )
            steps.append(
                self._wallet_step(
                    "consumer_wallet",
                    f"/v1/agents/{self.config.consumer_agent_id}/wallet/install",
                    {
                        "role": "consumer",
                        "display_name": f"OpenCOAT consumer wallet for {self.config.consumer_agent_id}",
                    },
                )
            )

        if grant_trial:
            steps.append(
                {
                    "name": "trial_credit",
                    "status": "ok",
                    "result": self._post(
                        "/v1/trial-credit",
                        headers={"x-opencoat-consumer-agent-id": self.config.consumer_agent_id},
                    ),
                }
            )

        return {
            "status": self._bootstrap_status(steps),
            "sidecar_url": self.sidecar_url,
            "provider_config": self.provider_config(),
            "steps": steps,
        }

    def chat_completion(self, prompt: str) -> dict[str, Any]:
        return self._post(
            "/v1/chat/completions",
            headers={"x-opencoat-consumer-agent-id": self.config.consumer_agent_id},
            json={
                "model": self.config.model,
                "provider_agent_id": self.config.provider_agent_id,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

    def smoke_test(self, prompt: str) -> dict[str, Any]:
        wallet = self._get_optional("/v1/wallet")
        if wallet and wallet.get("payment_mode") == "x402":
            return self._chat_completion_with_x402_payment(prompt)
        return self.chat_completion(prompt)

    def _chat_completion_with_x402_payment(self, prompt: str) -> dict[str, Any]:
        settings = Settings.from_env()
        if not settings.privy_app_id or not settings.privy_app_secret:
            raise RuntimeError(
                "OPENCOAT_PRIVY_APP_ID and OPENCOAT_PRIVY_APP_SECRET are required for x402 smoke-test"
            )

        agent_wallet = self._get(f"/v1/agents/{self.config.consumer_agent_id}/wallet")
        if agent_wallet.get("status") != "installed":
            raise RuntimeError(
                f"Consumer wallet for {self.config.consumer_agent_id} is not installed. "
                "Run `opencoat-inference openclaw bootstrap` first."
            )

        wallet_id = settings.consumer_privy_wallet_id or agent_wallet.get("wallet_id")
        wallet_address = settings.consumer_privy_wallet_address or agent_wallet.get("address")
        if not wallet_id or not wallet_address:
            raise RuntimeError(
                f"No Privy payer wallet found for {self.config.consumer_agent_id}."
            )

        privy = PrivyClient(
            app_id=settings.privy_app_id,
            app_secret=settings.privy_app_secret,
            base_url=settings.privy_api_base_url,
        )
        headers = {"x-opencoat-consumer-agent-id": self.config.consumer_agent_id}
        payload = {
            "model": self.config.model,
            "provider_agent_id": self.config.provider_agent_id,
            "messages": [{"role": "user", "content": prompt}],
        }
        first = self.client.post(
            f"{self.sidecar_url}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        if first.status_code != 402:
            first.raise_for_status()
            return first.json()

        payment_required = first.headers.get(PAYMENT_REQUIRED_HEADER)
        if not payment_required:
            raise RuntimeError("Server returned 402 without PAYMENT-REQUIRED header")

        payment_signature = create_payment_signature_header(
            payment_required_header=payment_required,
            wallet_id=wallet_id,
            wallet_address=wallet_address,
            privy=privy,
        )
        paid = self.client.post(
            f"{self.sidecar_url}/v1/chat/completions",
            headers={**headers, PAYMENT_SIGNATURE_HEADER: payment_signature},
            json=payload,
        )
        paid.raise_for_status()
        return paid.json()

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.client.get(f"{self.sidecar_url}{path}", **kwargs)
        response.raise_for_status()
        return response.json()

    def _get_optional(self, path: str, **kwargs: Any) -> dict[str, Any] | None:
        response = self.client.get(f"{self.sidecar_url}{path}", **kwargs)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.client.post(f"{self.sidecar_url}{path}", **kwargs)
        response.raise_for_status()
        return response.json()

    def _wallet_step(self, name: str, path: str, json: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"{self.sidecar_url}{path}", json=json)
        if response.status_code == 400:
            detail = response.json().get("detail", response.text)
            return {
                "name": name,
                "status": "needs_configuration",
                "detail": detail,
            }
        response.raise_for_status()
        return {
            "name": name,
            "status": "ok",
            "result": response.json(),
        }

    @staticmethod
    def _bootstrap_status(steps: list[dict[str, Any]]) -> str:
        if any(step["status"] == "needs_configuration" for step in steps):
            return "ready_needs_wallet_configuration"
        return "ready"
