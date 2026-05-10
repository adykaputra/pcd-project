"""Adversarial benchmark suite for privacy firewall evaluation."""
from __future__ import annotations

import time
from typing import Dict, Any, List

from app.module2.logic import tokenize_prompt_for_llm, detect_pii_counts
from app.privacy_risk import evaluate_prompt_risk
from app.privacy_benchmark_dataset import get_benchmark_cases


BENCHMARK_CASES = get_benchmark_cases(version="v1", split="all")


def _utility_score(original: str, tokenized: str) -> float:
    if not original:
        return 1.0
    # Proxy metric: preserve semantics by keeping sentence shape similar.
    ratio = min(len(tokenized), len(original)) / max(len(tokenized), len(original))
    return round(ratio, 3)


def run_privacy_benchmark(dataset_version: str = "v1", split: str = "all") -> Dict[str, Any]:
    benchmark_cases = get_benchmark_cases(version=dataset_version, split=split)
    results: List[Dict[str, Any]] = []
    total_pii_cases = 0
    detected_cases = 0
    leaked_cases = 0
    utilities = []
    elapsed_ms_total = 0.0
    policy_counts = {"allow": 0, "challenge": 0, "block": 0}
    by_language: Dict[str, int] = {}

    for case in benchmark_cases:
        prompt = case["prompt"]
        start = time.perf_counter()
        tokenization = tokenize_prompt_for_llm(prompt)
        tokenized = tokenization["tokenized_prompt"]
        risk = evaluate_prompt_risk(
            original_prompt=prompt,
            tokenization=tokenization,
            tokenized_prompt=tokenized,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        elapsed_ms_total += elapsed_ms

        residual = detect_pii_counts(tokenized)
        leaked = any((residual or {}).values())
        utility = _utility_score(prompt, tokenized)
        utilities.append(utility)

        if case["contains_pii"]:
            total_pii_cases += 1
        if tokenization.get("had_pii"):
            detected_cases += 1
        if leaked and case["contains_pii"]:
            leaked_cases += 1

        action = risk.get("policy_action", "allow")
        if action in policy_counts:
            policy_counts[action] += 1
        lang = str(case.get("language", "unknown"))
        by_language[lang] = by_language.get(lang, 0) + 1

        results.append(
            {
                "case": case["name"],
                "contains_pii": case["contains_pii"],
                "expected_action": case.get("expected_action"),
                "split": case.get("split"),
                "language": case.get("language"),
                "tokenized_prompt": tokenized,
                "tokenization_applied": tokenization.get("had_pii", False),
                "risk_score": risk.get("risk_score"),
                "risk_level": risk.get("risk_level"),
                "policy_action": action,
                "leaked_core_pii": leaked,
                "latency_ms": round(elapsed_ms, 3),
                "utility_score": utility,
            }
        )

    leak_rate = (leaked_cases / total_pii_cases) if total_pii_cases else 0.0
    avg_utility = sum(utilities) / len(utilities) if utilities else 1.0
    avg_latency = elapsed_ms_total / len(benchmark_cases) if benchmark_cases else 0.0

    return {
        "metrics": {
            "dataset_version": dataset_version,
            "split": split,
            "total_cases": len(benchmark_cases),
            "pii_cases": total_pii_cases,
            "detected_cases": detected_cases,
            "core_pii_leak_rate": round(leak_rate, 3),
            "avg_utility_score": round(avg_utility, 3),
            "avg_latency_ms": round(avg_latency, 3),
            "policy_action_counts": policy_counts,
            "language_distribution": by_language,
        },
        "cases": results,
        "visualization": {
            "policy_action_chart": [
                {"label": "allow", "value": policy_counts["allow"]},
                {"label": "challenge", "value": policy_counts["challenge"]},
                {"label": "block", "value": policy_counts["block"]},
            ],
            "quality_gauges": {
                "core_pii_leak_rate_pct": round(leak_rate * 100.0, 1),
                "avg_utility_score_pct": round(avg_utility * 100.0, 1),
            },
        },
    }


def run_privacy_benchmark_cross_split(dataset_version: str = "v1") -> Dict[str, Any]:
    """Run benchmark independently for train/validation/test and aggregate."""
    splits = ["train", "validation", "test"]
    split_results = {split: run_privacy_benchmark(dataset_version=dataset_version, split=split) for split in splits}
    all_result = run_privacy_benchmark(dataset_version=dataset_version, split="all")
    return {
        "dataset_version": dataset_version,
        "overall": all_result,
        "by_split": split_results,
    }
