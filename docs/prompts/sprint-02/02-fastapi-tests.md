# Prompt: FastAPI Integration Tests — BSA-10 / TD-031

**Task:** Write a `backend-v2/tests/` test suite for the FastAPI routes using `httpx` + `pytest-asyncio`.  
**Sprint ref:** Sprint-02 · Ticket: BSA-10 · Tech debt: TD-031  
**Estimated time:** 3-4 hours  
**Why now:** Tests are the prerequisite for BSA-09 (Flask cutover). We cannot safely cut the frontend over to FastAPI until we can prove parity.

---

## Why This Change Is Needed

The `backend/tests/` suite covers Flask only. FastAPI's `/api/health` and `/api/analyze/bank/statement` endpoints are completely untested. This means:

1. We have no parity baseline — we can't prove the two backends return the same JSON shape
2. Any regression in the FastAPI route (response model mismatch, CORS breakage, middleware bug) ships silently
3. BSA-09 (Flask cutover) is blocked until we have confidence the FastAPI endpoint works

---

## Files to Read First

1. `backend-v2/app/routers/analyze.py` — the route we're testing
2. `backend-v2/app/routers/health.py` — the health route
3. `backend-v2/app/models/schemas.py` — the response shape (`AnalyzeResponse`)
4. `backend-v2/app/main.py` — the FastAPI app
5. `backend-v2/requirements.txt` — confirm `pytest-asyncio` and `httpx` are listed
6. `backend/tests/test_health.py` and `backend/tests/test_parse_amount.py` — see how the Flask tests are structured, we follow the same style
7. `backend/conftest.py` — see the Flask fixture pattern

---

## What to Build

### 0. Add dependencies (if not already in requirements.txt)

Check `backend-v2/requirements.txt`. If missing, add:
```
pytest==8.3.5
pytest-asyncio==0.25.3
httpx==0.28.1
```

### 1. Create `backend-v2/conftest.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

### 2. Create `backend-v2/tests/__init__.py`

Empty file.

### 3. Create `backend-v2/tests/test_health.py`

```python
import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_correct_json(client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
```

### 4. Create `backend-v2/tests/test_analyze.py`

This test needs fixture files. Create `backend-v2/tests/fixtures/` and add a minimal CSV fixture.

**Fixture CSV (`backend-v2/tests/fixtures/sample.csv`):**
Create a minimal 5-row CSV that matches the format the analyzer expects:
```csv
Date,Narration,Debit,Credit,Balance
2024-01-05,UPI/123456789/PhonePe/PAYTM/TXN001,500.00,,24500.00
2024-01-06,NEFT/HDFC/SALARY/TXN002,,50000.00,74500.00
2024-01-07,ATM WDL/BRANCH/TXN003,2000.00,,72500.00
2024-01-08,UPI/987654321/Swiggy/ICICI/TXN004,350.00,,72150.00
2024-01-09,IMPS/654321/AMAZON/PAYTM/TXN005,1200.00,,70950.00
```

**Test file:**
```python
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_analyze_csv_returns_200(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_analyze_csv_response_shape(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    data = response.json()
    # Top-level keys
    assert "success" in data
    assert "status_code" in data
    assert "message" in data
    assert "result" in data
    # Result structure
    result = data["result"]
    assert "transactions" in result
    assert "account_info" in result
    assert "confidence_summary" in result
    assert isinstance(result["transactions"], list)


@pytest.mark.asyncio
async def test_analyze_rejects_bad_extension(client):
    response = await client.post(
        "/api/analyze/bank/statement",
        files={"file": ("malware.exe", b"fake content", "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_analyze_rejects_oversized_file(client):
    # Generate a file that exceeds 20 MB
    oversized_content = b"x" * (21 * 1024 * 1024)
    response = await client.post(
        "/api/analyze/bank/statement",
        files={"file": ("big.csv", oversized_content, "text/csv")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_analyze_transactions_have_required_fields(client):
    csv_path = FIXTURES_DIR / "sample.csv"
    with open(csv_path, "rb") as f:
        response = await client.post(
            "/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    transactions = response.json()["result"]["transactions"]
    assert len(transactions) > 0
    for txn in transactions:
        # These fields must exist (can be None but must be present)
        assert "transaction_date" in txn
        assert "narration" in txn
        assert "amount" in txn
        assert "transaction_type" in txn
        assert "confidence_score" in txn
```

### 5. Create `backend-v2/tests/test_parity.py` (optional but recommended before BSA-09)

This test sends the same fixture file to both the Flask and FastAPI backends and asserts the JSON shapes match. It requires both servers to be running — mark it with a `@pytest.mark.integration` marker so it doesn't run in standard CI.

```python
import pytest
import httpx

FLASK_URL = "http://localhost:5000"
FASTAPI_URL = "http://localhost:8000"
FIXTURES_DIR = __file__.__class__("tests/fixtures")  # adjust path as needed


def get_shape(obj, depth=3):
    """Recursively extract the shape (keys only, no values) of a dict/list."""
    if depth == 0:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: get_shape(v, depth - 1) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [get_shape(obj[0], depth - 1)] if obj else []
    return type(obj).__name__


@pytest.mark.integration
def test_flask_fastapi_response_shape_parity(tmp_path):
    """Assert Flask and FastAPI return the same JSON shape for a CSV upload."""
    import pathlib
    csv_path = pathlib.Path("backend-v2/tests/fixtures/sample.csv")
    
    with open(csv_path, "rb") as f:
        flask_resp = httpx.post(
            f"{FLASK_URL}/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
            timeout=30,
        )
    
    with open(csv_path, "rb") as f:
        fastapi_resp = httpx.post(
            f"{FASTAPI_URL}/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
            timeout=30,
        )
    
    assert flask_resp.status_code == fastapi_resp.status_code == 200
    flask_shape = get_shape(flask_resp.json())
    fastapi_shape = get_shape(fastapi_resp.json())
    assert flask_shape == fastapi_shape, (
        f"Shape mismatch!\nFlask: {flask_shape}\nFastAPI: {fastapi_shape}"
    )
```

### 6. Create `backend-v2/pyproject.toml` (or add pytest config to existing)

Add `asyncio_mode = "auto"` so every async test doesn't need `@pytest.mark.asyncio`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: tests that require both Flask and FastAPI servers running",
]
```

---

## Constraints

- Do not modify any files outside `backend-v2/`
- Do not modify the analyzer or router code to make tests pass — tests should work against the real implementation
- If a test fails, report what failed and why, but do not fix the underlying code without a separate prompt
- The fixture CSV should be a minimal real-looking bank statement — not just `a,b,c` — so the analyzer actually processes it

---

## Verification Steps

```bash
cd backend-v2
python -m pytest tests/ -v --ignore=tests/test_parity.py

# Expected output:
# tests/test_health.py::test_health_returns_200 PASSED
# tests/test_health.py::test_health_returns_correct_json PASSED
# tests/test_analyze.py::test_analyze_csv_returns_200 PASSED
# tests/test_analyze.py::test_analyze_csv_response_shape PASSED
# tests/test_analyze.py::test_analyze_rejects_bad_extension PASSED
# tests/test_analyze.py::test_analyze_rejects_oversized_file PASSED
# tests/test_analyze.py::test_analyze_transactions_have_required_fields PASSED
```

---

## Commit Message (hand to Ronit)

```
test(backend-v2): add FastAPI integration tests with httpx (BSA-10, TD-031)

- conftest.py: AsyncClient fixture using ASGITransport (no server needed)
- tests/test_health.py: 2 tests — status 200 + JSON shape
- tests/test_analyze.py: 5 tests — CSV upload, response shape, bad extension, oversized file, transaction fields
- tests/test_parity.py: shape-parity test (marked integration, requires both servers)
- tests/fixtures/sample.csv: 5-row minimal fixture
- pyproject.toml: asyncio_mode = auto

All 7 unit tests pass without a running server.
```

---

## After This Task

Update `docs/changelog.md`. Run the parity test manually against both servers to confirm shape match, then proceed to `docs/prompts/sprint-02/03-flask-cutover.md`.
