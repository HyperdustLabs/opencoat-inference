# OpenClaw Provider Adapter

This directory contains the OpenClaw provider adapter/plugin for OpenCOAT
Inference.

The adapter automates the setup steps that were previously manual:

- check the local OpenCOAT Inference sidecar
- install/reuse the provider Privy merchant wallet
- install/reuse the OpenClaw consumer Privy payer wallet
- grant local trial credit for ledger-mode demos
- print the OpenAI-compatible provider config OpenClaw should use
- run a smoke-test request through the sidecar

```text
OpenClaw
  -> OpenClaw tool plugin
  -> opencoat-inference openclaw bootstrap/status/smoke-test
  -> http://127.0.0.1:7888
  -> OpenCOAT Inference sidecar
```

## Start the Sidecar

Start OpenCOAT Inference:

```bash
uv sync --dev
uv run opencoat-inference init
uv run opencoat-inference serve
```

For real x402 + Privy, load `.env.local` before starting the server:

```bash
set -a
source .env.local
set +a
uv run opencoat-inference serve
```

## CLI Adapter

The Python CLI is the stable adapter surface. It can be used directly or through
the OpenClaw plugin:

```bash
uv run opencoat-inference openclaw bootstrap
uv run opencoat-inference openclaw status
uv run opencoat-inference openclaw config
uv run opencoat-inference openclaw smoke-test
```

`bootstrap` returns JSON containing the OpenClaw provider config:

```json
{
  "provider": "openai-compatible",
  "base_url": "http://127.0.0.1:7888/v1",
  "model": "opencoat-stub",
  "api_key": "not-required",
  "headers": {
    "x-opencoat-consumer-agent-id": "openclaw-local"
  }
}
```

Configure OpenClaw model routing to use:

```text
base_url: http://127.0.0.1:7888/v1
model: opencoat-stub
api_key: not-required
x-opencoat-consumer-agent-id: openclaw-local
```

## OpenClaw Plugin

This directory is also an OpenClaw simple tool plugin. Install it from the repo:

```bash
cd integrations/openclaw
npm install
npm run plugin:build
openclaw plugins install -l .
openclaw plugins enable opencoat-inference
openclaw gateway restart
```

In local source checkouts, point plugin tool calls at `uv run` by passing:

```json
{
  "cliCommand": "uv",
  "cliArgsPrefix": ["run"]
}
```

or export:

```bash
export OPENCOAT_INFERENCE_CLI=uv
export OPENCOAT_INFERENCE_CLI_ARGS=run
```

The plugin exposes these tools:

```text
opencoat_inference_provider_config
opencoat_inference_bootstrap
opencoat_inference_status
opencoat_inference_smoke_test
```

The tools return the same JSON as the CLI adapter. Wallet installation is
idempotent. If Privy credentials are not configured, bootstrap still returns
the OpenAI-compatible provider config and marks wallet steps as
`needs_configuration`.
