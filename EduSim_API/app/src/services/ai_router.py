import os
import logging
import json
import uuid
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_router")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b").strip() or "gemma3:4b"
try:
    OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))
except (ValueError, TypeError):
    OLLAMA_TIMEOUT = 60.0


async def call_ai(
    prompt: str,
    system_prompt: str = "",
    model: str = "gemma3:4b",
    history: list[dict[str, str]] | None = None,
    temperature: float = 0.2,
    response_format: dict | None = None,
    request_id: str | None = None,
    timeout: float | None = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Unified AI router for EduSim.
    Attempts Ollama first at http://localhost:11434/api/generate with OLLAMA_TIMEOUT (default 60s).
    If USE_CLOUD_AI=true or on timeout/connection error, falls back to OpenRouter.
    Logs which provider was used for each request.

    Returns:
        {
            "text": str,
            "provider": "ollama" | "openrouter",
            "tokens_used": int
        }
    """
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    effective_model = model or OLLAMA_DEFAULT_MODEL
    effective_timeout = timeout if timeout is not None else OLLAMA_TIMEOUT
    use_cloud_ai = os.getenv("USE_CLOUD_AI", "false").lower() in ("true", "1", "yes")

    # -------------------------------------------------------------
    # 1. Primary Provider: Ollama (http://localhost:11434/api/generate)
    # -------------------------------------------------------------
    ollama_error_reason: Optional[str] = None
    if use_cloud_ai:
        ollama_error_reason = "USE_CLOUD_AI=true (Forced Cloud OpenRouter Mode)"
    else:
        try:
            logger.info(
                f"[AI ROUTER] [OLLAMA ATTEMPT] request_id={req_id} "
                f"model={effective_model} url={OLLAMA_GENERATE_URL} timeout={effective_timeout}s"
            )

            ollama_prompt = prompt
            if history:
                history_lines = []
                for msg in history:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    content = msg.get("content", "").strip()
                    if content:
                        history_lines.append(f"{role}: {content}")
                if history_lines:
                    ollama_prompt = "\n".join(history_lines) + f"\nUser: {prompt}\nAssistant:"

            payload: Dict[str, Any] = {
                "model": effective_model,
                "prompt": ollama_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                }
            }
            if system_prompt:
                payload["system"] = system_prompt

            # Support JSON mode if requested
            if response_format and response_format.get("type") == "json_object":
                payload["format"] = "json"

            async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout, connect=5.0)) as client:
                resp = await client.post(OLLAMA_GENERATE_URL, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("response", "").strip()
                    if text:
                        prompt_eval_count = data.get("prompt_eval_count", 0) or 0
                        eval_count = data.get("eval_count", 0) or 0
                        tokens_used = prompt_eval_count + eval_count

                        logger.info(
                            f"[AI ROUTER] [PROVIDER USED: ollama] request_id={req_id} "
                            f"model={effective_model} tokens_used={tokens_used}"
                        )
                        return {
                            "text": text,
                            "provider": "ollama",
                            "tokens_used": tokens_used,
                        }
                    else:
                        ollama_error_reason = "Ollama returned an empty response"
                else:
                    ollama_error_reason = f"Ollama returned HTTP {resp.status_code}: {resp.text[:100]}"

        except httpx.TimeoutException:
            ollama_error_reason = f"Ollama timed out after {effective_timeout}s"
        except (httpx.ConnectError, httpx.NetworkError) as e:
            ollama_error_reason = f"Ollama connection error: {e}"
        except Exception as e:
            ollama_error_reason = f"Ollama exception: {e}"

    # -------------------------------------------------------------
    # 2. Fallback Provider: OpenRouter
    # -------------------------------------------------------------
    logger.warning(
        f"[AI ROUTER] [FALLBACK TRIGGERED] request_id={req_id} "
        f"reason=\"{ollama_error_reason}\". Falling back to OpenRouter..."
    )

    from app.src.modules.legacy_rag.generator import generate_llm_text_async

    openrouter_text = await generate_llm_text_async(
        final_prompt=prompt,
        temperature=temperature,
        system_prompt=system_prompt,
        history=history,
        response_format=response_format,
        request_id=req_id,
    )

    # Estimate tokens used for OpenRouter response
    tokens_used = max(1, (len(prompt.split()) + len(openrouter_text.split())) * 4 // 3) if openrouter_text else 0

    logger.info(
        f"[AI ROUTER] [PROVIDER USED: openrouter] request_id={req_id} "
        f"tokens_used={tokens_used}"
    )

    return {
        "text": openrouter_text,
        "provider": "openrouter",
        "tokens_used": tokens_used,
    }


__all__ = ["call_ai", "OLLAMA_BASE_URL", "OLLAMA_GENERATE_URL", "OLLAMA_DEFAULT_MODEL", "OLLAMA_TIMEOUT"]
