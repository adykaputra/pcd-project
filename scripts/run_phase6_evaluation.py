#!/usr/bin/env python3
"""Generate reproducible Phase 6 evaluation artifacts."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.privacy_benchmark import run_privacy_benchmark, run_privacy_benchmark_cross_split
from app.privacy_benchmark_dataset import list_dataset_versions
from app.privacy_calibration import calibrate_policy_thresholds
from app.privacy_gate import evaluate_benchmark_gate
from app.privacy_autotune import recommend_thresholds_from_audit


REPORT_DIR = Path("reports/phase6")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_versions = list_dataset_versions()
    default_dataset = "v2" if "v2" in dataset_versions else (dataset_versions[0] if dataset_versions else "v1")

    benchmark_overall = run_privacy_benchmark(dataset_version=default_dataset, split="all")
    benchmark_splits = run_privacy_benchmark_cross_split(dataset_version=default_dataset)
    calibration = calibrate_policy_thresholds(dataset_version=default_dataset, split="validation")
    autotune = recommend_thresholds_from_audit(hours=24 * 7, min_samples=10)
    gate = evaluate_benchmark_gate(benchmark_overall)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_versions": dataset_versions,
        "selected_dataset": default_dataset,
        "benchmark_overall": benchmark_overall,
        "benchmark_cross_split": benchmark_splits,
        "calibration": calibration,
        "autotune_recommendation": autotune,
        "gate": gate,
    }
    json_path = REPORT_DIR / "phase6_evaluation.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Phase 6 Evaluation Summary",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Dataset: `{default_dataset}`",
        f"- Gate passed: **{gate['passed']}**",
        f"- Leak rate: `{benchmark_overall['metrics']['core_pii_leak_rate']}`",
        f"- Detection rate: `{benchmark_overall['metrics']['pii_detection_rate']}`",
        f"- Expected action accuracy: `{benchmark_overall['metrics']['expected_action_accuracy']}`",
        f"- Avg utility score: `{benchmark_overall['metrics']['avg_utility_score']}`",
        f"- Avg latency ms: `{benchmark_overall['metrics']['avg_latency_ms']}`",
        "",
        "## Calibration",
        f"- Challenge threshold: `{calibration['challenge_threshold']}`",
        f"- Block threshold: `{calibration['block_threshold']}`",
        "",
        "## Autotune",
        f"- Source: `{autotune.get('source')}`",
        f"- Sample count: `{autotune.get('sample_count')}`",
        "",
        f"Full JSON artifact: `{json_path}`",
    ]
    md_path = REPORT_DIR / "phase6_evaluation.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
