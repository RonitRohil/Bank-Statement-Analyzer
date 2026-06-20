# Study Document — Sprint-02

**Sprint window:** 2026-06-13 → 2026-06-19 (shipped) · **Written:** 2026-06-20
**Audience:** a developer reading this code for the first time who wants to understand not just *what* Sprint-02 did but *why every decision was made*.

Sprint-01 built the FastAPI foundation. Sprint-02 was the "collect on the investment" sprint: cut the frontend over to FastAPI, decommission Flask, and ship the first two real features — LLM categorization and a financial summary — on top of the async backend.

---

## 1. What Was Built

Seven distinct pieces of work landed:

1. **FastAPI housekeeping** (TD-028/029/030/032) — four one-line fixes carried from the Sprint-01 review.
2. **FastAPI integration tests** (BSA-10 / TD-031) — the safety net the cutover required.
3. **Flask → FastAPI cutover** (BSA-09) — frontend now talks to port 8000; Flask deprecated.
4. **LLM categorization fallback** (BSA-04) — uncategorized transactions enriched by a local Ollama model.
5. **Financial summary endpoint** (BSA-05) — `POST /api/analyze/bank/summary`.
6. **Multi-page PDF row stitching** (TD-021) — fixed a silent data-loss bug.
7. **Parser & dashboard polish** — CSV robustness, Dr/Cr detection, metadata regex, UI restyle.

---

## 2. Why It Was Built (the problem each solves)

- **Cutover (BSA-09):** FastAPI had been live since Sprint-01 but no user ever hit it — the frontend still pointed at Flask:5000. Until the cutover, every new FastAPI feature (BSA-04, BSA-05) had no path to a user. BSA-09 was the gateway that made the whole sprint worth shipping.
- **Tests first (BSA-10):** You cannot responsibly cut over to a backend you can't prove behaves like the old one. The parity test exists precisely to de-risk BSA-09.
- **LLM categorization (BSA-04):** The regex narration analyzer leaves `category=[]` on any narration it doesn't recognize (anything not in the hardcoded merchant list). That's a lot of real transactions. An LLM fallback fills the gap without hand-maintaining an ever-growing regex table.
- **Summary (BSA-05):** Users want a one-glance "where did my money go." All the raw data was already in the response; it just needed aggregating into income/expense/net/by-category/top-merchants.
- **Multi-page PDF (TD-021):** The single highest-impact correctness bug in the backlog — multi-page statements were silently returning only page 1's transactions.

---

## 3. How It Works (key code paths)

### 3.1 The cutover (BSA-09)

The functional change is tiny: `frontend/.env.local` sets `VITE_API_URL=http://localhost:8000`, and `api.ts` reads it via `import.meta.env.VITE_API_URL`. Flask's `run.py` got a `DeprecationWarning` on startup but is otherwise untouched — kept alive one sprint as a rollback. `CLAUDE.md` and `architecture.md` were updated to mark Flask deprecated.

**Gotcha that slipped through:** the *functional* URL moved to 8000, but two **error-message strings** still say "localhost:5000" (`App.tsx:35`, `api.ts:22`), and the env fallback in `api.ts:3` is still `5000`. So a user whose backend is down is told to check the wrong port. Logged as TD-037. Lesson: when you change a config value, grep the *whole* surface, not just the code path — strings in error messages count.

### 3.2 LLM enrichment (BSA-04)

`backend-v2/app/services/llm_enricher.py` exposes `async def enrich_with_llm(transactions)`. Flow:

1. Find transactions where `category` is falsy (`uncategorized_indices`).
2. Batch them 10 at a time. Each batch is `[{"index": i, "narration": ...}]` where `i` is the **global** transaction index.
3. POST each batch to Ollama's OpenAI-compatible endpoint (`/v1/chat/completions`) via `httpx.AsyncClient`. A system prompt constrains the model to return a JSON array of `{index, category, merchant}` with one of 16 known categories.
4. Map results back onto the transactions; set `llm_enriched=True`.

It is called from `analyze.py` after `extract_transactions()` succeeds, and only when the transactions list is non-empty.

**Design decisions that were right:**
- **Batched, never per-transaction** — 10 narrations per call keeps cost/latency sane.
- **Non-blocking failure** — every exception is caught; Ollama being down just returns the transactions unchanged. `ConnectError` breaks the batch loop early (no point retrying 19 more batches if the server is gone).
- **No new dependency** — used the already-present `httpx` instead of pulling in `anthropic`.

**The provider pivot (logged in changelog):** the prompt (BSA-04) specified Claude Haiku. Implementation switched to local Ollama (`qwen2.5:7b`) because Anthropic's API is paid and Ollama was free and already in use in a sibling project. This is swappable — point `ollama_base_url` at any OpenAI-compatible host for production. Good call for a personal project; just note the output-quality characteristics differ from Haiku.

**The bug that shipped (TD-033):** the result mapping is `txn_index = batch_indices[item["index"]]`. But `item["index"]` is already the global transaction index, so this indexes into `batch_indices` a second time. It either throws `IndexError` (swallowed by the catch-all → enrichment silently does nothing) or writes a category onto the wrong transaction. **BSA-04 currently doesn't actually enrich anything**, and because of the broad `except`, nothing logs an error. This is the textbook argument for the unit test in `docs/testing-strategy.md §3.1`: a feature with no test that fails silently looks exactly like a feature that works.

### 3.3 Financial summary (BSA-05)

`backend-v2/app/routers/summary.py` — `summarize_transactions()` is a sync `def` (pure CPU math, no I/O, so `async` would only add overhead). It walks the transactions once, splitting CREDIT into income and everything else into expense, tallying per-category and per-merchant spend, and returns a `SummaryResponse` with totals, net, top-10 merchants, by-category breakdown (sorted desc), transaction count, average, and a derived date range.

**Subtlety:** a transaction with two categories adds its full amount to *each* category, so category percentages can sum to >100%. This is intentional (a coffee that's both "Food & Dining" and "Shopping" really did cost what it cost), but it's a UX trap — the frontend must not render it as a naive pie that claims to sum to 100%. See CR-S2-06.

**The gap:** the endpoint takes `list[dict[str, Any]]` instead of the typed `Transaction` model, so a malformed `amount` reaches `float()` and 500s. Logged as TD-036.

### 3.4 Multi-page PDF stitching (TD-021)

`_looks_like_header(row)` (new `@staticmethod`) checks whether any cell matches known header keywords. `_process_pdf_transactions` now keeps `last_known_headers`: if a table's first row looks like a header, use and remember it; if not but a header was seen earlier, reuse it (this is a continuation page — every row is data); if no header has ever been seen, warn and skip. Applied to **both** backends to keep the copies in sync. This is the cleanest fix shape — it relies on the *content* of the row, not a fragile page-count or row-count heuristic.

---

## 4. Key Decisions & Alternatives Considered

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| LLM provider | Local Ollama `qwen2.5:7b` | Anthropic Claude Haiku (as planned) | Free for dev; swappable via one env var |
| LLM call shape | Batch of 10 | Per-transaction | 10× fewer calls; cheaper, faster |
| LLM failure mode | Catch-all, return unchanged | Propagate error | Enrichment is a *nice-to-have*; must never break the core parse |
| Summary delivery | Separate endpoint | `?include_summary=true` on analyze | Endpoint is more flexible for the frontend; second round-trip is cheap |
| Summary sync vs async | sync `def` | `async def` + `to_thread` | Pure CPU, no I/O — async adds overhead with no benefit |
| PDF header detection | Content-based `_looks_like_header` | Page-count / row-count heuristic | Robust to varying bank layouts |
| Cutover safety | Keep Flask + parity test | Delete Flask immediately | Reversible; parity test proves equivalence first |

---

## 5. What To Watch Out For (gotchas & known limitations)

1. **BSA-04 is currently a silent no-op** (TD-033). Don't believe it works until the index bug is fixed and a unit test proves a category lands on the right row.
2. **Enrichment results never reach `merchant_insights` / `confidence_summary`** (TD-034) — they're computed before enrichment runs. The response is internally inconsistent once TD-033 is fixed.
3. **Enrichment can block for minutes** (TD-035) — no global timeout, sequential 60 s batches.
4. **Summary trusts client input** (TD-036) — untyped dicts, easy 500.
5. **Two category taxonomies** (CR-S2-08) — the regex categorizer emits `FOOD_DELIVERY`; the LLM emits `Food & Dining`. They don't reconcile. Unify before anything downstream groups by category.
6. **Neither new feature has a UI** (TD-038) — both ship invisible. That's fine as a decision, dangerous as an accident.
7. **Stale port strings** (TD-037) — cosmetic but actively misleading.

---

## 6. What's Next

The honest framing: **Sprint-02 shipped the plumbing for two features but neither is user-ready.** Sprint-03's first job is to *finish* Sprint-02, not pile on new scope. Concretely:

- **Fast-follow (Sprint-03 P0):** TD-033 (index bug), TD-037 (port strings), TD-036 (type summary), TD-034 (aggregate after enrich), TD-035 (bound enrichment). All small; all the difference between "shipped" and "works."
- **Then surface the value (P1):** wire a Spending Summary card and an "AI-categorized" badge into the dashboard (TD-038).
- **Then the architectural debt:** persistence layer (the gateway to recurring-detection, chat, and month-over-month comparison), and the TD-007 analyzer split.

Full plan in `docs/sprint-03-plan.md`. Feature ideas explored in `docs/feature-brainstorm.md`.

---

*Previous study docs: `docs/study/sprint-01-learnings.md`, `docs/study/fastapi-migration-sprint-01.md`, `docs/study/multipage-pdf-fix-td021.md` · Review: `docs/code-review.md` · Changelog: `docs/changelog.md`*
