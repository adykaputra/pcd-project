"""Viva/export helper for reproducible evidence artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from app.privacy_benchmark import run_privacy_benchmark
from app.privacy_comparison import run_privacy_comparison
from app.privacy_adversarial import run_adversarial_stress


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def generate_viva_pack(dataset_version: str = "v3", report_dir: str | Path = "reports/viva") -> Dict[str, Any]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    benchmark = run_privacy_benchmark(dataset_version=dataset_version, split="all")
    comparison = run_privacy_comparison(dataset_version=dataset_version, split="all", include_cases=True)
    adversarial = run_adversarial_stress(dataset_version=dataset_version, split="test", max_cases=30, max_variants=3)

    leaderboard_csv = output_dir / "method_leaderboard.csv"
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

    adversarial_csv = output_dir / "adversarial_cases.csv"
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
    json_path = output_dir / "viva_pack.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    hashes = {
        "json": _sha256_file(json_path),
        "leaderboard_csv": _sha256_file(leaderboard_csv),
        "adversarial_csv": _sha256_file(adversarial_csv),
    }
    top_method = (comparison.get("method_metrics") or [{}])[0]
    md_path = output_dir / "viva_pack.md"
    md_path.write_text(
        "\n".join(
            [
                "# Viva Evidence Pack",
                "",
                f"- Generated at: `{payload['generated_at']}`",
                f"- Git commit: `{payload['git_commit']}`",
                f"- Dataset: `{dataset_version}`",
                "",
                "## Baseline Firewall Metrics",
                f"- Leak rate: `{benchmark['metrics']['core_pii_leak_rate']}`",
                f"- Detection rate: `{benchmark['metrics']['pii_detection_rate']}`",
                "",
                "## Comparative Winner",
                f"- Method: `{top_method.get('method_name', 'n/a')}`",
                f"- Micro F1: `{top_method.get('micro_f1', 'n/a')}`",
                "",
                "## Adversarial Stress Summary",
                f"- Baseline leak rate: `{adversarial['summary']['baseline_core_leak_rate']}`",
                f"- Attacked leak rate: `{adversarial['summary']['attacked_core_leak_rate']}`",
                "",
                "## Artifact Hashes",
                f"- `viva_pack.json`: `{hashes['json']}`",
                f"- `method_leaderboard.csv`: `{hashes['leaderboard_csv']}`",
                f"- `adversarial_cases.csv`: `{hashes['adversarial_csv']}`",
            ]
        ),
        encoding="utf-8",
    )
    hashes["markdown"] = _sha256_file(md_path)

    return {
        "generated_at": payload["generated_at"],
        "git_commit": payload["git_commit"],
        "dataset_version": dataset_version,
        "baseline_leak_rate": benchmark["metrics"]["core_pii_leak_rate"],
        "baseline_detection_rate": benchmark["metrics"]["pii_detection_rate"],
        "top_method": top_method.get("method_name"),
        "artifacts": {
            "json": str(json_path),
            "markdown": str(md_path),
            "leaderboard_csv": str(leaderboard_csv),
            "adversarial_csv": str(adversarial_csv),
        },
        "hashes": hashes,
    }
