"""Encrypted PII vault for reversible tokenization.

The vault maps sensitive values to deterministic pseudonym tokens so prompts can
be sent to LLM providers without exposing raw user PII. Authorized workflows
can later detokenize for compliance/audit purposes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional


DB_PATH = Path("data/pii_vault.db")
TOKEN_PREFIX = {
    "id": "ID",
    "phone": "PHONE",
    "email": "EMAIL",
    "name": "NAME",
    "location": "LOCATION",
    "organization": "ORG",
}


@dataclass
class VaultToken:
    token: str
    pii_type: str
    value_hash: str


class PIIVault:
    """SQLite-backed vault with authenticated encryption."""

    def __init__(self, db_path: Optional[Path] = None, secret: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        material = (secret or os.getenv("PII_VAULT_KEY", "dev-vault-key-change-me")).encode("utf-8")
        self._token_key = hashlib.sha256(material + b":token").digest()
        self._enc_key = hashlib.sha256(material + b":enc").digest()
        self._lock = Lock()
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
            CREATE TABLE IF NOT EXISTS vault_entries (
                token TEXT PRIMARY KEY,
                pii_type TEXT NOT NULL,
                value_hash TEXT NOT NULL UNIQUE,
                value_ciphertext TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                last_accessed_at TIMESTAMP,
                access_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
        conn.close()

    def _normalize(self, value: str, pii_type: str) -> str:
        text = (value or "").strip()
        if pii_type in {"id", "phone"}:
            return "".join(ch for ch in text if ch.isdigit())
        if pii_type in {"email", "name", "location", "organization"}:
            return text.lower()
        return text

    def _make_value_hash(self, value: str, pii_type: str) -> str:
        normalized = self._normalize(value, pii_type)
        payload = f"{pii_type}:{normalized}".encode("utf-8")
        return hmac.new(self._token_key, payload, hashlib.sha256).hexdigest()

    def _build_token(self, value_hash: str, pii_type: str) -> str:
        prefix = TOKEN_PREFIX.get(pii_type, pii_type.upper())
        return f"[{prefix}_{value_hash[:12].upper()}]"

    def _encrypt(self, plaintext: str) -> str:
        # Stream cipher based on HMAC-derived keystream + integrity tag.
        # This keeps dependencies minimal while preventing plaintext at rest.
        nonce = os.urandom(16)
        source = plaintext.encode("utf-8")
        stream = bytearray()
        counter = 0
        while len(stream) < len(source):
            block = hmac.new(self._enc_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            stream.extend(block)
            counter += 1
        cipher = bytes(a ^ b for a, b in zip(source, stream[: len(source)]))
        mac = hmac.new(self._enc_key, nonce + cipher, hashlib.sha256).digest()
        packed = nonce + cipher + mac
        return base64.urlsafe_b64encode(packed).decode("ascii")

    def _decrypt(self, packed_text: str) -> str:
        packed = base64.urlsafe_b64decode(packed_text.encode("ascii"))
        nonce = packed[:16]
        mac = packed[-32:]
        cipher = packed[16:-32]
        expected = hmac.new(self._enc_key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError("Vault ciphertext integrity check failed")
        stream = bytearray()
        counter = 0
        while len(stream) < len(cipher):
            block = hmac.new(self._enc_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            stream.extend(block)
            counter += 1
        plain = bytes(a ^ b for a, b in zip(cipher, stream[: len(cipher)]))
        return plain.decode("utf-8")

    def get_or_create_token(self, value: str, pii_type: str) -> VaultToken:
        value_hash = self._make_value_hash(value, pii_type)
        token = self._build_token(value_hash, pii_type)

        with self._lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT token FROM vault_entries WHERE value_hash = ?", (value_hash,))
            row = cur.fetchone()
            if row:
                conn.close()
                return VaultToken(token=row["token"], pii_type=pii_type, value_hash=value_hash)

            ciphertext = self._encrypt(value)
            cur.execute(
                """
                INSERT INTO vault_entries (token, pii_type, value_hash, value_ciphertext, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token, pii_type, value_hash, ciphertext, datetime.utcnow()),
            )
            conn.commit()
            conn.close()
        return VaultToken(token=token, pii_type=pii_type, value_hash=value_hash)

    def resolve_token(self, token: str) -> Optional[str]:
        with self._lock:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT value_ciphertext, access_count FROM vault_entries WHERE token = ?", (token,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            value = self._decrypt(row["value_ciphertext"])
            cur.execute(
                """
                UPDATE vault_entries
                SET access_count = ?, last_accessed_at = ?
                WHERE token = ?
                """,
                ((row["access_count"] or 0) + 1, datetime.utcnow(), token),
            )
            conn.commit()
            conn.close()
        return value


_VAULT: Optional[PIIVault] = None


def get_vault() -> PIIVault:
    global _VAULT
    if _VAULT is None:
        _VAULT = PIIVault()
    return _VAULT
