"""Auto-tune policy thresholds from observed production risk signals."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.audit import get_manager
from app.privacy_calibration import calibrate_policy_thresholds


def _percentile(values: List[int], p: float) -> int:
    if not values:
        return 0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * p))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return int(sorted_vals[idx])


def _extract_risk_score(event_type: str, metadata_raw: str) -> int | None:
    if not metadata_raw:
        return None
    try:
        metadata = json.loads(metadata_raw)
    except Exception:
        return None

    if isinstance(metadata, dict):
        risk = metadata.get("risk") or metadata.get("risk_assessment")
        if isinstance(risk, dict) and "risk_score" in risk:
            return int(risk["risk_score"])
        if "risk_score" in metadata:
            return int(metadata["risk_score"])
        if event_type == "PII_TOKENIZED":
            # Older logs may only store token_counts; use conservative proxy.
            token_counts = metadata.get("token_counts") or {}
            score = (
                int(token_counts.get("id", 0)) * 16
                + int(token_counts.get("phone", 0)) * 16
                + int(token_counts.get("email", 0)) * 16
                + int(token_counts.get("name", 0)) * 7
                + int(token_counts.get("location", 0)) * 7
            )
            return min(score, 100)
    return None


def recommend_thresholds_from_audit(hours: int = 24 * 7, min_samples: int = 10) -> Dict[str, Any]:
    """Recommend policy thresholds using recent audit telemetry."""
    mgr = get_manager()
    since = datetime.utcnow() - timedelta(hours=max(1, int(hours)))
    conn = mgr._connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT event_type, metadata
        FROM audit_events
        WHERE event_type IN (?, ?, ?)
          AND ts >= ?
        ORDER BY ts DESC
        """,
        ("PII_TOKENIZED", "PRIVACY_POLICY_CHALLENGE", "PRIVACY_POLICY_BLOCK", since),
    )
    rows = cur.fetchall()
    conn.close()

    allow_scores: List[int] = []
    challenge_scores: List[int] = []
    block_scores: List[int] = []

    for row in rows:
        event_type = row[0]
        score = _extract_risk_score(event_type, row[1])
        if score is None:
            continue
        if event_type == "PII_TOKENIZED":
            allow_scores.append(score)
        elif event_type == "PRIVACY_POLICY_CHALLENGE":
            challenge_scores.append(score)
        elif event_type == "PRIVACY_POLICY_BLOCK":
            block_scores.append(score)

    sample_count = len(allow_scores) + len(challenge_scores) + len(block_scores)
    if sample_count < min_samples:
        fallback = calibrate_policy_thresholds()
        fallback["source"] = "benchmark_fallback_insufficient_audit_samples"
        fallback["sample_count"] = sample_count
        fallback["sample_breakdown"] = {
            "allow_samples": len(allow_scores),
            "challenge_samples": len(challenge_scores),
            "block_samples": len(block_scores),
        }
        return fallback

    if allow_scores and challenge_scores:
        challenge_threshold = int(round((_percentile(allow_scores, 0.9) + _percentile(challenge_scores, 0.25)) / 2))
    elif challenge_scores:
        challenge_threshold = max(25, _percentile(challenge_scores, 0.2) - 5)
    else:
        challenge_threshold = max(30, _percentile(allow_scores, 0.95) + 5) if allow_scores else 45

    if challenge_scores and block_scores:
        block_threshold = int(round((_percentile(challenge_scores, 0.85) + _percentile(block_scores, 0.25)) / 2))
    elif block_scores:
        block_threshold = max(challenge_threshold + 10, _percentile(block_scores, 0.3) - 4)
    else:
        block_threshold = max(challenge_threshold + 15, 80)

    challenge_threshold = max(20, min(challenge_threshold, 85))
    block_threshold = max(challenge_threshold + 5, min(block_threshold, 98))

    return {
        "challenge_threshold": int(challenge_threshold),
        "block_threshold": int(block_threshold),
        "source": "audit_telemetry",
        "sample_count": sample_count,
        "sample_breakdown": {
            "allow_samples": len(allow_scores),
            "challenge_samples": len(challenge_scores),
            "block_samples": len(block_scores),
        },
        "distribution": {
            "allow_p90": _percentile(allow_scores, 0.9) if allow_scores else None,
            "challenge_p50": _percentile(challenge_scores, 0.5) if challenge_scores else None,
            "block_p25": _percentile(block_scores, 0.25) if block_scores else None,
        },
    }
