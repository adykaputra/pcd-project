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


def test_comparison_engine_supports_scenario_and_language_filters():
    filtered = run_privacy_comparison(
        dataset_version="v3",
        split="all",
        include_cases=False,
        scenario="obfuscation",
        language="en",
    )
    assert filtered["filters"]["scenario"] == "obfuscation"
    assert filtered["filters"]["language"] == "en"
    assert filtered["total_cases"] >= 1
    assert set(filtered["scenario_distribution"].keys()) == {"obfuscation"}
    assert set(filtered["language_distribution"].keys()) == {"en"}


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


def test_privacy_comparison_endpoint_accepts_filters(client):
    token = _admin_token(client)
    resp = client.get(
        "/privacy/comparison?dataset_version=v3&include_cases=0&scenario=explicit&language=en",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["comparison"]["filters"]["scenario"] == "explicit"
    assert payload["comparison"]["filters"]["language"] == "en"
