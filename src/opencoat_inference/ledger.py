from __future__ import annotations

import sqlite3
from pathlib import Path
from time import time

from .models import InferenceRecord, LedgerDecision, LedgerStatus

DEFAULT_DB = Path.home() / ".opencoat-inference" / "ledger.sqlite3"
DEFAULT_CONSUMER_ID = "local-agent"
TRIAL_CREDIT_USDC = 0.10


class Ledger:
    def __init__(self, path: Path = DEFAULT_DB) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists balances (
                    consumer_id text primary key,
                    balance_usdc real not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists inference_records (
                    request_id text primary key,
                    consumer_id text not null,
                    provider_agent_id text not null default 'agent_opencoat_stub',
                    model text not null,
                    cost_usdc real not null,
                    latency_ms integer not null,
                    status text not null,
                    payment_protocol text not null default 'local-ledger',
                    created_at real not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists wallets (
                    owner_id text not null,
                    provider text not null,
                    wallet_id text not null,
                    address text not null,
                    chain_type text not null,
                    external_id text,
                    created_at real not null,
                    primary key (owner_id, provider)
                )
                """
            )
            self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("pragma table_info(inference_records)").fetchall()
        }
        if "provider_agent_id" not in columns:
            conn.execute(
                """
                alter table inference_records
                add column provider_agent_id text not null default 'agent_opencoat_stub'
                """
            )
        if "payment_protocol" not in columns:
            conn.execute(
                """
                alter table inference_records
                add column payment_protocol text not null default 'local-ledger'
                """
            )

    def grant_trial(self, consumer_id: str = DEFAULT_CONSUMER_ID) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "select balance_usdc from balances where consumer_id = ?",
                (consumer_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "insert into balances(consumer_id, balance_usdc) values (?, ?)",
                    (consumer_id, TRIAL_CREDIT_USDC),
                )
                return TRIAL_CREDIT_USDC
            return float(row["balance_usdc"])

    def balance(self, consumer_id: str = DEFAULT_CONSUMER_ID) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "select balance_usdc from balances where consumer_id = ?",
                (consumer_id,),
            ).fetchone()
            return 0.0 if row is None else float(row["balance_usdc"])

    def charge(self, cost_usdc: float, consumer_id: str = DEFAULT_CONSUMER_ID) -> LedgerDecision:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                update balances
                set balance_usdc = balance_usdc - ?
                where consumer_id = ?
                  and balance_usdc >= ?
                """,
                (cost_usdc, consumer_id, cost_usdc),
            )
            row = conn.execute(
                "select balance_usdc from balances where consumer_id = ?",
                (consumer_id,),
            ).fetchone()
            updated = 0.0 if row is None else float(row["balance_usdc"])
            if cursor.rowcount == 0:
                return LedgerDecision(
                    status=LedgerStatus.insufficient_funds,
                    cost_usdc=cost_usdc,
                    balance_usdc=updated,
                )
            return LedgerDecision(
                status=LedgerStatus.accepted,
                cost_usdc=cost_usdc,
                balance_usdc=updated,
            )

    def record(
        self,
        *,
        request_id: str,
        model: str,
        cost_usdc: float,
        latency_ms: int,
        status: str,
        provider_agent_id: str = "agent_opencoat_stub",
        payment_protocol: str = "local-ledger",
        consumer_id: str = DEFAULT_CONSUMER_ID,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into inference_records(
                    request_id, consumer_id, provider_agent_id, model, cost_usdc,
                    latency_ms, status, payment_protocol, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    consumer_id,
                    provider_agent_id,
                    model,
                    cost_usdc,
                    latency_ms,
                    status,
                    payment_protocol,
                    time(),
                ),
            )

    def history(
        self,
        limit: int = 20,
        consumer_id: str = DEFAULT_CONSUMER_ID,
    ) -> list[InferenceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select
                    request_id,
                    consumer_id,
                    provider_agent_id,
                    model,
                    cost_usdc,
                    latency_ms,
                    status,
                    payment_protocol,
                    created_at
                from inference_records
                where consumer_id = ?
                order by created_at desc
                limit ?
                """,
                (consumer_id, limit),
            ).fetchall()
            return [InferenceRecord(**dict(row)) for row in rows]

    def save_wallet(
        self,
        *,
        owner_id: str,
        provider: str,
        wallet_id: str,
        address: str,
        chain_type: str,
        external_id: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into wallets(
                    owner_id, provider, wallet_id, address, chain_type, external_id, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(owner_id, provider) do update set
                    wallet_id = excluded.wallet_id,
                    address = excluded.address,
                    chain_type = excluded.chain_type,
                    external_id = excluded.external_id
                """,
                (owner_id, provider, wallet_id, address, chain_type, external_id, time()),
            )

    def wallet(self, owner_id: str, provider: str = "privy") -> dict[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select owner_id, provider, wallet_id, address, chain_type, external_id
                from wallets
                where owner_id = ? and provider = ?
                """,
                (owner_id, provider),
            ).fetchone()
            return None if row is None else dict(row)
