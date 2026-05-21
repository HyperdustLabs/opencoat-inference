from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from .ledger import Ledger
from .models import ChatCompletionRequest, LedgerStatus
from .upstream import StubInferenceAgent

REQUEST_COST_USDC = 0.001


def create_app(ledger: Ledger | None = None) -> FastAPI:
    app = FastAPI(title="OpenCOAT Inference", version="0.1.0")
    store = ledger or Ledger()
    agent = StubInferenceAgent()

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/v1/models")
    def models() -> dict[str, list[dict[str, str]]]:
        return {"data": [{"id": agent.model, "object": "model", "owned_by": "opencoat"}]}

    @app.get("/v1/balance")
    def balance() -> dict[str, float | str]:
        return {"consumer_id": "local-agent", "balance_usdc": store.balance()}

    @app.post("/v1/trial-credit")
    def trial_credit() -> dict[str, float | str]:
        return {"consumer_id": "local-agent", "balance_usdc": store.grant_trial()}

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatCompletionRequest) -> dict[str, object]:
        if request.stream:
            raise HTTPException(status_code=400, detail="streaming is not implemented in the MVP")

        decision = store.charge(REQUEST_COST_USDC)
        if decision.status == LedgerStatus.insufficient_funds:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "payment_required",
                    "cost_usdc": decision.cost_usdc,
                    "balance_usdc": decision.balance_usdc,
                    "payment": "x402-placeholder",
                },
            )

        request_id = f"chatcmpl-{uuid4().hex}"
        started = perf_counter()
        content = agent.complete(request)
        latency_ms = int((perf_counter() - started) * 1000)
        store.record(
            request_id=request_id,
            model=request.model,
            cost_usdc=decision.cost_usdc,
            latency_ms=latency_ms,
            status="success",
        )

        return {
            "id": request_id,
            "object": "chat.completion",
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "opencoat": {
                "provider_agent_id": agent.id,
                "cost_usdc": decision.cost_usdc,
                "balance_usdc": decision.balance_usdc,
                "payment": "local-ledger",
            },
        }

    return app


app = create_app()

