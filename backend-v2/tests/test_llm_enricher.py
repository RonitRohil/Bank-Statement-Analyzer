"""
Tests for enrich_with_llm() — TD-033 (index fix), TD-035 (timeout budget + batch cap).
"""

import asyncio
import json
import pytest
import httpx

from unittest.mock import patch

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


# ── TD-035: global timeout budget ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_global_timeout_returns_partial_enrichment(monkeypatch):
    """When the LLM takes longer than llm_total_timeout_s the call must still
    return (no exception raised) with whatever was enriched so far."""
    transactions = _make_transactions()

    async def mock_post(self, url, **kwargs):
        await asyncio.sleep(5)  # longer than the 0.05 s budget below
        return _ollama_response([])

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with patch("app.services.llm_enricher.settings") as mock_settings:
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen2.5:7b"
        mock_settings.llm_total_timeout_s = 0.05
        mock_settings.llm_max_enriched = 100

        result = await enrich_with_llm(transactions)

    # Must return without raising; uncategorized rows stay empty (partial = zero here)
    assert result is transactions
    assert result[1]["category"] == []
    assert result[3]["category"] == []


# ── TD-035: batch cap ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_cap_limits_enriched_count(monkeypatch):
    """With llm_max_enriched=5, at most 5 of 15 uncategorized rows are enriched."""
    transactions = [
        {"narration": f"TXN {i}", "category": [], "merchant": None} for i in range(15)
    ]
    enriched_indices: list[int] = []

    async def mock_post(self, url, **kwargs):
        payload = json.loads(kwargs["json"]["messages"][1]["content"])
        results = [
            {"index": item["index"], "category": "Other", "merchant": None}
            for item in payload
        ]
        enriched_indices.extend(item["index"] for item in payload)
        return _ollama_response(results)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    with patch("app.services.llm_enricher.settings") as mock_settings:
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "qwen2.5:7b"
        mock_settings.llm_total_timeout_s = 30.0
        mock_settings.llm_max_enriched = 5

        result = await enrich_with_llm(transactions)

    enriched_count = sum(1 for t in result if t.get("llm_enriched"))
    assert enriched_count <= 5


# ── CR-S2-08: unified taxonomy ─────────────────────────────────────────────────

def test_regex_and_llm_categories_normalize_to_same_label():
    """FOOD_DELIVERY (regex code) and 'Food & Dining' (LLM label) must map to the
    same canonical label so per-category summaries group them together."""
    from app.services.categories import REGEX_TO_CANONICAL, CANONICAL_CATEGORIES

    regex_canonical = REGEX_TO_CANONICAL["FOOD_DELIVERY"]
    llm_label = "Food & Dining"

    assert regex_canonical == llm_label
    assert llm_label in CANONICAL_CATEGORIES
    assert REGEX_TO_CANONICAL["E-COMMERCE"] == "Shopping"
