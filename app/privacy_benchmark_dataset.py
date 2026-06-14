"""Versioned benchmark dataset loader for privacy evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List


DATASET_DIR = Path("data/privacy_benchmarks")


def _dataset_path(version: str) -> Path:
    safe = (version or "").strip().lower()
    if not safe:
        safe = "v1"
    return DATASET_DIR / f"{safe}.json"


def list_dataset_versions() -> List[str]:
    if not DATASET_DIR.exists():
        return []
    versions = []
    for path in sorted(DATASET_DIR.glob("*.json")):
        versions.append(path.stem)
    return versions


def load_benchmark_dataset(version: str = "v1") -> Dict[str, Any]:
    path = _dataset_path(version)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark dataset version not found: {version}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    return data


def get_benchmark_cases(version: str = "v1", split: str = "all") -> List[Dict[str, Any]]:
    data = load_benchmark_dataset(version=version)
    cases = data.get("cases") or []
    if split == "all":
        return list(cases)
    target = (split or "").strip().lower()
    return [c for c in cases if str(c.get("split", "all")).lower() == target]


def summarize_benchmark_dimensions(version: str = "v1", split: str = "all") -> Dict[str, Any]:
    """Return searchable dataset dimensions for dynamic UI filters."""
    cases = get_benchmark_cases(version=version, split=split)
    scenario_counts: Dict[str, int] = {}
    language_counts: Dict[str, int] = {}
    split_counts: Dict[str, int] = {}

    for case in cases:
        scenario = str(case.get("scenario", "general")).strip() or "general"
        language = str(case.get("language", "unknown")).strip() or "unknown"
        case_split = str(case.get("split", "all")).strip() or "all"
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        language_counts[language] = language_counts.get(language, 0) + 1
        split_counts[case_split] = split_counts.get(case_split, 0) + 1

    return {
        "dataset_version": version,
        "split": split,
        "total_cases": len(cases),
        "scenarios": sorted(scenario_counts.keys()),
        "languages": sorted(language_counts.keys()),
        "scenario_counts": scenario_counts,
        "language_counts": language_counts,
        "split_counts": split_counts,
    }
