# Testing Strategy — Bank Statement Analyzer

**Author:** Claude (Cowork)
**Date:** 2026-06-20 (post-Sprint-02)
**Status:** Living document — update when the test surface changes

This document defines *what* we test, *where* each kind of test lives, and *why*. It is the reference for every Claude Code prompt that touches tests. The guiding principle for a single-developer personal project: **maximize correctness-per-hour**. We don't chase coverage numbers — we test the things that have silently broken before (parsing, regex, money math) and the things that would fail silently if broken (LLM enrichment, multi-page stitching).

---

## 1. Where We Are Today

| Suite | Location | Count | Runs in CI? |
|-------|----------|-------|-------------|
| Flask unit tests | `backend/tests/` | 23 pass, 1 xfail | yes (no live server) |
| FastAPI integration | `backend-v2/tests/` | 7 pass | yes (in-process ASGI) |
| Flask↔FastAPI parity | `backend-v2/tests/test_parity.py` | gated | no — `integration` marker, needs both servers |
| Frontend | — | **0** | no suite exists |

**Coverage gaps that matter (ranked):**
1. **LLM enricher** (`llm_enricher.py`) — zero tests, and it currently has a live index bug (TD-033). Highest priority.
2. **Summary endpoint** (`summary.py`) — zero tests; untyped input (TD-036).
3. **Frontend** — no tests at all. The cutover (BSA-09) and stale-URL bug (TD-037) would have been caught by one render test.
4. **PDF path** — `test_analyze.py` uses a CSV fixture; the multi-page PDF stitching fix (TD-021) has no regression test on a real multi-page PDF.

---

## 2. The Test Pyramid (target shape)

```
            ┌─────────────────────┐
            │  E2E (manual today)  │   browser upload → dashboard; keep manual for now
            ├─────────────────────┤
            │   Integration (API)  │   httpx ASGI: route → analyzer → response shape
            ├─────────────────────┤
            │       Unit (core)     │   parse_amount, normalize_date, narration,
            │                       │   enricher mapping, summary math
            └─────────────────────┘
```

We deliberately keep the base wide (cheap, fast, deterministic unit tests on the parsing core) and the top thin (E2E stays manual until there's a second developer or a regression that demands automation).

---

## 3. Layer-by-Layer Plan

### 3.1 Unit tests — the parsing & enrichment core

These are pure-function tests with no I/O. They are the highest-value tests because the bugs this project has actually shipped were all here (Cr./Dr. regex, `and`→`or`, double-assignment, phone regex with no capture group).

**Already covered (`backend/tests/`):** `parse_amount` (9), `normalize_date` (7), `analyze_narration_details` (6 + 1 xfail).

**Add this sprint:**

| Target | File | Cases to add |
|--------|------|--------------|
| `enrich_with_llm()` mapping | `backend-v2/tests/test_llm_enricher.py` (new) | Mock the httpx call (return a canned JSON array). Assert the category lands on the **correct** transaction (this is the TD-033 regression test). Assert out-of-range/garbage index is skipped, not crashing. Assert `category != []` transactions are untouched. Assert `llm_enriched=True` is set only on enriched rows. |
| `summarize_transactions()` math | `backend-v2/tests/test_summary.py` (new) | Known 5-txn fixture → assert income/expense/net, per-category totals, top-merchant ordering, `avg_transaction_amount`, and the `date_range`. Assert empty input → zeros, no division error. Assert a string `amount` is rejected at the schema boundary (after TD-036). |
| `_looks_like_header()` | `backend-v2/tests/test_pdf_header.py` (new) | Header row → `True`; data row → `False`; the TD-021 continuation case (header on page 1, none on page 2). |
| Resolve the narration xfail | `backend/tests/test_narration.py` | `UPI/.../AMAZON PAY/...` should yield `merchant="AMAZON"` once the structured-match early-return is fixed. Flip xfail → pass. |

**Convention:** mock the LLM. Never hit a live Ollama/Anthropic endpoint in unit tests — it's non-deterministic, slow, and may be offline. Use `httpx.MockTransport` or `monkeypatch` the `client.post`.

### 3.2 Integration tests — FastAPI routes

In-process via `httpx.AsyncClient(transport=ASGITransport(app=app))`. No live server, runs in CI.

**Already covered (`backend-v2/tests/test_analyze.py`):** CSV upload, response shape vs `AnalyzeResponse`, 400 bad extension, 413 oversize, required transaction fields.

**Add:**
- **Multi-page PDF fixture** → assert all rows from page 2+ survive (TD-021 at the integration level, not just the unit helper). Generate a small 2-page PDF fixture with `reportlab` or check in a tiny real one.
- **Summary route** → POST the analyze output's `transactions` to `/api/analyze/bank/summary`, assert `SummaryResponse` shape and that totals match the unit-level fixture.
- **Enrichment path with Ollama down** → monkeypatch the enricher's client to raise `ConnectError`; assert the analyze endpoint still returns 200 with unchanged transactions (the non-blocking guarantee).
- **Enrichment path with a mocked LLM up** → assert a previously-empty `category` is filled and `llm_enriched=True` (end-to-end of the TD-033 fix).

### 3.3 Parity tests — Flask vs FastAPI

`test_parity.py` exists and is correctly gated behind the `integration` marker (needs both servers). **Keep it until Flask is deleted in Sprint-03, then delete it** — there's nothing to compare against once Flask is gone. Until then it's the safety net for the cutover rollback.

### 3.4 Frontend tests (new surface)

Currently zero. Minimum viable suite with **Vitest + React Testing Library** (Vite-native, fast):

| Priority | Test | Why |
|----------|------|-----|
| P0 | `api.ts` builds the URL from `VITE_API_URL` and surfaces the right error on network failure | Would have caught TD-037 (stale port) |
| P0 | `App.tsx` renders the upload empty-state, then renders the dashboard when given mock `AnalysisResult` | Smoke test for the whole render tree + ErrorBoundary wiring |
| P1 | `AnalyticsCharts` handles empty transactions, all-debit, and missing balances without throwing | Charts do client-side math with `|| 0` guards — verify them |
| P1 | `TransactionTable` renders CREDIT vs DEBIT styling and the empty state | Pure presentational, cheap |
| P2 | `MerchantInsights` filters the `UNKNOWN`/numeric noise keys | Mirrors `isNamedMerchant` logic |

Mock `fetch` (or `uploadBankStatement`) — never hit a real backend in component tests.

---

## 4. Fixtures

Centralize under `backend-v2/tests/fixtures/`:
- `sample.csv` — exists (5-row statement).
- **Add** `sample_multipage.pdf` — 2-page table, header only on page 1 (TD-021 regression).
- **Add** `llm_batch_response.json` — canned Ollama response for enricher unit tests.
- **Add** `statement_no_balance.csv` — a balance-less format (credit-card style) to pin down the TD-026 confidence behavior once fixed.

Keep fixtures tiny and synthetic — **never check in a real bank statement** (PII). Fabricate realistic-but-fake narrations.

---

## 5. CI Plan (TD-019 / TD-001 adjacent)

There is no CI workflow yet. Recommended `.github/workflows/test.yml`:

```yaml
name: tests
on: [push, pull_request]
jobs:
  backend-v2:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend-v2/requirements.txt
      - run: cd backend-v2 && pytest -m "not integration"
      - name: Guard requirements.txt encoding (TD-001)
        run: file backend/requirements.txt | grep -qE 'ASCII|UTF-8'
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run test --if-present
```

The `file ... | grep` step finally closes TD-001's "add a CI guard" requirement — the UTF-16 regression can't silently return.

---

## 6. What We Deliberately Don't Test (yet)

- **Live LLM output quality.** We test the *plumbing* (does a category land on the right row), not whether `qwen2.5:7b` picks the "right" category. Output-quality evaluation needs an eval harness (a Sprint-04+ item — see `docs/improvement-analysis.md`).
- **End-to-end browser flows.** Manual for now. Revisit with Playwright when there's a second contributor.
- **Load / concurrency.** Not until there's a real deployment. TD-035 (unbounded enrichment) is a correctness fix, not a load-test target.

---

## 7. Definition of "Tested" for a New Feature

Before a feature is called done in a study doc:
1. The core logic has a unit test with at least one happy path and one edge case.
2. If it adds a route, it has an integration test asserting the response schema.
3. If it can fail externally (LLM, file I/O), there's a test that the failure degrades gracefully.
4. `pytest -m "not integration"` is green in both backends.

---

*Code review: `docs/code-review.md` · Tech debt: `docs/tech-debt.md` (TD-033, TD-036) · Sprint plan: `docs/sprint-03-plan.md`*
