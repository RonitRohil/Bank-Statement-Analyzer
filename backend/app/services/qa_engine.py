import asyncio
import json
import logging
from typing import Optional

import httpx
from sqlmodel import Session, select

from app.config.settings import settings
from app.db.crud import get_monthly_summary
from app.db.models import StatementDB, TransactionDB

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_transactions",
            "description": "Search stored transactions by date range, category, merchant, or transaction type. Use for questions about spending amounts, counts, or lists of transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Optional. Filter to a specific account."},
                    "start_date": {"type": "string", "description": "Optional. ISO date YYYY-MM-DD. Start of date range."},
                    "end_date": {"type": "string", "description": "Optional. ISO date YYYY-MM-DD. End of date range."},
                    "category": {"type": "string", "description": "Optional. Category name, e.g. 'Food & Dining'."},
                    "merchant": {"type": "string", "description": "Optional. Merchant name (partial match), e.g. 'AMAZON'."},
                    "txn_type": {"type": "string", "enum": ["CREDIT", "DEBIT"], "description": "Optional. CREDIT or DEBIT."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_totals",
            "description": "Get income, expense, and net totals for a specific account grouped by month. Use for month-over-month questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Account number to summarize."}
                },
                "required": ["account_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_statements",
            "description": "List all stored statements with their metadata (bank, account, period, transaction count). Use for questions about which statements are available.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _execute_tool(tool_name: str, args: dict, session: Session) -> str:
    """Execute the tool chosen by the LLM and return a JSON string of results."""
    if tool_name == "query_transactions":
        account_number = args.get("account_number")
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        category = args.get("category")
        merchant = args.get("merchant")
        txn_type = args.get("txn_type")

        query = select(TransactionDB)

        if account_number:
            stmts = session.exec(
                select(StatementDB).where(StatementDB.account_number == account_number)
            ).all()
            stmt_ids = [s.id for s in stmts]
            if not stmt_ids:
                return json.dumps([])
            query = query.where(TransactionDB.statement_id.in_(stmt_ids))

        if start_date:
            query = query.where(TransactionDB.transaction_date >= start_date)
        if end_date:
            query = query.where(TransactionDB.transaction_date <= end_date)
        if category:
            query = query.where(TransactionDB.category.contains(category))
        if merchant:
            query = query.where(TransactionDB.merchant.contains(merchant))
        if txn_type:
            query = query.where(TransactionDB.transaction_type == txn_type)

        rows = session.exec(query.limit(200)).all()
        result = [
            {
                "date": r.transaction_date,
                "type": r.transaction_type,
                "amount": r.amount,
                "narration": r.narration,
                "merchant": r.merchant,
                "category": json.loads(r.category or "[]"),
            }
            for r in rows
        ]
        return json.dumps(result)

    elif tool_name == "get_monthly_totals":
        account_number = args.get("account_number", "")
        result = get_monthly_summary(account_number, session)
        return json.dumps(result)

    elif tool_name == "list_statements":
        rows = session.exec(select(StatementDB).limit(50)).all()
        result = [
            {
                "id": r.id,
                "bank_name": r.bank_name,
                "account_holder": r.account_holder,
                "account_number": r.account_number,
                "period_from": r.period_from,
                "period_to": r.period_to,
                "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
            }
            for r in rows
        ]
        return json.dumps(result)

    logger.warning("[QA] Unknown tool: %s", tool_name)
    return json.dumps([])


async def answer_question(
    question: str, account_number: Optional[str], session: Session
) -> dict:
    """Two-pass LLM call over stored transaction history.

    Pass 1 — tool selection: LLM picks which query to run.
    Pass 2 — answer generation: LLM summarizes the query result in plain language.

    Returns: {"answer": str, "tool_used": str, "data_points": int}
    """
    url = f"{settings.ollama_base_url}/v1/chat/completions"

    async def _run() -> dict:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=55.0, write=10.0, pool=5.0)
        ) as client:
            # Pass 1: tool selection
            pass1 = await client.post(
                url,
                json={
                    "model": settings.ollama_model,
                    "messages": [{"role": "user", "content": question}],
                    "tools": TOOLS,
                    "tool_choice": "auto",
                    "stream": False,
                },
            )
            pass1.raise_for_status()
            pass1_data = pass1.json()

            message = pass1_data["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            # LLM answered directly without calling a tool
            if not tool_calls:
                direct = message.get("content") or "I couldn't find relevant data to answer that question."
                return {"answer": direct, "tool_used": "none", "data_points": 0}

            tool_call = tool_calls[0]
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            tool_call_id = tool_call.get("id", "tool_0")

            # Inject account_number if provided at request level and not already set
            if account_number and "account_number" not in tool_args:
                tool_args["account_number"] = account_number

            logger.info("[QA] Tool: %s  args: %s", tool_name, tool_args)

            result_json = _execute_tool(tool_name, tool_args, session)

            try:
                parsed = json.loads(result_json)
                data_points = len(parsed) if isinstance(parsed, list) else 1
            except (json.JSONDecodeError, TypeError):
                data_points = 1

            # Pass 2: answer generation
            pass2 = await client.post(
                url,
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "user", "content": question},
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls,
                        },
                        {
                            "role": "tool",
                            "content": result_json,
                            "tool_call_id": tool_call_id,
                        },
                    ],
                    "stream": False,
                },
            )
            pass2.raise_for_status()
            pass2_data = pass2.json()

            answer = (pass2_data["choices"][0]["message"].get("content") or "").strip()
            if not answer:
                answer = "I found the data but couldn't generate a summary."

            return {"answer": answer, "tool_used": tool_name, "data_points": data_points}

    try:
        return await asyncio.wait_for(_run(), timeout=60.0)
    except (httpx.ConnectError, asyncio.TimeoutError):
        return {
            "answer": "Q&A is unavailable — make sure Ollama is running (`ollama serve`)",
            "tool_used": "error",
            "data_points": 0,
        }
    except Exception as e:
        logger.error("[QA] Unexpected error: %s", e, exc_info=True)
        return {
            "answer": "Q&A is unavailable — make sure Ollama is running (`ollama serve`)",
            "tool_used": "error",
            "data_points": 0,
        }
