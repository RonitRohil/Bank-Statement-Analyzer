"""
Regression tests for enrich_with_llm() — TD-033.

Before the fix, item["index"] was used as an offset into batch_indices
(double-indexing), causing categories to land on the wrong transaction
or silently crash. These tests pin the correct behaviour.
"""

import json
import pytest
import httpx

from app.services.llm_enricher import enrich_with_llm


def _make_transactions():
    """4 transactions; indices 1 and 3 have no category (LLM targets)."""
    return [
        {"narration": "NEFT SALARY", "category": ["Salary"], "merchant": None},
        {"narration": "POS/ZOMATO/MUMBAI", "category": [], "merchant": None},
        {"narration": "UPI/HDFC/RENT", "category": ["Transfer"], "merchant": None},
        {"narration": "POS/MAKEMYTRIP/DEL", "category": [], "merchant": None},
    ]


def _ollama_response(items: list) -> httpx.Response:
    """Wrap a list of result dicts in a fake Ollama /v1/chat/completions response."""
    body = {
        "choices": [{"message": {"content": json.dumps(items)}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    # raise_for_status() requires the request to be set on the response
    request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    return httpx.Response(200, json=body, request=request)


@pytest.mark.asyncio
async def test_category_lands_on_correct_transaction(monkeypatch):
    """LLM result with index=1 and index=3 must enrich transactions[1] and [3]."""
    transactions = _make_transactions()

    llm_results = [
        {"index": 1, "category": "Food & Dining", "merchant": "Zomato"},
        {"index": 3, "category": "Travel", "merchant": None},
    ]

    async def mock_post(self, url, **kwargs):
        return _ollama_response(llm_results)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await enrich_with_llm(transactions)

    # Rows 1 and 3 enriched
    assert result[1]["category"] == ["Food & Dining"]
    assert result[1]["merchant"] == "Zomato"
    assert result[1].get("llm_enriched") is True

    assert result[3]["category"] == ["Travel"]
    assert result[3].get("llm_enriched") is True

    # Row 0 and 2 untouched (were already categorized)
    assert result[0]["category"] == ["Salary"]
    assert result[0].get("llm_enriched") is None
    assert result[2]["category"] == ["Transfer"]
    assert result[2].get("llm_enriched") is None


@pytest.mark.asyncio
async def test_out_of_range_index_is_skipped(monkeypatch):
    """A model returning an index outside [0, len(transactions)) must not crash."""
    transactions = _make_transactions()

    llm_results = [
        {
            "index": 99,
            "category": "Food & Dining",
            "merchant": "Zomato",
        },  # out-of-range
        {"index": 1, "category": "Food & Dining", "merchant": "Zomato"},  # valid
    ]

    async def mock_post(self, url, **kwargs):
        return _ollama_response(llm_results)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await enrich_with_llm(transactions)

    # Valid row enriched
    assert result[1]["category"] == ["Food & Dining"]
    assert result[1].get("llm_enriched") is True
    # No crash, all rows present
    assert len(result) == 4


@pytest.mark.asyncio
async def test_merchant_not_overwritten_when_already_set(monkeypatch):
    """If a transaction already has a merchant, the LLM must not overwrite it."""
    transactions = _make_transactions()
    transactions[1]["merchant"] = "Existing Merchant"

    llm_results = [
        {"index": 1, "category": "Food & Dining", "merchant": "Zomato"},
        {"index": 3, "category": "Travel", "merchant": None},
    ]

    async def mock_post(self, url, **kwargs):
        return _ollama_response(llm_results)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await enrich_with_llm(transactions)

    assert result[1]["merchant"] == "Existing Merchant"


@pytest.mark.asyncio
async def test_ollama_down_returns_transactions_unchanged(monkeypatch):
    """A ConnectError must not crash the function; original transactions returned."""
    transactions = _make_transactions()

    async def mock_post(self, url, **kwargs):
        raise httpx.ConnectError("Ollama not reachable")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await enrich_with_llm(transactions)

    assert result is transactions
    assert result[1]["category"] == []
    assert result[3]["category"] == []
