import pytest
from app.models.analyzeModel import BankStatementAnalyzer


@pytest.fixture
def analyzer():
    return BankStatementAnalyzer("dummy.csv")


@pytest.mark.parametrize("date_input,expected", [
    ("01-02-2025",   "2025-02-01"),
    ("01/02/2025",   "2025-02-01"),
    ("01-Feb-2025",  "2025-02-01"),
    ("2025-02-01",   "2025-02-01"),
    ("01 Feb 2025",  "2025-02-01"),
    ("not a date",   "not a date"),
])
def test_normalize_date(analyzer, date_input, expected):
    assert analyzer.normalize_date(date_input) == expected


def test_normalize_date_empty(analyzer):
    # normalize_date("") hits `if not date_input: return None`
    result = analyzer.normalize_date("")
    assert result is None or result == ""
