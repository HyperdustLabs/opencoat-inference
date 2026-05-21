from __future__ import annotations

import json

import click
import uvicorn

from .ledger import Ledger
from .server import create_app


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
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7888, show_default=True)
def serve(host: str, port: int) -> None:
    """Run the local OpenAI-compatible inference sidecar."""
    uvicorn.run(create_app(), host=host, port=port)

