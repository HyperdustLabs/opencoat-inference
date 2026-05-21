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
        conn = sqlite3.connect(self.path)
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
                    model text not null,
                    cost_usdc real not null,
                    latency_ms integer not null,
                    status text not null,
                    created_at real not null
                )
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
            current = self.balance(consumer_id)
            if current < cost_usdc:
                return LedgerDecision(
                    status=LedgerStatus.insufficient_funds,
                    cost_usdc=cost_usdc,
                    balance_usdc=current,
                )
            updated = current - cost_usdc
            conn.execute(
                "update balances set balance_usdc = ? where consumer_id = ?",
                (updated, consumer_id),
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
        consumer_id: str = DEFAULT_CONSUMER_ID,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into inference_records(
                    request_id, consumer_id, model, cost_usdc, latency_ms, status, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, consumer_id, model, cost_usdc, latency_ms, status, time()),
            )

    def history(self, limit: int = 20) -> list[InferenceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select request_id, model, cost_usdc, latency_ms, status
                from inference_records
                order by created_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()
            return [InferenceRecord(**dict(row)) for row in rows]

