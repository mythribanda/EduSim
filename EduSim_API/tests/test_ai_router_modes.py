import pytest
import httpx
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.src.services.ai_router import (
    call_ai,
    invalidate_ollama_tags_cache,
    limit_context_budget,
)


@pytest.fixture(autouse=True)
def clear_tags_cache():
    """Ensure preflight tags cache is fresh for each test."""
    invalidate_ollama_tags_cache()
    yield
    invalidate_ollama_tags_cache()


@pytest.mark.asyncio
async def test_ollama_up_used(monkeypatch):
    """
    1. Ollama up → used.
    Verifies that when Ollama is running and has the model, it is used,
    and options (num_ctx=4096, keep_alive="30m") are included.
    """
    monkeypatch.setenv("USE_CLOUD_AI", "false")
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "false")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "180")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "30m")
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")

    posted_payloads = []

    async def mock_get(self, url, *args, **kwargs):
        if "/api/tags" in str(url):
            return httpx.Response(200, json={"models": [{"name": "gemma3:4b"}]})
        return httpx.Response(404)

    async def mock_post(self, url, *args, **kwargs):
        if "/api/generate" in str(url):
            posted_payloads.append(kwargs.get("json", {}))
            return httpx.Response(
                200,
                json={
                    "response": "F = ma is Newton's second law of motion.",
                    "prompt_eval_count": 25,
                    "eval_count": 35,
                },
            )
        return httpx.Response(404)

    with patch.object(httpx.AsyncClient, "get", new=mock_get), \
         patch.object(httpx.AsyncClient, "post", new=mock_post):

        result = await call_ai(
            prompt="State Newton's second law",
            model="gemma3:4b",
            temperature=0.2,
        )

        assert result["provider"] == "ollama"
        assert result["text"] == "F = ma is Newton's second law of motion."
        assert result["tokens_used"] == 60

        assert len(posted_payloads) == 1
        payload = posted_payloads[0]
        assert payload["model"] == "gemma3:4b"
        assert payload["keep_alive"] == "30m"
        assert payload["options"]["num_ctx"] == 4096
        assert payload["options"]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_ollama_down_fallback_disabled_returns_structured_error(monkeypatch):
    """
    2. Ollama down + fallback disabled → returns structured error LOCAL_LLM_UNAVAILABLE.
    """
    monkeypatch.setenv("USE_CLOUD_AI", "false")
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    async def mock_get(url, *args, **kwargs):
        raise httpx.ConnectError("Connection refused on port 11434")

    with patch.object(httpx.AsyncClient, "get", new=mock_get):
        result = await call_ai(
            prompt="Explain inertia",
            model="gemma3:4b",
            allow_fallback=False,
        )

        assert result.get("generation_failed") is True
        assert result.get("error_type") == "LOCAL_LLM_UNAVAILABLE"
        assert "Ollama unreachable" in result.get("message", "")
        assert result.get("provider") == "ollama"


@pytest.mark.asyncio
async def test_ollama_model_not_pulled_skips_generate(monkeypatch):
    """
    Model not pulled logs warning and returns LOCAL_LLM_UNAVAILABLE without waiting.
    """
    monkeypatch.setenv("USE_CLOUD_AI", "false")
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "false")

    generate_called = False

    async def mock_get(self, url, *args, **kwargs):
        # Ollama has llama3, but not gemma3:4b
        return httpx.Response(200, json={"models": [{"name": "llama3:8b"}]})

    async def mock_post(self, url, *args, **kwargs):
        nonlocal generate_called
        generate_called = True
        return httpx.Response(200, json={"response": "unexpected"})

    with patch.object(httpx.AsyncClient, "get", new=mock_get), \
         patch.object(httpx.AsyncClient, "post", new=mock_post):

        result = await call_ai(
            prompt="Explain gravity",
            model="gemma3:4b",
        )

        assert result.get("generation_failed") is True
        assert result.get("error_type") == "LOCAL_LLM_UNAVAILABLE"
        assert "not pulled" in result.get("message", "")
        assert "ollama pull gemma3:4b" in result.get("message", "")
        assert generate_called is False


@pytest.mark.asyncio
async def test_ollama_down_fallback_enabled_uses_openrouter(monkeypatch):
    """
    3. Ollama down + fallback enabled → OpenRouter used.
    """
    monkeypatch.setenv("USE_CLOUD_AI", "false")
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-mock-test-key")

    async def mock_get(url, *args, **kwargs):
        raise httpx.ConnectError("Ollama offline")

    with patch.object(httpx.AsyncClient, "get", new=mock_get), \
         patch("app.src.modules.legacy_rag.generator.generate_llm_text_async", new_callable=AsyncMock) as mock_cloud:

        mock_cloud.return_value = "Cloud answer from Claude 3.5 Sonnet"

        result = await call_ai(
            prompt="Explain momentum",
            model="gemma3:4b",
            allow_fallback=True,
        )

        assert result["provider"] == "openrouter"
        assert result["text"] == "Cloud answer from Claude 3.5 Sonnet"
        assert mock_cloud.call_count == 1


def test_tutor_router_maps_local_llm_unavailable_to_http_503(monkeypatch):
    """
    Verifies /api/tutor/analyze maps LOCAL_LLM_UNAVAILABLE structured error to HTTP 503.
    """
    monkeypatch.setenv("USE_CLOUD_AI", "false")
    monkeypatch.setenv("ALLOW_CLOUD_FALLBACK", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    from main import app
    client = TestClient(app)

    async def mock_get(url, *args, **kwargs):
        raise httpx.ConnectError("Ollama service down")

    with patch.object(httpx.AsyncClient, "get", new=mock_get):
        response = client.post(
            "/api/tutor/analyze",
            json={"query": "What is Newton's third law?"},
            headers={"Origin": "http://localhost:8080"},
        )

        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data.get("error_type") == "LOCAL_LLM_UNAVAILABLE"
        assert "message" in data
        assert "access-control-allow-origin" in response.headers


def test_limit_context_budget():
    """
    Verifies that context is capped to specified chunk count and tokens.
    """
    chunks = [
        "Chunk 1: " + "alpha " * 100,  # ~100 tokens
        "Chunk 2: " + "beta " * 100,   # ~100 tokens
        "Chunk 3: " + "gamma " * 100,  # ~100 tokens
        "Chunk 4: " + "delta " * 100,  # ~100 tokens
        "Chunk 5: " + "epsilon " * 100, # ~100 tokens
        "Chunk 6: " + "zeta " * 100,   # ~100 tokens
    ]
    raw_context = "\n\n---\n\n".join(chunks)

    # Cap to 4 chunks
    capped = limit_context_budget(raw_context, max_chunks=4, max_tokens=2000)
    capped_blocks = capped.split("\n\n---\n\n")
    assert len(capped_blocks) == 4
    assert "Chunk 1" in capped_blocks[0]
    assert "Chunk 4" in capped_blocks[3]

    # Cap to token budget
    tight_capped = limit_context_budget(raw_context, max_chunks=4, max_tokens=250)
    tight_blocks = tight_capped.split("\n\n---\n\n")
    assert len(tight_blocks) <= 3
