def calculate_confidence_score(txn: dict) -> float:
    score = 1.0

    transaction_date = txn.get("transaction_date")
    if not transaction_date or not isinstance(transaction_date, str):
        score -= 0.25

    amount = txn.get("amount")
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        score -= 0.25

    narration = txn.get("narration")
    if not narration:
        score -= 0.15
    elif isinstance(narration, str) and len(narration.strip()) < 5:
        score -= 0.05

    if not txn.get("transaction_type"):
        score -= 0.10

    receiver = txn.get("receiver_details", {})
    if (
        not receiver.get("name")
        and not receiver.get("account")
        and not receiver.get("vpa")
    ):
        score -= 0.10

    if txn.get("balance") is None:
        score -= 0.05

    return max(0.0, min(round(score, 2), 1.0))
