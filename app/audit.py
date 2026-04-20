"""Audit manager: persist high-priority security events to SQLite and provide query helpers."""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

DB_PATH = Path("data/audit_log.db")


class AuditManager:
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
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL,
                event_type TEXT NOT NULL,
                request_id TEXT,
                user_role TEXT,
                endpoint TEXT,
                message TEXT,
                count_id INTEGER DEFAULT 0,
                count_email INTEGER DEFAULT 0,
                count_phone INTEGER DEFAULT 0,
                forbidden_intents TEXT,
                metadata TEXT,
                signature TEXT,
                winning_tool TEXT,
                tool_a_counts TEXT,
                tool_b_counts TEXT,
                tool_c_counts TEXT
            )
            """
        )
        # If table existed prior, attempt to add missing columns for jury comparison
        cur.execute("PRAGMA table_info(audit_events)")
        cols = [r[1] for r in cur.fetchall()]
        
        if 'signature' not in cols:
            try:
                cur.execute("ALTER TABLE audit_events ADD COLUMN signature TEXT")
            except Exception:
                pass
        
        if 'winning_tool' not in cols:
            try:
                cur.execute("ALTER TABLE audit_events ADD COLUMN winning_tool TEXT")
            except Exception:
                pass
        
        if 'tool_a_counts' not in cols:
            try:
                cur.execute("ALTER TABLE audit_events ADD COLUMN tool_a_counts TEXT")
            except Exception:
                pass
        
        if 'tool_b_counts' not in cols:
            try:
                cur.execute("ALTER TABLE audit_events ADD COLUMN tool_b_counts TEXT")
            except Exception:
                pass
        
        if 'tool_c_counts' not in cols:
            try:
                cur.execute("ALTER TABLE audit_events ADD COLUMN tool_c_counts TEXT")
            except Exception:
                pass
        
        conn.commit()
        conn.close()

    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        """Return HMAC-SHA256 hex signature of the canonical JSON payload."""
        key = os.getenv('AUDIT_HMAC_KEY', 'audit-secret').encode('utf-8')
        # Canonical representation: sorted keys, compact separators, convert datetimes to ISO
        def _default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            return str(o)

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_default)
        mac = hmac.new(key, canonical.encode('utf-8'), hashlib.sha256)
        return mac.hexdigest()

    def record_event(self, event: Dict[str, Any]):
        """Insert an event dict into the audit_events table.

        Expected keys: event_type, ts (datetime), request_id, user_role, endpoint, message,
        count_id, count_email, count_phone, forbidden_intents, metadata (dict),
        winning_tool, tool_a_counts, tool_b_counts, tool_c_counts (optional)
        """
        # Build canonical payload for signing
        payload = {
            "ts": event.get("ts", datetime.utcnow()),
            "event_type": event.get("event_type"),
            "request_id": event.get("request_id"),
            "user_role": event.get("user_role"),
            "endpoint": event.get("endpoint"),
            "message": event.get("message"),
            "count_id": int(event.get("count_id", 0)),
            "count_email": int(event.get("count_email", 0)),
            "count_phone": int(event.get("count_phone", 0)),
            "forbidden_intents": list(event.get("forbidden_intents") or []),
            "metadata": event.get("metadata") or {},
            "winning_tool": event.get("winning_tool"),
        }
        signature = self._sign_payload(payload)

        # Serialize tool counts as JSON
        tool_a_counts = json.dumps(event.get("tool_a_counts")) if event.get("tool_a_counts") else None
        tool_b_counts = json.dumps(event.get("tool_b_counts")) if event.get("tool_b_counts") else None
        tool_c_counts = json.dumps(event.get("tool_c_counts")) if event.get("tool_c_counts") else None

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_events (ts, event_type, request_id, user_role, endpoint, message, count_id, count_email, count_phone, forbidden_intents, metadata, signature, winning_tool, tool_a_counts, tool_b_counts, tool_c_counts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ts"],
                payload["event_type"],
                payload["request_id"],
                payload["user_role"],
                payload["endpoint"],
                payload["message"],
                payload["count_id"],
                payload["count_email"],
                payload["count_phone"],
                (";".join(payload["forbidden_intents"]) if payload["forbidden_intents"] else None),
                json.dumps(payload["metadata"]),
                signature,
                payload["winning_tool"],
                tool_a_counts,
                tool_b_counts,
                tool_c_counts,
            ),
        )
        conn.commit()
        conn.close()

    def verify_integrity(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Verify HMAC signatures for audit events. Returns a dict with integrity_ok and tampered ids."""
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id, ts, event_type, request_id, user_role, endpoint, message, count_id, count_email, count_phone, forbidden_intents, metadata, signature FROM audit_events")
        rows = cur.fetchall()
        tampered = []
        for r in rows:
            row_dict = {
                "ts": r[1],
                "event_type": r[2],
                "request_id": r[3],
                "user_role": r[4],
                "endpoint": r[5],
                "message": r[6],
                "count_id": int(r[7] or 0),
                "count_email": int(r[8] or 0),
                "count_phone": int(r[9] or 0),
                "forbidden_intents": r[10].split(";") if r[10] else [],
                "metadata": json.loads(r[11] or "{}"),
            }
            expected_sig = r[12]
            if not expected_sig:
                tampered.append(r[0])
                continue
            actual_sig = self._sign_payload(row_dict)
            if not hmac.compare_digest(actual_sig, expected_sig):
                tampered.append(r[0])
        conn.close()
        return {"integrity_ok": (len(tampered) == 0), "tampered_ids": tampered}

    def summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        since = since or (datetime.utcnow() - timedelta(days=1))
        conn = self._connect()
        cur = conn.cursor()

        # Total blocked requests (SECURITY_DENIED) in the period
        cur.execute(
            "SELECT COUNT(*) as c FROM audit_events WHERE event_type = ? AND ts >= ?",
            ("SECURITY_DENIED", since),
        )
        total_blocked = cur.fetchone()[0]

        # Sum PII counts (PII_REDACTED)
        cur.execute(
            "SELECT SUM(count_id) as ids, SUM(count_email) as emails FROM audit_events WHERE event_type = ? AND ts >= ?",
            ("PII_REDACTED", since),
        )
        row = cur.fetchone()
        ids = row[0] or 0
        emails = row[1] or 0

        # Most frequent forbidden intents in period
        cur.execute(
            "SELECT forbidden_intents FROM audit_events WHERE event_type = ? AND ts >= ? AND forbidden_intents IS NOT NULL",
            ("SECURITY_DENIED", since),
        )
        intent_rows = cur.fetchall()
        intent_counts: Dict[str, int] = {}
        for r in intent_rows:
            fs = r[0]
            if not fs:
                continue
            for intent in fs.split(";"):
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

        # Sort intents by frequency
        frequent_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)

        conn.close()

        return {
            "total_blocked_last_24h": total_blocked,
            "pii_redacted_last_24h": {"malaysian_ic": ids, "emails": emails},
            "frequent_forbidden_intents": frequent_intents,
        }


# Singleton manager instance used by the logging handler
_MANAGER: Optional[AuditManager] = None


def get_manager() -> AuditManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = AuditManager()
    return _MANAGER


# Logging handler that forwards relevant LogRecords to the AuditManager
import logging
from datetime import datetime
import os
import hmac
import hashlib


class AuditHandler(logging.Handler):
    PRIORITY_EVENTS = {"SECURITY_DENIED", "PII_REDACTED", "LLM_TOKEN_USAGE"}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event_type = getattr(record, "event_type", None)
            if event_type not in self.PRIORITY_EVENTS:
                return

            mgr = get_manager()
            ev = {
                "ts": datetime.utcfromtimestamp(record.created),
                "event_type": event_type,
                "request_id": getattr(record, "request_id", None),
                "user_role": getattr(record, "user_role", None),
                "endpoint": getattr(record, "endpoint", None),
                "message": record.getMessage(),
            }

            counts = getattr(record, "counts", None)
            if counts:
                ev["count_id"] = counts.get("id", 0)
                ev["count_email"] = counts.get("email", 0)
                ev["count_phone"] = counts.get("phone", 0)

            forbidden = getattr(record, "forbidden_intents", None)
            if forbidden:
                ev["forbidden_intents"] = list(forbidden)

            # Attach raw metadata if present
            ev["metadata"] = getattr(record, "metadata", None) or {}

            mgr.record_event(ev)
        except Exception:
            self.handleError(record)


def init_audit_logging(app):
    handler = AuditHandler()
    logging.getLogger().addHandler(handler)
    # Also attach to app logger specifically
    app.logger.addHandler(handler)
