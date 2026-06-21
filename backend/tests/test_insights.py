from app.services.insights import detect_recurring, generate_insights

# Shared fixture: salary credit + varied debits across multiple merchants
FIXTURE_TXN = [
    {
        "transaction_date": "2025-01-01",
        "transaction_type": "CREDIT",
        "amount": 80000.0,
        "merchant": None,
        "category": [],
        "narration": "SALARY",
    },
    {
        "transaction_date": "2025-01-05",
        "transaction_type": "DEBIT",
        "amount": 1200.0,
        "merchant": "AMAZON",
        "category": ["E-COMMERCE"],
        "narration": "Amazon order",
    },
    {
        "transaction_date": "2025-01-10",
        "transaction_type": "DEBIT",
        "amount": 15000.0,
        "merchant": "AMAZON",
        "category": ["E-COMMERCE"],
        "narration": "Amazon electronics",
    },
    {
        "transaction_date": "2025-01-15",
        "transaction_type": "DEBIT",
        "amount": 800.0,
        "merchant": "SWIGGY",
        "category": ["FOOD_DELIVERY"],
        "narration": "Swiggy order",
    },
    {
        "transaction_date": "2025-01-20",
        "transaction_type": "DEBIT",
        "amount": 800.0,
        "merchant": "SWIGGY",
        "category": ["FOOD_DELIVERY"],
        "narration": "Swiggy order",
    },
    {
        "transaction_date": "2025-01-25",
        "transaction_type": "DEBIT",
        "amount": 800.0,
        "merchant": "SWIGGY",
        "category": ["FOOD_DELIVERY"],
        "narration": "Swiggy order",
    },
]

FIXTURE_MERCHANT_INSIGHTS = {
    "AMAZON": {
        "count": 2,
        "avg_amount": 8100.0,
        "median_amount": 8100.0,
        "std_amount": 9758.79,
        "first_seen": "2025-01-05",
        "last_seen": "2025-01-10",
        "common_days": [],
    },
    "SWIGGY": {
        "count": 3,
        "avg_amount": 800.0,
        "median_amount": 800.0,
        "std_amount": 0.0,
        "first_seen": "2025-01-15",
        "last_seen": "2025-01-25",
        "common_days": [],
    },
}


def test_top_category_identified():
    insights = generate_insights(FIXTURE_TXN, FIXTURE_MERCHANT_INSIGHTS)
    top_cat = next((i for i in insights if i.startswith("Top spending category")), None)
    assert top_cat is not None
    # E-COMMERCE: 16200, FOOD_DELIVERY: 2400 → E-COMMERCE wins
    assert "E-COMMERCE" in top_cat
    assert "%" in top_cat


def test_most_frequent_merchant():
    insights = generate_insights(FIXTURE_TXN, FIXTURE_MERCHANT_INSIGHTS)
    freq = next((i for i in insights if i.startswith("Most frequent merchant")), None)
    assert freq is not None
    # SWIGGY has count=3, AMAZON count=2
    assert "SWIGGY" in freq
    assert "3×" in freq


def test_large_transaction_count():
    insights = generate_insights(FIXTURE_TXN, FIXTURE_MERCHANT_INSIGHTS)
    large = next((i for i in insights if "above ₹10,000" in i), None)
    assert large is not None
    # Only the 15000 AMAZON debit qualifies; salary credit (80000) also qualifies
    assert large.startswith("2")


def test_net_direction_positive():
    insights = generate_insights(FIXTURE_TXN, FIXTURE_MERCHANT_INSIGHTS)
    net = next((i for i in insights if i.startswith("Net")), None)
    assert net is not None
    # 80000 - (1200+15000+800+800+800) = 80000 - 18600 = 61400 → positive
    assert "positive" in net
    assert "61,400" in net


def test_likely_recurring_teaser():
    insights = generate_insights(FIXTURE_TXN, FIXTURE_MERCHANT_INSIGHTS)
    recurring = next((i for i in insights if "Likely recurring" in i), None)
    assert recurring is not None
    # SWIGGY: count=3, std=0.0, cv=0.0 → qualifies
    assert "SWIGGY" in recurring


def test_empty_transactions_returns_empty_list():
    assert generate_insights([], {}) == []
    assert generate_insights([], FIXTURE_MERCHANT_INSIGHTS) == []


def test_single_transaction_no_crash():
    single = [
        {
            "transaction_date": "2025-01-01",
            "transaction_type": "CREDIT",
            "amount": 5000.0,
            "merchant": None,
            "category": [],
            "narration": "SALARY",
        }
    ]
    insights = generate_insights(single, {})
    # No debit → no category insight; only net direction
    assert isinstance(insights, list)
    net = next((i for i in insights if i.startswith("Net positive")), None)
    assert net is not None


def test_all_credit_statement_no_category_insight():
    credits_only = [
        {
            "transaction_date": "2025-01-01",
            "transaction_type": "CREDIT",
            "amount": 10000.0,
            "merchant": None,
            "category": ["SALARY"],
            "narration": "SALARY",
        }
        for _ in range(3)
    ]
    insights = generate_insights(credits_only, {})
    # No debit → category_totals is empty → no top-category insight
    assert not any(i.startswith("Top spending category") for i in insights)
    # Net should be positive
    assert any("Net positive" in i for i in insights)


def test_no_large_txns_no_large_insight():
    small_txns = [
        {
            "transaction_date": "2025-01-01",
            "transaction_type": "DEBIT",
            "amount": 500.0,
            "merchant": "CAFE",
            "category": ["FOOD_DELIVERY"],
            "narration": "Coffee",
        }
    ]
    insights = generate_insights(
        small_txns, {"CAFE": {"count": 1, "avg_amount": 500.0, "std_amount": None}}
    )
    assert not any("above ₹10,000" in i for i in insights)


def test_unknown_merchant_excluded_from_frequent():
    txns = [
        {
            "transaction_date": "2025-01-01",
            "transaction_type": "DEBIT",
            "amount": 200.0,
            "merchant": None,
            "category": [],
            "narration": "misc",
        }
    ] * 5
    merchant_insights = {
        "UNKNOWN": {"count": 5, "avg_amount": 200.0, "std_amount": 0.0}
    }
    insights = generate_insights(txns, merchant_insights)
    assert not any("UNKNOWN" in i for i in insights)


# ── detect_recurring tests ──────────────────────────────────────────────────


def test_recurring_detected_when_cv_low():
    merchant_insights = {
        "NETFLIX": {
            "count": 3,
            "avg_amount": 649.0,
            "std_amount": 5.0,  # CV = 0.0077 — well below 0.25
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert len(result) == 1
    assert result[0]["merchant"] == "NETFLIX"
    assert result[0]["cv"] < 0.25


def test_recurring_excluded_when_cv_high():
    merchant_insights = {
        "AMAZON": {
            "count": 5,
            "avg_amount": 2000.0,
            "std_amount": 1500.0,  # CV = 0.75 — above threshold
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []


def test_recurring_excluded_when_count_below_3():
    merchant_insights = {
        "NETFLIX": {
            "count": 2,
            "avg_amount": 649.0,
            "std_amount": 0.0,
            "first_seen": "2026-01-01",
            "last_seen": "2026-02-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []


def test_recurring_excludes_unknown():
    merchant_insights = {
        "UNKNOWN": {
            "count": 10,
            "avg_amount": 100.0,
            "std_amount": 1.0,
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []
