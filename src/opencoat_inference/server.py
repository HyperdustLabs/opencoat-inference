from __future__ import annotations

from time import perf_counter
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Response

from .ledger import DEFAULT_CONSUMER_ID, Ledger
from .models import (
    A2AInferenceRequest,
    AgentWalletInstallRequest,
    ChatCompletionRequest,
    ChatMessage,
    LedgerStatus,
    PaymentChallenge,
    PrivyWalletProvisionRequest,
)
from .privy import PrivyClient, safe_external_id
from .settings import Settings
from .upstream import InferenceProvider, OpenAICompatibleProvider, StubInferenceProvider
from .x402 import (
    PAYMENT_REQUIRED_HEADER,
    PAYMENT_RESPONSE_HEADER,
    PAYMENT_SIGNATURE_HEADER,
    X402Config,
    X402FacilitatorClient,
    build_payment_required,
    decode_header,
    encode_header,
    select_payment_requirement,
)

REQUEST_COST_USDC = 0.001


def create_app(
    ledger: Ledger | None = None,
    settings: Settings | None = None,
    privy_client: PrivyClient | None = None,
) -> FastAPI:
    app = FastAPI(title="OpenCOAT Inference", version="0.1.0")
    store = ledger or Ledger()
    config = settings or Settings.from_env()
    x402_config = X402Config(
        facilitator_url=config.x402_facilitator_url,
        pay_to=config.x402_pay_to or config.wallet_address,
        network=config.x402_network,
        asset=config.x402_asset,
        scheme=config.x402_scheme,
    )
    configured_privy_client = privy_client or (
        PrivyClient(
            app_id=config.privy_app_id,
            app_secret=config.privy_app_secret,
            base_url=config.privy_api_base_url,
        )
        if config.privy_app_id and config.privy_app_secret
        else None
    )
    x402_facilitator = (
        X402FacilitatorClient(
            config.x402_facilitator_url,
            bearer_token=config.x402_facilitator_bearer_token,
        )
        if config.x402_facilitator_url
        else None
    )
    providers: dict[str, InferenceProvider] = {}
    stub_provider = StubInferenceProvider()
    providers[stub_provider.id] = stub_provider
    if config.upstream_base_url:
        upstream_provider = OpenAICompatibleProvider(
            id=config.upstream_provider_id,
            name=config.upstream_provider_name,
            base_url=config.upstream_base_url,
            api_key=config.upstream_api_key,
            model=config.upstream_model,
        )
        providers[upstream_provider.id] = upstream_provider

    def resolve_consumer(
        request_consumer_id: str | None = None,
        header_consumer_id: str | None = None,
    ) -> str:
        return request_consumer_id or header_consumer_id or DEFAULT_CONSUMER_ID

    def resolve_provider(provider_agent_id: str | None, model: str) -> InferenceProvider:
        if provider_agent_id is not None:
            provider = providers.get(provider_agent_id)
            if provider is None:
                raise HTTPException(status_code=404, detail="provider_agent_id not found")
            if model not in provider.metadata().models:
                raise HTTPException(status_code=400, detail="model is not served by provider")
            return provider

        for provider in providers.values():
            if model in provider.metadata().models:
                return provider
        raise HTTPException(status_code=400, detail="model is not available")

    def payment_required(
        *,
        consumer_agent_id: str,
        provider_agent_id: str,
        cost_usdc: float,
        balance_usdc: float,
        resource: str,
    ) -> HTTPException:
        payment_intent_id = f"pi_{uuid4().hex}"
        pay_to = resolve_pay_to()
        dynamic_x402_config = X402Config(
            facilitator_url=x402_config.facilitator_url,
            pay_to=pay_to,
            network=x402_config.network,
            asset=x402_config.asset,
            scheme=x402_config.scheme,
        )
        payment_required_body = build_payment_required(
            config=dynamic_x402_config,
            resource=resource,
            description="OpenCOAT A2A inference request",
            amount_usdc=cost_usdc,
            payment_intent_id=payment_intent_id,
            extra={"feePayer": config.x402_fee_payer} if config.x402_fee_payer else None,
        )
        payment_required_header = encode_header(payment_required_body)
        challenge = PaymentChallenge(
            payment_protocol="x402",
            payment_intent_id=payment_intent_id,
            consumer_agent_id=consumer_agent_id,
            provider_agent_id=provider_agent_id,
            amount_usdc=cost_usdc,
            balance_usdc=balance_usdc,
            header=payment_required_header,
        )
        return HTTPException(
            status_code=402,
            detail=challenge.model_dump(mode="json"),
            headers={PAYMENT_REQUIRED_HEADER: payment_required_header},
        )

    def verify_x402_payment(
        *,
        payment_signature: str | None,
        resource: str,
        cost_usdc: float,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        if config.payment_mode != "x402":
            return None, None
        pay_to = resolve_pay_to()
        if not pay_to:
            raise HTTPException(status_code=500, detail="x402 pay_to address is not configured")

        dynamic_x402_config = X402Config(
            facilitator_url=x402_config.facilitator_url,
            pay_to=pay_to,
            network=x402_config.network,
            asset=x402_config.asset,
            scheme=x402_config.scheme,
        )
        payment_requirements = build_payment_required(
            config=dynamic_x402_config,
            resource=resource,
            description="OpenCOAT A2A inference request",
            amount_usdc=cost_usdc,
            payment_intent_id=f"pi_{uuid4().hex}",
            extra={"feePayer": config.x402_fee_payer} if config.x402_fee_payer else None,
        )
        if not payment_signature:
            header = encode_header(payment_requirements)
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "payment_required",
                    "payment_protocol": "x402",
                    "amount_usdc": cost_usdc,
                    "header": header,
                },
                headers={PAYMENT_REQUIRED_HEADER: header},
            )
        if x402_facilitator is None:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "payment_required",
                    "payment_protocol": "x402",
                    "message": "OPENCOAT_X402_FACILITATOR_URL is required to verify payment",
                },
                headers={PAYMENT_REQUIRED_HEADER: encode_header(payment_requirements)},
            )

        try:
            payment_payload = decode_header(payment_signature)
            selected_payment_requirement = select_payment_requirement(payment_requirements)
            verification = x402_facilitator.verify(
                payment_payload=payment_payload,
                payment_requirements=selected_payment_requirement,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=402,
                detail={"error": "x402_payment_verification_failed", "reason": str(exc)},
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "x402_payment_verification_failed",
                    "status_code": exc.response.status_code,
                    "response": exc.response.text,
                },
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=402,
                detail={"error": "x402_payment_verification_failed", "reason": str(exc)},
            ) from exc

        valid = verification.get("isValid", verification.get("valid", verification.get("success", False)))
        if valid is not True:
            raise HTTPException(status_code=402, detail=verification)
        return payment_payload, selected_payment_requirement

    def settle_x402_payment(
        *,
        payment_payload: dict[str, object] | None,
        payment_requirements: dict[str, object] | None,
        response: Response,
    ) -> None:
        if config.payment_mode != "x402" or payment_payload is None or payment_requirements is None:
            return
        if x402_facilitator is None:
            return
        try:
            settlement = x402_facilitator.settle(
                payment_payload=payment_payload,
                payment_requirements=payment_requirements,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=402, detail="x402 payment settlement failed") from exc
        response.headers[PAYMENT_RESPONSE_HEADER] = encode_header(settlement)

    def resolve_pay_to() -> str | None:
        if x402_config.pay_to:
            return x402_config.pay_to
        provider_wallet = store.wallet("opencoat-provider", provider="privy")
        if provider_wallet:
            return provider_wallet["address"]
        return None

    def install_privy_wallet(
        *,
        owner_id: str,
        external_id: str | None,
        display_name: str,
    ) -> dict[str, object]:
        if configured_privy_client is None:
            raise HTTPException(
                status_code=400,
                detail="OPENCOAT_PRIVY_APP_ID and OPENCOAT_PRIVY_APP_SECRET are required",
            )

        resolved_external_id = external_id or safe_external_id(f"opencoat-{owner_id}")
        wallets = configured_privy_client.list_wallets(
            chain_type=config.privy_wallet_chain_type,
            external_id=resolved_external_id,
        )
        existed = bool(wallets)
        wallet = wallets[0] if wallets else configured_privy_client.create_wallet(
            chain_type=config.privy_wallet_chain_type,
            external_id=resolved_external_id,
            display_name=display_name,
        )
        store.save_wallet(
            owner_id=owner_id,
            provider="privy",
            wallet_id=wallet.id,
            address=wallet.address,
            chain_type=wallet.chain_type,
            external_id=wallet.external_id,
        )
        return {
            "owner_id": owner_id,
            "provider": "privy",
            "wallet_id": wallet.id,
            "address": wallet.address,
            "chain_type": wallet.chain_type,
            "external_id": wallet.external_id or resolved_external_id,
            "status": "installed",
            "existed": existed,
        }

    def run_completion(
        *,
        request: ChatCompletionRequest,
        consumer_agent_id: str,
        provider: InferenceProvider,
        resource: str,
        payment_signature: str | None,
        response: Response,
    ) -> tuple[str, str, int, float]:
        payment_payload, payment_requirements = verify_x402_payment(
            payment_signature=payment_signature,
            resource=resource,
            cost_usdc=REQUEST_COST_USDC,
        )
        if config.payment_mode == "local-ledger":
            decision = store.charge(REQUEST_COST_USDC, consumer_id=consumer_agent_id)
            if decision.status == LedgerStatus.insufficient_funds:
                raise payment_required(
                    consumer_agent_id=consumer_agent_id,
                    provider_agent_id=provider.id,
                    cost_usdc=decision.cost_usdc,
                    balance_usdc=decision.balance_usdc,
                    resource=resource,
                )
            balance_usdc = decision.balance_usdc
            payment_protocol = "local-ledger"
        else:
            balance_usdc = store.balance(consumer_agent_id)
            payment_protocol = "x402"

        request_id = f"chatcmpl-{uuid4().hex}"
        started = perf_counter()
        content = provider.complete(request)
        latency_ms = int((perf_counter() - started) * 1000)
        settle_x402_payment(
            payment_payload=payment_payload,
            payment_requirements=payment_requirements,
            response=response,
        )
        store.record(
            request_id=request_id,
            consumer_id=consumer_agent_id,
            provider_agent_id=provider.id,
            model=request.model,
            cost_usdc=REQUEST_COST_USDC,
            latency_ms=latency_ms,
            status="success",
            payment_protocol=payment_protocol,
        )
        return request_id, content, latency_ms, balance_usdc

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/v1/models")
    def models() -> dict[str, list[dict[str, str]]]:
        data = []
        for provider in providers.values():
            metadata = provider.metadata()
            data.extend(
                {"id": model, "object": "model", "owned_by": metadata.provider_agent_id}
                for model in metadata.models
            )
        return {"data": data}

    @app.get("/v1/balance")
    def balance(
        x_opencoat_consumer_agent_id: str | None = Header(default=None),
    ) -> dict[str, float | str]:
        consumer_agent_id = resolve_consumer(header_consumer_id=x_opencoat_consumer_agent_id)
        return {
            "consumer_id": consumer_agent_id,
            "balance_usdc": store.balance(consumer_agent_id),
        }

    @app.get("/v1/wallet")
    def wallet() -> dict[str, str | None]:
        provider_wallet = store.wallet("opencoat-provider", provider="privy")
        return {
            "address": config.wallet_address,
            "x402_pay_to": resolve_pay_to(),
            "network": x402_config.network,
            "asset": x402_config.asset,
            "payment_mode": config.payment_mode,
            "provider": "privy" if provider_wallet else None,
            "wallet_id": provider_wallet["wallet_id"] if provider_wallet else None,
            "consumer_wallet_provider": config.consumer_wallet_provider,
            "consumer_privy_owner_id": config.consumer_privy_owner_id,
            "consumer_privy_wallet_id": config.consumer_privy_wallet_id,
            "consumer_privy_wallet_address": config.consumer_privy_wallet_address,
        }

    @app.post("/v1/wallet/privy")
    def provision_privy_wallet(request: PrivyWalletProvisionRequest) -> dict[str, object]:
        return install_privy_wallet(
            owner_id=request.owner_id,
            external_id=request.external_id,
            display_name=request.display_name,
        )

    @app.post("/v1/agents/{agent_id}/wallet/install")
    def install_agent_wallet(
        agent_id: str,
        request: AgentWalletInstallRequest,
    ) -> dict[str, object]:
        display_name = request.display_name or f"OpenCOAT {request.role} wallet for {agent_id}"
        result = install_privy_wallet(
            owner_id=agent_id,
            external_id=request.external_id,
            display_name=display_name,
        )
        result["agent_id"] = agent_id
        result["role"] = request.role
        return result

    @app.get("/v1/agents/{agent_id}/wallet")
    def agent_wallet(agent_id: str) -> dict[str, str | None]:
        wallet = store.wallet(agent_id, provider="privy")
        if wallet is None:
            return {
                "agent_id": agent_id,
                "provider": "privy",
                "status": "not_installed",
                "wallet_id": None,
                "address": None,
                "chain_type": None,
                "external_id": None,
            }
        return {
            "agent_id": agent_id,
            "provider": wallet["provider"],
            "status": "installed",
            "wallet_id": wallet["wallet_id"],
            "address": wallet["address"],
            "chain_type": wallet["chain_type"],
            "external_id": wallet["external_id"],
        }

    @app.post("/v1/trial-credit")
    def trial_credit(
        x_opencoat_consumer_agent_id: str | None = Header(default=None),
    ) -> dict[str, float | str]:
        consumer_agent_id = resolve_consumer(header_consumer_id=x_opencoat_consumer_agent_id)
        return {
            "consumer_id": consumer_agent_id,
            "balance_usdc": store.grant_trial(consumer_agent_id),
        }

    @app.get("/v1/inference-agents")
    def inference_agents() -> dict[str, list[dict[str, object]]]:
        agents = []
        for provider in providers.values():
            metadata = provider.metadata().model_dump(mode="json")
            metadata["payment"] = {
                "protocol": config.payment_mode,
                "asset": config.x402_asset,
            }
            agents.append(metadata)
        return {
            "agents": agents,
        }

    @app.get("/v1/requests")
    def requests(
        limit: int = 20,
        x_opencoat_consumer_agent_id: str | None = Header(default=None),
    ) -> dict[str, list[dict[str, object]]]:
        consumer_agent_id = resolve_consumer(header_consumer_id=x_opencoat_consumer_agent_id)
        rows = store.history(limit=limit, consumer_id=consumer_agent_id)
        return {"requests": [row.model_dump(mode="json") for row in rows]}

    @app.post("/v1/chat/completions")
    def chat_completions(
        request: ChatCompletionRequest,
        response: Response,
        x_opencoat_consumer_agent_id: str | None = Header(default=None),
        payment_signature: str | None = Header(default=None, alias=PAYMENT_SIGNATURE_HEADER),
    ) -> dict[str, object]:
        if request.stream:
            raise HTTPException(status_code=400, detail="streaming is not implemented in the MVP")

        consumer_agent_id = resolve_consumer(
            request_consumer_id=request.consumer_agent_id,
            header_consumer_id=x_opencoat_consumer_agent_id,
        )
        provider = resolve_provider(request.provider_agent_id, request.model)
        request_id, content, _latency_ms, balance_usdc = run_completion(
            request=request,
            consumer_agent_id=consumer_agent_id,
            provider=provider,
            resource="/v1/chat/completions",
            payment_signature=payment_signature,
            response=response,
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
                "request_id": request_id,
                "consumer_agent_id": consumer_agent_id,
                "provider_agent_id": provider.id,
                "cost_usdc": REQUEST_COST_USDC,
                "balance_usdc": balance_usdc,
                "payment": config.payment_mode,
            },
        }

    @app.post("/v1/a2a/inference")
    def a2a_inference(
        request: A2AInferenceRequest,
        response: Response,
        x_opencoat_consumer_agent_id: str | None = Header(default=None),
        payment_signature: str | None = Header(default=None, alias=PAYMENT_SIGNATURE_HEADER),
    ) -> dict[str, object]:
        if request.max_price_usdc is not None and request.max_price_usdc < REQUEST_COST_USDC:
            raise HTTPException(status_code=400, detail="max_price_usdc is below provider price")

        consumer_agent_id = resolve_consumer(
            request_consumer_id=request.consumer_agent_id,
            header_consumer_id=x_opencoat_consumer_agent_id,
        )
        provider = resolve_provider(request.provider_agent_id, request.model)
        chat_request = ChatCompletionRequest(
            model=request.model,
            messages=[ChatMessage(role="user", content=request.input)],
            consumer_agent_id=consumer_agent_id,
            provider_agent_id=provider.id,
        )
        request_id, content, latency_ms, balance_usdc = run_completion(
            request=chat_request,
            consumer_agent_id=consumer_agent_id,
            provider=provider,
            resource="/v1/a2a/inference",
            payment_signature=payment_signature,
            response=response,
        )
        return {
            "request_id": request_id,
            "result": content,
            "provider_agent_id": provider.id,
            "consumer_agent_id": consumer_agent_id,
            "model": request.model,
            "cost_usdc": REQUEST_COST_USDC,
            "balance_usdc": balance_usdc,
            "latency_ms": latency_ms,
            "receipt": {
                "payment": config.payment_mode,
                "status": "settled",
            },
        }

    return app


app = create_app()
