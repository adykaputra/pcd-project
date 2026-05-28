#!/usr/bin/env python3
"""Basic deployment smoke checks for local/prod container runtime."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def call_json(url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None) -> dict:
    payload = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, method=method, data=payload, headers=request_headers)
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 - controlled local smoke target
        data = resp.read().decode("utf-8")
        return json.loads(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run privacy-firewall smoke checks.")
    parser.add_argument("--base-url", default="http://localhost:5100", help="Gateway base URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    checks = []
    try:
        health = call_json(f"{base}/healthz")
        checks.append(("healthz", health.get("status") == "ok"))

        login = call_json(f"{base}/login", method="POST", body={"password": "admin-pass"})
        token = login.get("token")
        checks.append(("login", bool(token)))

        generate = call_json(
            f"{base}/generate",
            method="POST",
            body={"prompt": "Explain zero-trust architecture.", "provider": "mock"},
        )
        checks.append(("generate", generate.get("status") == "ok"))

        summary = call_json(
            f"{base}/audit/summary",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        checks.append(("audit_summary", summary.get("status") == "ok"))
    except urllib.error.HTTPError as exc:
        print(f"[FAIL] HTTP {exc.code}: {exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] Unexpected error: {exc}")
        return 1

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")

    if failed:
        print(f"Smoke checks failed: {', '.join(failed)}")
        return 1
    print("All deployment smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
