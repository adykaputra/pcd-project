"""Risk scoring and policy decisions for the LLM privacy firewall."""
from __future__ import annotations

import os
import re
from typing import Dict, Any, List

from app.module2.logic import detect_pii_counts


OBFUSCATED_EMAIL_RE = re.compile(
    r"\b[a-z0-9._%+-]+\s*(?:\(\s*at\s*\)|\[\s*at\s*\]| at )\s*[a-z0-9.-]+\s*(?:\(\s*dot\s*\)|\[\s*dot\s*\]| dot )\s*[a-z]{2,}\b",
    re.IGNORECASE,
)
# Obfuscation patterns intentionally exclude common standard formats (e.g. 012-3456789).
SPLIT_PHONE_RE = re.compile(r"(?:\d[\s\.]){8,}\d")
SPLIT_ID_RE = re.compile(r"\b\d{6}[\s/_.]\d{2}[\s/_.]\d{4}\b")
SENSITIVE_INTENT_RE = re.compile(
    r"(?:exfiltrate|dump database|steal|leak|other users data|bypass privacy|raw pii)",
    re.IGNORECASE,
)


def _threshold(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _rate_confidence(signal_count: int) -> float:
    # Monotonic confidence scale for explainability.
    return min(0.99, round(0.45 + signal_count * 0.06, 3))


def evaluate_prompt_risk(
    original_prompt: str,
    tokenization: Dict[str, Any],
    tokenized_prompt: str,
    challenge_threshold: int | None = None,
    block_threshold: int | None = None,
) -> Dict[str, Any]:
    """Calculate privacy risk score and policy action for an inbound prompt."""
    token_counts = tokenization.get("token_counts", {})
    core_count = (
        int(token_counts.get("id", 0))
        + int(token_counts.get("phone", 0))
        + int(token_counts.get("email", 0))
    )
    contextual_count = int(token_counts.get("name", 0)) + int(token_counts.get("location", 0))
    ner_person = int(token_counts.get("ner_person", 0))
    ner_location = int(token_counts.get("ner_location", 0))
    ner_organization = int(token_counts.get("ner_organization", 0))
    ner_count = ner_person + ner_location + ner_organization
    obfuscated_email = len(OBFUSCATED_EMAIL_RE.findall(original_prompt or ""))
    split_phone = len(SPLIT_PHONE_RE.findall(original_prompt or ""))
    split_id = len(SPLIT_ID_RE.findall(original_prompt or ""))
    sensitive_intent = len(SENSITIVE_INTENT_RE.findall(original_prompt or ""))
    residual = detect_pii_counts(tokenized_prompt or "")
    residual_count = int(residual.get("id", 0)) + int(residual.get("phone", 0)) + int(residual.get("email", 0))

    score = 0
    score += core_count * 16
    score += contextual_count * 7
    score += ner_count * 5
    score += obfuscated_email * 24
    score += split_phone * 12
    score += split_id * 16
    score += sensitive_intent * 14
    score += residual_count * 30
    score = min(score, 100)

    reasons: List[str] = []
    if core_count:
        reasons.append(f"detected_core_pii={core_count}")
    if contextual_count:
        reasons.append(f"detected_contextual_pii={contextual_count}")
    if ner_count:
        reasons.append(f"ner_entities={ner_count}")
    if obfuscated_email or split_phone or split_id:
        reasons.append(
            f"obfuscation_signals=email:{obfuscated_email},phone:{split_phone},id:{split_id}"
        )
    if sensitive_intent:
        reasons.append(f"sensitive_intent_hits={sensitive_intent}")
    if residual_count:
        reasons.append(f"residual_core_pii_after_tokenization={residual_count}")

    challenge_threshold = int(challenge_threshold if challenge_threshold is not None else _threshold("PRIVACY_CHALLENGE_THRESHOLD", 45))
    block_threshold = int(block_threshold if block_threshold is not None else _threshold("PRIVACY_BLOCK_THRESHOLD", 80))

    if score >= block_threshold:
        action = "block"
    elif score >= challenge_threshold:
        action = "challenge"
    else:
        action = "allow"

    signal_count = sum(
        1 for value in [core_count, contextual_count, obfuscated_email + split_phone + split_id, sensitive_intent, residual_count] if value > 0
    )

    return {
        "risk_score": score,
        "risk_level": "high" if score >= block_threshold else ("medium" if score >= challenge_threshold else "low"),
        "confidence": _rate_confidence(signal_count),
        "policy_action": action,
        "reasons": reasons,
        "thresholds": {"challenge": challenge_threshold, "block": block_threshold},
        "signals": {
            "core_pii_count": core_count,
            "contextual_pii_count": contextual_count,
            "ner_person": ner_person,
            "ner_location": ner_location,
            "ner_organization": ner_organization,
            "obfuscated_email": obfuscated_email,
            "split_phone": split_phone,
            "split_id": split_id,
            "sensitive_intent_hits": sensitive_intent,
            "residual_core_pii": residual_count,
        },
    }
