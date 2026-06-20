import asyncio
import json
import logging
from typing import Any

import httpx

from app.config.settings import settings
from app.services.categories import CANONICAL_CATEGORIES

logger = logging.getLogger(__name__)

BATCH_SIZE = 10

SYSTEM_PROMPT = f"""You are a bank transaction categorizer for Indian bank statements.

Given a list of transaction narrations, return a JSON array where each element is an object with:
- "index": the original index (integer, 0-based)
- "category": the best matching category from this list: {json.dumps(CANONICAL_CATEGORIES)}
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


async def _run_batch(
    client: httpx.AsyncClient,
    url: str,
    batch_indices: list[int],
    transactions: list[dict[str, Any]],
    sem: asyncio.Semaphore,
    batch_num: int,
    total_batches: int,
) -> None:
    async with sem:
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
                batch_num,
                total_batches,
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
                        "[LLM] Out-of-range index %r in batch %d — skipping",
                        txn_index,
                        batch_num,
                    )
                    continue
                if item.get("category"):
                    transactions[txn_index]["category"] = [item["category"]]
                    transactions[txn_index]["llm_enriched"] = True
                if item.get("merchant") and not transactions[txn_index].get("merchant"):
                    transactions[txn_index]["merchant"] = item["merchant"]

        except httpx.ConnectError:
            logger.warning(
                "[LLM] Ollama not reachable at %s — skipping batch %d",
                settings.ollama_base_url,
                batch_num,
            )
        except httpx.TimeoutException:
            logger.warning(
                "[LLM] Ollama timed out on batch %d (model may still be loading)",
                batch_num,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "[LLM] Ollama HTTP error %s on batch %d: %s",
                e.response.status_code,
                batch_num,
                e,
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "[LLM] Failed to parse LLM response on batch %d: %s — raw: %s",
                batch_num,
                e,
                raw[:200],
            )
        except Exception as e:
            logger.error(
                "[LLM] Unexpected error on batch %d: %s", batch_num, e, exc_info=True
            )


async def enrich_with_llm(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich uncategorized transactions (category==[]) with LLM-assigned categories.

    Bounded by llm_max_enriched (cap) and llm_total_timeout_s (wall-clock budget).
    Batches run concurrently (up to 3 at a time). Partial enrichment is returned on
    timeout — the endpoint always gets a response.
    """
    uncategorized_indices = [
        i for i, txn in enumerate(transactions) if not txn.get("category")
    ]

    if not uncategorized_indices:
        logger.debug("[LLM] All transactions already categorized — skipping")
        return transactions

    if len(uncategorized_indices) > settings.llm_max_enriched:
        logger.info(
            "[LLM] Capping enrichment at %d (skipping %d uncategorized transactions)",
            settings.llm_max_enriched,
            len(uncategorized_indices) - settings.llm_max_enriched,
        )
        uncategorized_indices = uncategorized_indices[: settings.llm_max_enriched]

    logger.info(
        "[LLM] Enriching %d uncategorized transactions via Ollama (%s)",
        len(uncategorized_indices),
        settings.ollama_model,
    )

    url = f"{settings.ollama_base_url}/v1/chat/completions"
    sem = asyncio.Semaphore(3)

    batches = [
        uncategorized_indices[i : i + BATCH_SIZE]
        for i in range(0, len(uncategorized_indices), BATCH_SIZE)
    ]
    total_batches = len(batches)

    async def run_all() -> None:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        ) as client:
            tasks = [
                _run_batch(
                    client, url, batch, transactions, sem, batch_num + 1, total_batches
                )
                for batch_num, batch in enumerate(batches)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    try:
        await asyncio.wait_for(run_all(), timeout=settings.llm_total_timeout_s)
    except asyncio.TimeoutError:
        logger.warning(
            "[LLM] Global enrichment budget (%.0fs) exceeded — returning partial results",
            settings.llm_total_timeout_s,
        )

    return transactions
