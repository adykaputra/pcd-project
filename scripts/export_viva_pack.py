#!/usr/bin/env python3
"""Export viva-ready evidence pack for comparative privacy firewall."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.privacy_benchmark import run_privacy_benchmark
from app.privacy_comparison import run_privacy_comparison
from app.privacy_adversarial import run_adversarial_stress


REPORT_DIR = Path("reports/viva")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_version = "v3"

    benchmark = run_privacy_benchmark(dataset_version=dataset_version, split="all")
    comparison = run_privacy_comparison(dataset_version=dataset_version, split="all", include_cases=True)
    adversarial = run_adversarial_stress(dataset_version=dataset_version, split="test", max_cases=30, max_variants=3)

    leaderboard_csv = REPORT_DIR / "method_leaderboard.csv"
    with leaderboard_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "method_id",
                "method_name",
                "composite_score",
                "avg_target_recall",
                "core_pii_leak_rate",
                "avg_utility_score",
                "avg_latency_ms",
                "micro_precision",
                "micro_recall",
                "micro_f1",
                "macro_f1",
                "wins",
            ],
        )
        writer.writeheader()
        for row in comparison.get("method_metrics", []):
            writer.writerow({key: row.get(key) for key in writer.fieldnames})

    adversarial_csv = REPORT_DIR / "adversarial_cases.csv"
    with adversarial_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case",
                "scenario",
                "baseline_method",
                "baseline_recall",
                "baseline_core_leak",
                "variant_prompt",
                "variant_method",
                "variant_recall",
                "variant_core_leak",
            ],
        )
        writer.writeheader()
        for case in adversarial.get("cases", []):
            baseline = case.get("baseline", {})
            for variant in case.get("variants", []):
                writer.writerow(
                    {
                        "case": case.get("case"),
                        "scenario": case.get("scenario"),
                        "baseline_method": baseline.get("selected_method_id"),
                        "baseline_recall": baseline.get("target_recall"),
                        "baseline_core_leak": baseline.get("core_leak"),
                        "variant_prompt": variant.get("variant_prompt"),
                        "variant_method": variant.get("selected_method_id"),
                        "variant_recall": variant.get("target_recall"),
                        "variant_core_leak": variant.get("core_leak"),
                    }
                )

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "git_commit": _git_commit(),
        "dataset_version": dataset_version,
        "benchmark": benchmark,
        "comparison": comparison,
        "adversarial": adversarial,
    }
    json_path = REPORT_DIR / "viva_pack.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    hashes = {
        "viva_pack.json": _sha256_file(json_path),
        "method_leaderboard.csv": _sha256_file(leaderboard_csv),
        "adversarial_cases.csv": _sha256_file(adversarial_csv),
    }

    top_method = (comparison.get("method_metrics") or [{}])[0]
    md_lines = [
        "# Viva Evidence Pack",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Git commit: `{payload['git_commit']}`",
        f"- Dataset: `{dataset_version}`",
        "",
        "## Baseline Firewall Metrics",
        f"- Leak rate: `{benchmark['metrics']['core_pii_leak_rate']}`",
        f"- Detection rate: `{benchmark['metrics']['pii_detection_rate']}`",
        f"- Avg utility: `{benchmark['metrics']['avg_utility_score']}`",
        f"- Avg latency ms: `{benchmark['metrics']['avg_latency_ms']}`",
        "",
        "## Comparative Winner",
        f"- Method: `{top_method.get('method_name', 'n/a')}`",
        f"- Composite score: `{top_method.get('composite_score', 'n/a')}`",
        f"- Micro F1: `{top_method.get('micro_f1', 'n/a')}`",
        f"- Macro F1: `{top_method.get('macro_f1', 'n/a')}`",
        "",
        "## Adversarial Stress Summary",
        f"- Baseline leak rate: `{adversarial['summary']['baseline_core_leak_rate']}`",
        f"- Attacked leak rate: `{adversarial['summary']['attacked_core_leak_rate']}`",
        f"- Recall degradation events: `{adversarial['summary']['recall_degradation_events']}`",
        "",
        "## Artifact Hashes (integrity proof)",
        f"- `viva_pack.json`: `{hashes['viva_pack.json']}`",
        f"- `method_leaderboard.csv`: `{hashes['method_leaderboard.csv']}`",
        f"- `adversarial_cases.csv`: `{hashes['adversarial_cases.csv']}`",
    ]
    md_path = REPORT_DIR / "viva_pack.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {leaderboard_csv}")
    print(f"Wrote {adversarial_csv}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
