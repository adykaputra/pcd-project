from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_export_viva_pack_script_generates_artifacts():
    proc = subprocess.run(
        ["python3", "scripts/export_viva_pack.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert (ROOT / "reports/viva/viva_pack.json").exists()
    assert (ROOT / "reports/viva/viva_pack.md").exists()
    assert (ROOT / "reports/viva/method_leaderboard.csv").exists()
    assert (ROOT / "reports/viva/adversarial_cases.csv").exists()
