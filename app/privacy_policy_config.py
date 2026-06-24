"""Persistent threshold configuration for privacy policy engine."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


CONFIG_PATH = Path("data/privacy_policy_config.json")


def _default_thresholds() -> Dict[str, int]:
    return {"challenge_threshold": 45, "block_threshold": 80}


def load_policy_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_policy_thresholds() -> Dict[str, int]:
    config = load_policy_config()
    thresholds = config.get("thresholds") or {}
    challenge = int(thresholds.get("challenge_threshold", _default_thresholds()["challenge_threshold"]))
    block = int(thresholds.get("block_threshold", _default_thresholds()["block_threshold"]))
    if challenge >= block:
        return _default_thresholds()
    return {"challenge_threshold": challenge, "block_threshold": block}


def save_policy_thresholds(challenge_threshold: int, block_threshold: int, source: str = "manual") -> Dict[str, Any]:
    if challenge_threshold >= block_threshold:
        raise ValueError("challenge_threshold must be lower than block_threshold")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "thresholds": {
            "challenge_threshold": int(challenge_threshold),
            "block_threshold": int(block_threshold),
        },
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
