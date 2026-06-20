# Feature Brainstorm — Post-Sprint-02

**Date:** 2026-06-20 · **Facilitator:** Claude (Cowork, thinking-partner mode)
**Companion docs:** `docs/ml-ai-brainstorm.md` (the original ML/AI roadmap), `docs/improvement-analysis.md` (prerequisites analysis)

This is a sparring session, not a wish list. Each idea gets the same treatment: what it is, why it matters, what it *really* costs (including the unglamorous prerequisites), and a verdict. The job here is to separate "exciting" from "valuable" and to be honest about the order things have to happen in.

---

## The Core Strategic Tension

The product can go in two directions, and they compete for the same evenings-and-weekends budget:

- **Direction A — "Deeper single-statement intelligence":** make one uploaded statement produce dramatically more insight (better categorization, anomaly flags, smart narrative insights, a chat box). Stateless. No database.
- **Direction B — "Longitudinal financial picture":** stitch *many* statements over time into trends, recurring-bill detection, month-over-month comparison, budgets. Requires persistence.

**The blunt truth:** almost everything genuinely valuable lives in Direction B, and Direction B is gated on one decision the project keeps deferring — **adding a persistence layer.** Until that exists, the team will keep building clever stateless features that can't compound. The single highest-leverage move in the next two sprints is to stop deferring the database decision.

A second blunt truth: **Sprint-02 shipped two features that don't work yet** (BSA-04 silently no-ops, BSA-05 has no UI). Brainstorming new features while the last batch is half-finished is how a personal project accumulates a graveyard. **Finish before you start.**

---

## Tier 1 — Finish What's Already Built (do these first, they're not really "new")

| Idea | Why it matters | Real cost | Verdict |
|------|----------------|-----------|---------|
| **Make BSA-04 actually enrich** (TD-033) | The feature the whole sprint was justified by is currently a no-op | ~1h | **Must do.** Non-negotiable. |
| **Spending Summary card** (consumes BSA-05) | Turns the invisible summary endpoint into the single most-requested user view: "where did my money go" | 3–4h frontend | **Do.** Highest visible value-per-hour available right now. |
| **"AI-categorized" badge** on enriched rows | Builds user trust + creates the feedback surface for future correction data | 1h | **Do.** Pairs with the summary card. |

These three convert *sunk* Sprint-02 effort into actual user value. That's a better return than any net-new idea below.

---

## Tier 2 — High-Value, Low-Prerequisite (stateless, ship soon)

### 2.1 Smart Insights strip (BSA-15) — *stats, no LLM*
A row of plain-language callouts computed from data already in the response: *"Top category: Food & Dining (32%)"*, *"Most frequent merchant: PAYTM (12×)"*, *"3 transactions above ₹10,000."*
- **Why:** Feels like AI, costs nothing, no new infra, no LLM latency. The perceived-intelligence-per-hour is the best in the whole backlog.
- **Cost:** Half a day. Pure derivation from `merchant_insights` + `transactions`.
- **Watch:** Keep it honest — these are descriptive stats, don't over-claim "insight."
- **Verdict: Strong yes.** This is the sleeper hit.

### 2.2 Export to CSV / Excel (BSA-13)
Download the parsed, enriched transactions.
- **Why:** The #1 reason people parse a PDF statement is to get it *out* of the PDF. This closes the loop. Also the cheapest possible "the tool did something useful" moment.
- **Cost:** A few hours, frontend-only (or reuse the `xlsx` path server-side).
- **Verdict: Yes.** Quick, concrete, universally wanted.

### 2.3 Recurring / subscription detection (BSA-07) — *single-statement version*
Flag likely recurring charges within one statement: same merchant, similar amount, regular cadence.
- **Why:** "You have 8 likely subscriptions totaling ₹4,200/mo" is a genuinely valuable, shareable insight. The "find my forgotten subscriptions" use case sells itself.
- **Cost:** Medium. Single-statement detection is stats on the transaction array (no DB). *Cross-statement* recurring detection needs persistence — defer that half.
- **Watch:** One statement is a weak signal for "recurring." Be honest about confidence; market it as "likely recurring," not certainty.
- **Verdict: Yes, the stateless half.** Strong teaser for the longitudinal version.

### 2.4 PII redaction before LLM calls — *prerequisite, not a feature*
Account numbers, names, and phone numbers currently go to the LLM verbatim.
- **Why:** Even with local Ollama, this is the right habit before any hosted model is ever used. It's also a trust story ("your data is masked before AI sees it").
- **Cost:** 1–2h regex masking pass on narrations before enrichment.
- **Verdict: Do it alongside the BSA-04 fix.** Cheap insurance; flagged in `improvement-analysis.md` as a roadmap prerequisite.

---

## Tier 3 — The Database Decision (unlocks the real product)

Everything here needs persistence. Recommend **SQLite via SQLModel** for a single-user personal app (zero infra, one file, native FastAPI ORM; migrate to Postgres only if multi-user ever happens).

| Idea | What it unlocks | Prerequisite |
|------|-----------------|--------------|
| **Month-over-month comparison** (BSA-17) | Upload Jan/Feb/Mar → trend lines, "spending up 18% vs last month" | History store + statement dedup (TD-024) |
| **True recurring detection** (BSA-07) | Confident subscription tracking across months | History store |
| **Budgets & alerts** | "You've spent 80% of your Food budget" | History + category persistence |
| **Natural-language Q&A** (BSA-06) | "How much did I spend on Uber last quarter?" | History + retrieval; the chat is the *easy* part |
| **Category-correction learning** (BSA-16) | User fixes a category → trains future classification | Persistence to store corrections (localStorage is a stopgop, not the real thing) |

**Verdict:** Pick a date in Sprint-03 to make this decision and design the data model **before** building any of the above. The model is small — `statements`, `transactions`, `corrections`. Designing it badly (or repeatedly deferring it) is the main risk to the project's trajectory.

---

## Tier 4 — Interesting but Premature

| Idea | Why it's tempting | Why not yet |
|------|-------------------|-------------|
| **Anomaly detection (IsolationForest, BSA-08)** | "Fraud-style" flagging sounds impressive | Needs months of history to train; on one statement it's just an outlier highlighter (which Smart Insights already covers more cheaply). Revisit after the history store exists. |
| **SSE streaming progress bar (BSA-11)** | FastAPI makes it easy; nice UX | Parsing is usually fast; a progress bar on a 2-second operation is polish, not value. Only worth it once large multi-page PDFs + LLM enrichment make requests genuinely slow (and TD-035 bounds that first). |
| **Scanned-PDF OCR (Tesseract/Azure)** | Expands the universe of supported statements | Real value, real cost (OCR pipeline + quality handling). A whole sprint on its own. Park until digital-PDF + CSV/Excel paths are rock-solid. |
| **Multi-bank / multi-currency** | Broader market | This is a personal tool for Indian (INR) statements today. Don't generalize before there's a second user asking. |

---

## Tier 5 — The Honest "Probably Never" Pile

- **Mobile app** — it's a personal web tool; a responsive layout is enough.
- **Multi-user accounts / auth** — explicitly out of scope per `CLAUDE.md` until user accounts are a real requirement. Adding auth now is infrastructure for users who don't exist.
- **Real-time bank API integration (account aggregation)** — regulatory and security weight far beyond a personal project. The whole premise of this tool is "upload a file," and that premise is fine.

---

## Recommended Sequencing (the one-paragraph version)

Finish Sprint-02's two features (Tier 1). Ship the stateless quick wins that compound trust and utility — Smart Insights, CSV export, single-statement recurring detection, PII redaction (Tier 2). **In parallel, make the SQLite decision and design the data model** so Sprint-04 can open Direction B (month-over-month, budgets, Q&A). Keep OCR, anomaly ML, and streaming parked until the data foundation and the core parser (TD-007 split) are solid. Resist net-new features while old ones are half-built.

---

*Translated into a dated plan in `docs/sprint-03-plan.md`. ML/AI deep-dive: `docs/ml-ai-brainstorm.md`. Prerequisites: `docs/improvement-analysis.md`.*
