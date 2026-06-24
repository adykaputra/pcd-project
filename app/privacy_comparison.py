"""Comparative redaction study engine for thesis-grade privacy evaluation.

This module upgrades benchmarking from single-pipeline scoring to a method
comparison framework aligned with the FYP direction:
  1) basic regex
  2) Microsoft Presidio (optional dependency)
  3) keyword + vault tokenization
  4) NER-based masking
  5) LLM-validator style heuristic guard
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.module2.logic import (
    COMMON_LOCATIONS,
    COMMON_NAMES,
    EMAIL_RE,
    MALAYSIAN_IC_RE,
    PHONE_RE,
    detect_pii_counts,
)
from app.privacy_benchmark_dataset import get_benchmark_cases
from app.privacy_ner import detect_named_entities
from app.privacy_risk import evaluate_prompt_risk
from app.privacy_vault import get_vault


OBFUSCATED_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+-]+\s*(?:@|\[at\]|\(at\)|\sat\s)\s*[a-zA-Z0-9.-]+\s*(?:\.|\sdot\s)\s*[a-zA-Z]{2,}\b",
    re.IGNORECASE,
)
SPACED_PHONE_RE = re.compile(r"\b(?:\+?6?\s*)?(?:0\s*1\s*[0-9](?:[\s-]*\d){7,8})\b")
SPACED_ID_RE = re.compile(r"\b\d{6}[\s-]?\d{2}[\s-]?\d{4}\b")


_PRESIDIO_READY: Optional[bool] = None
_PRESIDIO_ANALYZER = None
_PRESIDIO_ANONYMIZER = None
_PRESIDIO_ERROR = ""
ENTITY_TYPES = ["id", "phone", "email", "name", "location", "organization"]
METHOD_TIE_PRIORITY = ["llm_validator", "keyword_vault", "ner", "presidio", "basic_regex"]


def _canonical_entity_type(raw: str) -> str:
    key = str(raw or "").strip().lower()
    mapping = {
        "id": "id",
        "malaysian_ic": "id",
        "phone": "phone",
        "phone_number": "phone",
        "email": "email",
        "emails": "email",
        "name": "name",
        "person": "name",
        "per": "name",
        "ner_person": "name",
        "location": "location",
        "loc": "location",
        "gpe": "location",
        "ner_location": "location",
        "organization": "organization",
        "org": "organization",
        "ner_organization": "organization",
    }
    return mapping.get(key, key)


def _normalize_method_counts(counts: Dict[str, Any]) -> Dict[str, int]:
    normalized = {entity: 0 for entity in ENTITY_TYPES}
    for key, value in (counts or {}).items():
        entity = _canonical_entity_type(key)
        if entity in normalized:
            try:
                normalized[entity] += int(value or 0)
            except Exception:
                continue
    return normalized


def _targets_to_type_counts(targets: List[Dict[str, str]]) -> Dict[str, int]:
    totals = {entity: 0 for entity in ENTITY_TYPES}
    for target in targets:
        entity = _canonical_entity_type(target.get("type", "unknown"))
        if entity in totals:
            totals[entity] += 1
    return totals


def _utility_score(original: str, redacted: str) -> float:
    if not original:
        return 1.0
    ratio = min(len(redacted), len(original)) / max(len(redacted), len(original))
    return round(ratio, 3)


def _replace_pattern(text: str, pattern: re.Pattern, replacement: str) -> Tuple[str, int]:
    updated, count = pattern.subn(replacement, text)
    return updated, count


def _replace_literal_ci(text: str, literal: str, replacement: str) -> Tuple[str, int]:
    if not literal.strip():
        return text, 0
    pattern = re.compile(re.escape(literal), re.IGNORECASE)
    return pattern.subn(replacement, text)


def _dedupe_targets(targets: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped: List[Dict[str, str]] = []
    for target in targets:
        value = str(target.get("value", "")).strip()
        pii_type = str(target.get("type", "unknown")).strip().lower() or "unknown"
        if not value:
            continue
        key = (value.lower(), pii_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"value": value, "type": pii_type})
    return deduped


def _infer_targets_from_prompt(prompt: str, contains_pii: bool) -> List[Dict[str, str]]:
    if not prompt or not contains_pii:
        return []

    targets: List[Dict[str, str]] = []
    for match in MALAYSIAN_IC_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "id"})
    for match in PHONE_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "phone"})
    for match in EMAIL_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "email"})
    for match in OBFUSCATED_EMAIL_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "email"})
    for match in SPACED_PHONE_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "phone"})
    for match in SPACED_ID_RE.finditer(prompt):
        targets.append({"value": match.group(0), "type": "id"})

    lower = prompt.lower()
    for name in sorted(COMMON_NAMES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", lower, re.IGNORECASE):
            targets.append({"value": name, "type": "name"})
    for location in sorted(COMMON_LOCATIONS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(location) + r"\b", lower, re.IGNORECASE):
            targets.append({"value": location, "type": "location"})

    ner = detect_named_entities(prompt)
    for entity in ner.get("entities", []):
        label = str(entity.get("label", "")).upper()
        pii_type = {
            "PERSON": "name",
            "PER": "name",
            "GPE": "location",
            "LOC": "location",
            "ORG": "organization",
        }.get(label, "unknown")
        value = str(entity.get("text", "")).strip()
        if value:
            targets.append({"value": value, "type": pii_type})

    return _dedupe_targets(targets)


def _resolve_case_targets(case: Dict[str, Any]) -> List[Dict[str, str]]:
    explicit = case.get("pii_targets")
    if isinstance(explicit, list) and explicit:
        normalized = []
        for item in explicit:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "value": str(item.get("value", "")).strip(),
                    "type": str(item.get("type", "unknown")).strip().lower() or "unknown",
                }
            )
        return _dedupe_targets(normalized)
    return _infer_targets_from_prompt(str(case.get("prompt", "")), bool(case.get("contains_pii")))


def resolve_case_targets(case: Dict[str, Any]) -> List[Dict[str, str]]:
    """Public helper to obtain normalized target list for a benchmark case."""
    return _resolve_case_targets(case)


def _method_basic_regex(text: str) -> Dict[str, Any]:
    redacted, count_id = _vault_replace_pattern(text, MALAYSIAN_IC_RE, "id")
    redacted, count_phone = _vault_replace_pattern(redacted, PHONE_RE, "phone")
    redacted, count_email = _vault_replace_pattern(redacted, EMAIL_RE, "email")
    return {
        "redacted_text": redacted,
        "counts": {"id": count_id, "phone": count_phone, "email": count_email},
        "metadata": {"backend": "regex"},
    }


def _load_presidio() -> bool:
    global _PRESIDIO_READY, _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER, _PRESIDIO_ERROR
    if _PRESIDIO_READY is not None:
        return _PRESIDIO_READY
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
        from presidio_anonymizer import AnonymizerEngine  # type: ignore

        _PRESIDIO_ANALYZER = AnalyzerEngine()
        _PRESIDIO_ANONYMIZER = AnonymizerEngine()
        _PRESIDIO_READY = True
        _PRESIDIO_ERROR = ""
        return True
    except Exception as exc:
        _PRESIDIO_READY = False
        _PRESIDIO_ERROR = str(exc)
        _PRESIDIO_ANALYZER = None
        _PRESIDIO_ANONYMIZER = None
        return False


def _method_presidio(text: str) -> Dict[str, Any]:
    if not _load_presidio() or _PRESIDIO_ANALYZER is None or _PRESIDIO_ANONYMIZER is None:
        fallback = _method_basic_regex(text)
        fallback["metadata"]["backend"] = "fallback"
        fallback["metadata"]["reason"] = _PRESIDIO_ERROR or "presidio not installed"
        return fallback

    try:
        analyzer_results = _PRESIDIO_ANALYZER.analyze(text=text, language="en")
        anonymized = _PRESIDIO_ANONYMIZER.anonymize(text=text, analyzer_results=analyzer_results).text
        counts: Dict[str, int] = {}
        for item in analyzer_results:
            key = str(getattr(item, "entity_type", "unknown")).lower()
            counts[key] = counts.get(key, 0) + 1
        return {
            "redacted_text": anonymized,
            "counts": counts,
            "metadata": {"backend": "presidio", "entities": len(analyzer_results)},
        }
    except Exception as exc:
        fallback = _method_basic_regex(text)
        fallback["metadata"]["backend"] = "fallback"
        fallback["metadata"]["reason"] = f"presidio runtime failure: {exc}"
        return fallback


def _vault_replace_pattern(text: str, pattern: re.Pattern, pii_type: str) -> Tuple[str, int]:
    vault = get_vault()
    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        count += 1
        return vault.get_or_create_token(value=match.group(0), pii_type=pii_type).token

    return pattern.sub(_replace, text), count


def _vault_replace_dictionary(text: str, terms: set, pii_type: str) -> Tuple[str, int]:
    vault = get_vault()
    redacted = text
    total = 0
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)

        def _replace(match: re.Match) -> str:
            nonlocal total
            total += 1
            return vault.get_or_create_token(value=match.group(0), pii_type=pii_type).token

        redacted = pattern.sub(_replace, redacted)
    return redacted, total


def _method_keyword_vault(text: str) -> Dict[str, Any]:
    redacted, count_id = _vault_replace_pattern(text, MALAYSIAN_IC_RE, "id")
    redacted, count_phone = _vault_replace_pattern(redacted, PHONE_RE, "phone")
    redacted, count_email = _vault_replace_pattern(redacted, EMAIL_RE, "email")
    redacted, count_names = _vault_replace_dictionary(redacted, COMMON_NAMES, "name")
    redacted, count_locations = _vault_replace_dictionary(redacted, COMMON_LOCATIONS, "location")
    return {
        "redacted_text": redacted,
        "counts": {
            "id": count_id,
            "phone": count_phone,
            "email": count_email,
            "name": count_names,
            "location": count_locations,
        },
        "metadata": {"backend": "vault"},
    }


def _method_ner(text: str) -> Dict[str, Any]:
    ner_result = detect_named_entities(text)
    entities = ner_result.get("entities", [])
    redacted = text
    counts = {"person": 0, "organization": 0, "location": 0}
    vault = get_vault()
    # Replace from end to start to avoid offset drift.
    sorted_entities = sorted(
        [e for e in entities if isinstance(e, dict)],
        key=lambda item: int(item.get("start", 0)),
        reverse=True,
    )
    for entity in sorted_entities:
        start = int(entity.get("start", 0))
        end = int(entity.get("end", 0))
        if end <= start or end > len(redacted):
            continue
        label = str(entity.get("label", "ENTITY")).upper()
        entity_text = redacted[start:end]
        if label in {"PERSON", "PER"}:
            placeholder = vault.get_or_create_token(entity_text, "name").token
            counts["person"] += 1
        elif label in {"ORG", "ORGANIZATION"}:
            placeholder = vault.get_or_create_token(entity_text, "organization").token
            counts["organization"] += 1
        elif label in {"GPE", "LOC", "LOCATION"}:
            placeholder = vault.get_or_create_token(entity_text, "location").token
            counts["location"] += 1
        else:
            placeholder = "[NER_" + label + "]"
        redacted = redacted[:start] + placeholder + redacted[end:]
    return {
        "redacted_text": redacted,
        "counts": counts,
        "metadata": {
            "backend": ner_result.get("backend"),
            "entities_detected": len(entities),
            "model": ner_result.get("model"),
        },
    }


def _method_llm_validator(text: str) -> Dict[str, Any]:
    redacted = text
    counts: Dict[str, int] = {"id": 0, "phone": 0, "email": 0, "name": 0, "location": 0}

    redacted, n = _vault_replace_pattern(redacted, MALAYSIAN_IC_RE, "id")
    counts["id"] += n
    redacted, n = _vault_replace_pattern(redacted, SPACED_ID_RE, "id")
    counts["id"] += n
    redacted, n = _vault_replace_pattern(redacted, PHONE_RE, "phone")
    counts["phone"] += n
    redacted, n = _vault_replace_pattern(redacted, SPACED_PHONE_RE, "phone")
    counts["phone"] += n
    redacted, n = _vault_replace_pattern(redacted, EMAIL_RE, "email")
    counts["email"] += n
    redacted, n = _vault_replace_pattern(redacted, OBFUSCATED_EMAIL_RE, "email")
    counts["email"] += n

    redacted, n = _vault_replace_dictionary(redacted, COMMON_NAMES, "name")
    counts["name"] += n
    redacted, n = _vault_replace_dictionary(redacted, COMMON_LOCATIONS, "location")
    counts["location"] += n

    ner = detect_named_entities(redacted)
    vault = get_vault()
    for entity in sorted(ner.get("entities", []), key=lambda e: int(e.get("start", 0)), reverse=True):
        start = int(entity.get("start", 0))
        end = int(entity.get("end", 0))
        if end <= start or end > len(redacted):
            continue
        label = str(entity.get("label", "ENTITY")).upper()
        value = redacted[start:end]
        if label in {"PERSON", "PER"}:
            placeholder = vault.get_or_create_token(value, "name").token
            counts["name"] += 1
        elif label in {"GPE", "LOC", "LOCATION"}:
            placeholder = vault.get_or_create_token(value, "location").token
            counts["location"] += 1
        elif label in {"ORG", "ORGANIZATION"}:
            placeholder = vault.get_or_create_token(value, "organization").token
        else:
            placeholder = "[SAFE_ENTITY]"
        redacted = redacted[:start] + placeholder + redacted[end:]

    risk = evaluate_prompt_risk(
        original_prompt=text,
        tokenization={"had_pii": redacted != text, "token_counts": counts},
        tokenized_prompt=redacted,
    )
    return {
        "redacted_text": redacted,
        "counts": counts,
        "metadata": {
            "backend": "heuristic-validator",
            "policy_action": risk.get("policy_action"),
            "risk_score": risk.get("risk_score"),
            "risk_level": risk.get("risk_level"),
        },
    }


METHOD_REGISTRY: Dict[str, Dict[str, Any]] = {
    "basic_regex": {"name": "Basic Regex", "runner": _method_basic_regex},
    "presidio": {"name": "Microsoft Presidio", "runner": _method_presidio},
    "keyword_vault": {"name": "Keyword + Vault", "runner": _method_keyword_vault},
    "ner": {"name": "Named Entity Recognition (NER)", "runner": _method_ner},
    "llm_validator": {"name": "LLM Validator Guard", "runner": _method_llm_validator},
}


def _evaluate_method_output(
    original: str,
    redacted: str,
    targets: List[Dict[str, str]],
    latency_ms: float,
) -> Dict[str, Any]:
    unresolved = []
    for target in targets:
        value = str(target.get("value", "")).strip()
        if not value:
            continue
        if re.search(re.escape(value), redacted, re.IGNORECASE):
            unresolved.append(target)
    target_total = len(targets)
    target_hits = target_total - len(unresolved)
    recall = (target_hits / target_total) if target_total else 1.0
    residual_core = detect_pii_counts(redacted)
    core_leak = any((residual_core or {}).values())
    utility = _utility_score(original, redacted)
    return {
        "target_total": target_total,
        "target_hits": target_hits,
        "target_recall": round(recall, 3),
        "unresolved_targets": unresolved,
        "core_residual_counts": residual_core,
        "core_leak_detected": core_leak,
        "utility_score": utility,
        "latency_ms": round(latency_ms, 3),
    }


def run_privacy_comparison(
    dataset_version: str = "v2",
    split: str = "all",
    methods: Optional[List[str]] = None,
    include_cases: bool = True,
    scenario: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Run multi-method comparison and adaptive selector analysis."""
    benchmark_cases = get_benchmark_cases(version=dataset_version, split=split)
    scenario_filter = str(scenario or "all").strip().lower()
    language_filter = str(language or "all").strip().lower()
    if scenario_filter and scenario_filter != "all":
        benchmark_cases = [
            case
            for case in benchmark_cases
            if str(case.get("scenario", "general")).strip().lower() == scenario_filter
        ]
    if language_filter and language_filter != "all":
        benchmark_cases = [
            case
            for case in benchmark_cases
            if str(case.get("language", "unknown")).strip().lower() == language_filter
        ]
    enabled = [m for m in (methods or list(METHOD_REGISTRY.keys())) if m in METHOD_REGISTRY]
    if not enabled:
        enabled = list(METHOD_REGISTRY.keys())

    method_stats: Dict[str, Dict[str, Any]] = {
        method_id: {
            "method_id": method_id,
            "method_name": METHOD_REGISTRY[method_id]["name"],
            "cases": 0,
            "wins": 0,
            "total_recall": 0.0,
            "leak_cases": 0,
            "total_utility": 0.0,
            "total_latency_ms": 0.0,
            "total_score": 0.0,
            "entity_confusion": {
                entity: {"tp": 0, "fp": 0, "fn": 0}
                for entity in ENTITY_TYPES
            },
        }
        for method_id in enabled
    }

    case_results: List[Dict[str, Any]] = []
    scenario_distribution: Dict[str, int] = {}
    language_distribution: Dict[str, int] = {}
    adaptive_leak_cases = 0
    adaptive_recall_sum = 0.0
    adaptive_utility_sum = 0.0
    adaptive_method_counts = {method_id: 0 for method_id in enabled}
    for case in benchmark_cases:
        prompt = str(case.get("prompt", ""))
        targets = _resolve_case_targets(case)
        target_type_counts = _targets_to_type_counts(targets)
        case_scenario = str(case.get("scenario", "general"))
        case_language = str(case.get("language", "unknown"))
        scenario_distribution[case_scenario] = scenario_distribution.get(case_scenario, 0) + 1
        language_distribution[case_language] = language_distribution.get(case_language, 0) + 1
        method_runs: Dict[str, Dict[str, Any]] = {}

        for method_id in enabled:
            runner: Callable[[str], Dict[str, Any]] = METHOD_REGISTRY[method_id]["runner"]
            start = time.perf_counter()
            output = runner(prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            redacted = str(output.get("redacted_text", prompt))
            metrics = _evaluate_method_output(prompt, redacted, targets, elapsed_ms)
            normalized_counts = _normalize_method_counts(output.get("counts", {}))
            method_runs[method_id] = {
                "method_id": method_id,
                "method_name": METHOD_REGISTRY[method_id]["name"],
                "redacted_text": redacted,
                "counts": normalized_counts,
                "metadata": output.get("metadata", {}),
                **metrics,
            }

        max_latency = max((item["latency_ms"] for item in method_runs.values()), default=1.0) or 1.0
        for method_id, output in method_runs.items():
            latency_component = 1.0 - (float(output["latency_ms"]) / max_latency)
            leak_penalty = 0.0 if output["core_leak_detected"] else 1.0
            score = (
                0.55 * float(output["target_recall"])
                + 0.2 * leak_penalty
                + 0.15 * float(output["utility_score"])
                + 0.1 * latency_component
            )
            output["composite_score"] = round(score, 3)

        winner = max(
            method_runs.values(),
            key=lambda item: (
                item["composite_score"],
                -METHOD_TIE_PRIORITY.index(item["method_id"]) if item["method_id"] in METHOD_TIE_PRIORITY else -999,
            ),
        )
        winner_id = winner["method_id"]
        adaptive_method_counts[winner_id] += 1
        adaptive_recall_sum += float(winner["target_recall"])
        adaptive_utility_sum += float(winner["utility_score"])
        if winner["core_leak_detected"]:
            adaptive_leak_cases += 1

        for method_id, output in method_runs.items():
            stats = method_stats[method_id]
            stats["cases"] += 1
            stats["total_recall"] += float(output["target_recall"])
            stats["total_utility"] += float(output["utility_score"])
            stats["total_latency_ms"] += float(output["latency_ms"])
            stats["total_score"] += float(output["composite_score"])
            if output["core_leak_detected"]:
                stats["leak_cases"] += 1
            if method_id == winner_id:
                stats["wins"] += 1
            confusion = stats["entity_confusion"]
            predicted_type_counts = output.get("counts", {})
            for entity in ENTITY_TYPES:
                true_count = int(target_type_counts.get(entity, 0))
                pred_count = int(predicted_type_counts.get(entity, 0))
                tp = min(true_count, pred_count)
                fp = max(pred_count - true_count, 0)
                fn = max(true_count - pred_count, 0)
                confusion[entity]["tp"] += tp
                confusion[entity]["fp"] += fp
                confusion[entity]["fn"] += fn

        case_results.append(
            {
                "case": case.get("name"),
                "scenario": case.get("scenario", "general"),
                "language": case.get("language", "unknown"),
                "contains_pii": bool(case.get("contains_pii")),
                "target_count": len(targets),
                "adaptive_selected_method": winner_id,
                "adaptive_selected_method_name": METHOD_REGISTRY[winner_id]["name"],
                "adaptive_score": winner["composite_score"],
                "adaptive_core_leak": winner["core_leak_detected"],
                "adaptive_recall": winner["target_recall"],
                "method_results": method_runs if include_cases else None,
            }
        )

    method_metrics = []
    for method_id in enabled:
        stats = method_stats[method_id]
        cases = max(int(stats["cases"]), 1)
        entity_metrics = {}
        micro_tp = micro_fp = micro_fn = 0
        f1_values = []
        for entity in ENTITY_TYPES:
            confusion = stats["entity_confusion"][entity]
            tp = int(confusion["tp"])
            fp = int(confusion["fp"])
            fn = int(confusion["fn"])
            micro_tp += tp
            micro_fp += fp
            micro_fn += fn
            precision = (tp / (tp + fp)) if (tp + fp) else 1.0
            recall = (tp / (tp + fn)) if (tp + fn) else 1.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            entity_metrics[entity] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
            }
            f1_values.append(f1)

        micro_precision = (micro_tp / (micro_tp + micro_fp)) if (micro_tp + micro_fp) else 1.0
        micro_recall = (micro_tp / (micro_tp + micro_fn)) if (micro_tp + micro_fn) else 1.0
        micro_f1 = (
            (2 * micro_precision * micro_recall / (micro_precision + micro_recall))
            if (micro_precision + micro_recall)
            else 0.0
        )
        macro_f1 = (sum(f1_values) / len(f1_values)) if f1_values else 0.0

        method_metrics.append(
            {
                "method_id": method_id,
                "method_name": stats["method_name"],
                "cases": stats["cases"],
                "wins": stats["wins"],
                "win_rate": round(stats["wins"] / cases, 3),
                "avg_target_recall": round(stats["total_recall"] / cases, 3),
                "core_pii_leak_rate": round(stats["leak_cases"] / cases, 3),
                "avg_utility_score": round(stats["total_utility"] / cases, 3),
                "avg_latency_ms": round(stats["total_latency_ms"] / cases, 3),
                "composite_score": round(stats["total_score"] / cases, 3),
                "micro_precision": round(micro_precision, 3),
                "micro_recall": round(micro_recall, 3),
                "micro_f1": round(micro_f1, 3),
                "macro_f1": round(macro_f1, 3),
                "entity_metrics": entity_metrics,
            }
        )

    method_metrics.sort(key=lambda item: item["composite_score"], reverse=True)
    total_cases = max(len(benchmark_cases), 1)
    adaptive_summary = {
        "selected_method_counts": adaptive_method_counts,
        "core_pii_leak_rate": round(adaptive_leak_cases / total_cases, 3),
        "avg_target_recall": round(adaptive_recall_sum / total_cases, 3),
        "avg_utility_score": round(adaptive_utility_sum / total_cases, 3),
        "selection_coverage": round(sum(adaptive_method_counts.values()) / total_cases, 3),
    }

    evaluation_protocol = {
        "entity_types": ENTITY_TYPES,
        "metrics": [
            "target_recall",
            "core_pii_leak_rate",
            "avg_utility_score",
            "avg_latency_ms",
            "micro_precision",
            "micro_recall",
            "micro_f1",
            "macro_f1",
        ],
        "composite_formula": "0.55*target_recall + 0.20*leak_free + 0.15*utility + 0.10*latency_component",
    }

    return {
        "dataset_version": dataset_version,
        "split": split,
        "filters": {"scenario": scenario_filter, "language": language_filter},
        "total_cases": len(benchmark_cases),
        "scenario_distribution": scenario_distribution,
        "language_distribution": language_distribution,
        "evaluation_protocol": evaluation_protocol,
        "method_metrics": method_metrics,
        "adaptive_summary": adaptive_summary,
        "cases": case_results if include_cases else [],
    }


def _runtime_has_pii_signals(prompt: str) -> bool:
    if not prompt:
        return False
    if (
        MALAYSIAN_IC_RE.search(prompt)
        or PHONE_RE.search(prompt)
        or EMAIL_RE.search(prompt)
        or OBFUSCATED_EMAIL_RE.search(prompt)
        or SPACED_PHONE_RE.search(prompt)
        or SPACED_ID_RE.search(prompt)
    ):
        return True
    entities = detect_named_entities(prompt).get("entities", [])
    return len(entities) > 0


def route_prompt_adaptive(prompt: str, methods: Optional[List[str]] = None) -> Dict[str, Any]:
    """Route a live prompt through multiple methods and select best runtime output."""
    enabled = [m for m in (methods or list(METHOD_REGISTRY.keys())) if m in METHOD_REGISTRY]
    if not enabled:
        enabled = list(METHOD_REGISTRY.keys())

    prompt = str(prompt or "")
    has_pii_signals = _runtime_has_pii_signals(prompt)
    candidates: List[Dict[str, Any]] = []
    max_latency_ms = 1.0

    for method_id in enabled:
        runner = METHOD_REGISTRY[method_id]["runner"]
        start = time.perf_counter()
        output = runner(prompt)
        latency_ms = (time.perf_counter() - start) * 1000.0
        max_latency_ms = max(max_latency_ms, latency_ms)

        redacted = str(output.get("redacted_text", prompt))
        counts = _normalize_method_counts(output.get("counts", {}))
        residual = detect_pii_counts(redacted)
        residual_total = int(sum(int(v or 0) for v in residual.values()))
        predicted_total = int(sum(counts.values()))
        utility = _utility_score(prompt, redacted)
        redaction_applied = redacted != prompt

        candidates.append(
            {
                "method_id": method_id,
                "method_name": METHOD_REGISTRY[method_id]["name"],
                "redacted_prompt": redacted,
                "counts": counts,
                "metadata": output.get("metadata", {}),
                "latency_ms": round(latency_ms, 3),
                "residual_core_counts": residual,
                "residual_core_total": residual_total,
                "predicted_total": predicted_total,
                "utility_score": utility,
                "redaction_applied": redaction_applied,
            }
        )

    for candidate in candidates:
        latency_component = 1.0 - (float(candidate["latency_ms"]) / max_latency_ms)
        leak_free = 1.0 if candidate["residual_core_total"] == 0 else 0.0
        expected_detection = 1.0 if (not has_pii_signals or candidate["redaction_applied"]) else 0.0
        count_signal = 1.0 if (not has_pii_signals or candidate["predicted_total"] > 0) else 0.0
        score = (
            0.45 * leak_free
            + 0.2 * float(candidate["utility_score"])
            + 0.15 * expected_detection
            + 0.1 * count_signal
            + 0.1 * latency_component
        )
        candidate["runtime_score"] = round(score, 3)

    selected = max(
        candidates,
        key=lambda item: (
            item["runtime_score"],
            -METHOD_TIE_PRIORITY.index(item["method_id"]) if item["method_id"] in METHOD_TIE_PRIORITY else -999,
        ),
    )

    return {
        "mode": "adaptive",
        "selected_method_id": selected["method_id"],
        "selected_method_name": selected["method_name"],
        "redacted_prompt": selected["redacted_prompt"],
        "token_counts": selected["counts"],
        "remaining_pii_counts": selected["residual_core_counts"],
        "redaction_applied": selected["redaction_applied"],
        "has_pii_signals": has_pii_signals,
        "candidates": [
            {
                "method_id": item["method_id"],
                "method_name": item["method_name"],
                "runtime_score": item["runtime_score"],
                "latency_ms": item["latency_ms"],
                "residual_core_total": item["residual_core_total"],
                "predicted_total": item["predicted_total"],
                "utility_score": item["utility_score"],
            }
            for item in sorted(candidates, key=lambda x: x["runtime_score"], reverse=True)
        ],
        "selected_metadata": selected.get("metadata", {}),
    }
