"""Named entity detection layer for privacy firewall.

Supports an optional spaCy backend when available, with deterministic fallback
rules so the system remains functional in minimal environments.
"""
from __future__ import annotations

import os
import re
from typing import Dict, Any, List, Tuple


_SPACY_MODEL = None
_SPACY_MODEL_NAME = None
_SPACY_READY = None
_TRANSFORMER_PIPELINE = None
_TRANSFORMER_MODEL_NAME = None
_TRANSFORMER_READY = None


KNOWN_NAMES = {
    "ali",
    "ahmad",
    "muhammad",
    "fatimah",
    "siti",
    "nurul",
    "musa",
    "hamid",
    "karim",
    "hassan",
    "john",
    "michael",
    "sarah",
    "amanda",
}

KNOWN_LOCATIONS = {
    "kuala lumpur",
    "selangor",
    "penang",
    "johor",
    "melaka",
    "perak",
    "kedah",
    "terengganu",
    "kelantan",
    "pahang",
    "perlis",
    "sabah",
    "sarawak",
    "putrajaya",
    "labuan",
    "petaling jaya",
    "shah alam",
    "malaysia",
}

TITLE_CASE_NAME_RE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b")
ORG_HINT_RE = re.compile(r"\b([A-Z][A-Za-z0-9& ]{2,}\s(?:Sdn Bhd|Berhad|Corp|Inc|Ltd|Bank))\b")


def _load_spacy_model() -> Tuple[bool, str]:
    """Lazy-load spaCy model if installed."""
    global _SPACY_MODEL, _SPACY_MODEL_NAME, _SPACY_READY
    if _SPACY_READY is not None:
        return _SPACY_READY, (_SPACY_MODEL_NAME or "none")

    requested_model = os.getenv("PRIVACY_NER_MODEL", "en_core_web_sm")
    backend = os.getenv("PRIVACY_NER_BACKEND", "auto").lower()
    if backend not in {"auto", "spacy"}:
        _SPACY_READY = False
        return False, requested_model

    try:
        import spacy  # type: ignore

        _SPACY_MODEL = spacy.load(requested_model)
        _SPACY_MODEL_NAME = requested_model
        _SPACY_READY = True
        return True, requested_model
    except Exception:
        _SPACY_READY = False
        _SPACY_MODEL = None
        _SPACY_MODEL_NAME = requested_model
        return False, requested_model


def _load_transformer_pipeline() -> Tuple[bool, str]:
    """Lazy-load transformer NER pipeline if installed."""
    global _TRANSFORMER_PIPELINE, _TRANSFORMER_MODEL_NAME, _TRANSFORMER_READY
    if _TRANSFORMER_READY is not None:
        return _TRANSFORMER_READY, (_TRANSFORMER_MODEL_NAME or "none")

    requested_model = os.getenv("PRIVACY_NER_TRANSFORMER_MODEL", "dslim/bert-base-NER")
    backend = os.getenv("PRIVACY_NER_BACKEND", "auto").lower()
    if backend not in {"auto", "transformer"}:
        _TRANSFORMER_READY = False
        return False, requested_model

    try:
        from transformers import pipeline  # type: ignore

        _TRANSFORMER_PIPELINE = pipeline(
            "token-classification",
            model=requested_model,
            aggregation_strategy="simple",
        )
        _TRANSFORMER_MODEL_NAME = requested_model
        _TRANSFORMER_READY = True
        return True, requested_model
    except Exception:
        _TRANSFORMER_READY = False
        _TRANSFORMER_PIPELINE = None
        _TRANSFORMER_MODEL_NAME = requested_model
        return False, requested_model


def _dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove overlapping entities while preferring higher confidence."""
    if not entities:
        return []
    ranked = sorted(
        entities,
        key=lambda e: (-(float(e.get("confidence", 0.0))), e.get("start", 0), -(e.get("end", 0) - e.get("start", 0))),
    )
    accepted: List[Dict[str, Any]] = []
    spans: List[Tuple[int, int]] = []
    for entity in ranked:
        start = int(entity.get("start", 0))
        end = int(entity.get("end", 0))
        overlap = any(not (end <= s or start >= e) for s, e in spans)
        if overlap:
            continue
        accepted.append(entity)
        spans.append((start, end))
    return sorted(accepted, key=lambda e: e.get("start", 0))


def _detect_with_spacy(text: str) -> Dict[str, Any]:
    ready, model_name = _load_spacy_model()
    if not ready or _SPACY_MODEL is None:
        return {"backend": "fallback", "model": model_name, "entities": []}

    doc = _SPACY_MODEL(text)
    entities: List[Dict[str, Any]] = []
    for ent in doc.ents:
        if ent.label_ not in {"PERSON", "ORG", "GPE", "LOC"}:
            continue
        entities.append(
            {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 0.82,
                "source": "spacy",
            }
        )
    return {"backend": "spacy", "model": model_name, "entities": _dedupe_entities(entities)}


def _normalize_transformer_label(raw: str) -> str:
    label = (raw or "").upper().replace("B-", "").replace("I-", "")
    mapping = {
        "PER": "PERSON",
        "PERSON": "PERSON",
        "ORG": "ORG",
        "ORGANIZATION": "ORG",
        "LOC": "LOC",
        "GPE": "GPE",
        "LOCATION": "LOC",
    }
    return mapping.get(label, label)


def _detect_with_transformer(text: str) -> Dict[str, Any]:
    ready, model_name = _load_transformer_pipeline()
    if not ready or _TRANSFORMER_PIPELINE is None:
        return {"backend": "fallback", "model": model_name, "entities": []}

    entities: List[Dict[str, Any]] = []
    for item in _TRANSFORMER_PIPELINE(text):
        label = _normalize_transformer_label(item.get("entity_group", item.get("entity", "")))
        if label not in {"PERSON", "ORG", "GPE", "LOC"}:
            continue
        start = int(item.get("start", 0))
        end = int(item.get("end", 0))
        if end <= start:
            continue
        entities.append(
            {
                "text": text[start:end],
                "label": label,
                "start": start,
                "end": end,
                "confidence": float(item.get("score", 0.65)),
                "source": "transformer",
            }
        )
    return {"backend": "transformer", "model": model_name, "entities": _dedupe_entities(entities)}


def _detect_with_fallback(text: str) -> Dict[str, Any]:
    entities: List[Dict[str, Any]] = []
    lower = text.lower()

    for location in sorted(KNOWN_LOCATIONS, key=len, reverse=True):
        for match in re.finditer(r"\b" + re.escape(location) + r"\b", lower, re.IGNORECASE):
            entities.append(
                {
                    "text": text[match.start() : match.end()],
                    "label": "GPE",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.7,
                    "source": "fallback-dictionary",
                }
            )

    for name in sorted(KNOWN_NAMES, key=len, reverse=True):
        for match in re.finditer(r"\b" + re.escape(name) + r"\b", lower, re.IGNORECASE):
            entities.append(
                {
                    "text": text[match.start() : match.end()],
                    "label": "PERSON",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.68,
                    "source": "fallback-dictionary",
                }
            )

    for match in TITLE_CASE_NAME_RE.finditer(text):
        candidate = match.group(1).strip()
        lower_candidate = candidate.lower()
        if lower_candidate in KNOWN_LOCATIONS:
            label = "GPE"
            confidence = 0.58
        else:
            label = "PERSON"
            confidence = 0.52
        if lower_candidate in {"please review", "thank you", "hello world"}:
            continue
        entities.append(
            {
                "text": candidate,
                "label": label,
                "start": match.start(1),
                "end": match.end(1),
                "confidence": confidence,
                "source": "fallback-titlecase",
            }
        )

    for match in ORG_HINT_RE.finditer(text):
        entities.append(
            {
                "text": match.group(1),
                "label": "ORG",
                "start": match.start(1),
                "end": match.end(1),
                "confidence": 0.63,
                "source": "fallback-org-hint",
            }
        )

    return {"backend": "fallback", "model": "rule-based", "entities": _dedupe_entities(entities)}


def detect_named_entities(text: str) -> Dict[str, Any]:
    """Detect PERSON/ORG/LOCATION entities for privacy-aware tokenization."""
    if not text:
        return {"backend": "none", "model": "none", "entities": []}

    backend = os.getenv("PRIVACY_NER_BACKEND", "auto").lower()
    if backend in {"auto", "transformer"}:
        tf_result = _detect_with_transformer(text)
        if tf_result["backend"] == "transformer":
            return tf_result

    if backend in {"auto", "spacy"}:
        spacy_result = _detect_with_spacy(text)
        if spacy_result["backend"] == "spacy":
            return spacy_result

    return _detect_with_fallback(text)
