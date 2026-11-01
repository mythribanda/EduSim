import os
import logging
import uuid
import time
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_router")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b").strip() or "gemma3:4b"

try:
    OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
except (ValueError, TypeError):
    OLLAMA_TIMEOUT = 180.0

OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m").strip() or "30m"

try:
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
except (ValueError, TypeError):
    OLLAMA_NUM_CTX = 4096

_TAGS_CACHE_TTL = 30.0
_tags_cache: Dict[str, Any] = {
    "timestamp": 0.0,
    "base_url": "",
    "is_reachable": False,
    "models": [],
    "error": None,
}


def invalidate_ollama_tags_cache() -> None:
    """Invalidates the in-memory preflight tags cache."""
    _tags_cache["timestamp"] = 0.0
    _tags_cache["base_url"] = ""
    _tags_cache["is_reachable"] = False
    _tags_cache["models"] = []
    _tags_cache["error"] = None


def _is_model_in_tags(target_model: str, model_names: list[str]) -> bool:
    target_clean = target_model.strip().lower()
    target_bare = target_clean.split(":")[0]
    for name in model_names:
        name_clean = name.strip().lower()
        name_bare = name_clean.split(":")[0]
        if name_clean == target_clean:
            return True
        if ":" not in target_clean and (name_clean == f"{target_clean}:latest" or name_bare == target_clean):
            return True
        if target_clean.endswith(":latest") and (name_clean == target_clean.removesuffix(":latest") or name_bare == target_bare):
            return True
        if name_clean == target_clean or name_bare == target_clean:
            return True
    return False


async def preflight_ollama_check(base_url: str, required_model: str) -> tuple[bool, Optional[str]]:
    """
    Cheap preflight in ai_router: GET {base_url}/api/tags (2s timeout, cached for 30s).
    If Ollama is unreachable or OLLAMA_MODEL isn't listed, logs a clear one-line warning:
      - "Ollama unreachable at {base_url}"
      - "model {required_model} not pulled, run: ollama pull {required_model}"
    and returns (False, warning_reason).
    """
    now = time.time()
    if (
        _tags_cache["base_url"] == base_url
        and (now - _tags_cache["timestamp"]) < _TAGS_CACHE_TTL
        and _tags_cache["is_reachable"]
    ):
        if _is_model_in_tags(required_model, _tags_cache["models"]):
            return True, None
        warn = f"model {required_model} not pulled, run: ollama pull {required_model}"
        logger.warning(warn)
        return False, warn

    tags_url = f"{base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=2.0, read=2.0)) as client:
            resp = await client.get(tags_url)
            if resp.status_code == 200:
                data = resp.json()
                models_data = data.get("models", [])
                model_names = [m.get("name", "") for m in models_data if isinstance(m, dict)]
                _tags_cache["timestamp"] = now
                _tags_cache["base_url"] = base_url
                _tags_cache["is_reachable"] = True
                _tags_cache["models"] = model_names
                _tags_cache["error"] = None

                if _is_model_in_tags(required_model, model_names):
                    return True, None

                warn = f"model {required_model} not pulled, run: ollama pull {required_model}"
                logger.warning(warn)
                return False, warn
            else:
                warn = f"Ollama unreachable at {base_url}"
                logger.warning(warn)
                _tags_cache["timestamp"] = now
                _tags_cache["base_url"] = base_url
                _tags_cache["is_reachable"] = False
                _tags_cache["models"] = []
                _tags_cache["error"] = warn
                return False, warn
    except Exception:
        warn = f"Ollama unreachable at {base_url}"
        logger.warning(warn)
        _tags_cache["timestamp"] = now
        _tags_cache["base_url"] = base_url
        _tags_cache["is_reachable"] = False
        _tags_cache["models"] = []
        _tags_cache["error"] = warn
        return False, warn


def limit_context_budget(
    context: str,
    max_chunks: int = 4,
    max_tokens: int = 1500,
) -> str:
    """
    Limits prompt context size for models by capping chunk count and total estimated tokens.
    Uses ~4 characters per token heuristic.
    """
    if not context:
        return ""
    delimiter = "\n\n---\n\n" if "\n\n---\n\n" in context else "\n\n"
    chunks = [c for c in context.split(delimiter) if c.strip()]
    if not chunks:
        return context

    selected = chunks[:max_chunks]
    result = []
    current_tokens = 0
    for chunk in selected:
        tokens = max(1, len(chunk) // 4)
        if current_tokens + tokens > max_tokens:
            remaining = max(0, max_tokens - current_tokens)
            if remaining > 25:
                result.append(chunk[: remaining * 4].rstrip() + "...")
            break
        result.append(chunk)
        current_tokens += tokens

    return delimiter.join(result) if result else selected[0][: max_tokens * 4]


async def call_ai(
    prompt: str,
    system_prompt: str = "",
    model: str = "gemma3:4b",
    history: list[dict[str, str]] | None = None,
    temperature: float = 0.2,
    response_format: dict | None = None,
    request_id: str | None = None,
    timeout: float | None = None,
    allow_fallback: bool | None = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Unified AI router for EduSim.
    1. Preflights Ollama via GET {OLLAMA_BASE_URL}/api/tags (2s timeout, cached 30s).
    2. Attempts Ollama at {OLLAMA_BASE_URL}/api/generate with separate timeouts (connect 3s, read 180s).
    3. If Ollama fails and ALLOW_CLOUD_FALLBACK=true, falls back to OpenRouter.
       If ALLOW_CLOUD_FALLBACK=false, returns structured error:
       {
           "generation_failed": True,
           "error_type": "LOCAL_LLM_UNAVAILABLE",
           "message": ...
       }
    """
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    effective_model = model or OLLAMA_DEFAULT_MODEL
    effective_timeout = timeout if timeout is not None else OLLAMA_TIMEOUT
    use_cloud_ai = os.getenv("USE_CLOUD_AI", "false").lower() in ("true", "1", "yes")

    # Determine fallback permission:
    # ALLOW_CLOUD_FALLBACK defaults to false when OPENROUTER_API_KEY is empty.
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    env_fallback_str = os.getenv("ALLOW_CLOUD_FALLBACK")
    if env_fallback_str is not None:
        env_fallback = env_fallback_str.strip().lower() in ("true", "1", "yes")
    else:
        legacy_fallback_str = os.getenv("ENABLE_OPENROUTER_FALLBACK")
        if legacy_fallback_str is not None:
            env_fallback = legacy_fallback_str.strip().lower() in ("true", "1", "yes") and bool(openrouter_key)
        else:
            env_fallback = bool(openrouter_key)

    should_fallback = allow_fallback if allow_fallback is not None else env_fallback

    # -------------------------------------------------------------
    # 1. Primary Provider: Ollama
    # -------------------------------------------------------------
    ollama_error_reason: Optional[str] = None
    if use_cloud_ai:
        ollama_error_reason = "USE_CLOUD_AI=true (Forced Cloud OpenRouter Mode)"
    else:
        # Preflight check before long generate request
        preflight_ok, preflight_warn = await preflight_ollama_check(OLLAMA_BASE_URL, effective_model)
        if not preflight_ok:
            ollama_error_reason = preflight_warn or f"Ollama unreachable at {OLLAMA_BASE_URL}"
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
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {
                        "temperature": temperature,
                        "num_ctx": OLLAMA_NUM_CTX,
                    },
                }
                if system_prompt:
                    payload["system"] = system_prompt

                # Support JSON mode if requested
                if response_format and response_format.get("type") == "json_object":
                    payload["format"] = "json"

                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout=effective_timeout, connect=3.0, read=effective_timeout)
                ) as client:
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
    # 2. Fallback Provider: OpenRouter (or structured error)
    # -------------------------------------------------------------
    if not should_fallback:
        logger.warning(
            f"[AI ROUTER] Ollama attempt failed (reason=\"{ollama_error_reason}\") and cloud fallback is disabled."
        )
        if allow_fallback is False and os.getenv("ALLOW_CLOUD_FALLBACK") is None:
            raise RuntimeError(
                f"Ollama generation failed ({ollama_error_reason}). OpenRouter fallback is disabled."
            )
        return {
            "text": "",
            "generation_failed": True,
            "error_type": "LOCAL_LLM_UNAVAILABLE",
            "message": ollama_error_reason or "Local LLM is unavailable.",
            "provider": "ollama",
            "tokens_used": 0,
        }

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


__all__ = [
    "call_ai",
    "preflight_ollama_check",
    "invalidate_ollama_tags_cache",
    "limit_context_budget",
    "OLLAMA_BASE_URL",
    "OLLAMA_TAGS_URL",
    "OLLAMA_GENERATE_URL",
    "OLLAMA_DEFAULT_MODEL",
    "OLLAMA_TIMEOUT",
    "OLLAMA_KEEP_ALIVE",
    "OLLAMA_NUM_CTX",
]
