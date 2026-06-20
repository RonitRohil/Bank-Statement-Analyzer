# Prompt 05 — BSA-07 Lite: Single-Statement Recurring Detection

## Task: Detect recurring transactions within a single statement and surface them in the analyze response

**Context:** The `insights.py` service already generates a "Likely recurring: NETFLIX (₹649 avg, 3×)" teaser using CV < 0.15. This prompt promotes that detection to a first-class field — `recurring_candidates` — returned alongside `merchant_insights` in the analyze response. It also relaxes the CV threshold from 0.15 to 0.25 (CR-S3-01 from the Sprint-03 code review) and adds the missing recurring teaser test (CR-S3-05).

Full cross-statement recurring detection (requiring persistence) is BSA-07 proper and is deferred to Sprint-05.

**Files to read first:**
- `backend/app/services/insights.py` — existing CV threshold and recurring teaser logic
- `backend/app/models/schemas.py` — `AnalysisResult` where new field goes
- `backend/app/routers/analyze.py` — where `generate_insights()` is called
- `backend/tests/test_insights.py` — existing insight tests

---

## Change 1 — New `recurring_candidates` service function

**File:** `backend/app/services/insights.py`

Add a new function `detect_recurring(merchant_insights: dict) -> list[dict]` that extracts merchants meeting the recurring criteria, with richer data than the teaser string.

```python
def detect_recurring(merchant_insights: dict) -> list[dict]:
    """
    Returns merchants that appear recurring within a single statement.

    Criteria:
      - count >= 3
      - coefficient of variation (std / avg) < 0.25
      - not "UNKNOWN" / "OTHER" / empty

    Returns a list sorted by count desc. Each item:
      {
        "merchant": str,
        "count": int,
        "avg_amount": float,
        "std_amount": float,
        "cv": float,
        "first_seen": str | None,
        "last_seen": str | None,
        "common_days": list[int],
      }
    """
    candidates = []
    skip = {"UNKNOWN", "OTHER", "", None}

    for merchant, data in merchant_insights.items():
        if merchant in skip:
            continue
        count = data.get("count", 0)
        avg = data.get("avg_amount", 0.0)
        std = data.get("std_amount", 0.0)

        if count < 3 or avg == 0:
            continue

        cv = std / avg
        if cv >= 0.25:
            continue

        candidates.append({
            "merchant": merchant,
            "count": count,
            "avg_amount": round(avg, 2),
            "std_amount": round(std, 2),
            "cv": round(cv, 4),
            "first_seen": data.get("first_seen"),
            "last_seen": data.get("last_seen"),
            "common_days": data.get("common_days", []),
        })

    return sorted(candidates, key=lambda x: x["count"], reverse=True)
```

**Also update the existing recurring teaser** in `generate_insights()`: change the CV threshold from `< 0.15` to `< 0.25` to match.

---

## Change 2 — Add `recurring_candidates` to `AnalysisResult` schema

**File:** `backend/app/models/schemas.py`

In `AnalysisResult`, add:

```python
from typing import Any

recurring_candidates: list[dict[str, Any]] = []
```

Place it after `merchant_insights`. Default to `[]` so existing tests don't break.

---

## Change 3 — Populate `recurring_candidates` in the analyze endpoint

**File:** `backend/app/routers/analyze.py`

After the call to `generate_insights()`, add:

```python
from app.services.insights import detect_recurring

# existing:
result["result"]["insights"] = generate_insights(
    result["result"]["transactions"],
    result["result"]["merchant_insights"]
)

# new:
result["result"]["recurring_candidates"] = detect_recurring(
    result["result"]["merchant_insights"]
)
```

**Constraint:** This runs only if `merchant_insights` is non-empty. The `detect_recurring()` function handles empty dict gracefully (returns `[]`), so no guard needed.

---

## Change 4 — Update frontend types

**File:** `frontend/types.ts`

Add to `AnalysisResult`:

```typescript
recurring_candidates?: RecurringCandidate[];
```

Add a new interface:

```typescript
export interface RecurringCandidate {
  merchant: string;
  count: number;
  avg_amount: number;
  std_amount: number;
  cv: number;
  first_seen: string | null;
  last_seen: string | null;
  common_days: number[];
}
```

---

## Change 5 — Surface recurring candidates in the frontend (minimal)

**File:** `frontend/components/MerchantInsights.tsx`

Find the merchant table. For merchants that appear in `recurring_candidates`, add a small "↻ Recurring" pill next to the merchant name.

Pass `recurringCandidates` as a prop (from `App.tsx`):

```tsx
// In App.tsx, pass down:
<MerchantInsights
  merchantInsights={data.merchant_insights}
  recurringCandidates={data.recurring_candidates ?? []}
/>
```

In `MerchantInsights.tsx`:

```tsx
// Build a Set of recurring merchant names for O(1) lookup
const recurringSet = new Set(recurringCandidates.map(r => r.merchant));

// In the merchant name cell:
<span>{merchant}</span>
{recurringSet.has(merchant) && (
  <span
    title="Likely recurring"
    className="ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"
  >
    ↻
  </span>
)}
```

**Constraint:** Don't build a separate recurring panel — just the pill in the existing merchant table. A dedicated recurring view is Sprint-05 scope.

---

## Tests

**File:** `backend/tests/test_insights.py`

Add to the existing test file:

```python
from app.services.insights import detect_recurring

def test_recurring_detected_when_cv_low():
    merchant_insights = {
        "NETFLIX": {
            "count": 3,
            "avg_amount": 649.0,
            "std_amount": 5.0,      # CV = 0.0077 — well below 0.25
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert len(result) == 1
    assert result[0]["merchant"] == "NETFLIX"
    assert result[0]["cv"] < 0.25

def test_recurring_excluded_when_cv_high():
    merchant_insights = {
        "AMAZON": {
            "count": 5,
            "avg_amount": 2000.0,
            "std_amount": 1500.0,   # CV = 0.75 — above threshold
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []

def test_recurring_excluded_when_count_below_3():
    merchant_insights = {
        "NETFLIX": {
            "count": 2,
            "avg_amount": 649.0,
            "std_amount": 0.0,
            "first_seen": "2026-01-01",
            "last_seen": "2026-02-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []

def test_recurring_excludes_unknown():
    merchant_insights = {
        "UNKNOWN": {
            "count": 10,
            "avg_amount": 100.0,
            "std_amount": 1.0,
            "first_seen": "2026-01-01",
            "last_seen": "2026-03-01",
            "common_days": [1],
        }
    }
    result = detect_recurring(merchant_insights)
    assert result == []
```

---

## Documentation

1. `docs/changelog.md` — entry for BSA-07 lite: recurring detection MVP.
2. `docs/tech-debt.md` — mark CR-S3-01 (CV threshold) and CR-S3-05 (recurring test) as ✅ resolved. Open BSA-07-full (cross-statement recurring) as a new item if not already logged.

**Verification:**

```bash
cd backend && pytest tests/test_insights.py -v
pytest -v   # all tests green
```

Upload a statement with 3+ transactions from the same merchant (e.g., three Netflix charges). The analyze response should include `"recurring_candidates": [{"merchant": "NETFLIX", ...}]`. The merchant table should show the ↻ pill next to Netflix.
