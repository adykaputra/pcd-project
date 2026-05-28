"""Threshold calibration utilities for privacy policy engine."""
from __future__ import annotations

from typing import Dict, Any, Iterable, List, Tuple

from app.module2.logic import tokenize_prompt_for_llm
from app.privacy_risk import evaluate_prompt_risk
from app.privacy_benchmark_dataset import get_benchmark_cases


ACTION_ORDER = {"allow": 0, "challenge": 1, "block": 2}


def _classify(score: int, challenge_threshold: int, block_threshold: int) -> str:
    if score >= block_threshold:
        return "block"
    if score >= challenge_threshold:
        return "challenge"
    return "allow"


def _expected_action(case: Dict[str, Any]) -> str:
    if case.get("expected_action"):
        return str(case["expected_action"])
    if case.get("contains_pii"):
        return "challenge"
    return "allow"


def _score_thresholds(cases: Iterable[Dict[str, Any]], challenge: int, block: int) -> Tuple[float, List[Dict[str, Any]]]:
    total_cost = 0.0
    rows: List[Dict[str, Any]] = []

    for case in cases:
        prompt = case["prompt"]
        tokenization = tokenize_prompt_for_llm(prompt)
        risk = evaluate_prompt_risk(prompt, tokenization, tokenization["tokenized_prompt"])
        score = int(risk["risk_score"])
        predicted = _classify(score, challenge, block)
        expected = _expected_action(case)
        distance = abs(ACTION_ORDER[predicted] - ACTION_ORDER[expected])
        case_cost = float(distance)

        # Stronger penalty when dangerous prompts are under-classified.
        if expected == "block" and predicted != "block":
            case_cost += 1.5
        if expected == "challenge" and predicted == "allow":
            case_cost += 0.75

        total_cost += case_cost
        rows.append(
            {
                "case": case["name"],
                "risk_score": score,
                "expected_action": expected,
                "predicted_action": predicted,
                "cost": round(case_cost, 3),
            }
        )

    return total_cost, rows


def calibrate_policy_thresholds(
    dataset_version: str = "v1",
    split: str = "all",
    challenge_range: Tuple[int, int] = (25, 65),
    block_range: Tuple[int, int] = (60, 95),
) -> Dict[str, Any]:
    """Search threshold pairs that best align with benchmark expectations."""
    cases = get_benchmark_cases(version=dataset_version, split=split)
    if not cases:
        cases = get_benchmark_cases(version=dataset_version, split="all")

    best: Dict[str, Any] = {"cost": float("inf"), "challenge": 45, "block": 80, "rows": []}
    low_c, high_c = challenge_range
    low_b, high_b = block_range

    for challenge in range(low_c, high_c + 1):
        for block in range(max(challenge + 5, low_b), high_b + 1):
            cost, rows = _score_thresholds(cases, challenge, block)
            if cost < best["cost"]:
                best = {"cost": cost, "challenge": challenge, "block": block, "rows": rows}

    recommendation = {
        "dataset_version": dataset_version,
        "split": split if split in {"train", "validation", "test", "all"} else "all",
        "challenge_threshold": int(best["challenge"]),
        "block_threshold": int(best["block"]),
        "objective_cost": round(float(best["cost"]), 3),
        "case_evaluations": best["rows"],
    }
    return recommendation
