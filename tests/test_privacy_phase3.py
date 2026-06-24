from app.privacy_ner import detect_named_entities
from app.privacy_calibration import calibrate_policy_thresholds
from app.privacy_benchmark import run_privacy_benchmark


def test_ner_fallback_detects_entities(monkeypatch):
    monkeypatch.setenv("PRIVACY_NER_BACKEND", "fallback")
    text = "Ali from Kuala Lumpur works at Acme Bank."
    result = detect_named_entities(text)
    assert result["backend"] == "fallback"
    labels = {e["label"] for e in result["entities"]}
    assert "PERSON" in labels or "GPE" in labels


def test_calibration_recommends_valid_thresholds():
    result = calibrate_policy_thresholds()
    assert result["challenge_threshold"] < result["block_threshold"]
    assert isinstance(result["objective_cost"], float)
    assert len(result["case_evaluations"]) >= 6


def test_benchmark_includes_visualization_payload():
    result = run_privacy_benchmark()
    viz = result.get("visualization", {})
    assert "policy_action_chart" in viz
    assert "quality_gauges" in viz


def test_privacy_calibration_endpoint_admin_only(client):
    denied = client.get("/privacy/calibrate")
    assert denied.status_code == 403

    login = client.post("/login", json={"password": "admin-pass"})
    token = login.get_json()["token"]
    ok = client.get("/privacy/calibrate", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["status"] == "ok"
    cal = payload["calibration"]
    assert cal["challenge_threshold"] < cal["block_threshold"]
