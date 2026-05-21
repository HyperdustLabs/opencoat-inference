# OpenClaw Integration

This directory contains the first OpenClaw integration scaffold for OpenCOAT
Inference.

The MVP integration uses OpenAI-compatible routing:

```text
OpenClaw
  -> OpenAI-compatible provider config
  -> http://127.0.0.1:7888/v1
  -> OpenCOAT Inference
```

## Local Setup

Start OpenCOAT Inference:

```bash
uv sync --dev
uv run opencoat-inference init
uv run opencoat-inference serve
```

Configure OpenClaw to use:

```text
base_url: http://127.0.0.1:7888/v1
model: opencoat-stub
api_key: not-required
```

For per-agent ledger isolation, send this header from the OpenClaw provider
adapter when supported:

```text
x-opencoat-consumer-agent-id: openclaw-local
```

## Plugin Manifest

`openclaw.plugin.json` is intentionally minimal. It declares the local sidecar
configuration OpenClaw needs, but does not assume a specific OpenClaw runtime
plugin SDK implementation. The next step is to bind this manifest to OpenClaw's
provider plugin API once the target OpenClaw version and plugin entrypoint are
selected.
