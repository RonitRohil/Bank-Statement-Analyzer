import pathlib
import pytest
import httpx

FLASK_URL = "http://localhost:5000"
FASTAPI_URL = "http://localhost:8000"
CSV_PATH = pathlib.Path(__file__).parent / "fixtures" / "sample.csv"


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
def test_flask_fastapi_response_shape_parity():
    """Assert Flask and FastAPI return the same JSON shape for a CSV upload."""
    with open(CSV_PATH, "rb") as f:
        flask_resp = httpx.post(
            f"{FLASK_URL}/api/analyze/bank/statement",
            files={"file": ("sample.csv", f, "text/csv")},
            timeout=30,
        )

    with open(CSV_PATH, "rb") as f:
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
