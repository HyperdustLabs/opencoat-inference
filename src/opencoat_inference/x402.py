from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"


def encode_header(value: dict[str, Any]) -> str:
    data = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.b64encode(data).decode()


def decode_header(value: str) -> dict[str, Any]:
    return json.loads(base64.b64decode(value).decode())


@dataclass(frozen=True)
class X402Config:
    facilitator_url: str | None
    pay_to: str | None
    network: str
    asset: str
    scheme: str


class X402FacilitatorClient:
    def __init__(
        self,
        base_url: str,
        bearer_token: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def verify(
        self,
        *,
        payment_payload: dict[str, Any],
        payment_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/verify",
            headers=self._headers(),
            json={
                "x402Version": 2,
                "paymentPayload": payment_payload,
                "paymentRequirements": payment_requirements,
            },
        )
        response.raise_for_status()
        return response.json()

    def settle(
        self,
        *,
        payment_payload: dict[str, Any],
        payment_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/settle",
            headers=self._headers(),
            json={
                "x402Version": 2,
                "paymentPayload": payment_payload,
                "paymentRequirements": payment_requirements,
            },
        )
        response.raise_for_status()
        return response.json()


def build_payment_required(
    *,
    config: X402Config,
    resource: str,
    description: str,
    amount_usdc: float,
    payment_intent_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    requirement_extra = {"name": "USDC", "version": "2"}
    if extra:
        requirement_extra.update(extra)
    return {
        "x402Version": 2,
        "paymentIntentId": payment_intent_id,
        "resource": {
            "url": resource,
            "description": description,
            "serviceName": "OpenCOAT Inference",
            "tags": ["inference", "a2a"],
        },
        "accepts": [
            {
                "scheme": config.scheme,
                "network": config.network,
                "asset": config.asset,
                "amount": str(int(amount_usdc * 1_000_000)),
                "payTo": config.pay_to,
                "maxTimeoutSeconds": 60,
                "extra": requirement_extra,
            }
        ],
    }


def select_payment_requirement(payment_required: dict[str, Any]) -> dict[str, Any]:
    accepts = payment_required.get("accepts")
    if not isinstance(accepts, list) or not accepts:
        raise ValueError("payment requirements must include accepts")
    requirement = accepts[0]
    if not isinstance(requirement, dict):
        raise ValueError("payment requirement must be an object")
    return requirement
