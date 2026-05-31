# Improvement Analysis — Review of Planned Upgrades + What's Missing

**Date:** 2026-05-30
**Author:** Claude (Cowork)
**Purpose:** Review the three planned upgrade tracks — PDF compatibility, FastAPI migration, AI/ML — and pressure-test them. What's solid, what's risky, and what you haven't planned yet but should.

---

## TL;DR — straight version

Your plans are genuinely good and the sequencing in `sprint-01-plan.md` is sane. But there are **three gaps that will block the AI/ML work no matter how well you execute the individual features**, and none of them are in your current docs:

1. **No persistence layer.** The app is stateless — one file in, one JSON out, nothing stored. Anomaly detection, recurring-transaction detection, and forecasting *all require transaction history*. You cannot build them on a stateless architecture. This is the real unlock, and it's not on any roadmap doc.
2. **No PII strategy for LLM calls.** You're planning to send bank-transaction narrations to a third-party LLM. Those contain names, account numbers, VPAs. Sending them raw is a privacy problem and, depending on who uses this, a compliance one. Redaction has to be designed in, not bolted on.
3. **No evaluation harness.** You have no way to measure whether parsing or categorization is getting better or worse. Every ML/LLM change is currently a vibe check. Without a labeled test set and metrics, you'll ship "improvements" that silently regress accuracy — exactly like the requirements.txt fix that was marked done but never landed.

Fix those three and the rest of your roadmap becomes safe to execute fast. Details below, plan-by-plan.

---

## 1. PDF Compatibility — review of the plan

**What you have:** pdfplumber table extraction, with a documented limitation that scanned/image PDFs fail. The ML brainstorm correctly punts OCR to a third-party API.

**What's solid:** pdfplumber is the right default for digital statements, and you've already wired confidence scoring through the PDF path.

**What's underspecified or missing:**

| Gap | Why it matters | Suggested approach |
|-----|----------------|--------------------|
| **Password-protected PDFs** | Indian bank statements are *very often* PDF-password-protected (PAN/DOB/account-based). Right now pdfplumber throws and the user gets a generic failure. This is probably your #1 real-world PDF failure mode, ahead of scanned docs. | Accept an optional `password` field on the upload; pass to `pdfplumber.open(path, password=...)`. Detect encryption and return a specific "this PDF needs a password" error so the UI can prompt. |
| **Multi-page table continuation** | Real bug today (code-review CR-C-01 / TD-021): tables that span pages without a repeated header silently lose rows. | Carry the last header forward, or move to word/coordinate extraction and stitch. |
| **Table-less / layout-only statements** | Some banks render transactions as positioned text, not ruled tables. `extract_tables()` returns nothing → whole file fails. | Add a fallback that uses `page.extract_words()` with x-position clustering to reconstruct columns when `extract_tables()` is empty. |
| **Extractor fallback chain** | pdfplumber is good but not universal. | Try pdfplumber → fall back to `camelot` (lattice/stream) → fall back to OCR. Pick by confidence of the result, not by order. |
| **Scanned PDFs (OCR)** | You deferred this correctly, but it's the single biggest "why didn't it work" for end users. | When text extraction yields near-empty output, route to OCR: Tesseract for cost-free/local, AWS Textract / Azure Document Intelligence for accuracy. Textract has a purpose-built "tables" mode that's well-suited here. |
| **Bank-specific templates** | Generic detection will always be ~80%. The top 5 Indian banks cover most statements. | A light template registry keyed by detected bank name (you already extract it) that overrides column mapping and date format for known layouts. Falls back to the generic path. Big accuracy win for low effort. |

**Recommendation:** treat "password-protected" and "multi-page continuation" as the two highest-value PDF fixes — they're concrete, common, and currently broken. OCR and templates are phase-2.

---

## 2. FastAPI Migration — review of the ADR

**What you have:** `adr-001-flask-vs-fastapi.md` — a thorough, honest ADR. It correctly identifies the blocking-worker problem, correctly notes that FastAPI doesn't magically make pandas/pdfplumber async (must use `asyncio.to_thread`), and proposes an incremental port. This is good engineering judgment.

**One honest challenge to the decision:** the ADR's own analysis shows **Flask + a task queue solves the actual stated problem (blocking) at zero rewrite cost.** The strongest *real* arguments for FastAPI are (a) LLM streaming and (b) Pydantic as an API contract — both forward-looking, neither blocking today. That's a fine reason to migrate, but be clear-eyed: you're migrating for future DX and streaming, not to fix a current fire. If the ML/LLM features slip, the migration's ROI drops. Don't let the port consume the sprint capacity that the ML quick-wins need. The incremental "run both, port one endpoint" path in the ADR is the right hedge — stick to it.

**What's missing from the migration plan:**

| Gap | Why it matters | Suggested approach |
|-----|----------------|--------------------|
| **OpenAPI → TypeScript codegen** | You maintain `types.ts` by hand against the backend shape. Pydantic + FastAPI gives you a free OpenAPI schema. | Run `openapi-typescript` in the frontend build to generate `types.ts` from `/openapi.json`. Kills backend/frontend type drift permanently — a class of bug you can delete instead of fix. |
| **Job-status model for async** | The ADR mentions Celery but no API shape. | Define it now: `POST /analyze` → `202 {job_id}`; `GET /analyze/{job_id}` → `{status, result?}`. Even with FastAPI `BackgroundTasks` (no Celery yet), commit to this contract so the frontend is built for async from day one. |
| **Structured error contract** | Current errors are ad-hoc dicts. Pydantic is the moment to formalize. | A single `ErrorResponse` model (`code`, `message`, `details`) used everywhere. Your `api.ts` already digs through three possible error shapes — give it one. |
| **Settings via `pydantic-settings`** | Config is hand-rolled `os.getenv`. | `BaseSettings` validates env at startup and fails loudly on misconfig (which is how TD-002 slipped in originally). |
| **Health + readiness** | Action item in the ADR; do it in Flask too (TD-027) so monitoring isn't blocked on the migration finishing. | `/api/health` (liveness) and `/api/ready` (checks deps/model load). |

**Recommendation:** the ADR is approved-quality. Add the OpenAPI→TS codegen item explicitly — it's the highest-leverage thing the migration unlocks and it's currently unstated.

---

## 3. AI/ML — review of the brainstorm

**What you have:** `ml-ai-brainstorm.md` is strong. The hybrid "regex primary → ML → LLM fallback" strategy is exactly right. The phased roadmap (LLM quick-wins first, light ML second, full pipeline third) correctly front-loads value and defers training-data cost. The "what NOT to build" section shows good discipline.

**The three things that will bite you, in priority order:**

### 3.1 🔴 Persistence is a hard prerequisite, and it's not planned anywhere

Read your own ML brainstorm closely:
- Anomaly detection "works well with 3+ months of history" — *you have no history store.*
- Recurring detection groups "by merchant/receiver" across time — *across what time, if each request is one file?*
- The financial-summary example references "your typical transfer amount" and "4x" — *typical relative to what stored baseline?*

**Half your ML roadmap silently assumes a database that doesn't exist.** The app today is a pure function: file → JSON. That's a fine architecture for a parser and a terrible one for a personal-finance intelligence layer.

**Recommendation:** add a persistence track *before* Phase 2 ML.
- Postgres (or even SQLite to start) with `accounts`, `statements`, `transactions`, `categories`, `user_corrections`.
- De-dupe on ingest (TD-024) so re-uploading an overlapping statement doesn't double-count.
- This single change unlocks anomaly detection, recurring detection, forecasting, and the active-learning loop *at once*. It's the highest-ROI item on the whole AI/ML roadmap, and it's not on the roadmap.

### 3.2 🔴 PII redaction before any LLM call

Your LLM plans (categorization fallback, Q&A, summary) all send narration text — and in Q&A, *whole transaction sets* — to a third-party API. Narrations contain names, account numbers, VPAs, phone numbers. You already have the extractors to find them (`analyze_narration_details`, `extract_possible_account_numbers`).

**Recommendation:**
- Build a redaction pass that masks account numbers, VPAs, and phone numbers to placeholders (`<ACCT_1>`, `<VPA_1>`) before the prompt, and un-masks in the response. You already detect these entities — reuse that code.
- For categorization, you rarely need the PII at all — categorize on the merchant/structural tokens, not the counterparty identity.
- Document a data-handling stance (what leaves the machine, what's cached, retention). Even for a personal tool, decide it deliberately. If this ever touches anyone else's statements, it's mandatory.
- Consider a local small model (e.g., a distilled classifier or a 1–3B local LLM) for the high-volume categorization path so PII never leaves the box; reserve the cloud LLM for the rare, hard cases on redacted text.

### 3.3 🔴 No evaluation harness = flying blind

You have no labeled test set and no accuracy metric. Today you can't answer "did that regex change improve extraction or break it?" except by eyeballing. That's the same failure mode that let TD-001 get marked done while broken.

**Recommendation — build this first, before any ML:**
- A `tests/fixtures/` set of 15–30 real (anonymized) statements across formats/banks with a hand-labeled expected output (transaction count, a sample of categorized rows, extracted account holder).
- Metrics: extraction accuracy (rows found vs expected), category precision/recall, metadata field accuracy. A single `evaluate.py` that prints them.
- Now every regex tweak, ML model, and LLM prompt change is measured against the same bar. This is what turns "AI/ML" from a demo into a product. It's also cheap — a day of setup.

**Other AI/ML additions worth queuing (smaller):**

| Idea | Value | Notes |
|------|-------|-------|
| **Merchant canonicalization via embeddings** | Collapses `AMZN MKTP`, `AMAZON.IN`, `AMAZON SELLER` into one entity | `sentence-transformers` + cosine threshold; fixes the merchant-insights fragmentation directly |
| **Active-learning loop** | User corrects a category → stored as a label → retrains | Requires persistence (3.1) + a correction UI; turns usage into training data for free |
| **Transfer reconciliation** | Match a debit in one account to the credit in another | Needs multi-account persistence; removes double-counting from "spend" totals |
| **Cash-flow forecast** | "At this rate you'll end the month at ₹X" | Time-series on stored history; high perceived value, low complexity |
| **LLM Q&A grounding guardrail** | Don't let the LLM do arithmetic | Compute the numbers server-side from data; let the LLM only phrase the answer. Prevents confident-wrong money math. |
| **Confidence calibration** | Replace hand-tuned penalties with a learned score | Once you have the eval set, fit a simple model so the score actually predicts correctness |

---

## 4. Cross-cutting items not in any plan

- **Export.** Users will want the enriched transactions back out — CSV/Excel/a PDF summary report. Cheap to add, frequently requested for a tool like this.
- **Observability.** Log parse success rate, confidence distribution, and failure reasons per upload. You can't improve what you don't measure — and it tells you which banks/formats are failing in the wild.
- **Category taxonomy.** Categories are currently ad-hoc strings scattered in a dict. Define a closed, versioned taxonomy (with parent groups: Essentials / Discretionary / Income / Transfers). Everything downstream — charts, budgets, the LLM's allowed labels — depends on it being stable.
- **Idempotency / dedupe on re-upload.** Tied to persistence; re-uploading last month's statement shouldn't double the data.

---

## 5. Recommended re-sequencing

Your sprint plan front-loads the FastAPI scaffold and an LLM quick-win. Reasonable. But given the gaps above, here's a sharper order:

**Foundation first (unblocks everything):**
1. Fix TD-001 (requirements.txt) + add the regression guard — *nothing builds until this is real.*
2. Stand up the evaluation harness (§3.3) — *you need this to know if anything else helps.*
3. Add persistence (§3.1, SQLite to start) — *unlocks half the ML roadmap.*

**Then your existing plan, safely:**
4. FastAPI scaffold + OpenAPI→TS codegen (your BSA-02/03 + the codegen addition).
5. LLM categorization fallback **with redaction** (your BSA-04 + §3.2).
6. Financial summary + Q&A **with grounding guardrail** (your BSA-05/06 + §3.3 guardrail).
7. Recurring + anomaly detection — *now trivial because persistence exists* (your BSA-07/08).

**The reframe:** you planned features (PDF, FastAPI, AI/ML). What's missing is the *substrate* those features need — persistence, redaction, evaluation. Build the substrate first and the features get faster, safer, and actually work as designed. Build features first and you'll hit a wall at "anomaly detection needs history I don't store."

---

*Companion docs: `code-review.md` (current bugs), `tech-debt.md` (prioritized backlog), `adr-001-flask-vs-fastapi.md` (framework decision), `ml-ai-brainstorm.md` (original feature ideas).*
