from app import create_app


def _client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_root_portal_page_serves_role_options():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Client Access" in body
    assert "Admin Access" in body


def test_client_portal_page_renders():
    client = _client()
    resp = client.get("/client?name=Aisyah")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Privacy-Protected Chat" in body
    assert "Aisyah" in body


def test_client_chat_ok(monkeypatch):
    client = _client()

    def _fake_pipeline(**kwargs):
        return {
            "status": "ok",
            "provider": "mock",
            "response": "Mock assistant response",
            "offline_mode": True,
            "risk_assessment": {"policy_action": "allow"},
            "tokenization": {"applied": False},
        }, 200

    monkeypatch.setattr("app.module3.routes._run_firewall_pipeline", _fake_pipeline)

    resp = client.post("/client/chat", json={"prompt": "Hello", "provider": "mock"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["reply"] == "Mock assistant response"


def test_client_chat_challenge(monkeypatch):
    client = _client()

    def _fake_pipeline(**kwargs):
        return {
            "status": "challenge",
            "message": "Prompt requires human review before LLM forwarding.",
            "risk_assessment": {"policy_action": "challenge"},
        }, 409

    monkeypatch.setattr("app.module3.routes._run_firewall_pipeline", _fake_pipeline)

    resp = client.post("/client/chat", json={"prompt": "My phone is 012-3456789"})
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["status"] == "challenge"
    assert "sensitive" in body["reply"].lower()
