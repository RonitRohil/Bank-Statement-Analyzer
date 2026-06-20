import logging
from collections import defaultdict

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.schemas import CategoryBreakdown, StatementPeriod, SummaryResponse, TopMerchant, Transaction

router = APIRouter()
logger = logging.getLogger(__name__)


class SummaryRequest(BaseModel):
    transactions: list[Transaction]


@router.post("/api/analyze/bank/summary", response_model=SummaryResponse)
def summarize_transactions(body: SummaryRequest):
    transactions = body.transactions

    total_income = 0.0
    total_expenses = 0.0
    category_totals: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    merchant_totals: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    amounts = []
    dates = []

    for txn in transactions:
        amount = txn.amount
        if not amount or amount == 0:
            continue

        txn_type = (txn.transaction_type or "").upper()
        amount = abs(amount)
        amounts.append(amount)

        if txn_type in ("CREDIT", "CR"):
            total_income += amount
        else:
            total_expenses += amount
            # category is a list; spend counted once per category (totals may exceed 100% — intentional)
            categories = txn.category or ["Uncategorized"]
            for cat in categories:
                category_totals[cat]["total"] += amount
                category_totals[cat]["count"] += 1

            if txn.merchant:
                merchant_totals[txn.merchant]["total"] += amount
                merchant_totals[txn.merchant]["count"] += 1

        if txn.transaction_date:
            dates.append(txn.transaction_date)

    net = total_income - total_expenses

    if total_expenses <= 0:
        by_category = []
    else:
        by_category = sorted(
            [
                CategoryBreakdown(
                    category=cat,
                    total=round(data["total"], 2),
                    count=data["count"],
                    percentage=round((data["total"] / total_expenses) * 100, 1),
                )
                for cat, data in category_totals.items()
            ],
            key=lambda x: x.total,
            reverse=True,
        )

    top_merchants = sorted(
        [
            TopMerchant(
                merchant=merchant,
                total=round(data["total"], 2),
                count=data["count"],
            )
            for merchant, data in merchant_totals.items()
        ],
        key=lambda x: x.total,
        reverse=True,
    )[:10]

    date_range = None
    if dates:
        dates_sorted = sorted(dates)
        date_range = StatementPeriod(**{"from": dates_sorted[0], "to": dates_sorted[-1]})

    return SummaryResponse(
        total_income=round(total_income, 2),
        total_expenses=round(total_expenses, 2),
        net=round(net, 2),
        date_range=date_range,
        by_category=by_category,
        top_merchants=top_merchants,
        transaction_count=len(transactions),
        avg_transaction_amount=round(sum(amounts) / len(amounts), 2) if amounts else 0.0,
    )
