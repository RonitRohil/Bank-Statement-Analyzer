# Prompt: Bound LLM Enrichment + Unify Category Taxonomy — TD-035, CR-S2-08

**Task:** Add a wall-clock budget and batch cap to enrichment so it can't block for minutes, and unify the two category vocabularies.
**Sprint ref:** Sprint-03 · Tickets: TD-035 (🟠), CR-S2-08 (taxonomy)
**Review ref:** `docs/code-review.md` → CR-S2-04, CR-S2-08, CR-S2-09
**Estimated time:** 2 hours · **Depends on:** `01-llm-enricher-fix.md`

---

## Why This Change Is Needed

**TD-035:** `enrich_with_llm()` runs batches sequentially, each with a 60 s `httpx` timeout, awaited inline in the request. 200 uncategorized rows = 20 batches × up to 60 s = a possible 20-minute request. No global deadline, no cap.

**CR-S2-08:** The regex categorizer emits codes like `FOOD_DELIVERY`, `E-COMMERCE`; the LLM emits human labels like `Food & Dining`, `Shopping`. They never reconcile, so the summary's per-category grouping splits the same spend across two names.

## Files to Read First

1. `backend-v2/app/services/llm_enricher.py` — batch loop, `KNOWN_CATEGORIES`, timeout
2. `backend-v2/app/models/analyzer.py` — the regex categorizer's category vocabulary (`merchants_and_categories`, category inference)
3. `backend-v2/app/config/settings.py` — add the budget settings

## Changes to Make

### 1. Add settings

```python
class Settings(BaseSettings):
    ...
    llm_total_timeout_s: float = 30.0   # global enrichment wall-clock budget
    llm_max_enriched: int = 100         # cap transactions enriched per request
```

### 2. Bound the enrichment

- Truncate `uncategorized_indices` to `settings.llm_max_enriched` (log how many were skipped).
- Wrap the whole batch loop in `asyncio.wait_for(..., timeout=settings.llm_total_timeout_s)`; on `TimeoutError`, log and return whatever was enriched so far (partial enrichment is fine — the endpoint must still return).
- Optional: run batches concurrently with an `asyncio.Semaphore(3)` and `asyncio.gather` so the budget buys more throughput.

### 3. Startup health log (CR-S2-09)

In `main.py` lifespan, do a quick non-fatal check that `settings.ollama_base_url` is reachable; log a one-line warning if not. This makes "enrichment silently did nothing because Ollama is down" visible in logs.

### 4. Unify the taxonomy (CR-S2-08)

Pick **one** canonical category list — use the human-readable LLM set (`KNOWN_CATEGORIES`). Map the regex categorizer's output onto it (e.g. `FOOD_DELIVERY` → `Food & Dining`, `E-COMMERCE` → `Shopping`). Put the canonical list and the mapping in one module (e.g. `app/services/categories.py`) imported by both the analyzer and the enricher. State the mapping table in the study doc.

## Constraints

- Enrichment remains best-effort and non-blocking — a timeout must never error the endpoint.
- Don't change the category *meaning*, only normalize the *labels*.
- One canonical taxonomy module, imported in both places — no copy-paste lists.

## Verification Steps

1. Unit test: monkeypatch the LLM client to sleep > `llm_total_timeout_s` → assert the endpoint still returns 200 with partial/zero enrichment, within the budget.
2. Unit test: 150 uncategorized rows with `llm_max_enriched=100` → assert at most 100 enriched, skip logged.
3. Unit test: a regex `FOOD_DELIVERY` and an LLM `Food & Dining` on two rows → after normalization the summary groups them under one category.
4. `pytest -m "not integration"` green.

## Commit Message

```
feat(td-035): bound LLM enrichment (global timeout + batch cap); unify taxonomy

- llm_enricher.py: asyncio.wait_for budget, max_enriched cap, optional
  concurrent batches via Semaphore
- services/categories.py: single canonical category list + regex→canonical map
- analyzer.py + llm_enricher.py: import shared taxonomy (CR-S2-08)
- main.py: non-fatal Ollama reachability log at startup
- settings.py: llm_total_timeout_s, llm_max_enriched
```

## After This Task

Update `docs/changelog.md` and the study doc taxonomy note. P0 block complete — verify `pytest` green, then proceed to `05-delete-flask.md`.
