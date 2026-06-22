# Sprint-06 Prompt 02 — BSA-06: Natural-Language Q&A over Transaction History

## Task: Build a tool-calling Q&A service over stored transaction history

**Context:** BSA-06 has been in the backlog since Sprint-02 — deferred because it needs persistence (BSA-19, Sprint-04) and the transactions endpoint (CR-S4-02, Sprint-05). Both are now in place. This is the headline Sprint-06 feature.

The approach is **tool-calling over SQLite** — not RAG/embedding. Financial data is structured; the LLM picks which query to run, we run it, and the LLM summarizes the result. Two Ollama round-trips per question.

**Files to read first:**

- `backend/app/config/settings.py`
- `backend/app/services/llm_enricher.py` ← pattern to follow for Ollama calls
- `backend/app/db/crud.py`
- `backend/app/db/models.py`
- `backend/app/models/schemas.py`
- `backend/app/main.py`
- `frontend/App.tsx`
- `frontend/services/api.ts`
- `frontend/types.ts`

---

## Backend: `backend/app/services/qa_engine.py` (new file)

Create `backend/app/services/qa_engine.py`. This is the core Q&A logic.

### Tool definitions

Define three query tools as dicts (Ollama tool-calling format):

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_transactions",
            "description": "Search stored transactions by date range, category, merchant, or transaction type. Use for questions about spending amounts, counts, or lists of transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Optional. Filter to a specific account."},
                    "start_date": {"type": "string", "description": "Optional. ISO date YYYY-MM-DD. Start of date range."},
                    "end_date": {"type": "string", "description": "Optional. ISO date YYYY-MM-DD. End of date range."},
                    "category": {"type": "string", "description": "Optional. Category name, e.g. 'Food & Dining'."},
                    "merchant": {"type": "string", "description": "Optional. Merchant name (partial match), e.g. 'AMAZON'."},
                    "txn_type": {"type": "string", "enum": ["CREDIT", "DEBIT"], "description": "Optional. CREDIT or DEBIT."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_totals",
            "description": "Get income, expense, and net totals for a specific account grouped by month. Use for month-over-month questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_number": {"type": "string", "description": "Account number to summarize."}
                },
                "required": ["account_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_statements",
            "description": "List all stored statements with their metadata (bank, account, period, transaction count). Use for questions about which statements are available.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
```

### Tool executor

```python
def _execute_tool(tool_name: str, args: dict, session: Session) -> str:
    """Execute the tool chosen by the LLM and return a JSON string of results."""
    ...
```

- `query_transactions`: SELECT from `TransactionDB` with optional WHERE clauses. Cap at 200 rows. Return JSON list of `{date, type, amount, narration, merchant, category}` dicts.
- `get_monthly_totals`: Call `get_monthly_summary(args["account_number"], session)` from `crud.py`. Return the list as JSON.
- `list_statements`: SELECT all `StatementDB` rows (limit 50). Return JSON list of `{id, bank_name, account_holder, account_number, period_from, period_to, uploaded_at}` dicts.

All functions return a JSON string (not a dict) — this is what goes back into the LLM context.

### Main function

```python
async def answer_question(question: str, account_number: str | None, session: Session) -> dict:
    """
    Two-pass LLM call:
    1. Tool selection: send question + TOOLS to Ollama. LLM picks a tool and args.
    2. Answer generation: send question + tool result to LLM. LLM generates plain-language answer.

    Returns: {"answer": str, "tool_used": str, "data_points": int}
    """
```

**Implementation details:**

- Use `httpx.AsyncClient` (already in requirements). Same pattern as `llm_enricher.py`.
- Endpoint: `{settings.ollama_base_url}/v1/chat/completions`
- Model: `settings.ollama_model`
- Pass `1` (first call, tool selection): `messages=[{"role": "user", "content": question}]`, `tools=TOOLS`, `tool_choice="auto"`.
- If the LLM returns a `tool_calls` list, extract `tool_calls[0].function.name` and `json.loads(tool_calls[0].function.arguments)`.
- If no tool call in response (LLM answered directly), extract `choices[0].message.content` and return it as the answer with `tool_used="none"`.
- Execute the chosen tool: `result_json = _execute_tool(tool_name, args, session)`.
- Count data points: `data_points = len(json.loads(result_json))` (or 1 if the result isn't a list).
- Pass `2` (answer generation): `messages=[{"role": "user", "content": question}, {"role": "tool", "content": result_json, "tool_call_id": "..."}]`. Ask LLM to answer in 1–3 sentences.
- Wrap entire function in `asyncio.wait_for(..., timeout=60.0)`.
- On `ConnectError` or timeout: return `{"answer": "Q&A is unavailable — make sure Ollama is running (`ollama serve`)", "tool_used": "error", "data_points": 0}`.

**Constraints:**

- Never expose raw account numbers or transaction references in the answer.
- Data points cap: don't pass more than 200 transactions to the LLM in pass 2 (the executor already caps at 200).
- No new pip dependencies. `httpx` and `json` are already available.

---

## Backend: `backend/app/routers/qa.py` (new file)

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session
from app.db.database import get_session
from app.services.qa_engine import answer_question

router = APIRouter()

class QARequest(BaseModel):
    question: str
    account_number: str | None = None

class QAResponse(BaseModel):
    answer: str
    tool_used: str
    data_points: int

@router.post("/api/qa/ask", response_model=QAResponse)
async def ask_question(req: QARequest, session: Session = Depends(get_session)):
    if not req.question.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = await answer_question(req.question, req.account_number, session)
    return QAResponse(**result)
```

Register `qa.router` in `backend/app/main.py`.

---

## Frontend: `frontend/components/QAChat.tsx` (new file)

A simple chat-style widget with an input and an answer display.

**Component interface:**

```tsx
interface Props {
  accountNumber?: string;
}
```

**Behavior:**

- Text input (placeholder: "Ask about your transactions…") + "Ask" button.
- On submit: call `POST /api/qa/ask`, show loading skeleton.
- On response: display the `answer` in a chat bubble. Below it, show `data_points` in small gray text: "Based on {N} transactions".
- If `tool_used === "error"`: show the answer in amber/warning color.
- Clear the input after a successful response.
- Disabled state: button disabled while loading or when input is empty.

**Placement in `App.tsx`:** Render `QAChat` below `SubscriptionsCard`, only when `persistedStatements.length > 0`.

---

## Frontend: `frontend/services/api.ts`

Add:

```typescript
export async function askQuestion(question: string, accountNumber?: string) {
  const res = await fetch(`${API_BASE}/api/qa/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, account_number: accountNumber ?? null }),
  });
  if (!res.ok) throw new Error(`Q&A failed: ${res.status}`);
  return res.json() as Promise<{
    answer: string;
    tool_used: string;
    data_points: number;
  }>;
}
```

---

## Tests: `backend/tests/test_qa.py` (new file)

Write ≥4 tests. Use `unittest.mock.patch` to mock `httpx.AsyncClient.post` — do not make real Ollama calls in tests.

| Test                     | What it checks                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------ |
| `test_qa_returns_answer` | Mock Ollama returns a valid tool_call + answer → endpoint returns 200 with `answer` string |
| `test_qa_ollama_down`    | Mock `ConnectError` → endpoint returns 200 with the "Ollama unavailable" message           |
| `test_qa_empty_question` | Empty string body → 400                                                                    |
| `test_qa_direct_answer`  | Mock Ollama returns no tool_call (direct text answer) → endpoint extracts and returns it   |

---

## Constraints

- Do not change any existing file except `main.py` (add import + router) and `api.ts` (add function).
- Do not change any existing tests.
- The `qa_engine.py` module must handle Ollama being unreachable without crashing — always return a dict with `answer`, `tool_used`, `data_points`.
- Match existing code style: `logger = logging.getLogger(__name__)`, type hints on all function signatures, docstrings on public functions.

## Verification

```bash
cd backend && pytest tests/test_qa.py -v
pytest --tb=short -q  # full suite — no regressions
```

Then manually: start Ollama, start the backend, open the frontend, upload a statement with `persist=true`, ask "how much did I spend in total?".

## Changelog entry required

Add to `docs/changelog.md` after the housekeeping entry.
