import pytest
from app.module2.logic import redact_pii, sanitize_prompt_for_llm


def test_redact_ic_with_dashes():
    text = "My IC is 800101-01-1234"
    out = redact_pii(text)
    assert "[REDACTED_ID]" in out
    assert "800101-01-1234" not in out


def test_redact_ic_without_dashes():
    text = "My IC is 800101011234"
    out = redact_pii(text)
    assert "[REDACTED_ID]" in out
    assert "800101011234" not in out


def test_multiple_emails():
    text = "Contact a@ex.com or b@ex.org for details"
    out = redact_pii(text)
    assert out.count("[REDACTED_EMAIL]") == 2
    assert "a@ex.com" not in out


def test_no_pii_preserves_text():
    text = "There is no PII here, just a message about privacy."
    out = redact_pii(text)
    assert out == text


def test_phone_redaction_variants():
    samples = [
        "+6012-3456789",
        "012-3456789",
        "60123456789",
        "0123456789",
    ]
    for s in samples:
        out = redact_pii(f"Call me at {s}")
        assert "[REDACTED_PHONE]" in out
        assert s not in out


def test_invalid_month_not_redacted():
    # Month '13' is invalid (YYMMDD where MM must be 01-12) and should NOT be redacted
    text = "My IC is 801301-01-1234"
    out = redact_pii(text)
    assert "[REDACTED_ID]" not in out
    assert "801301-01-1234" in out


def test_sanitize_prompt_for_llm_layers_multiple_detectors():
    text = "Ali from Kuala Lumpur. Phone 012-3456789. Email ali@example.com"
    result = sanitize_prompt_for_llm(text)
    sanitized = result["sanitized_prompt"]

    assert result["had_pii"] is True
    assert "[REDACTED_NAME]" in sanitized
    assert "[REDACTED_LOCATION]" in sanitized
    assert "[REDACTED_PHONE]" in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert all(v == 0 for v in result["remaining_pii_counts"].values())


def test_sanitize_prompt_for_llm_preserves_clean_prompt():
    text = "Summarize this product feedback clearly."
    result = sanitize_prompt_for_llm(text)
    assert result["sanitized_prompt"] == text
    assert result["had_pii"] is False
