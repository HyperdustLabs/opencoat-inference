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
- Native A2A inference endpoint for explicit agent-to-agent calls.
- Provider discovery for the default inference agent.
- Local trial credit ledger.
- A default inference agent backed by a stub model for hermetic demos.
- Per-consumer request history and balance inspection.
- Structured x402 payment challenge headers.
- x402 v2 payment headers with optional facilitator verify/settle.
- Optional OpenAI-compatible upstream LLM provider.
- Wallet/payment receiver configuration endpoint.
- Atomic local ledger charge semantics for concurrent requests.
- OpenClaw provider adapter CLI and simple tool plugin.

Out of scope for the first repo scaffold:

- Real embedded wallet onboarding.
- Custodial wallet key management.
- ERC-8004 registry writes.
- Open marketplace onboarding.
- Multi-provider production routing.

## Quick Start

```bash
uv sync --dev
uv run opencoat-inference init
uv run opencoat-inference serve
```

For local secrets and external integration settings, copy values into
`.env.local` and load them before starting the server:

```bash
set -a
source .env.local
set +a
uv run opencoat-inference serve
```

In another shell:

```bash
curl -sS http://127.0.0.1:7888/v1/inference-agents | python3 -m json.tool
```

```bash
curl -sS http://127.0.0.1:7888/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "opencoat-stub",
    "messages": [
      {"role": "user", "content": "Say hello from OpenCOAT Inference"}
    ]
  }' | python3 -m json.tool
```

Native A2A request shape:

```bash
curl -sS http://127.0.0.1:7888/v1/a2a/inference \
  -H 'Content-Type: application/json' \
  -H 'x-opencoat-consumer-agent-id: local-agent' \
  -d '{
    "provider_agent_id": "agent_opencoat_stub",
    "model": "opencoat-stub",
    "input": "Say hello from native A2A inference",
    "max_price_usdc": 0.01
  }' | python3 -m json.tool
```

Inspect local state:

```bash
uv run opencoat-inference balance
uv run opencoat-inference history
uv run opencoat-inference wallet
uv run opencoat-inference openclaw status
curl -sS http://127.0.0.1:7888/v1/requests | python3 -m json.tool
```

Consumers can be isolated with `x-opencoat-consumer-agent-id`:

```bash
curl -sS http://127.0.0.1:7888/v1/trial-credit \
  -X POST \
  -H 'x-opencoat-consumer-agent-id: agent_consumer_demo'
```

## Real Upstream LLM

OpenCOAT Inference can route to any OpenAI-compatible upstream provider:

```bash
export OPENCOAT_UPSTREAM_BASE_URL="https://api.openai.com"
export OPENCOAT_UPSTREAM_API_KEY="..."
export OPENCOAT_UPSTREAM_MODEL="gpt-4.1-mini"
uv run opencoat-inference serve
```

Then request the configured model:

```bash
curl -sS http://127.0.0.1:7888/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4.1-mini",
    "messages": [
      {"role": "user", "content": "Use the real upstream model"}
    ]
  }' | python3 -m json.tool
```

The default `opencoat-stub` provider remains available for offline demos.

## x402 Mode

By default, the MVP uses the local trial-credit ledger. To require x402 payment
headers instead:

```bash
export OPENCOAT_PAYMENT_MODE="x402"
export OPENCOAT_WALLET_ADDRESS="YourSolanaMerchantAddress"
export OPENCOAT_X402_PAY_TO="YourSolanaMerchantAddress"
export OPENCOAT_X402_FACILITATOR_BEARER_TOKEN="..."
uv run opencoat-inference serve
```

The default x402 facilitator configuration targets the x402.org testnet
facilitator on Solana Devnet, which does not require CDP API keys:

```text
OPENCOAT_X402_FACILITATOR_URL=https://x402.org/facilitator
OPENCOAT_X402_NETWORK=solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1
OPENCOAT_X402_ASSET=4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
OPENCOAT_PRIVY_WALLET_CHAIN_TYPE=solana
```

`OPENCOAT_X402_FACILITATOR_BEARER_TOKEN` can also be provided as
`OPENCOAT_CDP_BEARER_TOKEN` when switching to Coinbase CDP:

```bash
export OPENCOAT_X402_FACILITATOR_URL="https://api.cdp.coinbase.com/platform/v2/x402"
export OPENCOAT_CDP_BEARER_TOKEN="..."
```

When a protected endpoint is called without payment, the server returns:

- HTTP `402`
- `PAYMENT-REQUIRED` header containing base64-encoded x402 payment requirements
- JSON body with the same challenge metadata for debugging

Clients retry with:

```text
PAYMENT-SIGNATURE: <base64 encoded x402 payment payload>
```

If `OPENCOAT_X402_FACILITATOR_URL` is set, OpenCOAT calls:

```text
POST {OPENCOAT_X402_FACILITATOR_URL}/verify
POST {OPENCOAT_X402_FACILITATOR_URL}/settle
```

and returns `PAYMENT-RESPONSE` with the base64-encoded settlement response.

## Privy Wallets

OpenCOAT can use Privy for wallet provisioning. There are two wallet roles:

```text
provider wallet
  receives x402 payments as merchant payTo

consumer wallet
  pays x402 requests and signs PAYMENT-SIGNATURE
```

Provider and consumer wallet installation are implemented. The CLI can also
perform a paid x402 call with a Privy consumer wallet.

Configure Privy REST credentials:

```bash
export OPENCOAT_PRIVY_APP_ID="..."
export OPENCOAT_PRIVY_APP_SECRET="..."
export OPENCOAT_PRIVY_WALLET_CHAIN_TYPE="solana"
export OPENCOAT_CONSUMER_WALLET_PROVIDER="privy"
export OPENCOAT_CONSUMER_PRIVY_OWNER_ID="opencoat-consumer"
```

Start the service, then provision the provider wallet:

```bash
curl -sS http://127.0.0.1:7888/v1/wallet/privy \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "owner_id": "opencoat-provider",
    "display_name": "OpenCOAT Provider"
}' | python3 -m json.tool
```

Agent wallet installation uses the same Privy provisioning path, keyed by
`agent_id`:

```bash
curl -sS http://127.0.0.1:7888/v1/agents/openclaw-local/wallet/install \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "consumer"
  }' | python3 -m json.tool
```

Check installation state:

```bash
curl -sS http://127.0.0.1:7888/v1/agents/openclaw-local/wallet \
  | python3 -m json.tool
```

The install call is idempotent. If Privy already has a wallet for the same
agent external id, OpenCOAT reuses it and records it locally.

Once the consumer wallet has devnet USDC and the merchant wallet can receive the
same token, the client can pay and call a protected endpoint in one command:

```bash
set -a
source .env.local
set +a

uv run opencoat-inference pay-and-call \
  --base-url http://127.0.0.1:7888 \
  --agent-id openclaw-local \
  --provider-agent-id agent_opencoat_stub \
  --model opencoat-stub \
  --input "Paid A2A inference"
```

This command performs:

```text
request protected endpoint
  -> receive 402 PAYMENT-REQUIRED
  -> create x402 Solana payment payload with the Privy consumer wallet
  -> retry with PAYMENT-SIGNATURE
  -> return inference response plus PAYMENT-RESPONSE
```

For Solana devnet, make sure the consumer and provider wallets have initialized
token accounts for:

```text
4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
```

## OpenClaw Provider Adapter

OpenClaw can use the sidecar as an OpenAI-compatible provider. The adapter
automates the setup and health checks:

```bash
uv run opencoat-inference openclaw bootstrap
uv run opencoat-inference openclaw config
uv run opencoat-inference openclaw smoke-test
```

The OpenClaw plugin wrapper lives in `integrations/openclaw` and exposes tools
for bootstrap, status, provider config, and smoke testing.

If the facilitator returns `transaction_simulation_failed` with
`InvalidAccountData`, the usual cause is a missing associated token account or
missing devnet USDC balance.

The wallet is stored in the local ledger and becomes the default x402 `payTo`
address when `OPENCOAT_X402_PAY_TO` and `OPENCOAT_WALLET_ADDRESS` are not set:

```bash
curl -sS http://127.0.0.1:7888/v1/wallet | python3 -m json.tool
```

Privy credentials are only read from environment variables. Do not commit them
to the repository.

## OpenClaw

The first OpenClaw integration scaffold is in:

```text
integrations/openclaw/
```

For the current MVP, configure OpenClaw as an OpenAI-compatible provider:

```text
base_url: http://127.0.0.1:7888/v1
model: opencoat-stub
api_key: not-required
```

When OpenClaw supports provider headers for this route, set:

```text
x-opencoat-consumer-agent-id: openclaw-local
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
