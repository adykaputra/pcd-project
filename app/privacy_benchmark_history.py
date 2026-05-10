"""Persistence and trend retrieval for privacy benchmark runs."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


DB_PATH = Path("data/privacy_benchmark.db")


class BenchmarkHistoryManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL,
                total_cases INTEGER NOT NULL,
                leak_rate REAL NOT NULL,
                utility_score REAL NOT NULL,
                latency_ms REAL NOT NULL,
                allow_count INTEGER NOT NULL,
                challenge_count INTEGER NOT NULL,
                block_count INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def record_run(self, benchmark: Dict[str, Any]) -> int:
        self._init_db()
        metrics = benchmark.get("metrics", {})
        policy_counts = metrics.get("policy_action_counts", {})
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO benchmark_runs (
                ts, total_cases, leak_rate, utility_score, latency_ms,
                allow_count, challenge_count, block_count, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow(),
                int(metrics.get("total_cases", 0)),
                float(metrics.get("core_pii_leak_rate", 0.0)),
                float(metrics.get("avg_utility_score", 0.0)),
                float(metrics.get("avg_latency_ms", 0.0)),
                int(policy_counts.get("allow", 0)),
                int(policy_counts.get("challenge", 0)),
                int(policy_counts.get("block", 0)),
                json.dumps(benchmark),
            ),
        )
        run_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        return run_id

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        self._init_db()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, ts, total_cases, leak_rate, utility_score, latency_ms, allow_count, challenge_count, block_count
            FROM benchmark_runs
            ORDER BY ts DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": int(row["id"]),
                "ts": row["ts"].isoformat() if hasattr(row["ts"], "isoformat") else str(row["ts"]),
                "total_cases": int(row["total_cases"]),
                "leak_rate": float(row["leak_rate"]),
                "utility_score": float(row["utility_score"]),
                "latency_ms": float(row["latency_ms"]),
                "allow_count": int(row["allow_count"]),
                "challenge_count": int(row["challenge_count"]),
                "block_count": int(row["block_count"]),
            }
            for row in rows
        ]


_MANAGER: Optional[BenchmarkHistoryManager] = None


def get_benchmark_history_manager() -> BenchmarkHistoryManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = BenchmarkHistoryManager()
    return _MANAGER
