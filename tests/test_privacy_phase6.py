from pathlib import Path
import subprocess

from app.privacy_benchmark import run_privacy_benchmark
from app.privacy_gate import evaluate_benchmark_gate


ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_gate_evaluator_returns_checks():
    benchmark = run_privacy_benchmark(dataset_version="v2", split="all")
    gate = evaluate_benchmark_gate(benchmark)
    assert "passed" in gate
    assert isinstance(gate["checks"], list)
    assert len(gate["checks"]) >= 5


def test_benchmark_gate_can_fail_with_strict_thresholds():
    benchmark = run_privacy_benchmark(dataset_version="v2", split="all")
    gate = evaluate_benchmark_gate(
        benchmark,
        thresholds={
            "max_leak_rate": 0.0,
            "min_utility_score": 0.99,
            "max_latency_ms": 0.001,
            "min_detection_rate": 1.0,
            "min_expected_action_accuracy": 1.0,
        },
    )
    assert gate["passed"] is False


def test_check_benchmark_gate_script_passes_with_defaults():
    proc = subprocess.run(
        ["python3", "scripts/check_benchmark_gate.py", "--dataset-version", "v2", "--split", "all"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Privacy benchmark gate PASSED" in proc.stdout


def test_phase6_repro_script_generates_artifacts():
    proc = subprocess.run(
        ["python3", "scripts/run_phase6_evaluation.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert (ROOT / "reports/phase6/phase6_evaluation.json").exists()
    assert (ROOT / "reports/phase6/phase6_evaluation.md").exists()
