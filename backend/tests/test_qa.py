"""
Tests for the /api/qa/ask endpoint and qa_engine.py.
Ollama calls are mocked — no real LLM required.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.main import app


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mem_client():
    """HTTP test client backed by an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _get_test_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _get_test_session
    yield app
    app.dependency_overrides.clear()


def _make_response(body: dict) -> httpx.Response:
    """Wrap a dict in a fake Ollama /v1/chat/completions httpx.Response."""
    request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    return httpx.Response(200, json=body, request=request)


def _tool_call_response(tool_name: str, arguments: dict) -> httpx.Response:
    body = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_test_1",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ]
    }
    return _make_response(body)


def _text_response(text: str) -> httpx.Response:
    body = {"choices": [{"message": {"content": text, "tool_calls": None}}]}
    return _make_response(body)


def _make_ollama_mock(*responses) -> tuple:
    """Return (mock_client, patch_target) for patching httpx.AsyncClient in qa_engine."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = list(responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


# ── Tests ──────────────────────────────────────────────────────────────────────


async def test_qa_returns_answer(mem_client):
    """Pass 1 returns a tool_call, pass 2 returns a text answer → 200 with answer string."""
    mock_client = _make_ollama_mock(
        _tool_call_response("list_statements", {}),
        _text_response("You have 2 statements saved."),
    )

    with patch("app.services.qa_engine.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=mem_client), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/qa/ask", json={"question": "How many statements do I have?"}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "You have 2 statements saved."
    assert data["tool_used"] == "list_statements"
    assert isinstance(data["data_points"], int)


async def test_qa_ollama_down(mem_client):
    """ConnectError → 200 with the Ollama-unavailable message (no crash)."""
    mock_client = _make_ollama_mock()
    mock_client.post.side_effect = httpx.ConnectError("Ollama not reachable")

    with patch("app.services.qa_engine.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=mem_client), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/qa/ask", json={"question": "What is my total spending?"}
            )

    assert response.status_code == 200
    data = response.json()
    assert "ollama" in data["answer"].lower() or "unavailable" in data["answer"].lower()
    assert data["tool_used"] == "error"
    assert data["data_points"] == 0


async def test_qa_empty_question(mem_client):
    """Empty question string → 400 Bad Request."""
    async with AsyncClient(
        transport=ASGITransport(app=mem_client), base_url="http://test"
    ) as client:
        response = await client.post("/api/qa/ask", json={"question": ""})

    assert response.status_code == 400


async def test_qa_direct_answer(mem_client):
    """LLM returns a direct text answer (no tool_calls) → endpoint extracts and returns it."""
    mock_client = _make_ollama_mock(
        _text_response("You have no transactions recorded yet.")
    )

    with patch("app.services.qa_engine.httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(
            transport=ASGITransport(app=mem_client), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/qa/ask", json={"question": "Show me my transactions."}
            )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "You have no transactions recorded yet."
    assert data["tool_used"] == "none"
    assert data["data_points"] == 0
