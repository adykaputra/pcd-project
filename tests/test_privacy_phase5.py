from app.module2.logic import tokenize_prompt_for_llm
from app.privacy_benchmark_dataset import list_dataset_versions, get_benchmark_cases
from app.privacy_benchmark import run_privacy_benchmark, run_privacy_benchmark_cross_split


def _admin_token(client):
    resp = client.post("/login", json={"password": "admin-pass"})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def test_dataset_versions_and_case_splits_available():
    versions = list_dataset_versions()
    assert "v1" in versions
    assert "v2" in versions
    val_cases = get_benchmark_cases(version="v2", split="validation")
    assert len(val_cases) >= 2


def test_multilingual_tokenization_detects_malay_entities():
    text = "Encik Ahmad dari Kuala Lumpur minta laporan segera."
    tokenized = tokenize_prompt_for_llm(text)
    counts = tokenized["token_counts"]
    assert counts.get("ner_person", 0) >= 1 or counts.get("name", 0) >= 1
    assert counts.get("ner_location", 0) >= 1 or counts.get("location", 0) >= 1


def test_benchmark_supports_dataset_version_and_split():
    result = run_privacy_benchmark(dataset_version="v2", split="validation")
    metrics = result["metrics"]
    assert metrics["dataset_version"] == "v2"
    assert metrics["split"] == "validation"
    assert metrics["total_cases"] >= 2


def test_cross_split_benchmark_returns_all_sections():
    result = run_privacy_benchmark_cross_split(dataset_version="v2")
    assert result["dataset_version"] == "v2"
    assert set(result["by_split"].keys()) == {"train", "validation", "test"}
    assert result["overall"]["metrics"]["total_cases"] >= 6


def test_phase5_dataset_endpoints_admin(client):
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    datasets = client.get("/privacy/benchmark/datasets", headers=headers)
    assert datasets.status_code == 200
    assert "v2" in datasets.get_json()["versions"]

    bench = client.get("/privacy/benchmark?dataset_version=v2&split=validation", headers=headers)
    assert bench.status_code == 200
    assert bench.get_json()["benchmark"]["metrics"]["dataset_version"] == "v2"

    cross = client.get("/privacy/benchmark?dataset_version=v2&mode=cross_split&persist=0", headers=headers)
    assert cross.status_code == 200
    payload = cross.get_json()["benchmark"]
    assert "overall" in payload and "by_split" in payload

    calib = client.get("/privacy/calibrate?dataset_version=v2&split=validation", headers=headers)
    assert calib.status_code == 200
    assert calib.get_json()["calibration"]["dataset_version"] == "v2"
