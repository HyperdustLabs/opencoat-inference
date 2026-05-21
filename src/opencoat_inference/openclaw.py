from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


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
        wallet = self._get("/v1/wallet")
        agent_wallet = self._get(f"/v1/agents/{self.config.consumer_agent_id}/wallet")
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

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.client.get(f"{self.sidecar_url}{path}", **kwargs)
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
