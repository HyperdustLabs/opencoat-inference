from __future__ import annotations

from .models import ChatCompletionRequest


class StubInferenceAgent:
    id = "agent_opencoat_stub"
    model = "opencoat-stub"

    def complete(self, request: ChatCompletionRequest) -> str:
        user_messages = [m.content for m in request.messages if m.role == "user"]
        prompt = user_messages[-1] if user_messages else ""
        return f"OpenCOAT Inference stub response: {prompt}"

