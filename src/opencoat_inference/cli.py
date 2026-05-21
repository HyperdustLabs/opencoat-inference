from __future__ import annotations

import json

import click
import httpx
import uvicorn

from .ledger import Ledger
from .openclaw import OpenClawProviderAdapter, OpenClawProviderConfig
from .payer import create_payment_signature_header
from .privy import PrivyClient
from .server import create_app
from .settings import Settings


@click.group()
def main() -> None:
    """OpenCOAT Inference local sidecar."""


@main.command()
def init() -> None:
    """Grant local trial credit."""
    balance = Ledger().grant_trial()
    click.echo(f"trial credit ready: {balance:.3f} USDC")


@main.command()
def balance() -> None:
    """Show local inference balance."""
    click.echo(f"{Ledger().balance():.3f} USDC")


@main.command()
@click.option("--limit", default=20, show_default=True)
def history(limit: int) -> None:
    """Show recent inference requests."""
    rows = [row.model_dump(mode="json") for row in Ledger().history(limit=limit)]
    click.echo(json.dumps(rows, indent=2))


@main.command()
def wallet() -> None:
    """Show wallet and x402 receiver configuration."""
    settings = Settings.from_env()
    click.echo(
        json.dumps(
            {
                "address": settings.wallet_address,
                "x402_pay_to": settings.x402_pay_to or settings.wallet_address,
                "network": settings.x402_network,
                "asset": settings.x402_asset,
                "payment_mode": settings.payment_mode,
                "facilitator_url": settings.x402_facilitator_url,
                "facilitator_auth_configured": bool(settings.x402_facilitator_bearer_token),
                "privy_configured": bool(settings.privy_app_id and settings.privy_app_secret),
                "privy_chain_type": settings.privy_wallet_chain_type,
                "consumer_wallet_provider": settings.consumer_wallet_provider,
                "consumer_privy_owner_id": settings.consumer_privy_owner_id,
                "consumer_privy_wallet_id": settings.consumer_privy_wallet_id,
                "consumer_privy_wallet_address": settings.consumer_privy_wallet_address,
                "solana_payer_address": settings.solana_payer_address,
                "solana_payer_keypair_path": settings.solana_payer_keypair_path,
            },
            indent=2,
        )
    )


@main.group()
def openclaw() -> None:
    """Automate OpenClaw provider adapter setup."""


def _openclaw_config(
    base_url: str,
    agent_id: str,
    model: str,
    provider_agent_id: str,
) -> OpenClawProviderConfig:
    return OpenClawProviderConfig(
        sidecar_url=base_url,
        consumer_agent_id=agent_id,
        model=model,
        provider_agent_id=provider_agent_id,
    )


@openclaw.command("config")
@click.option("--base-url", default="http://127.0.0.1:7888", show_default=True)
@click.option("--agent-id", default="openclaw-local", show_default=True)
@click.option("--model", default="opencoat-stub", show_default=True)
@click.option("--provider-agent-id", default="agent_opencoat_stub", show_default=True)
def openclaw_config(
    base_url: str,
    agent_id: str,
    model: str,
    provider_agent_id: str,
) -> None:
    """Print OpenClaw OpenAI-compatible provider configuration."""
    config = _openclaw_config(base_url, agent_id, model, provider_agent_id)
    click.echo(json.dumps(config.model_config(), indent=2))


@openclaw.command("status")
@click.option("--base-url", default="http://127.0.0.1:7888", show_default=True)
@click.option("--agent-id", default="openclaw-local", show_default=True)
@click.option("--model", default="opencoat-stub", show_default=True)
@click.option("--provider-agent-id", default="agent_opencoat_stub", show_default=True)
def openclaw_status(
    base_url: str,
    agent_id: str,
    model: str,
    provider_agent_id: str,
) -> None:
    """Check sidecar, wallet, provider, and OpenClaw routing readiness."""
    with OpenClawProviderAdapter(
        _openclaw_config(base_url, agent_id, model, provider_agent_id)
    ) as adapter:
        click.echo(json.dumps(adapter.status(), indent=2))


@openclaw.command("bootstrap")
@click.option("--base-url", default="http://127.0.0.1:7888", show_default=True)
@click.option("--agent-id", default="openclaw-local", show_default=True)
@click.option("--model", default="opencoat-stub", show_default=True)
@click.option("--provider-agent-id", default="agent_opencoat_stub", show_default=True)
@click.option("--provider-owner-id", default="opencoat-provider", show_default=True)
@click.option("--install-wallets/--no-install-wallets", default=True, show_default=True)
@click.option("--grant-trial/--no-grant-trial", default=True, show_default=True)
def openclaw_bootstrap(
    base_url: str,
    agent_id: str,
    model: str,
    provider_agent_id: str,
    provider_owner_id: str,
    install_wallets: bool,
    grant_trial: bool,
) -> None:
    """Install wallets, grant trial credit, and print OpenClaw provider config."""
    with OpenClawProviderAdapter(
        _openclaw_config(base_url, agent_id, model, provider_agent_id)
    ) as adapter:
        click.echo(
            json.dumps(
                adapter.bootstrap(
                    install_wallets=install_wallets,
                    grant_trial=grant_trial,
                    provider_owner_id=provider_owner_id,
                ),
                indent=2,
            )
        )


@openclaw.command("smoke-test")
@click.option("--base-url", default="http://127.0.0.1:7888", show_default=True)
@click.option("--agent-id", default="openclaw-local", show_default=True)
@click.option("--model", default="opencoat-stub", show_default=True)
@click.option("--provider-agent-id", default="agent_opencoat_stub", show_default=True)
@click.option("--input", "prompt", default="OpenClaw provider adapter smoke test", show_default=True)
def openclaw_smoke_test(
    base_url: str,
    agent_id: str,
    model: str,
    provider_agent_id: str,
    prompt: str,
) -> None:
    """Send one OpenAI-compatible request through the OpenCOAT sidecar."""
    with OpenClawProviderAdapter(
        _openclaw_config(base_url, agent_id, model, provider_agent_id)
    ) as adapter:
        click.echo(json.dumps(adapter.chat_completion(prompt), indent=2))


@main.command("pay-and-call")
@click.option("--base-url", default="http://127.0.0.1:7888", show_default=True)
@click.option("--agent-id", default=None, help="Consumer agent id that owns the payer wallet.")
@click.option("--provider-agent-id", default="agent_opencoat_stub", show_default=True)
@click.option("--model", default="opencoat-stub", show_default=True)
@click.option("--input", "prompt", required=True, help="Prompt for /v1/a2a/inference.")
def pay_and_call(
    base_url: str,
    agent_id: str | None,
    provider_agent_id: str,
    model: str,
    prompt: str,
) -> None:
    """Call a paid A2A endpoint using a Privy payer wallet."""
    settings = Settings.from_env()
    if not settings.privy_app_id or not settings.privy_app_secret:
        raise click.ClickException("OPENCOAT_PRIVY_APP_ID and OPENCOAT_PRIVY_APP_SECRET are required")

    owner_id = agent_id or settings.consumer_privy_owner_id
    stored_wallet = Ledger().wallet(owner_id, provider="privy")
    wallet_id = settings.consumer_privy_wallet_id or (
        stored_wallet["wallet_id"] if stored_wallet else None
    )
    wallet_address = settings.consumer_privy_wallet_address or (
        stored_wallet["address"] if stored_wallet else None
    )
    if not wallet_id or not wallet_address:
        raise click.ClickException(
            f"No Privy payer wallet found for {owner_id}. "
            f"Install it first with POST /v1/agents/{owner_id}/wallet/install."
        )

    privy = PrivyClient(
        app_id=settings.privy_app_id,
        app_secret=settings.privy_app_secret,
        base_url=settings.privy_api_base_url,
    )
    url = f"{base_url.rstrip('/')}/v1/a2a/inference"
    headers = {
        "Content-Type": "application/json",
        "x-opencoat-consumer-agent-id": owner_id,
    }
    payload = {
        "consumer_agent_id": owner_id,
        "provider_agent_id": provider_agent_id,
        "model": model,
        "input": prompt,
        "max_price_usdc": 0.01,
    }

    with httpx.Client(timeout=180) as client:
        first = client.post(url, headers=headers, json=payload)
        if first.status_code != 402:
            click.echo(json.dumps(first.json(), indent=2))
            return

        payment_required = first.headers.get("PAYMENT-REQUIRED")
        if not payment_required:
            raise click.ClickException("Server returned 402 without PAYMENT-REQUIRED header")

        payment_signature = create_payment_signature_header(
            payment_required_header=payment_required,
            wallet_id=wallet_id,
            wallet_address=wallet_address,
            privy=privy,
        )
        paid = client.post(
            url,
            headers={**headers, "PAYMENT-SIGNATURE": payment_signature},
            json=payload,
        )
        click.echo(json.dumps(paid.json(), indent=2))
        if paid.status_code >= 400:
            raise click.ClickException(f"paid request failed with HTTP {paid.status_code}")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7888, show_default=True)
def serve(host: str, port: int) -> None:
    """Run the local OpenAI-compatible inference sidecar."""
    uvicorn.run(create_app(), host=host, port=port)
