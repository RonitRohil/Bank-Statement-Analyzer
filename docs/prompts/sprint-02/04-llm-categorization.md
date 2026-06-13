# Prompt: LLM Categorization Fallback — BSA-04

**Task:** Call Claude Haiku to categorize transactions where the regex analyzer returns `category = []`.  
**Sprint ref:** Sprint-02 · Ticket: BSA-04  
**ADR ref:** `docs/ml-ai-brainstorm.md` — hybrid approach (regex primary, LLM fallback)  
**Estimated time:** 2-3 hours  
**Prerequisite:** BSA-09 cutover must be done first (FastAPI must be the active backend)

---

## Why This Change Is Needed

The current regex-based narration analyzer works well for structured UPI/IMPS/NEFT transactions, but leaves `category = []` for unknown merchants, unusual narration formats, and newer payment gateways. LLM categorization is the "quick win" from the AI/ML roadmap — it fills in the gaps without needing training data.

Why Claude Haiku specifically:
- Cheapest Anthropic model (~$0.00025 per 1K tokens)
- Fast (< 1 second per batch)
- Does not require fine-tuning
- Batch 10 transactions per call → ~$0.001 per statement (negligible)

FastAPI's async architecture makes this possible without blocking the event loop.

---

## Files to Read First

1. `backend-v2/app/routers/analyze.py` — where we'll call the LLM enricher
2. `backend-v2/app/models/schemas.py` — `Transaction` schema, particularly the `category` field
3. `backend-v2/app/config/settings.py` — where to add `anthropic_api_key`
4. `backend-v2/requirements.txt` — add `anthropic` dependency
5. `docs/ml-ai-brainstorm.md` — the hybrid approach rationale
6. `backend-v2/.env.example` (if it exists) — add the new key

---

## Architecture Decision

**Batch size:** 10 transactions per LLM call. Never call per-transaction — it's expensive and slow.  
**When to call:** Only for transactions where `len(category) == 0` after regex analysis.  
**Client:** Use `anthropic.AsyncAnthropic` — the async client integrates with FastAPI's event loop without `asyncio.to_thread`.  
**Error handling:** If the LLM call fails (network, API key missing, rate limit), log the error and return transactions unchanged. LLM failure must never break the analyze endpoint.  
**Token logging:** Log estimated tokens per call so we can track costs during testing.

---

## Changes to Make

### 1. Add `anthropic` to `backend-v2/requirements.txt`

```
anthropic==0.52.0
```

### 2. Add `anthropic_api_key` to `backend-v2/app/config/settings.py`

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_size_mb: int = 20
    debug: bool = False
    anthropic_api_key: Optional[str] = None   # ADD THIS

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

### 3. Add `ANTHROPIC_API_KEY` to `backend-v2/.env.example`

Create or update this file:
```env
# Bank Statement Analyzer v2 — Environment Variables

# API port (default: 8000)
# PORT=8000

# Reload on code change (dev only, never production)
# UVICORN_RELOAD=true

# CORS — comma-separated allowed origins
# CORS_ORIGINS=["http://localhost:3000"]

# Max file upload size in MB
# MAX_UPLOAD_SIZE_MB=20

# Anthropic API key — required for LLM categorization fallback (BSA-04)
# Get yours at https://console.anthropic.com
# ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Create `backend-v2/app/services/llm_enricher.py` (new file)

```python
"""
LLM Categorization Fallback (BSA-04)

Calls Claude Haiku to assign categories to transactions where the regex
analyzer returned category=[]. Called in batches of 10 to minimize cost.

If the API key is not configured or the call fails, returns transactions
unchanged — LLM enrichment is best-effort, never blocking.
"""

import json
import logging
from typing import Any

import anthropic

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Anthropic category list — keep in sync with regex analyzer categories
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
    """
    Enrich transactions that have no category with LLM-assigned categories.
    
    Only processes transactions where category == [].
    Modifies the list in-place and returns it.
    """
    if not settings.anthropic_api_key:
        logger.debug("[LLM] ANTHROPIC_API_KEY not set — skipping LLM enrichment")
        return transactions

    # Find indices of uncategorized transactions
    uncategorized_indices = [
        i for i, txn in enumerate(transactions)
        if not txn.get("category")
    ]

    if not uncategorized_indices:
        logger.debug("[LLM] All transactions already categorized — skipping")
        return transactions

    logger.info("[LLM] Enriching %d uncategorized transactions", len(uncategorized_indices))

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Process in batches of BATCH_SIZE
    for batch_start in range(0, len(uncategorized_indices), BATCH_SIZE):
        batch_indices = uncategorized_indices[batch_start:batch_start + BATCH_SIZE]
        batch_input = [
            {"index": i, "narration": transactions[i].get("narration", "") or ""}
            for i in batch_indices
        ]

        try:
            message = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": json.dumps(batch_input)}
                ],
            )

            raw = message.content[0].text.strip()
            logger.debug(
                "[LLM] Batch %d/%d — %d tokens used",
                batch_start // BATCH_SIZE + 1,
                (len(uncategorized_indices) + BATCH_SIZE - 1) // BATCH_SIZE,
                message.usage.input_tokens + message.usage.output_tokens,
            )

            results = json.loads(raw)

            for item in results:
                txn_index = batch_indices[item["index"]]
                if item.get("category"):
                    transactions[txn_index]["category"] = [item["category"]]
                    transactions[txn_index]["llm_enriched"] = True
                if item.get("merchant") and not transactions[txn_index].get("merchant"):
                    transactions[txn_index]["merchant"] = item["merchant"]

        except json.JSONDecodeError as e:
            logger.warning("[LLM] Failed to parse LLM response: %s — raw: %s", e, raw[:200])
        except anthropic.APIError as e:
            logger.error("[LLM] Anthropic API error: %s", e)
        except Exception as e:
            logger.error("[LLM] Unexpected error during LLM enrichment: %s", e, exc_info=True)

    return transactions
```

### 5. Update `backend-v2/app/routers/analyze.py`

Import and call the enricher after `extract_transactions()`:

```python
# Add to imports at the top:
from app.services.llm_enricher import enrich_with_llm

# In the route handler, after the asyncio.to_thread call:
# BEFORE (existing):
result = await asyncio.to_thread(
    lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
)

# AFTER (add the enrichment step):
result = await asyncio.to_thread(
    lambda: BankStatementAnalyzer(str(file_path)).extract_transactions()
)

http_status = result.get("status_code", 200)
if http_status != 200:
    raise HTTPException(status_code=http_status, detail=result.get("message", "Analysis failed"))

# Enrich uncategorized transactions with LLM
if result.get("result", {}).get("transactions"):
    result["result"]["transactions"] = await enrich_with_llm(
        result["result"]["transactions"]
    )

return result
```

Note: The `return result` and `raise HTTPException` lines that already exist should be replaced with this version — do not duplicate them.

### 6. Add `llm_enriched` field to `Transaction` schema (optional but clean)

In `backend-v2/app/models/schemas.py`, add to the `Transaction` class:
```python
llm_enriched: bool = False
```

This field is `False` by default and becomes `True` when LLM filled in the category. Useful for debugging and for future training data collection.

---

## Constraints

- The LLM call must never block the endpoint — all errors must be caught and logged
- If `ANTHROPIC_API_KEY` is not set, the endpoint must still work (just no LLM enrichment)
- Never call the LLM for transactions that already have a category
- Use `claude-haiku-4-5` (not Sonnet or Opus) — cheapest model, sufficient for classification
- Log token usage at DEBUG level for cost tracking
- Do not hardcode the API key anywhere — always from settings

---

## Verification Steps

1. Set `ANTHROPIC_API_KEY=your-key` in `backend-v2/.env`
2. Upload a CSV with a mix of known (UPI/IMPS) and unknown merchants
3. Check the response — known transactions should have categories from regex; unknown ones should show LLM-assigned categories with `"llm_enriched": true`
4. Check logs for `[LLM] Enriching N uncategorized transactions` and token count
5. Remove the API key from `.env`, upload again — endpoint should still work, categories will just be empty for unknown transactions
6. `grep -rn "ANTHROPIC_API_KEY" backend-v2/app/` → should only appear in `settings.py` and `.env.example`

---

## Commit Message (hand to Ronit)

```
feat(bsa-04): LLM categorization fallback via Claude Haiku

- services/llm_enricher.py: async batch enrichment (10 txns/call)
  - only processes transactions with category=[]
  - adds llm_enriched=True flag for traceability
  - full error handling — LLM failure never breaks the endpoint
  - logs token usage for cost tracking
- routers/analyze.py: calls enricher after extract_transactions()
- config/settings.py: anthropic_api_key Optional[str] from env
- requirements.txt: anthropic==0.52.0
- .env.example: ANTHROPIC_API_KEY documented
- schemas.py: llm_enriched: bool = False on Transaction
```

---

## After This Task

Write `docs/study/llm-categorization-bsa04.md` covering:
- The batch architecture and why (cost)
- The prompt design
- How `llm_enriched` flag enables future training data collection
- What happens when the key is missing (graceful degradation)

Then update `docs/changelog.md`. Optional next: `docs/prompts/sprint-02/05-financial-summary.md`.
