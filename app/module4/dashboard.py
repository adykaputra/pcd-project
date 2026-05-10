"""High-fidelity dashboard renderer for Privacy Firewall prototype."""
import json
from flask import render_template


def render_dashboard(
    logs=None,
    benchmark=None,
    calibration=None,
    autotune=None,
    benchmark_history=None,
    policy_thresholds=None,
    dataset_version=None,
    available_dataset_versions=None,
    initial_token=None,
):
    if logs is None:
        logs = []

    for log in logs:
        for key in ["tool_a_counts", "tool_b_counts", "tool_c_counts"]:
            try:
                log[f"{key}_parsed"] = json.loads(log[key]) if log.get(key) else {}
            except Exception:
                log[f"{key}_parsed"] = {}

    return render_template(
        "privacy_dashboard.html",
        logs=logs,
        benchmark=benchmark,
        calibration=calibration,
        autotune=autotune,
        benchmark_history=benchmark_history or [],
        policy_thresholds=policy_thresholds,
        dataset_version=dataset_version,
        available_dataset_versions=available_dataset_versions or [],
        initial_token=initial_token,
    )
