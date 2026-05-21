# OpenCOAT Inference

Trusted A2A inference access for local agents.

OpenCOAT Inference is the companion project to
[OpenCOAT Runtime](https://github.com/HyperdustLabs/OpenCOAT). The runtime
observes and governs agent thinking through joinpoints, pointcuts, advice, and
weaving. This repository focuses on the inference access layer:

```text
Local Agent
  -> OpenCOAT Inference sidecar
  -> service discovery / ledger / payment challenge
  -> trusted Inference Agent
  -> upstream LLM
```

The first MVP goal is narrow:

```text
An OpenClaw or OpenAI-compatible local agent can run without a human-managed
provider API key by pointing its model base URL at OpenCOAT Inference.
```

## Current Scope

- OpenAI-compatible endpoint for local agents.
- Local trial credit ledger.
- A default inference agent backed by a stub model for hermetic demos.
- Request history and balance inspection.
- x402-shaped payment challenge placeholder.

Out of scope for the first repo scaffold:

- Real embedded wallet onboarding.
- Real x402 settlement.
- ERC-8004 registry writes.
- Open marketplace onboarding.
- Multi-provider production routing.

## Quick Start

```bash
uv sync --dev
uv run opencoat-inference init
uv run opencoat-inference serve
```

In another shell:

```bash
curl -sS http://127.0.0.1:7888/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opencoat-stub",
    "messages": [
      {"role": "user", "content": "Say hello from OpenCOAT Inference"}
    ]
  }' | python -m json.tool
```

## Relationship To OpenCOAT Runtime

Keep the dependency direction one-way:

```text
opencoat-inference may integrate with OpenCOAT Runtime protocols and audit logs.
OpenCOAT Runtime should not depend on opencoat-inference.
```

Runtime integration points to add later:

- emit inference request/response joinpoints into OpenCOAT Runtime,
- write payment and model-selection metadata into the audit stream,
- allow concerns to influence model routing and spend policy.

