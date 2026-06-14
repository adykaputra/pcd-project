#!/usr/bin/env python3
"""Generate comparative redaction study artifacts for FYP reporting."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.privacy_benchmark_dataset import list_dataset_versions
from app.privacy_comparison import run_privacy_comparison


REPORT_DIR = Path("reports/comparative")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run comparative redaction benchmark.")
    parser.add_argument("--dataset-version", default="", help="Dataset version (default: v3 if available)")
    parser.add_argument("--split", default="all", help="Benchmark split (all/train/validation/test)")
    parser.add_argument("--include-cases", action="store_true", help="Include full per-case method output in JSON")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    versions = list_dataset_versions()
    dataset_version = args.dataset_version.strip().lower()
    if not dataset_version:
        dataset_version = "v3" if "v3" in versions else ("v2" if "v2" in versions else "v1")

    comparison = run_privacy_comparison(
        dataset_version=dataset_version,
        split=args.split,
        include_cases=args.include_cases,
    )
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "available_dataset_versions": versions,
        "comparison": comparison,
    }

    json_path = REPORT_DIR / "comparative_study.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    method_rows = comparison.get("method_metrics", [])
    best_method = method_rows[0] if method_rows else {}
    adaptive = comparison.get("adaptive_summary", {})

    md_lines = [
        "# Comparative Redaction Study",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Dataset version: `{comparison.get('dataset_version')}`",
        f"- Split: `{comparison.get('split')}`",
        f"- Total cases: `{comparison.get('total_cases')}`",
        "",
        "## Adaptive Selector Summary",
        f"- Avg target recall: `{adaptive.get('avg_target_recall')}`",
        f"- Core PII leak rate: `{adaptive.get('core_pii_leak_rate')}`",
        f"- Avg utility score: `{adaptive.get('avg_utility_score')}`",
        f"- Selected method counts: `{adaptive.get('selected_method_counts')}`",
        "",
        "## Top Method",
        f"- Method: `{best_method.get('method_name', 'n/a')}`",
        f"- Composite score: `{best_method.get('composite_score', 'n/a')}`",
        f"- Avg recall: `{best_method.get('avg_target_recall', 'n/a')}`",
        f"- Leak rate: `{best_method.get('core_pii_leak_rate', 'n/a')}`",
        "",
        f"Full JSON artifact: `{json_path}`",
    ]
    md_path = REPORT_DIR / "comparative_study.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
