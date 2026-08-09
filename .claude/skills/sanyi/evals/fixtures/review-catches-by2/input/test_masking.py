"""Tests for PII masking — evidence for the Buyi contract."""

from masking import mask_pii


def test_pii_always_masked():
    """PII patterns are replaced."""
    text = "Contact john@example.com or 555-123-4567"
    result = mask_pii(text)
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "john@example.com" not in result


def test_no_bypass_flag():
    """No env var or flag can disable masking."""
    import os

    os.environ["ENABLE_PII_MASKING"] = "false"
    try:
        text = "SSN: 123-45-6789"
        result = mask_pii(text)
        # This test verifies the invariant: masking cannot be turned off
        assert "[SSN]" in result
        assert "123-45-6789" not in result
    finally:
        os.environ.pop("ENABLE_PII_MASKING", None)
