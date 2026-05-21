from __future__ import annotations

from typing import Protocol

import httpx

from .models import ChatCompletionRequest, InferenceProviderMetadata, ProviderPayment, ProviderReputation


class InferenceProvider(Protocol):
    id: str
    model = "opencoat-stub"

    def metadata(self) -> InferenceProviderMetadata: ...

    def complete(self, request: ChatCompletionRequest) -> str: ...


class StubInferenceProvider:
    id = "agent_opencoat_stub"
    model = "opencoat-stub"
    name = "OpenCOAT Stub Inference Agent"

    def metadata(self) -> InferenceProviderMetadata:
        return InferenceProviderMetadata(
            provider_agent_id=self.id,
            name=self.name,
            models=[self.model],
            capabilities=["chat"],
            payment=ProviderPayment(protocol="local-ledger", asset="USDC"),
            reputation=ProviderReputation(score=None, completed_requests=0),
        )

    def complete(self, request: ChatCompletionRequest) -> str:
        user_messages = [m.content for m in request.messages if m.role == "user"]
        prompt = user_messages[-1] if user_messages else ""
        return f"OpenCOAT Inference stub response: {prompt}"


StubInferenceAgent = StubInferenceProvider


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        id: str,
        name: str,
        base_url: str,
        api_key: str | None,
        model: str,
    ) -> None:
        self.id = id
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def metadata(self) -> InferenceProviderMetadata:
        return InferenceProviderMetadata(
            provider_agent_id=self.id,
            name=self.name,
            models=[self.model],
            capabilities=["chat"],
            payment=ProviderPayment(protocol="local-ledger", asset="USDC"),
            reputation=ProviderReputation(score=None, completed_requests=0),
        )

    def complete(self, request: ChatCompletionRequest) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, object] = {
            "model": self.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "stream": False,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = httpx.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"upstream LLM returned {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("upstream LLM request failed") from exc

        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("upstream LLM returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("upstream LLM returned invalid message content")
        return content
