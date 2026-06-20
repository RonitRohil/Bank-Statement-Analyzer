from collections import defaultdict
from typing import Any

LARGE_TXN_THRESHOLD = 10_000


def generate_insights(
    transactions: list[dict[str, Any]],
    merchant_insights: dict[str, Any],
) -> list[str]:
    """
    Derive plain-language descriptive callouts from already-computed data.
    Pure function — no I/O, no side effects. Returns [] for empty/sparse input.
    """
    if not transactions:
        return []

    insights: list[str] = []

    category_totals: dict[str, float] = defaultdict(float)
    total_debit = 0.0
    total_credit = 0.0
    large_txn_count = 0

    for txn in transactions:
        amount = txn.get("amount")
        txn_type = (txn.get("transaction_type") or "").upper()
        categories = txn.get("category") or []

        if not isinstance(amount, (int, float)) or amount == 0:
            continue

        amount = abs(amount)

        if amount > LARGE_TXN_THRESHOLD:
            large_txn_count += 1

        if txn_type in ("CREDIT", "CR"):
            total_credit += amount
        else:
            total_debit += amount
            for cat in categories:
                category_totals[cat] += amount

    # 1. Top spending category + share of spend
    if category_totals and total_debit > 0:
        top_cat = max(category_totals, key=lambda c: category_totals[c])
        share = (category_totals[top_cat] / total_debit) * 100
        insights.append(f"Top spending category: {top_cat} ({share:.0f}% of spend)")

    # 2. Most frequent merchant (excluding UNKNOWN bucket)
    named = {k: v for k, v in (merchant_insights or {}).items() if k != "UNKNOWN"}
    if named:
        top_merchant = max(named, key=lambda m: named[m].get("count", 0))
        count = named[top_merchant].get("count", 0)
        if count >= 2:
            insights.append(f"Most frequent merchant: {top_merchant} ({count}×)")

    # 3. Large transaction count
    if large_txn_count > 0:
        label = "transaction" if large_txn_count == 1 else "transactions"
        insights.append(f"{large_txn_count} {label} above ₹10,000")

    # 4. Net cash flow direction
    if total_credit > 0 or total_debit > 0:
        net = total_credit - total_debit
        if net > 0:
            insights.append(f"Net positive: +₹{net:,.0f} for the period")
        elif net < 0:
            insights.append(f"Net negative: −₹{abs(net):,.0f} for the period")

    # 5. Likely-recurring teaser: ≥3 hits with coefficient of variation < 15%
    for merchant, data in (merchant_insights or {}).items():
        if merchant == "UNKNOWN":
            continue
        m_count = data.get("count", 0)
        avg = data.get("avg_amount")
        std = data.get("std_amount")
        if m_count >= 3 and avg and avg > 0:
            cv = (std / avg) if std is not None else 1.0
            if cv < 0.15:
                insights.append(
                    f"Likely recurring: {merchant} (₹{avg:,.0f} avg, {m_count}×)"
                )
                break  # teaser — one match only

    return insights
