from app import create_app


def test_healthz_endpoint_reports_ok():
    app = create_app()
    app.testing = True
    with app.test_client() as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["status"] == "ok"
        assert payload["service"] == "llm-privacy-firewall"
        assert payload["checks"]["audit_db"] == "ok"
