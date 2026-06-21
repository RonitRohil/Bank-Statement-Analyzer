import logging
import pytest
from app.models.analyzer import BankStatementAnalyzer


@pytest.fixture
def analyzer(tmp_path):
    dummy = tmp_path / "dummy.csv"
    dummy.write_text("date,narration,amount,balance\n")
    return BankStatementAnalyzer(str(dummy))


def _txn(date="2025-01-01", amount=100.0, narration="UPI/transfer", balance=5000.0):
    return {
        "transaction_date": date,
        "amount": amount,
        "narration": narration,
        "balance": balance,
        "transaction_type": "DEBIT",
    }


def test_exact_duplicate_is_removed(analyzer):
    txn = _txn()
    result = analyzer._deduplicate_transactions([txn, txn.copy()])
    assert len(result) == 1


def test_near_duplicate_different_narration_kept(analyzer):
    txn1 = _txn(narration="UPI/swiggy")
    txn2 = _txn(narration="UPI/zomato")
    result = analyzer._deduplicate_transactions([txn1, txn2])
    assert len(result) == 2


def test_none_balance_deduped_correctly(analyzer):
    txn1 = _txn(balance=None)
    txn2 = _txn(balance=None)
    result = analyzer._deduplicate_transactions([txn1, txn2])
    assert len(result) == 1


def test_no_duplicates_unchanged(analyzer):
    txns = [
        _txn(date="2025-01-01"),
        _txn(date="2025-01-02"),
        _txn(date="2025-01-03"),
    ]
    result = analyzer._deduplicate_transactions(txns)
    assert len(result) == 3


def test_keeps_first_occurrence(analyzer):
    txn1 = {**_txn(), "transaction_type": "DEBIT"}
    txn2 = {**_txn(), "transaction_type": "CREDIT"}  # same key, different extra field
    result = analyzer._deduplicate_transactions([txn1, txn2])
    assert len(result) == 1
    assert result[0]["transaction_type"] == "DEBIT"


def test_log_emitted_on_drop(analyzer, caplog):
    txn = _txn()
    with caplog.at_level(logging.INFO, logger="app.models.analyzer"):
        analyzer._deduplicate_transactions([txn, txn.copy()])
    assert any("[DEDUP]" in msg for msg in caplog.messages)


def test_no_log_when_clean(analyzer, caplog):
    with caplog.at_level(logging.INFO, logger="app.models.analyzer"):
        analyzer._deduplicate_transactions([_txn(date="2025-01-01"), _txn(date="2025-01-02")])
    assert not any("[DEDUP]" in msg for msg in caplog.messages)
