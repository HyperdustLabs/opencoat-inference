from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    upstream_base_url: str | None = None
    upstream_api_key: str | None = None
    upstream_model: str = "opencoat-stub"
    upstream_provider_id: str = "agent_opencoat_upstream"
    upstream_provider_name: str = "OpenCOAT Upstream Inference Agent"
    payment_mode: str = "local-ledger"
    x402_facilitator_url: str | None = "https://x402.org/facilitator"
    x402_facilitator_bearer_token: str | None = None
    x402_pay_to: str | None = None
    x402_network: str = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
    x402_asset: str = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    x402_scheme: str = "exact"
    x402_fee_payer: str | None = "CKPKJWNdJEqa81x7CkZ14BVPiY6y16Sxs7owznqtWYp5"
    wallet_address: str | None = None
    privy_api_base_url: str = "https://api.privy.io"
    privy_app_id: str | None = None
    privy_app_secret: str | None = None
    privy_wallet_chain_type: str = "solana"
    consumer_wallet_provider: str = "privy"
    consumer_privy_owner_id: str = "opencoat-consumer"
    consumer_privy_wallet_id: str | None = None
    consumer_privy_wallet_address: str | None = None
    solana_payer_address: str | None = None
    solana_payer_keypair_path: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            upstream_base_url=os.getenv("OPENCOAT_UPSTREAM_BASE_URL"),
            upstream_api_key=os.getenv("OPENCOAT_UPSTREAM_API_KEY"),
            upstream_model=os.getenv("OPENCOAT_UPSTREAM_MODEL", "opencoat-stub"),
            upstream_provider_id=os.getenv(
                "OPENCOAT_UPSTREAM_PROVIDER_ID",
                "agent_opencoat_upstream",
            ),
            upstream_provider_name=os.getenv(
                "OPENCOAT_UPSTREAM_PROVIDER_NAME",
                "OpenCOAT Upstream Inference Agent",
            ),
            payment_mode=os.getenv("OPENCOAT_PAYMENT_MODE", "local-ledger"),
            x402_facilitator_url=os.getenv(
                "OPENCOAT_X402_FACILITATOR_URL",
                "https://x402.org/facilitator",
            ),
            x402_facilitator_bearer_token=os.getenv("OPENCOAT_X402_FACILITATOR_BEARER_TOKEN")
            or os.getenv("OPENCOAT_CDP_BEARER_TOKEN"),
            x402_pay_to=os.getenv("OPENCOAT_X402_PAY_TO"),
            x402_network=os.getenv(
                "OPENCOAT_X402_NETWORK",
                "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1",
            ),
            x402_asset=os.getenv(
                "OPENCOAT_X402_ASSET",
                "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
            ),
            x402_scheme=os.getenv("OPENCOAT_X402_SCHEME", "exact"),
            x402_fee_payer=os.getenv(
                "OPENCOAT_X402_FEE_PAYER",
                "CKPKJWNdJEqa81x7CkZ14BVPiY6y16Sxs7owznqtWYp5",
            ),
            wallet_address=os.getenv("OPENCOAT_WALLET_ADDRESS"),
            privy_api_base_url=os.getenv("OPENCOAT_PRIVY_API_BASE_URL", "https://api.privy.io"),
            privy_app_id=os.getenv("OPENCOAT_PRIVY_APP_ID"),
            privy_app_secret=os.getenv("OPENCOAT_PRIVY_APP_SECRET"),
            privy_wallet_chain_type=os.getenv("OPENCOAT_PRIVY_WALLET_CHAIN_TYPE", "solana"),
            consumer_wallet_provider=os.getenv("OPENCOAT_CONSUMER_WALLET_PROVIDER", "privy"),
            consumer_privy_owner_id=os.getenv(
                "OPENCOAT_CONSUMER_PRIVY_OWNER_ID",
                "opencoat-consumer",
            ),
            consumer_privy_wallet_id=os.getenv("OPENCOAT_CONSUMER_PRIVY_WALLET_ID"),
            consumer_privy_wallet_address=os.getenv("OPENCOAT_CONSUMER_PRIVY_WALLET_ADDRESS"),
            solana_payer_address=os.getenv("OPENCOAT_SOLANA_PAYER_ADDRESS"),
            solana_payer_keypair_path=os.getenv("OPENCOAT_SOLANA_PAYER_KEYPAIR_PATH"),
        )
