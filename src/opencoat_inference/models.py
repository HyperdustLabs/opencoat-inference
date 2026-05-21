from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "opencoat-stub"
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    stream: bool = False
    consumer_agent_id: str | None = None
    provider_agent_id: str | None = None


class A2AInferenceRequest(BaseModel):
    input: str
    model: str = "opencoat-stub"
    consumer_agent_id: str | None = None
    provider_agent_id: str | None = None
    max_price_usdc: float | None = Field(default=None, ge=0.0)
    quality: str = "standard"
    latency: str = "normal"


class PrivyWalletProvisionRequest(BaseModel):
    owner_id: str = "opencoat-provider"
    external_id: str | None = None
    display_name: str = "OpenCOAT Inference Wallet"


class AgentWalletInstallRequest(BaseModel):
    role: Literal["consumer", "provider"] = "consumer"
    external_id: str | None = None
    display_name: str | None = None


class LedgerStatus(StrEnum):
    accepted = "accepted"
    insufficient_funds = "insufficient_funds"


class LedgerDecision(BaseModel):
    status: LedgerStatus
    cost_usdc: float
    balance_usdc: float


class ProviderPayment(BaseModel):
    protocol: str
    asset: str


class ProviderReputation(BaseModel):
    score: float | None = None
    completed_requests: int = 0


class InferenceProviderMetadata(BaseModel):
    provider_agent_id: str
    name: str
    models: list[str]
    capabilities: list[str]
    payment: ProviderPayment
    reputation: ProviderReputation


class PaymentChallenge(BaseModel):
    error: Literal["payment_required"] = "payment_required"
    payment_protocol: str
    payment_intent_id: str
    consumer_agent_id: str
    provider_agent_id: str
    amount_usdc: float
    balance_usdc: float
    asset: str = "USDC"
    next_action: str = "grant trial credit or complete x402 payment"
    header: str | None = None


class InferenceRecord(BaseModel):
    request_id: str
    consumer_id: str
    provider_agent_id: str
    model: str
    cost_usdc: float
    latency_ms: int
    status: str
    payment_protocol: str
    created_at: float
