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


class LedgerStatus(StrEnum):
    accepted = "accepted"
    insufficient_funds = "insufficient_funds"


class LedgerDecision(BaseModel):
    status: LedgerStatus
    cost_usdc: float
    balance_usdc: float


class InferenceRecord(BaseModel):
    request_id: str
    model: str
    cost_usdc: float
    latency_ms: int
    status: str

