from app.privacy_adversarial import run_adversarial_stress


def _admin_token(client):
    resp = client.post("/login", json={"password": "admin-pass"})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def test_generate_exposes_adaptive_router_metadata(client, monkeypatch):
    class _Adapter:
        provider_name = "mock"

        def send_prompt(self, prompt):
            return {"text": "ok", "usage": {}}

    monkeypatch.setattr("app.module3.adapters.get_adapter", lambda provider, model=None: _Adapter())
    resp = client.post("/generate", json={"prompt": "Call me at 012-3456789", "provider": "mock"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["tokenization"]["router"]["mode"] in {"adaptive", "legacy"}
    if body["tokenization"]["router"]["mode"] == "adaptive":
        assert body["tokenization"]["router"]["selected_method_id"]
        assert body["dispatch_proof"]["selected_method_id"]


def test_adversarial_stress_function_runs():
    payload = run_adversarial_stress(dataset_version="v3", split="test", max_cases=3, max_variants=2)
    assert payload["dataset_version"] == "v3"
    assert "summary" in payload
    assert payload["total_cases"] >= 1


def test_adversarial_and_vault_endpoints_admin(client):
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    stress = client.get("/privacy/adversarial?dataset_version=v3&max_cases=2&max_variants=2", headers=headers)
    assert stress.status_code == 200
    assert stress.get_json()["status"] == "ok"

    stats = client.get("/privacy/vault/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.get_json()["status"] == "ok"

    purge = client.post("/privacy/vault/purge", json={"retention_hours": 1}, headers=headers)
    assert purge.status_code == 200
    assert purge.get_json()["status"] == "ok"
