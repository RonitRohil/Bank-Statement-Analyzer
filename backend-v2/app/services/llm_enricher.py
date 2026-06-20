import json
import logging
from typing import Any

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

KNOWN_CATEGORIES = [
    "Food & Dining",
    "Shopping",
    "Entertainment",
    "Travel",
    "Utilities",
    "Healthcare",
    "Education",
    "Investment",
    "Salary",
    "Transfer",
    "Refund",
    "EMI/Loan",
    "Insurance",
    "Fuel",
    "Groceries",
    "Other",
]

BATCH_SIZE = 10

SYSTEM_PROMPT = f"""You are a bank transaction categorizer for Indian bank statements.

Given a list of transaction narrations, return a JSON array where each element is an object with:
- "index": the original index (integer, 0-based)
- "category": the best matching category from this list: {json.dumps(KNOWN_CATEGORIES)}
- "merchant": the merchant or counterparty name if identifiable, otherwise null

Rules:
- Always pick exactly one category from the provided list
- If genuinely unclear, use "Other"
- Return ONLY the JSON array, no explanation
- The array must have exactly as many elements as the input

Example input:
[{{"index": 0, "narration": "POS/ZOMATO/MUMBAI"}}]

Example output:
[{{"index": 0, "category": "Food & Dining", "merchant": "Zomato"}}]"""


async def enrich_with_llm(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich uncategorized transactions (category==[]) with LLM-assigned categories."""
    uncategorized_indices = [
        i for i, txn in enumerate(transactions) if not txn.get("category")
    ]

    if not uncategorized_indices:
        logger.debug("[LLM] All transactions already categorized — skipping")
        return transactions

    logger.info(
        "[LLM] Enriching %d uncategorized transactions via Ollama (%s)",
        len(uncategorized_indices),
        settings.ollama_model,
    )

    url = f"{settings.ollama_base_url}/v1/chat/completions"

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
    ) as client:
        for batch_start in range(0, len(uncategorized_indices), BATCH_SIZE):
            batch_indices = uncategorized_indices[
                batch_start : batch_start + BATCH_SIZE
            ]
            batch_input = [
                {"index": i, "narration": transactions[i].get("narration", "") or ""}
                for i in batch_indices
            ]

            raw = ""
            try:
                response = await client.post(
                    url,
                    json={
                        "model": settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": json.dumps(batch_input)},
                        ],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                raw = data["choices"][0]["message"]["content"].strip()

                logger.debug(
                    "[LLM] Batch %d/%d — %d prompt + %d completion tokens",
                    batch_start // BATCH_SIZE + 1,
                    (len(uncategorized_indices) + BATCH_SIZE - 1) // BATCH_SIZE,
                    data.get("usage", {}).get("prompt_tokens", 0),
                    data.get("usage", {}).get("completion_tokens", 0),
                )

                results = json.loads(raw)

                for item in results:
                    txn_index = item.get("index")
                    if not isinstance(txn_index, int) or not (
                        0 <= txn_index < len(transactions)
                    ):
                        logger.warning(
                            "[LLM] Out-of-range index %r in batch result — skipping",
                            txn_index,
                        )
                        continue
                    if item.get("category"):
                        transactions[txn_index]["category"] = [item["category"]]
                        transactions[txn_index]["llm_enriched"] = True
                    if item.get("merchant") and not transactions[txn_index].get(
                        "merchant"
                    ):
                        transactions[txn_index]["merchant"] = item["merchant"]

            except httpx.ConnectError:
                logger.warning(
                    "[LLM] Ollama not reachable at %s — skipping enrichment",
                    settings.ollama_base_url,
                )
                break  # no point retrying further batches if Ollama is down
            except httpx.TimeoutException:
                logger.warning(
                    "[LLM] Ollama timed out (model may still be loading) — skipping enrichment"
                )
                break
            except httpx.HTTPStatusError as e:
                logger.error(
                    "[LLM] Ollama HTTP error %s: %s", e.response.status_code, e
                )
            except json.JSONDecodeError as e:
                logger.warning(
                    "[LLM] Failed to parse LLM response: %s — raw: %s", e, raw[:200]
                )
            except Exception as e:
                logger.error(
                    "[LLM] Unexpected error during LLM enrichment: %s", e, exc_info=True
                )

    return transactions
