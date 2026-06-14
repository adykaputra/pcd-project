from app.privacy_comparison import run_privacy_comparison


def _admin_token(client):
    resp = client.post("/login", json={"password": "admin-pass"})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def test_comparison_engine_returns_method_ranking():
    result = run_privacy_comparison(dataset_version="v3", split="all", include_cases=False)
    assert result["dataset_version"] == "v3"
    assert result["total_cases"] >= 8
    assert len(result["method_metrics"]) >= 5
    top = result["method_metrics"][0]
    assert "method_id" in top
    assert "composite_score" in top


def test_comparison_engine_adaptive_summary_is_consistent():
    result = run_privacy_comparison(dataset_version="v3", split="validation", include_cases=False)
    summary = result["adaptive_summary"]
    assert summary["selection_coverage"] == 1.0
    assert isinstance(summary["selected_method_counts"], dict)


def test_privacy_comparison_endpoint_requires_admin_and_returns_payload(client):
    denied = client.get("/privacy/comparison?dataset_version=v3")
    assert denied.status_code == 403

    token = _admin_token(client)
    resp = client.get("/privacy/comparison?dataset_version=v3&include_cases=0", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["comparison"]["dataset_version"] == "v3"
    assert len(payload["comparison"]["method_metrics"]) >= 5
