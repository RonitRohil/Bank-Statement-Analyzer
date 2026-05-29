# ML/AI + LLM Feature Brainstorm — Bank Statement Analyzer

**Date:** 2026-05-29  
**Goal:** Identify where ML and LLM capabilities can meaningfully improve the product

---

## 1. Where the Current System Breaks Down (the problems to solve)

Before picking ML/AI tools, it's worth being specific about what the regex-based approach fails at today:

| Problem | Example | Current behavior |
|---------|---------|-----------------|
| Unknown merchants | "CRED TECHNOLOGIES PVT" | Returns `merchant: null` |
| Ambiguous categories | "HDFC ERGO" could be insurance or just a bank transfer | No category assigned |
| Non-English narrations | Tamil/Hindi bank narration text | Regex misses entirely |
| Complex UPI narrations | "UPI/431200120045/RCH/PHONEPEBILLPAY/916291..." | Partial extraction |
| Salary detection | "NETBANKING CR INW NEFT 123456 EMPLOYER PAYROLL" | Misses many patterns |
| Statement quality scoring | Scanned vs digital PDF | Binary fail/pass, no nuance |

---

## 2. ML Feature Ideas

### 2A. Learned Transaction Categorization (Classifier)

**What:** A text classifier that maps narration strings to categories.  
**Why better than regex:** Generalizes to narrations it hasn't seen before. A regex for `AMAZON` misses `AMAZON.IN`, `AMZ*MKTPLACE`, `AMZN MKTP US`.

**Implementation options:**

| Approach | Complexity | Accuracy | Latency |
|----------|-----------|----------|---------|
| TF-IDF + Logistic Regression | Low | Good for known patterns | <1ms |
| Fine-tuned sentence-transformers (e.g., `all-MiniLM-L6-v2`) | Medium | Better on new merchants | ~5ms |
| Fine-tuned BERT/DistilBERT | High | Best | ~50ms |

**Recommended start:** TF-IDF + Logistic Regression on a labeled dataset of 2,000–5,000 narrations. Cheap, fast, explainable. Upgrade to sentence-transformers when you hit its ceiling.

**Training data:** You can bootstrap labels using the existing regex system (auto-label what the regex is confident about), then manually correct a sample.

---

### 2B. NER (Named Entity Recognition) for Receiver/Merchant Extraction

**What:** Use a lightweight NER model to extract the person/company name from unstructured narration text.  
**Why:** Current regex patterns only catch structured formats like `UPI/{id}/{name}`. Most NEFT/RTGS narrations are free-form.

**Example:**
```
Input:  "NEFT CR HDFC0001234 RAJESH KUMAR SHARMA 10012025 00123"
Output: receiver_details.name = "RAJESH KUMAR SHARMA"
```

**Tools:**
- `spaCy` with `en_core_web_sm` — works out-of-the-box for English names, reasonable on Indian names
- Fine-tune on a small labeled set of Indian banking narrations for big accuracy gains
- Alternative: use an LLM call for extraction (see section 3)

---

### 2C. Anomaly Detection

**What:** Flag statistically unusual transactions automatically.  
**Why useful:** Users can't visually scan 500 rows to find the one ₹2.5L transfer they forgot about.

**Approaches:**
- **Rule-based first:** Flag transactions >3 std deviations from merchant average (already have `std_amount` in `merchant_insights`)
- **Isolation Forest / Local Outlier Factor:** Unsupervised; trains on the user's own history; no labels needed
- **Output:** `is_anomaly: bool`, `anomaly_reason: str` on each transaction

**Data requirement:** Works well with 3+ months of history (100+ transactions). Single-statement analysis will have limited context.

---

### 2D. Recurring Transaction Detection

**What:** Identify subscriptions, EMIs, rent, salary — transactions that repeat on a pattern.  
**Why:** Helps users see fixed vs variable expenses.

**Algorithm:**
1. Group by merchant/receiver
2. Compute inter-transaction intervals
3. Apply FFT or autocorrelation to detect dominant period (weekly/monthly/quarterly)
4. Label as `RECURRING` with `frequency` and `expected_next_date`

**Complexity:** Low-medium. Mostly statistics, no ML model needed. Can be done in pandas.

---

## 3. LLM Feature Ideas

### 3A. Natural Language Q&A on Statements ("Chat with your bank statement")

**What:** User asks a question in plain English; the LLM answers using the transaction data.  
**Examples:**
```
"How much did I spend on food last month?"
"Show me all transactions over ₹5,000 in March"
"What's my biggest expense category this year?"
"Did I pay my Netflix subscription this month?"
```

**Architecture:**
```
User question
  → Build context: top N transactions + summary stats as JSON/text
  → Prompt: "You are a personal finance assistant. Here is the transaction data: {context}. Answer: {question}"
  → LLM (GPT-4o-mini / Claude Haiku) returns answer
  → Stream response to frontend
```

**Why GPT-4o-mini or Claude Haiku:** Fast, cheap, sufficient for structured data Q&A. No need for GPT-4 Turbo.

**Implementation path:**
1. Add a `POST /api/chat` endpoint (FastAPI + SSE streaming)
2. Format transactions as a compact text block or CSV string
3. System prompt: define the assistant role, inject the data
4. Stream token-by-token response to frontend

**Cost estimate:** ~$0.0001–0.001 per query with Claude Haiku/GPT-4o-mini. Negligible.

---

### 3B. Smart Categorization Fallback (LLM as enrichment oracle)

**What:** When the regex + ML classifier both return `category: null`, call an LLM to categorize the transaction.  
**Why:** LLMs have seen essentially all merchant names and narration patterns in training data.

**Architecture:**
```
narration = "AUFC FEES 2025-02 HDFC BANK"
→ regex: category = null
→ ML classifier: low confidence (<0.7)
→ LLM call: "Categorize this bank transaction narration. Return one of: [E-COMMERCE, FOOD, TRANSPORT, TELECOM, INSURANCE, EDUCATION, INVESTMENT, SALARY, TRANSFER, OTHER]. Narration: {narration}"
→ LLM returns: "EDUCATION"
→ Store result with confidence_score boost
```

**Caching:** Cache LLM responses by narration prefix to avoid repeat calls. Most narrations are formulaic.

---

### 3C. Automated Financial Summary Report

**What:** After analysis, auto-generate a 1-page natural language summary.  
**Output:** A paragraph like:

> "In February 2025, you spent ₹42,500 across 67 transactions. Your largest expense category was Food & Delivery (₹8,200, driven by frequent Zomato orders). Your salary credit of ₹85,000 arrived on the 1st. You have 3 recurring charges totalling ₹2,400/month: Netflix, Spotify, and a gym membership. Notable: an unusual ₹25,000 transfer to account XXXXXX4321 on Feb 15 — this is 4x your typical transfer amount."

**Implementation:**
- Build a structured summary dict from the analysis result
- Pass to LLM with a "write a financial summary" prompt
- Return alongside the transaction data

**User value:** High — this is the kind of insight a human financial advisor would give. Takes 5 minutes to implement once FastAPI is in place.

---

### 3D. Receipt / Narration Clarification

**What:** Some narrations are cryptic (e.g., "BFT/DF/230154020/00001 CR"). An LLM can often decode these.  
**Use:** Tooltip or expandable explanation next to confusing narrations in the UI.

---

## 4. Implementation Roadmap

### Phase 1 — Quick Wins (no model training, LLM API only)
1. LLM-powered categorization fallback (3B) — 1 day
2. Natural language Q&A endpoint (3A) — 2 days
3. Automated financial summary (3C) — 1 day
4. Recurring transaction detection (2D) — 1 day (pure stats)

**Total: ~1 sprint. Adds massive user-visible value. No training data needed.**

### Phase 2 — Light ML
5. Anomaly detection with Isolation Forest (2C) — 2 days
6. TF-IDF + Logistic Regression categorizer (2A) — 3 days (needs labeled data)

### Phase 3 — Full ML Pipeline
7. Fine-tuned sentence-transformer categorizer (2A upgrade)
8. NER for receiver extraction (2B)
9. Active learning loop: user corrects → model improves

---

## 5. Technology Decisions

| Component | Recommended tool | Reason |
|-----------|-----------------|--------|
| LLM API | Claude Haiku (Anthropic) or GPT-4o-mini | Cheap, fast, good for structured data tasks |
| Embeddings (Phase 2) | `sentence-transformers` — `all-MiniLM-L6-v2` | Runs locally, 22 MB, fast |
| NER | `spaCy en_core_web_sm` | Lightweight, no API cost |
| Anomaly detection | `scikit-learn` IsolationForest | Already in requirements (can now justify the dependency) |
| LLM streaming | FastAPI SSE (`StreamingResponse`) | Native fit — reinforces the FastAPI migration decision |
| Caching LLM responses | Redis with narration hash as key | Pairs with Celery for async processing |

---

## 6. What NOT to Build (yet)

- **Fine-tuning a custom LLM** — overkill; prompt engineering with a good base model is 90% as good
- **On-device ML model** — the user base is small; API calls are fine
- **OCR for scanned PDFs** — complex problem; use a third-party API (AWS Textract, Azure Form Recognizer) if needed
- **Fraud detection** — requires multi-user data; not viable as a single-user tool

---

*Related: `adr-001-flask-vs-fastapi.md` (LLM streaming requires FastAPI), `tech-debt.md` TD-009 (sklearn can now be justified)*
