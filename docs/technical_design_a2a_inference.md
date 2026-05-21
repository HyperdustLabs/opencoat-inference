# OpenCOAT A2A Inference Technical Design

## 1. Purpose

This document turns the product-level A2A inference PRD into an implementation
shape for this repository.

OpenCOAT Inference should not be a generic API-key proxy. It should expose a
trusted agent-to-agent inference access layer where a consumer agent can
discover, pay for, and call a provider inference agent.

The first implementation should remain small, but the boundaries should match
the final system:

```text
Consumer Agent
  -> OpenCOAT Inference sidecar
  -> service discovery / payment gate / ledger
  -> Provider Inference Agent
  -> upstream LLM
```

## 2. Goals

- Provide an OpenAI-compatible local endpoint for existing agent runtimes.
- Model inference providers as identifiable agents, not anonymous API keys.
- Track per-consumer balance, request history, provider identity, and cost.
- Make the ledger concurrency-safe before real payments are added.
- Leave stable seams for x402, wallet onboarding, registry, and reputation.
- Keep this repository focused on inference access, ledger, x402, wallet,
  discovery, and reputation concerns.

## 3. Non-goals

- Do not vendor OpenCOAT Runtime internals.
- Do not build a general human-facing API gateway.
- Do not implement marketplace onboarding in the first MVP.
- Do not require real on-chain settlement for local demos.
- Do not add multi-provider production routing before the provider runtime and
  ledger semantics are stable.

## 4. System Roles

### Consumer Agent

The local agent that needs LLM inference.

Examples:

- OpenClaw
- OpenAI-compatible local agent clients
- browser agents
- automation agents

Responsibilities:

- Identify itself to OpenCOAT Inference.
- Discover available inference providers.
- Submit inference requests.
- Authorize payment or consume trial credit.
- Receive results and optionally submit feedback.

### OpenCOAT Inference Sidecar

The local or hosted access layer in this repository.

Responsibilities:

- Expose OpenAI-compatible endpoints.
- Maintain local or hosted ledger state.
- Apply spend policy and concurrency policy.
- Perform provider discovery and selection for simple cases.
- Coordinate payment challenges.
- Store request history and audit metadata.

### Provider Inference Agent

The service agent that performs inference.

It may wrap:

- a hosted upstream LLM provider,
- local vLLM / Ollama / TGI,
- a specialized model,
- a third-party compliant model aggregator.

A provider inference agent must have a stable identity and service metadata:

```json
{
  "provider_agent_id": "agent_provider_default",
  "name": "OpenCOAT Default Inference Agent",
  "models": ["opencoat-stub"],
  "capabilities": ["chat"],
  "payment": {
    "protocol": "local-ledger",
    "asset": "USDC"
  },
  "reputation": {
    "score": null,
    "completed_requests": 0
  }
}
```

### OpenCOAT Control Plane

The later shared coordination layer.

Responsibilities:

- Provider registry.
- Agent identity.
- Reputation scoring.
- x402 facilitation.
- policy and risk metadata.

The current repo may include local placeholders for these functions, but should
not depend on OpenCOAT Runtime internals.

## 5. Protocol Shape

OpenCOAT should support two protocol surfaces:

1. OpenAI-compatible endpoints for immediate compatibility.
2. Native A2A endpoints for explicit discovery, payment, and provider metadata.

### OpenAI-compatible Surface

Existing local agents should be able to point their model base URL at this
sidecar:

```http
GET  /v1/models
POST /v1/chat/completions
```

The response should include OpenCOAT metadata without breaking OpenAI-compatible
clients:

```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "model": "opencoat-stub",
  "choices": [],
  "usage": {},
  "opencoat": {
    "request_id": "req_...",
    "consumer_agent_id": "agent_consumer_local",
    "provider_agent_id": "agent_provider_default",
    "cost_usdc": 0.001,
    "balance_usdc": 0.099,
    "payment": "local-ledger"
  }
}
```

### Native A2A Surface

The native surface should expose the agentic flow directly:

```http
GET  /v1/inference-agents
POST /v1/a2a/inference
GET  /v1/requests
GET  /v1/balance
POST /v1/trial-credit
```

The MVP can implement `GET /v1/inference-agents` and keep
`POST /v1/a2a/inference` as a later wrapper around the same provider runtime
used by `POST /v1/chat/completions`.

## 6. Request Lifecycle

The expected request lifecycle is:

```text
1. Consumer Agent sends an inference request.
2. Sidecar resolves consumer_agent_id.
3. Sidecar selects or validates provider_agent_id.
4. Sidecar estimates or assigns request cost.
5. Ledger atomically reserves or charges the cost.
6. Provider runtime accepts the request into its scheduler.
7. Provider adapter calls the upstream model.
8. Sidecar records final status, cost, latency, and provider metadata.
9. Response returns inference result plus OpenCOAT metadata.
10. Reputation and audit hooks receive request outcome metadata.
```

For local trial credit, reserve and charge may be the same operation. For real
x402, the sidecar should create a payment challenge before provider execution
and finalize settlement after verification.

## 7. Provider Runtime

The provider runtime should be explicit even when the only provider is the
current stub.

Recommended internal interfaces:

```text
InferenceProvider
  id
  metadata()
  complete(request, context) -> InferenceResult

ProviderRegistry
  list()
  get(provider_agent_id)

PaymentGate
  authorize(context, estimated_cost)
  finalize(request_id, actual_cost, status)

RequestScheduler
  acquire(context)
  release(context)
```

The current `StubInferenceAgent` should become one implementation of
`InferenceProvider`. Real upstream adapters should be added behind the same
interface.

## 8. Concurrency Model

Concurrency must be handled at three layers.

### HTTP Layer

FastAPI can accept concurrent requests. Endpoints that call upstream LLMs should
eventually be async so slow provider calls do not block the server worker.

### Ledger Layer

Ledger operations must be atomic. The current read-then-update pattern is not
sufficient once multiple requests can charge the same consumer at the same time.

The charge operation should use a single conditional update:

```sql
update balances
set balance_usdc = balance_usdc - ?
where consumer_id = ?
  and balance_usdc >= ?
```

Then the implementation should check the affected row count. If zero rows were
updated, the request is rejected with insufficient funds.

For x402, the equivalent operation is an atomic transition:

```text
payment_intent: created -> authorized -> settled
```

Each transition must be idempotent by `request_id` or `payment_intent_id`.

### Provider Layer

The provider runtime needs explicit scheduling limits:

```text
global inflight request limit
per-consumer inflight request limit
per-provider inflight request limit
per-model inflight request limit
queue timeout
upstream timeout
```

MVP defaults can be simple:

```text
global: 128
per consumer: 4
per provider: 64
per model: 32
queue timeout: 30s
upstream timeout: 120s
```

These limits should be configuration, not hardcoded policy.

## 9. Isolation Model

Isolation is required because multiple agents may share the same sidecar or
provider network.

### Identity Isolation

Every request should carry or resolve:

```text
consumer_agent_id
provider_agent_id
request_id
```

The current hardcoded `local-agent` is acceptable for the first demo, but should
be replaced by an explicit consumer context.

### Ledger Isolation

Balances and history must be scoped by `consumer_agent_id`.

No consumer should be able to read another consumer's balance, request history,
payment intents, or wallet metadata.

### Request Isolation

Each request must have its own context object:

```text
request_id
consumer_agent_id
provider_agent_id
model
deadline
payment state
audit metadata
```

Prompt messages and tool payloads must not be stored in process-global state.

### Provider Credential Isolation

Provider credentials and upstream API keys belong to the provider runtime, not
to the consumer agent.

Consumers should never see provider credentials, upstream account identifiers,
or raw upstream billing metadata unless explicitly exposed as an attested
receipt.

### Execution Isolation

The MVP may run providers in-process. Later stages should support worker or
container boundaries for third-party provider adapters.

Recommended future isolation levels:

```text
Level 0: in-process stub provider
Level 1: in-process trusted official provider adapter
Level 2: separate worker process per provider
Level 3: container or sandbox per third-party provider
Level 4: remote provider agent with signed metadata and x402 settlement
```

## 10. Failure Handling

Failures should be explicit and auditable.

Important cases:

- insufficient funds,
- payment challenge expired,
- provider unavailable,
- provider concurrency limit exceeded,
- queue timeout,
- upstream timeout,
- upstream error,
- client cancellation,
- malformed provider response.

Ledger behavior:

- If payment is charged before provider execution and provider execution fails,
  record failure and refund or release the reservation.
- If payment is authorized before execution, settle only after accepted
  execution.
- If the client cancels after provider execution starts, policy must decide
  whether the request is billable.

HTTP behavior:

```text
400 invalid request
402 payment required
408 queue or provider timeout
429 concurrency or rate limit
500 internal error
502 upstream provider error
503 provider unavailable
```

## 11. Data Model

The MVP data model should move toward these entities:

```text
consumer_agents
  consumer_agent_id
  display_name
  created_at

balances
  consumer_agent_id
  balance_usdc

provider_agents
  provider_agent_id
  name
  endpoint
  metadata_json
  status

inference_records
  request_id
  consumer_agent_id
  provider_agent_id
  model
  cost_usdc
  latency_ms
  status
  payment_protocol
  created_at

payment_intents
  payment_intent_id
  request_id
  consumer_agent_id
  provider_agent_id
  amount_usdc
  protocol
  status
  created_at
  updated_at
```

The current SQLite ledger can support the MVP, but schema changes should keep
the above target shape in mind.

## 12. Implementation Plan

### Step 1: Consumer Context

- Add an explicit `consumer_agent_id` concept.
- Keep `local-agent` as the default.
- Accept the consumer identity from a header or request field.
- Scope balance and history by consumer.

### Step 2: Atomic Ledger

- Replace read-then-update charge logic with an atomic conditional update.
- Add tests for concurrent charges against the same balance.
- Add failed request records where appropriate.

### Step 3: Provider Abstraction

- Introduce an `InferenceProvider` protocol.
- Convert `StubInferenceAgent` into `StubInferenceProvider`.
- Add provider metadata.
- Return `provider_agent_id` consistently.

### Step 4: Discovery Endpoint

- Add `GET /v1/inference-agents`.
- Return the stub provider metadata.
- Keep the structure compatible with later registry-backed discovery.

### Step 5: Request History Endpoint

- Add `GET /v1/requests`.
- Scope by consumer.
- Include provider, model, cost, latency, status, and timestamp.

### Step 6: Scheduler

- Add a minimal in-process scheduler.
- Enforce global and per-consumer concurrency limits.
- Return `429` for limit exhaustion or `408` for queue timeout.

### Step 7: Payment Challenge Placeholder

- Replace the string `x402-placeholder` with a structured payment challenge.
- Keep local-ledger trial credit as the first payment protocol.
- Add idempotent `payment_intent_id` semantics before real settlement.

## 13. Open Questions

- Which header should carry `consumer_agent_id` for OpenAI-compatible clients?
- Should native A2A requests use OpenAI message format or a task-oriented input
  schema?
- What is the minimum useful x402 challenge shape for local demos?
- Should trial credit be per machine, per wallet, or per consumer agent?
- How should prompt and response data be redacted in request history?
- Which provider metadata should be signed before third-party providers are
  allowed?
- What is the first real upstream provider adapter to implement?

## 14. Current Repository Mapping

Current files already map to the proposed architecture:

```text
src/opencoat_inference/server.py
  HTTP API and OpenAI-compatible surface

src/opencoat_inference/ledger.py
  local balance and request records

src/opencoat_inference/upstream.py
  current stub provider implementation

src/opencoat_inference/models.py
  API and ledger data models

src/opencoat_inference/cli.py
  local operator commands
```

The next code changes should be small and follow the implementation plan above.
