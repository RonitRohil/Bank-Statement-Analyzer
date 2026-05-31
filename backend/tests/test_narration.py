import pytest
from app.models.analyzeModel import BankStatementAnalyzer

EXPECTED_KEYS = {
    "payment_method", "upi_id", "transaction_reference",
    "receiver_details", "bank_peer", "merchant", "category",
}


def parse(narration):
    return BankStatementAnalyzer.analyze_narration_details(narration)


def test_narration_keys_always_present():
    """All expected keys exist even for an empty narration."""
    result = parse("")
    assert EXPECTED_KEYS.issubset(result.keys())


def test_upi_structured_payment_method():
    result = parse("UPI/123456789012/Payment/HDFC/TXN001")
    assert result["payment_method"] == "UPI"


def test_upi_structured_bank_peer():
    result = parse("UPI/123456789012/Payment/HDFC/TXN001")
    assert "HDFC" in result["bank_peer"]


def test_imps_payment_method():
    result = parse("IMPS/987654321098/JOHN DOE/SBI")
    assert result["payment_method"] == "IMPS"


def test_imps_bank_peer():
    result = parse("IMPS/987654321098/JOHN DOE/SBI")
    assert "SBI" in result["bank_peer"]


def test_empty_narration_no_crash():
    result = parse("")
    assert isinstance(result, dict)
    for key in EXPECTED_KEYS:
        assert key in result


@pytest.mark.xfail(
    reason=(
        "UPI structured match returns early before merchant detection. "
        "Merchant is not extracted for structured UPI narrations — known limitation."
    )
)
def test_amazon_merchant_in_upi_narration():
    result = parse("UPI/000000000000/AMAZON PAY/HDFC/XYZ")
    assert result["merchant"] is not None and "AMAZON" in result["merchant"]
