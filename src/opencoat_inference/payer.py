from __future__ import annotations

import base64
from dataclasses import dataclass

from solders.signature import Signature
from x402 import SchemeRegistration, parse_payment_required, x402ClientConfig, x402ClientSync
from x402.mechanisms.svm.exact import ExactSvmScheme

from .privy import PrivyClient
from .x402 import decode_header, encode_header


@dataclass
class PrivySvmKeypairAdapter:
    wallet_id: str
    privy: PrivyClient

    def sign_message(self, message: bytes) -> Signature:
        signature = self.privy.sign_solana_message(
            wallet_id=self.wallet_id,
            message_base64=base64.b64encode(message).decode(),
        )
        return Signature.from_bytes(signature)


@dataclass
class PrivySvmSigner:
    wallet_id: str
    address: str
    privy: PrivyClient

    @property
    def keypair(self) -> PrivySvmKeypairAdapter:
        return PrivySvmKeypairAdapter(wallet_id=self.wallet_id, privy=self.privy)


def create_payment_signature_header(
    *,
    payment_required_header: str,
    wallet_id: str,
    wallet_address: str,
    privy: PrivyClient,
) -> str:
    payment_required = parse_payment_required(decode_header(payment_required_header))
    client = x402ClientSync.from_config(
        x402ClientConfig(
            schemes=[
                SchemeRegistration(
                    network="solana:*",
                    client=ExactSvmScheme(
                        PrivySvmSigner(
                            wallet_id=wallet_id,
                            address=wallet_address,
                            privy=privy,
                        )
                    ),
                )
            ]
        )
    )
    payment_payload = client.create_payment_payload(payment_required)
    return encode_header(payment_payload.model_dump(mode="json", by_alias=True))
