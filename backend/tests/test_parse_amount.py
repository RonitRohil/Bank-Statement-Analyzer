import pytest
from app.models.analyzeModel import BankStatementAnalyzer


@pytest.mark.parametrize("value,expected", [
    ("1,234.56",        1234.56),
    ("₹ 50,000.00",    50000.0),
    ("1500.00 Cr.",     1500.0),
    ("750.00 Dr.",       750.0),
    ("(200.00)",        -200.0),
    ("0.00",              0.0),
    ("",                 None),
    ("N/A",              None),
    ("01/02/2025",       None),
])
def test_parse_amount(value, expected):
    assert BankStatementAnalyzer.parse_amount(value) == expected
