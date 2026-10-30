"""
EduSim_API/tests/test_rag_grounding.py
======================================
Tests grounding, refusal behavior, and fallback hardening of the RAG pipeline:
1. Off-topic query -> refuses with fixed refusal string, sources == [], call_ai is never called.
2. In-context query -> call_ai called exactly once with allow_fallback=False, sources returned with book/chapter/page/score.
3. Ollama failure (call_ai raises RuntimeError) -> API route returns HTTP 503 with clear message (no 500, no stack trace).
4. No request to openrouter.ai is made from legacy_rag unless RAG_ENABLE_OPENROUTER_FALLBACK is true.
5. Default path for other callers (allow_fallback=None) preserves OpenRouter fallback behavior when enabled.
"""

import os
import sys
import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["JWT_SECRET"] = "01234567890123456789012345678901"
os.environ["JWT_SECRET_KEY"] = "01234567890123456789012345678901"
os.environ["SUPABASE_URL"] = "https://qhdkgvthkktovccdyase.supabase.co"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.src.config.database import Base, get_db
from app.src.models.user import User
from app.src.utils.auth import create_access_token, hash_password
from app.src.modules.legacy_rag.service import REFUSAL_MESSAGE, query_rag_service
from app.src.modules.legacy_rag.generator import generate_response
from app.src.services.ai_router import call_ai
from main import app


@pytest.fixture(scope="module")
def rag_client_context():
    """Setup in-memory SQLite database, student test user, and TestClient."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    student = User(
        id=uuid.uuid4(),
        email="grounding_student@test.com",
        name="Grounding Student",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    db.add(student)
    db.commit()

    student_token = create_access_token({"sub": str(student.id), "role": "student"})

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "token": student_token,
        "headers": {"Authorization": f"Bearer {student_token}"},
    }

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_off_topic_query_refuses_without_llm_call():
    """
    (1a) Off-topic query where retriever returns no passing chunks:
    - Must return refusal string immediately
    - sources must be empty list
    - call_ai must never be invoked (call count 0)
    """
    with patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=[]), \
         patch("app.src.services.ai_router.call_ai", new_callable=AsyncMock) as mock_call_ai:

        result = await query_rag_service(query="Who won the 2011 cricket world cup?")

        assert result["answer"] == REFUSAL_MESSAGE
        assert result["sources"] == []
        assert result["fallback_mode"] is True
        assert mock_call_ai.call_count == 0


@pytest.mark.asyncio
async def test_in_context_query_invokes_call_ai_with_strict_fallback():
    """
    (1b) In-context query with mocked retriever returning 2 chunks:
    - call_ai invoked exactly once
    - allow_fallback=False must be enforced
    - Response contains sources with book, chapter, page, and score
    """
    mock_chunks = [
        {
            "text": "Photosynthesis is the process by which green plants synthesize nutrients.",
            "book_title": "Science Class 10",
            "chapter_title": "Life Processes",
            "page_start": 42,
            "score": 0.88,
            "board": "NCERT",
            "class": 10,
            "subject": "science",
            "topic_subtopic_path": "Autotrophic Nutrition",
        },
        {
            "text": "Chlorophyll pigments absorb light energy to drive the photosynthetic reaction.",
            "book_title": "Science Class 10",
            "chapter_title": "Life Processes",
            "page_start": 44,
            "score": 0.82,
            "board": "NCERT",
            "class": 10,
            "subject": "science",
            "topic_subtopic_path": "Autotrophic Nutrition",
        },
    ]

    mock_ai_output = {
        "text": "Photosynthesis is the synthesis of nutrients by green plants using chlorophyll and light.",
        "provider": "ollama",
        "tokens_used": 45,
    }

    with patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=mock_chunks), \
         patch("app.src.services.ai_router.call_ai", new_callable=AsyncMock, return_value=mock_ai_output) as mock_call_ai:

        result = await query_rag_service(query="Explain photosynthesis in plants.")

        # Assert call_ai called exactly once
        assert mock_call_ai.call_count == 1
        call_kwargs = mock_call_ai.call_args.kwargs
        assert call_kwargs.get("allow_fallback") is False
        assert call_kwargs.get("model") == "gemma3:4b"

        # Assert answer and rich sources
        assert result["answer"] == mock_ai_output["text"]
        assert len(result["sources"]) == 2
        for s in result["sources"]:
            assert "book" in s and s["book"] == "Science Class 10"
            assert "chapter" in s and s["chapter"] == "Life Processes"
            assert "page" in s and s["page"] in (42, 44)
            assert "score" in s and isinstance(s["score"], float)


def test_ollama_failure_returns_http_503(rag_client_context):
    """
    (1c) Ollama failure (call_ai raises RuntimeError):
    - The API route returns HTTP 503
    - Clear error message in detail
    - Not a 500 and not a stack trace
    """
    client = rag_client_context["client"]
    headers = rag_client_context["headers"]

    mock_chunk = [{
        "text": "Gravity is the attractive force between masses.",
        "book_title": "Physics Class 11",
        "chapter_title": "Gravitation",
        "page_start": 10,
        "score": 0.90,
    }]

    with patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=mock_chunk), \
         patch("app.src.services.ai_router.call_ai", side_effect=RuntimeError("Ollama service unreachable on localhost:11434")):

        response = client.post(
            "/api/rag/query",
            json={"query": "What is gravitation?"},
            headers=headers,
        )

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "AI service unavailable" in data["detail"]
        assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_no_openrouter_call_unless_explicitly_enabled(monkeypatch):
    """
    (1d) No code path in legacy_rag makes a request to openrouter.ai unless
    RAG_ENABLE_OPENROUTER_FALLBACK is set true (asserted by intercepting HTTP requests).
    """
    intercepted_urls = []

    # Intercept any HTTP request to verify if openrouter was reached
    original_send = httpx.AsyncClient.send

    async def tracking_send(self, request, *args, **kwargs):
        url_str = str(request.url)
        intercepted_urls.append(url_str)
        if "localhost:11434" in url_str:
            # Simulate Ollama connection failure
            raise httpx.ConnectError("Connection refused by Ollama", request=request)
        if "openrouter.ai" in url_str:
            return httpx.Response(200, json={"choices": [{"message": {"content": "Fallback answer"}}]})
        return await original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", tracking_send)

    # 1. Default (RAG_ENABLE_OPENROUTER_FALLBACK is off / unset)
    monkeypatch.delenv("RAG_ENABLE_OPENROUTER_FALLBACK", raising=False)
    intercepted_urls.clear()

    with pytest.raises(RuntimeError) as exc_info:
        await generate_response(
            context="Some valid textbook context",
            question="What is inertia?",
        )

    assert "OpenRouter fallback is disabled" in str(exc_info.value)
    # Verify openrouter.ai was NEVER called
    assert not any("openrouter.ai" in u for u in intercepted_urls), (
        f"Unexpected OpenRouter call occurred: {intercepted_urls}"
    )

    # 2. Opt-in fallback enabled (RAG_ENABLE_OPENROUTER_FALLBACK=true)
    monkeypatch.setenv("RAG_ENABLE_OPENROUTER_FALLBACK", "true")
    intercepted_urls.clear()

    with patch("app.src.modules.legacy_rag.generator.generate_llm_text_async", new_callable=AsyncMock) as mock_openrouter:
        mock_openrouter.return_value = "Fallback answer from OpenRouter"
        answer = await generate_response(
            context="Some valid textbook context",
            question="What is inertia?",
        )
        assert answer == "Fallback answer from OpenRouter"
        assert mock_openrouter.call_count == 1


@pytest.mark.asyncio
async def test_ai_router_default_fallback_behavior_for_other_callers(monkeypatch):
    """
    (3) Audit verification: Test that allow_fallback=None (the default) preserves
    previous behavior for non-RAG callers:
    - If ENABLE_OPENROUTER_FALLBACK=true (default) and Ollama fails, OpenRouter fallback is triggered.
    - If allow_fallback=False is explicitly passed, RuntimeError is raised without calling OpenRouter.
    """
    monkeypatch.setenv("ENABLE_OPENROUTER_FALLBACK", "true")

    # Mock Ollama post to fail
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Ollama down")), \
         patch("app.src.modules.legacy_rag.generator.generate_llm_text_async", new_callable=AsyncMock) as mock_cloud:

        mock_cloud.return_value = "Cloud response"

        # Case A: Default allow_fallback=None (used by tutor, simulations, question_service)
        result = await call_ai(prompt="Explain kinetic energy")
        assert result["provider"] == "openrouter"
        assert result["text"] == "Cloud response"
        assert mock_cloud.call_count == 1

        # Case B: allow_fallback=False explicitly passed (used by RAG)
        mock_cloud.reset_mock()
        with pytest.raises(RuntimeError) as exc_info:
            await call_ai(prompt="Explain kinetic energy", allow_fallback=False)

        assert "OpenRouter fallback is disabled" in str(exc_info.value)
        assert mock_cloud.call_count == 0
