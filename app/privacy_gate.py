"""Benchmark quality gate evaluation for CI."""
from __future__ import annotations

from typing import Dict, Any, List


DEFAULT_GATE_THRESHOLDS = {
    "max_leak_rate": 0.05,
    "min_utility_score": 0.75,
    "max_latency_ms": 100.0,
    "min_detection_rate": 0.6,
    "min_expected_action_accuracy": 0.3,
}


def evaluate_benchmark_gate(benchmark: Dict[str, Any], thresholds: Dict[str, float] | None = None) -> Dict[str, Any]:
    metrics = benchmark.get("metrics") or {}
    rules = dict(DEFAULT_GATE_THRESHOLDS)
    if thresholds:
        rules.update({k: float(v) for k, v in thresholds.items()})

    leak_rate = float(metrics.get("core_pii_leak_rate", 1.0))
    utility = float(metrics.get("avg_utility_score", 0.0))
    latency = float(metrics.get("avg_latency_ms", 9999.0))
    detection_rate = float(metrics.get("pii_detection_rate", 0.0))
    expected_action_accuracy = float(metrics.get("expected_action_accuracy", 0.0))

    checks: List[Dict[str, Any]] = [
        {
            "name": "leak_rate",
            "actual": leak_rate,
            "operator": "<=",
            "threshold": rules["max_leak_rate"],
            "passed": leak_rate <= rules["max_leak_rate"],
        },
        {
            "name": "utility_score",
            "actual": utility,
            "operator": ">=",
            "threshold": rules["min_utility_score"],
            "passed": utility >= rules["min_utility_score"],
        },
        {
            "name": "latency_ms",
            "actual": latency,
            "operator": "<=",
            "threshold": rules["max_latency_ms"],
            "passed": latency <= rules["max_latency_ms"],
        },
        {
            "name": "pii_detection_rate",
            "actual": detection_rate,
            "operator": ">=",
            "threshold": rules["min_detection_rate"],
            "passed": detection_rate >= rules["min_detection_rate"],
        },
        {
            "name": "expected_action_accuracy",
            "actual": expected_action_accuracy,
            "operator": ">=",
            "threshold": rules["min_expected_action_accuracy"],
            "passed": expected_action_accuracy >= rules["min_expected_action_accuracy"],
        },
    ]

    passed = all(c["passed"] for c in checks)
    return {
        "passed": passed,
        "checks": checks,
        "thresholds": rules,
        "metrics": metrics,
    }
