from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class PrivyWallet:
    id: str
    address: str
    chain_type: str
    external_id: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> PrivyWallet:
        return cls(
            id=str(data["id"]),
            address=str(data["address"]),
            chain_type=str(data["chain_type"]),
            external_id=data.get("external_id"),
        )


class PrivyClient:
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        base_url: str = "https://api.privy.io",
        client: httpx.Client | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=30)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "privy-app-id": self.app_id,
        }
        if idempotency_key:
            headers["privy-idempotency-key"] = idempotency_key
        return headers

    def list_wallets(
        self,
        *,
        chain_type: str | None = None,
        external_id: str | None = None,
    ) -> list[PrivyWallet]:
        params = {}
        if chain_type:
            params["chain_type"] = chain_type
        if external_id:
            params["external_id"] = external_id
        response = self.client.get(
            f"{self.base_url}/v1/wallets",
            auth=(self.app_id, self.app_secret),
            headers=self._headers(),
            params=params,
        )
        response.raise_for_status()
        return [PrivyWallet.from_api(wallet) for wallet in response.json().get("data", [])]

    def create_wallet(
        self,
        *,
        chain_type: str,
        external_id: str,
        display_name: str,
    ) -> PrivyWallet:
        response = self.client.post(
            f"{self.base_url}/v1/wallets",
            auth=(self.app_id, self.app_secret),
            headers=self._headers(idempotency_key=external_id),
            json={
                "chain_type": chain_type,
                "external_id": external_id,
                "display_name": display_name,
            },
        )
        response.raise_for_status()
        return PrivyWallet.from_api(response.json())

    def sign_solana_message(self, *, wallet_id: str, message_base64: str) -> bytes:
        response = self.client.post(
            f"{self.base_url}/v1/wallets/{wallet_id}/rpc",
            auth=(self.app_id, self.app_secret),
            headers=self._headers(),
            json={
                "method": "signMessage",
                "params": {
                    "message": message_base64,
                    "encoding": "base64",
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        signature = payload["data"]["signature"]
        import base64

        return base64.b64decode(signature)


def safe_external_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]", "-", value)
    return normalized[:64] or "opencoat-wallet"
