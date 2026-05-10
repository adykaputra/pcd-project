#!/usr/bin/env python3
"""Run privacy benchmark and enforce CI quality gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.privacy_benchmark import run_privacy_benchmark
from app.privacy_gate import evaluate_benchmark_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark quality gate checker")
    parser.add_argument("--dataset-version", default="v2")
    parser.add_argument("--split", default="all")
    parser.add_argument("--max-leak-rate", type=float, default=0.05)
    parser.add_argument("--min-utility-score", type=float, default=0.75)
    parser.add_argument("--max-latency-ms", type=float, default=100.0)
    parser.add_argument("--min-detection-rate", type=float, default=0.6)
    parser.add_argument("--min-expected-action-accuracy", type=float, default=0.3)
    args = parser.parse_args()

    benchmark = run_privacy_benchmark(dataset_version=args.dataset_version, split=args.split)
    gate = evaluate_benchmark_gate(
        benchmark,
        thresholds={
            "max_leak_rate": args.max_leak_rate,
            "min_utility_score": args.min_utility_score,
            "max_latency_ms": args.max_latency_ms,
            "min_detection_rate": args.min_detection_rate,
            "min_expected_action_accuracy": args.min_expected_action_accuracy,
        },
    )

    print(json.dumps({"benchmark": benchmark["metrics"], "gate": gate}, indent=2))
    if gate["passed"]:
        print("Privacy benchmark gate PASSED")
        return 0
    print("Privacy benchmark gate FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
