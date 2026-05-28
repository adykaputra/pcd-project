"""PII redaction logic for Module 2 (Privacy Shield) - Redaction Reliability Comparison System."""
import re
from typing import Dict, Tuple, Any
from app.privacy_vault import get_vault
from app.privacy_ner import detect_named_entities

# Compile regex patterns for Tool A (Advanced Regex)
# Match Malaysian IC numbers (YYMMDD-XX-XXXX) with or without dashes and validate month (01-12) and day (01-31)
MALAYSIAN_IC_RE = re.compile(r"\b\d{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])-?\d{2}-?\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?6?01)[0-46-9]-*[0-9]{7,8}\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Tool B: Keyword-based Dictionary for strict matching
COMMON_NAMES = {
    'ali', 'ahmad', 'muhammad', 'fatimah', 'siti', 'nurul', 'musa', 'hamid', 'karim', 'hassan',
    'aziz', 'nasir', 'rashid', 'salim', 'zainal', 'zainab', 'rania', 'amira', 'yasmin'
}

COMMON_LOCATIONS = {
    'kuala lumpur', 'selangor', 'penang', 'johor', 'melaka', 'perak', 'kedah', 'terengganu',
    'kelantan', 'pahang', 'perlis', 'sabah', 'sarawak', 'putrajaya', 'labuan', 'kl', 'jb',
    'malaysia', 'ampang', 'petaling jaya', 'subang', 'klang', 'shah alam'
}

TOKEN_RE = re.compile(r"\[(?:ID|PHONE|EMAIL|NAME|LOCATION|ORG)_[A-F0-9]{12}\]")


def _tool_a_regex_redaction(text: str) -> Tuple[str, Dict[str, int]]:
    """Tool A: Advanced Regex-based redaction for Malaysian patterns."""
    if not text:
        return text, {"id": 0, "phone": 0, "email": 0}

    redacted = text
    count_id = len(MALAYSIAN_IC_RE.findall(text))
    count_phone = len(PHONE_RE.findall(text))
    count_email = len(EMAIL_RE.findall(text))

    redacted, _ = MALAYSIAN_IC_RE.subn("[REDACTED_ID]", redacted)
    redacted, _ = PHONE_RE.subn("[REDACTED_PHONE]", redacted)
    redacted, _ = EMAIL_RE.subn("[REDACTED_EMAIL]", redacted)

    return redacted, {"id": count_id, "phone": count_phone, "email": count_email}


def _tool_b_dictionary_redaction(text: str) -> Tuple[str, Dict[str, int]]:
    """Tool B: Keyword-based dictionary redaction for names and locations."""
    if not text:
        return text, {"id": 0, "phone": 0, "email": 0}

    redacted = text
    count_names = 0
    count_locations = 0

    # Case-insensitive name matching
    for name in COMMON_NAMES:
        pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
        matches = pattern.findall(redacted)
        count_names += len(matches)
        redacted = pattern.sub('[REDACTED_NAME]', redacted)

    # Case-insensitive location matching
    for location in COMMON_LOCATIONS:
        pattern = re.compile(r'\b' + re.escape(location) + r'\b', re.IGNORECASE)
        matches = pattern.findall(redacted)
        count_locations += len(matches)
        redacted = pattern.sub('[REDACTED_LOCATION]', redacted)

    return redacted, {"id": count_names, "phone": count_locations, "email": 0}


def _tool_c_mock_ai_redaction(text: str) -> Tuple[str, Dict[str, int]]:
    """Tool C: Mock AI layer simulating NLP-based PII detection."""
    if not text:
        return text, {"id": 0, "phone": 0, "email": 0}

    redacted = text

    # Mock AI: Look for patterns that resemble PII by proximity analysis
    # Simulate detecting ID-like sequences (8-12 digit groups with separators)
    id_pattern = re.compile(r'\b\d{2}[-/]?\d{2}[-/]?\d{2}[-/]?\d{2}[-/]?\d{4}\b')
    count_id = len(id_pattern.findall(text))
    redacted, _ = id_pattern.subn("[REDACTED_ID]", redacted)

    # Simulate detecting phone patterns more broadly than Tool A
    phone_pattern = re.compile(r'\b(?:\+?6?01\d{1}[-\s]?\d{3,4}[-\s]?\d{3,4}|[0-9]{10,11})\b')
    count_phone = len(phone_pattern.findall(text))
    redacted, _ = phone_pattern.subn("[REDACTED_PHONE]", redacted)

    # Simulate detecting email-like patterns with variations
    email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
    count_email = len(email_pattern.findall(text))
    redacted, _ = email_pattern.subn("[REDACTED_EMAIL]", redacted)

    return redacted, {"id": count_id, "phone": count_phone, "email": count_email}


def run_redaction_jury(text: str) -> Dict[str, Any]:
    """Run all 3 redaction tools, score them, and return the winning result with comparison.

    Returns a dict with:
    - 'sanitized_prompt': The output from the best-performing tool
    - 'winning_tool': Which tool won ('A', 'B', or 'C')
    - 'tool_scores': The reliability scores for all three tools
    - 'tool_counts': Detailed PII counts from each tool
    """
    if not text:
        return {
            "sanitized_prompt": text,
            "winning_tool": None,
            "tool_scores": {"A": 0, "B": 0, "C": 0},
            "tool_counts": {
                "A": {"id": 0, "phone": 0, "email": 0},
                "B": {"id": 0, "phone": 0, "email": 0},
                "C": {"id": 0, "phone": 0, "email": 0},
            },
        }

    # Run all three tools
    redacted_a, counts_a = _tool_a_regex_redaction(text)
    redacted_b, counts_b = _tool_b_dictionary_redaction(text)
    redacted_c, counts_c = _tool_c_mock_ai_redaction(text)

    # Calculate reliability score: total PII items detected by each tool
    score_a = counts_a.get("id", 0) + counts_a.get("phone", 0) + counts_a.get("email", 0)
    score_b = counts_b.get("id", 0) + counts_b.get("phone", 0) + counts_b.get("email", 0)
    score_c = counts_c.get("id", 0) + counts_c.get("phone", 0) + counts_c.get("email", 0)

    # Determine the winner: tool with highest detection count
    scores = {"A": score_a, "B": score_b, "C": score_c}
    winning_tool = max(scores.items(), key=lambda x: x[1])[0]

    # Select the sanitized output from the winning tool
    if winning_tool == "A":
        winning_redacted = redacted_a
    elif winning_tool == "B":
        winning_redacted = redacted_b
    else:  # "C"
        winning_redacted = redacted_c

    return {
        "sanitized_prompt": winning_redacted,
        "winning_tool": winning_tool,
        "tool_scores": scores,
        "tool_counts": {
            "A": counts_a,
            "B": counts_b,
            "C": counts_c,
        },
    }


def sanitize_prompt_for_llm(text: str) -> Dict[str, Any]:
    """Apply layered PII redaction before forwarding content to any LLM.

    This function is stricter than ``run_redaction_jury`` because it is used as a
    final privacy boundary before model calls. It applies multiple detectors in
    sequence so PII categories covered by different tools are cumulatively
    removed.
    """
    if not text:
        return {
            "sanitized_prompt": text,
            "had_pii": False,
            "remaining_pii_counts": {"id": 0, "phone": 0, "email": 0},
            "tool_counts": {
                "A": {"id": 0, "phone": 0, "email": 0},
                "B": {"id": 0, "phone": 0, "email": 0},
                "C": {"id": 0, "phone": 0, "email": 0},
            },
        }

    # Layer detections to avoid relying on a single winning tool.
    redacted, counts_a = _tool_a_regex_redaction(text)
    redacted, counts_b = _tool_b_dictionary_redaction(redacted)
    redacted, counts_c = _tool_c_mock_ai_redaction(redacted)

    # Final deterministic pass for core identifiers.
    redacted = redact_pii(redacted)
    remaining = detect_pii_counts(redacted)

    return {
        "sanitized_prompt": redacted,
        "had_pii": redacted != text,
        "remaining_pii_counts": remaining,
        "tool_counts": {
            "A": counts_a,
            "B": counts_b,
            "C": counts_c,
        },
    }


def _tokenize_regex(text: str, pattern: re.Pattern, pii_type: str) -> Tuple[str, int]:
    """Replace regex matches with deterministic vault-backed pseudonym tokens."""
    vault = get_vault()
    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        # Avoid re-tokenizing already tokenized values.
        value = match.group(0)
        if TOKEN_RE.fullmatch(value):
            return value
        count += 1
        return vault.get_or_create_token(value=value, pii_type=pii_type).token

    return pattern.sub(_replace, text), count


def _tokenize_dictionary_terms(text: str, terms: set, pii_type: str) -> Tuple[str, int]:
    """Replace dictionary terms (case-insensitive) with vault-backed tokens."""
    vault = get_vault()
    redacted = text
    count = 0

    # Longest-first prevents shorter terms from partially masking longer ones.
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)

        def _replace(match: re.Match) -> str:
            nonlocal count
            value = match.group(0)
            if TOKEN_RE.fullmatch(value):
                return value
            count += 1
            return vault.get_or_create_token(value=value, pii_type=pii_type).token

        redacted = pattern.sub(_replace, redacted)

    return redacted, count


def _tokenize_ner_entities(text: str, entities: list) -> Tuple[str, Dict[str, int]]:
    """Apply vault tokenization using NER-detected entities."""
    vault = get_vault()
    redacted = text
    counts = {"person": 0, "location": 0, "organization": 0}

    label_to_type = {
        "PERSON": "name",
        "PER": "name",
        "GPE": "location",
        "LOC": "location",
        "LOCATION": "location",
        "ORG": "organization",
        "ORGANIZATION": "organization",
    }

    # Longest-first replacement avoids partial matches when entities overlap in text.
    sorted_entities = sorted(
        [e for e in entities if e.get("label") in label_to_type and e.get("text")],
        key=lambda e: len(e.get("text", "")),
        reverse=True,
    )

    for entity in sorted_entities:
        label = str(entity.get("label", "")).upper()
        pii_type = label_to_type.get(label)
        if not pii_type:
            continue
        raw = str(entity.get("text", "")).strip()
        if not raw:
            continue
        replacement = vault.get_or_create_token(value=raw, pii_type=pii_type).token
        pattern = re.compile(r"\b" + re.escape(raw) + r"\b", re.IGNORECASE)

        def _replace(match: re.Match) -> str:
            candidate = match.group(0)
            if TOKEN_RE.fullmatch(candidate):
                return candidate
            return replacement

        updated, n = pattern.subn(_replace, redacted)
        if n > 0:
            redacted = updated
            if pii_type == "name":
                counts["person"] += n
            elif pii_type == "location":
                counts["location"] += n
            elif pii_type == "organization":
                counts["organization"] += n

    return redacted, counts


def tokenize_prompt_for_llm(text: str) -> Dict[str, Any]:
    """Convert detected PII into stable vault tokens before LLM dispatch.

    Example:
        "Email ali@example.com" -> "Email [EMAIL_ABC123...]"
    """
    if not text:
        return {
            "tokenized_prompt": text,
            "had_pii": False,
            "token_counts": {
                "id": 0,
                "phone": 0,
                "email": 0,
                "name": 0,
                "location": 0,
                "ner_person": 0,
                "ner_location": 0,
                "ner_organization": 0,
            },
            "remaining_pii_counts": {"id": 0, "phone": 0, "email": 0},
            "ner_backend": "none",
            "ner_entities_detected": 0,
        }

    tokenized = text
    tokenized, count_id = _tokenize_regex(tokenized, MALAYSIAN_IC_RE, "id")
    tokenized, count_phone = _tokenize_regex(tokenized, PHONE_RE, "phone")
    tokenized, count_email = _tokenize_regex(tokenized, EMAIL_RE, "email")
    tokenized, count_name = _tokenize_dictionary_terms(tokenized, COMMON_NAMES, "name")
    tokenized, count_location = _tokenize_dictionary_terms(tokenized, COMMON_LOCATIONS, "location")
    ner_result = detect_named_entities(text)
    tokenized, ner_counts = _tokenize_ner_entities(tokenized, ner_result.get("entities", []))

    remaining = detect_pii_counts(tokenized)
    return {
        "tokenized_prompt": tokenized,
        "had_pii": tokenized != text,
        "token_counts": {
            "id": count_id,
            "phone": count_phone,
            "email": count_email,
            "name": count_name,
            "location": count_location,
            "ner_person": ner_counts.get("person", 0),
            "ner_location": ner_counts.get("location", 0),
            "ner_organization": ner_counts.get("organization", 0),
        },
        "remaining_pii_counts": remaining,
        "ner_backend": ner_result.get("backend"),
        "ner_entities_detected": len(ner_result.get("entities", [])),
    }


def detokenize_prompt_from_vault(text: str) -> Dict[str, Any]:
    """Resolve vault tokens back to source values (admin workflows only)."""
    if not text:
        return {"detokenized_text": text, "resolved_tokens": 0, "unresolved_tokens": []}

    vault = get_vault()
    unresolved = []
    resolved_count = 0

    def _replace(match: re.Match) -> str:
        nonlocal resolved_count
        token = match.group(0)
        value = vault.resolve_token(token)
        if value is None:
            unresolved.append(token)
            return token
        resolved_count += 1
        return value

    detokenized = TOKEN_RE.sub(_replace, text)
    return {
        "detokenized_text": detokenized,
        "resolved_tokens": resolved_count,
        "unresolved_tokens": unresolved,
    }


def redact_pii(text: str) -> str:
    """Return a copy of `text` with PII redacted using Tool A (Regex).

    Kept for backward compatibility.
    """
    if not text:
        return text

    redacted = text

    redacted, n_id = MALAYSIAN_IC_RE.subn("[REDACTED_ID]", redacted)
    redacted, n_phone = PHONE_RE.subn("[REDACTED_PHONE]", redacted)
    redacted, n_email = EMAIL_RE.subn("[REDACTED_EMAIL]", redacted)

    return redacted


def detect_pii_counts(text: str) -> dict:
    """Return counts of detected PII types in `text` without modifying it.

    Kept for backward compatibility - uses Tool A.
    """
    return {
        "id": len(MALAYSIAN_IC_RE.findall(text)) if text else 0,
        "phone": len(PHONE_RE.findall(text)) if text else 0,
        "email": len(EMAIL_RE.findall(text)) if text else 0,
    }
