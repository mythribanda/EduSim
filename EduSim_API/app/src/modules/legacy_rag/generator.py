import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.generator")

import os
import json
import re
from typing import Any, Dict, Optional

import httpx
from pathlib import Path
from app.src.config.models import (
    OPENROUTER_API_KEY,
    OPENROUTER_URL,
    get_model_chain,
)

# Load prompt templates
def _load_prompt_template(filename: str) -> str:
    """Read a prompt template from the prompt_templates directory."""
    base_path = Path(__file__).parent / "prompt_templates" / filename
    return base_path.read_text(encoding="utf-8")

ULTIMATE_TUTOR_PROMPT = _load_prompt_template("ultimate_tutor_prompt.txt")
# =========================================================
# NEW RENDERING SYSTEM (Sent to LLM)
# =========================================================
NEW_RENDERING_SYSTEM = r'''
You are an advanced Educational Content Synthesizer. Your output is consumed directly by a high-fidelity interactive frontend rendering engine. The engine automatically parses semantic Markdown headings and converts them into gorgeous, animated React cards, interactive tables, and mathematical dashboards.

To ensure a premium, modern textbook-like UI, you must adhere strictly to the following constraints:

=========================================================
1. STRICT FORMATTING CONSTRAINTS
=========================================================
* BE EXTREMELY CONCISE & COMPACT: To ensure maximum page responsiveness and fast generation (max 3-5 seconds), you must keep every section very brief. Write no more than 1 short paragraph (2-3 sentences) under any heading, and keep lists to 2-3 short bullet points. Avoid wordy introductions, transitions, or filler prose.
* DO NOT output any ASCII-art borders, frames, or box-drawing characters (e.g., `┌`, `└`, `│`, `─`, or `┌───────────────────────────┐`).
* DO NOT output mock action button links in brackets (e.g., `[ Explain Formula ]` or `[ Open Formula Lab ]`).
* Output standard, clean, valid GitHub Flavored Markdown (GFM). 
* Use bolding and formatting sparingly. Remaining content should be clean, professional textbook-style prose.

=========================================================
2. ADAPTIVE STRUCTURE (INTENT-BASED HEADINGS)
=========================================================
The orchestrator will inject a target structure based on the query intent. You must strictly align your headings to the structure provided.

# Definition
# Key Points
# Characteristics
# Formula
# Derivation
# Applications
# Advantages
# Disadvantages
# Summary
# Suggested Questions

CRITICAL ADAPTIVITY RULES:
* OMIT HEADINGS: If a section does not apply to the topic (e.g., there is no formula/derivation for a purely qualitative concept), DO NOT output that heading. Omit the section entirely to prevent hallucinations.
* NO PLACEHOLDERS: Never write placeholder text (e.g., "N/A" or "None") under any heading. Either write a complete, high-quality section, or omit the heading.

=========================================================
3. INTERACTIVE COMPONENT MAPPING (WRITE FOR THE UI)
=========================================================
Your markdown elements map directly to React components. Write content that maximizes their interactivity:

* Heading 1 (`# Heading Name`) ──> Becomes a standalone, expandable Accordion Card. Keep card content focused and punchy.
* Advantages & Disadvantages ──> Under consecutive `# Advantages` and `# Disadvantages` headings, list points in a standard bulleted list with the term in bold (e.g., `* **Pro:** Description`). The UI automatically places them side-by-side in a stunning green/red Comparison Card. Do not use Markdown tables here.
* Comparison Tables (Differences) ──> Under a `# Differences` or `# Differences Table` heading, use a standard Markdown table:
  ```markdown
  | Feature | Concept A | Concept B |
  |---|---|---|
  ```
* Characteristics & Properties ──> Under `## Key Properties` or `# Characteristics`, list each characteristic/property as a bullet point (e.g., `* **Property Name:** Description`). Do NOT write them as plain paragraphs.

'''

# =========================================================
# TUTOR SYSTEM PROMPT (Dedicated for premium explanations)
# =========================================================
TUTOR_SYSTEM_PROMPT = r'''
You are EduSim AI — a real-time physics tutor embedded directly inside an interactive simulation sandbox.

Your role is NOT to behave like:

* a chatbot
* a textbook
* a narrator
* a physics engine log

Your role is to behave like:

* an intelligent physics teacher
* actively observing the live simulation
* explaining the underlying physics dynamically
* guiding the student's attention
* predicting outcomes from changes
* helping students build intuition through observation

==================================================
CORE EDUCATIONAL BEHAVIOR
=========================

You MUST:

* explain CAUSE → EFFECT relationships
* explain WHY motion changes
* explain HOW variables influence behavior
* focus on visually observable physics
* connect simulation behavior to real-world intuition
* guide curiosity and experimentation

Always prioritize:

1. visible motion
2. physical cause
3. conceptual intuition
4. interactive experimentation

Avoid:

* robotic summaries
* textbook paragraphs
* implementation details
* engine terminology
* raw numerical narration
* overly academic language

==================================================
IMPORTANT TUTORING RULES
========================

1. Speak like a live physics mentor watching the sandbox in real time.

2. Explanations must feel:

* dynamic
* observational
* intuitive
* visual
* conversational

3. Keep explanations SHORT and SIDEBAR-FRIENDLY.
   Each section should be:

* concise
* punchy
* visually readable
* usually 1-2 short lines maximum

4. Focus on the MOST visually dominant physics interaction happening right now.

5. If the student changes a parameter:

* explain what changed
* explain why behavior changes
* explain what the student should observe next

6. Prioritize:

* motion changes
* instability
* collisions
* energy transfer
* orbital changes
* oscillation changes
* force balance changes

7. Never describe:

* raw engine state
* implementation details
* backend/runtime logic
* internal calculations
* debug-style output

BAD:
"The object's velocity vector was updated."

GOOD:
"The satellite accelerates as gravity pulls it toward Earth."

==================================================
RESPONSE FORMAT
===============

Always respond EXACTLY in this structure:

### ✦ LIVE EXPLANATION

Describe what is happening RIGHT NOW in intuitive visual language.

### ✦ WHY IT HAPPENS

Explain the primary physical cause behind the behavior.

### ✦ WHAT TO NOTICE

Direct the student's attention to important visual indicators.

### ✦ FORMULA

Show ONE key formula in LaTeX:

$$ ... $$

Then briefly explain:

* what the variables represent
* how changing them affects the motion

### ✦ DEEPER UNDERSTANDING

Connect the behavior to:

* a deeper physics law
* or a real-world phenomenon

### ✦ TRY THIS

Suggest 1-2 interactive experiments the student can try immediately.

==================================================
PHYSICS REASONING RULES
=======================

You MUST reason dynamically using:

* object motion
* forces
* energy changes
* orbital changes
* velocity changes
* acceleration changes
* collisions
* constraints
* oscillations
* stability changes

Do NOT give generic static explanations.

Always explain:

* why the behavior emerged
* what variables caused it
* what will happen next

==================================================
PREDICTIVE TUTORING
===================

If parameters change:

* predict likely future behavior
* guide student observation
* explain expected consequences

Example:
"Increasing orbital velocity raises orbital energy and expands the orbit."

==================================================
MISCONCEPTION CORRECTION
========================

If student actions imply misconceptions:

* gently correct them conceptually
* avoid sounding judgmental
* focus on intuition

Example:
"Heavier objects still fall similarly because gravitational acceleration remains nearly constant."

==================================================
VISUAL LEARNING PRIORITY
========================

Always prioritize what the student can SEE.

Examples:

* changing orbit size
* increasing oscillation speed
* energy loss
* faster perihelion motion
* collision recoil
* trajectory curvature

The explanation should feel synchronized with visible simulation behavior.

==================================================
TOPIC ADAPTABILITY
==================

The sandbox may involve:

* orbital mechanics
* Newton's laws
* springs
* pendulums
* collisions
* ramps
* friction
* oscillations
* projectiles
* energy systems

Adapt explanations dynamically based on the active physics concepts.

==================================================
STYLE RULES
===========

Use:

* intuitive language
* visual reasoning
* causal explanations
* educational guidance

Avoid:

* excessive jargon
* long paragraphs
* repetitive phrasing
* rigid textbook tone

The tutor should feel:

* intelligent
* reactive
* observant
* curious
* educationally helpful

==================================================
FINAL GOAL
==========

Your purpose is to transform the sandbox into:

* a live interactive physics laboratory
* an AI-guided conceptual learning environment
* a system that teaches students WHY physics happens visually

You are not merely explaining formulas.

You are helping students BUILD PHYSICAL INTUITION through live simulation interaction.
'''


def _format_prompt(prompt: str, system_prompt: str | None) -> str:
    if system_prompt:
        return f"{system_prompt}\n\n{prompt}"
    return prompt


def _openrouter_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://edusim.ai",
        "X-Title": "EduSim",
    }


def _extract_openrouter_content(data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(data, dict):
        return None

    choices = data.get("choices") or []
    if not choices:
        return None

    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content.strip()
    return None


import uuid
from collections import OrderedDict

# In-memory Request-ID deduplication cache (LRU eviction, max 1000 items)
_REQUEST_CACHE: OrderedDict[str, str] = OrderedDict()
_MAX_CACHE_SIZE = 1000


def _sanitize_error(msg: str) -> str:
    if not msg:
        return ""
    # Mask any Bearer tokens or sensitive keys
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [MASKED]', str(msg))
    sanitized = re.sub(r'sk-or-[A-Za-z0-9_\-\.]+', '[MASKED_KEY]', sanitized)
    if OPENROUTER_API_KEY and OPENROUTER_API_KEY != "YOUR_API_KEY" and len(OPENROUTER_API_KEY) > 6:
        sanitized = sanitized.replace(OPENROUTER_API_KEY, "[MASKED_KEY]")
    return sanitized


class OpenRouterError(Exception):
    def __init__(self, message: str, status_code: int | None = None, is_fatal: bool = False, error_type: str = "UNKNOWN"):
        clean_msg = _sanitize_error(message)
        super().__init__(clean_msg)
        self.status_code = status_code
        self.is_fatal = is_fatal
        self.error_type = error_type


def _cache_put(req_id: str, content: str):
    if not req_id or not content:
        return
    if req_id in _REQUEST_CACHE:
        _REQUEST_CACHE.move_to_end(req_id)
    _REQUEST_CACHE[req_id] = content
    if len(_REQUEST_CACHE) > _MAX_CACHE_SIZE:
        _REQUEST_CACHE.popitem(last=False)


def _log_model_attempt(model_name: str, fallback: bool = False, request_id: str | None = None):
    req_str = f"request_id={request_id} " if request_id else ""
    if fallback:
        logger.info(f"[LLM] {req_str}Fallback model triggered: {model_name}")
    else:
        logger.info(f"[LLM] {req_str}Using model: {model_name}")


def _log_model_failure(model_name: str, error: str, request_id: str | None = None):
    req_str = f"request_id={request_id} " if request_id else ""
    logger.error(f"[LLM] {req_str}Model failed: {model_name} ({error})")


def _log_model_success(model_name: str, request_id: str | None = None):
    req_str = f"request_id={request_id} " if request_id else ""
    logger.info(f"[LLM] {req_str}Response generated successfully ({model_name})")


def clean_history_for_llm(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not history:
        return []
    
    cleaned = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role not in ["user", "assistant"]:
            continue
            
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] = (cleaned[-1]["content"] + "\n\n" + content).strip()
        else:
            cleaned.append({"role": role, "content": content.strip()})
            
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
        
    return cleaned


def _generate_openrouter_text(
    prompt: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str | None = NEW_RENDERING_SYSTEM,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
) -> Optional[str]:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_API_KEY":
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} error=Missing or unconfigured OPENROUTER_API_KEY")
        raise OpenRouterError("Missing OpenRouter API key. Please configure OPENROUTER_API_KEY.", status_code=401, is_fatal=True)

    logger.info(f"[LLM REQUEST] request_id={req_id} model={model_name} prompt_preview={repr(prompt[:80])}")

    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            messages = (history or []) + [
                {
                    "role": "user",
                    "content": _format_prompt(prompt, system_prompt),
                }
            ]
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                payload["response_format"] = response_format

            response = client.post(
                OPENROUTER_URL,
                headers=_openrouter_headers(),
                json=payload,
            )

            if response.status_code == 402:
                logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=402 error=Payment Required (Billing/Credit Limit)")
                raise OpenRouterError("OpenRouter payment required (HTTP 402). Insufficient credits or model limit reached.", status_code=402, is_fatal=False, error_type="BILLING_CREDIT_LIMIT")

            if response.status_code == 401:
                logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=401 error=Unauthorized (Invalid API key)")
                raise OpenRouterError("OpenRouter authentication failed (HTTP 401). Invalid API key.", status_code=401, is_fatal=True, error_type="AUTH_ERROR")

            response.raise_for_status()
            data = response.json()
            usage = data.get("usage") or {}
            t_tokens = usage.get("total_tokens", 0)
            logger.info(f"[LLM RESPONSE] request_id={req_id} model={model_name} status=success tokens={t_tokens}")
            return _extract_openrouter_content(data)

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        err_detail = _sanitize_error(e.response.text[:200])
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code={status_code} error={err_detail}")
        if status_code == 402:
            raise OpenRouterError("OpenRouter payment required (HTTP 402). Insufficient credits or model limit reached.", status_code=402, is_fatal=False, error_type="BILLING_CREDIT_LIMIT")
        elif status_code == 401:
            raise OpenRouterError("OpenRouter authentication failed (HTTP 401). Invalid API key.", status_code=401, is_fatal=True, error_type="AUTH_ERROR")
        elif status_code == 429:
            raise OpenRouterError(f"OpenRouter rate limit exceeded (HTTP 429): {err_detail}", status_code=429, is_fatal=False, error_type="RATE_LIMIT")
        elif status_code >= 500:
            raise OpenRouterError(f"OpenRouter server error (HTTP {status_code}): {err_detail}", status_code=status_code, is_fatal=False, error_type="SERVER_ERROR")
        else:
            raise OpenRouterError(f"OpenRouter HTTP {status_code} error: {err_detail}", status_code=status_code, is_fatal=True, error_type="CLIENT_ERROR")
    except httpx.TimeoutException as e:
        clean_err = _sanitize_error(str(e))
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=timeout error={clean_err}")
        raise OpenRouterError(f"OpenRouter request timed out: {clean_err}", status_code=408, is_fatal=False, error_type="TIMEOUT")
    except OpenRouterError:
        raise
    except Exception as e:
        clean_err = _sanitize_error(str(e))
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=exception error={clean_err}")
        raise OpenRouterError(f"OpenRouter request failed: {clean_err}", status_code=500, is_fatal=False, error_type="EXCEPTION")


async def _generate_openrouter_text_async(
    prompt: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str | None = NEW_RENDERING_SYSTEM,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
) -> Optional[str]:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_API_KEY":
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} error=Missing or unconfigured OPENROUTER_API_KEY")
        raise OpenRouterError("Missing OpenRouter API key. Please configure OPENROUTER_API_KEY.", status_code=401, is_fatal=True)

    logger.info(f"[LLM REQUEST] request_id={req_id} model={model_name} prompt_preview={repr(prompt[:80])}")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            messages = (history or []) + [
                {
                    "role": "user",
                    "content": _format_prompt(prompt, system_prompt),
                }
            ]
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                payload["response_format"] = response_format

            response = await client.post(
                OPENROUTER_URL,
                headers=_openrouter_headers(),
                json=payload,
            )

            if response.status_code == 402:
                logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=402 error=Payment Required (Billing/Credit Limit)")
                raise OpenRouterError("OpenRouter payment required (HTTP 402). Insufficient credits or model limit reached.", status_code=402, is_fatal=False, error_type="BILLING_CREDIT_LIMIT")

            if response.status_code == 401:
                logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=401 error=Unauthorized (Invalid API key)")
                raise OpenRouterError("OpenRouter authentication failed (HTTP 401). Invalid API key.", status_code=401, is_fatal=True, error_type="AUTH_ERROR")

            response.raise_for_status()
            data = response.json()
            usage = data.get("usage") or {}
            t_tokens = usage.get("total_tokens", 0)
            logger.info(f"[LLM RESPONSE] request_id={req_id} model={model_name} status=success tokens={t_tokens}")
            return _extract_openrouter_content(data)

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        err_detail = _sanitize_error(e.response.text[:200])
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code={status_code} error={err_detail}")
        if status_code == 402:
            raise OpenRouterError("OpenRouter payment required (HTTP 402). Insufficient credits or model limit reached.", status_code=402, is_fatal=False, error_type="BILLING_CREDIT_LIMIT")
        elif status_code == 401:
            raise OpenRouterError("OpenRouter authentication failed (HTTP 401). Invalid API key.", status_code=401, is_fatal=True, error_type="AUTH_ERROR")
        elif status_code == 429:
            raise OpenRouterError(f"OpenRouter rate limit exceeded (HTTP 429): {err_detail}", status_code=429, is_fatal=False, error_type="RATE_LIMIT")
        elif status_code >= 500:
            raise OpenRouterError(f"OpenRouter server error (HTTP {status_code}): {err_detail}", status_code=status_code, is_fatal=False, error_type="SERVER_ERROR")
        else:
            raise OpenRouterError(f"OpenRouter HTTP {status_code} error: {err_detail}", status_code=status_code, is_fatal=True, error_type="CLIENT_ERROR")
    except httpx.TimeoutException as e:
        clean_err = _sanitize_error(str(e))
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=timeout error={clean_err}")
        raise OpenRouterError(f"OpenRouter request timed out: {clean_err}", status_code=408, is_fatal=False, error_type="TIMEOUT")
    except OpenRouterError:
        raise
    except Exception as e:
        clean_err = _sanitize_error(str(e))
        logger.error(f"[LLM ERROR] request_id={req_id} model={model_name} status_code=exception error={clean_err}")
        raise OpenRouterError(f"OpenRouter request failed: {clean_err}", status_code=500, is_fatal=False, error_type="EXCEPTION")


def generate_llm_text(
    final_prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 3000,
    system_prompt: str | None = NEW_RENDERING_SYSTEM,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
):
    final_prompt = final_prompt.strip()
    return generate_openrouter_text(
        final_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
        history=history,
        response_format=response_format,
        request_id=request_id,
    )


def generate_openrouter_text(
    prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 4096,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
) -> str:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"

    # Deduplication check: prevent sending the exact same request_id more than once
    if req_id in _REQUEST_CACHE:
        logger.info(f"[LLM CACHE HIT] request_id={req_id} returning cached response without OpenRouter request")
        return _REQUEST_CACHE[req_id]

    history = clean_history_for_llm(history)
    models = get_model_chain()
    primary_model = models[0] if models else "google/gemini-2.5-flash"
    fallback_model = models[1] if len(models) > 1 else None

    # --- ATTEMPT 1: PRIMARY MODEL (EXACTLY ONE ATTEMPT) ---
    logger.info(f"[LLM PRIMARY ATTEMPT] request_id={req_id} model={primary_model}")
    primary_error = None
    primary_status_code = None
    primary_error_type = None

    try:
        result = _generate_openrouter_text(
            prompt,
            primary_model,
            temperature,
            max_output_tokens,
            system_prompt=system_prompt,
            history=history,
            response_format=response_format,
            request_id=req_id,
        )
        if result and not result.startswith("Error:"):
            # SUCCESS: NEVER call fallback model after successful response!
            _cache_put(req_id, result)
            logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={primary_model}")
            return result
        else:
            primary_error = result or "Empty response from primary model"
            primary_error_type = "EMPTY_RESPONSE"
    except OpenRouterError as e:
        primary_error = _sanitize_error(str(e))
        primary_status_code = e.status_code
        primary_error_type = getattr(e, "error_type", "API_ERROR")
        if primary_status_code == 401:
            logger.error(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} status_code=401 error_type=AUTH_ERROR error={primary_error}")
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{primary_error}\"")
            return f"Error: {primary_error}"
    except Exception as e:
        primary_error = _sanitize_error(str(e))
        primary_error_type = "EXCEPTION"

    logger.warning(
        f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} "
        f"status_code={primary_status_code} error_type={primary_error_type} error={primary_error}"
    )

    # --- ATTEMPT 2: FALLBACK MODEL (AT MOST ONE ATTEMPT) ---
    if fallback_model and fallback_model != primary_model:
        reason = f"Primary failed with status_code={primary_status_code} ({primary_error_type})"
        logger.info(f"[LLM FALLBACK ATTEMPT] request_id={req_id} model={fallback_model} reason=\"{reason}\"")
        try:
            fb_result = _generate_openrouter_text(
                prompt,
                fallback_model,
                temperature,
                max_output_tokens,
                system_prompt=system_prompt,
                history=history,
                response_format=response_format,
                request_id=req_id,
            )
            if fb_result and not fb_result.startswith("Error:"):
                # Fallback succeeded! Return successful response normally and cache it.
                _cache_put(req_id, fb_result)
                logger.info(f"[LLM FALLBACK SUCCESS] request_id={req_id} model={fallback_model}")
                logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={fallback_model}")
                return fb_result
            else:
                fb_error = fb_result or "Empty response from fallback model"
                logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} status_code=None error_type=EMPTY_RESPONSE error={fb_error}")
                logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
                return fb_error
        except OpenRouterError as e:
            fb_error = _sanitize_error(str(e))
            logger.error(
                f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} "
                f"status_code={e.status_code} error_type={getattr(e, 'error_type', 'API_ERROR')} error={fb_error}"
            )
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
            return f"Error: {fb_error}"
        except Exception as e:
            fb_error = _sanitize_error(str(e))
            logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} status_code=exception error_type=EXCEPTION error={fb_error}")
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
            return f"Error: Fallback model {fallback_model} failed: {fb_error}"

    logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{primary_error}\"")
    return f"Error: {primary_error or 'Unable to generate response from OpenRouter.'}"


async def generate_llm_text_async(
    final_prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 2500,
    system_prompt: str | None = NEW_RENDERING_SYSTEM,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
):
    final_prompt = final_prompt.strip()
    return await generate_openrouter_text_async(
        final_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        system_prompt=system_prompt,
        history=history,
        response_format=response_format,
        request_id=request_id,
    )


async def generate_openrouter_text_async(
    prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 2500,
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
    response_format: dict | None = None,
    request_id: str | None = None,
) -> str:
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"

    # Deduplication check: prevent sending the exact same request_id more than once
    if req_id in _REQUEST_CACHE:
        logger.info(f"[LLM CACHE HIT] request_id={req_id} returning cached response without OpenRouter request")
        return _REQUEST_CACHE[req_id]

    history = clean_history_for_llm(history)
    models = get_model_chain()
    primary_model = models[0] if models else "google/gemini-2.5-flash"
    fallback_model = models[1] if len(models) > 1 else None

    # --- ATTEMPT 1: PRIMARY MODEL (EXACTLY ONE ATTEMPT) ---
    logger.info(f"[LLM PRIMARY ATTEMPT] request_id={req_id} model={primary_model}")
    primary_error = None
    primary_status_code = None
    primary_error_type = None

    try:
        result = await _generate_openrouter_text_async(
            prompt,
            primary_model,
            temperature,
            max_output_tokens,
            system_prompt=system_prompt,
            history=history,
            response_format=response_format,
            request_id=req_id,
        )
        if result and not result.startswith("Error:"):
            # SUCCESS: NEVER call fallback model after successful response!
            _cache_put(req_id, result)
            logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={primary_model}")
            return result
        else:
            primary_error = result or "Empty response from primary model"
            primary_error_type = "EMPTY_RESPONSE"
    except OpenRouterError as e:
        primary_error = _sanitize_error(str(e))
        primary_status_code = e.status_code
        primary_error_type = getattr(e, "error_type", "API_ERROR")
        if primary_status_code == 401:
            logger.error(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} status_code=401 error_type=AUTH_ERROR error={primary_error}")
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{primary_error}\"")
            return f"Error: {primary_error}"
    except Exception as e:
        primary_error = _sanitize_error(str(e))
        primary_error_type = "EXCEPTION"

    logger.warning(
        f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} "
        f"status_code={primary_status_code} error_type={primary_error_type} error={primary_error}"
    )

    # --- ATTEMPT 2: FALLBACK MODEL (AT MOST ONE ATTEMPT) ---
    if fallback_model and fallback_model != primary_model:
        reason = f"Primary failed with status_code={primary_status_code} ({primary_error_type})"
        logger.info(f"[LLM FALLBACK ATTEMPT] request_id={req_id} model={fallback_model} reason=\"{reason}\"")
        try:
            fb_result = await _generate_openrouter_text_async(
                prompt,
                fallback_model,
                temperature,
                max_output_tokens,
                system_prompt=system_prompt,
                history=history,
                response_format=response_format,
                request_id=req_id,
            )
            if fb_result and not fb_result.startswith("Error:"):
                # Fallback succeeded! Return successful response normally and cache it.
                _cache_put(req_id, fb_result)
                logger.info(f"[LLM FALLBACK SUCCESS] request_id={req_id} model={fallback_model}")
                logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={fallback_model}")
                return fb_result
            else:
                fb_error = fb_result or "Empty response from fallback model"
                logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} status_code=None error_type=EMPTY_RESPONSE error={fb_error}")
                logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
                return fb_error
        except OpenRouterError as e:
            fb_error = _sanitize_error(str(e))
            logger.error(
                f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} "
                f"status_code={e.status_code} error_type={getattr(e, 'error_type', 'API_ERROR')} error={fb_error}"
            )
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
            return f"Error: {fb_error}"
        except Exception as e:
            fb_error = _sanitize_error(str(e))
            logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} status_code=exception error_type=EXCEPTION error={fb_error}")
            logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{fb_error}\"")
            return f"Error: Fallback model {fallback_model} failed: {fb_error}"

    logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"{primary_error}\"")
    return f"Error: {primary_error or 'Unable to generate response from OpenRouter.'}"


async def generate_llm_stream_async(
    final_prompt: str,
    temperature: float = 0.3,
    max_output_tokens: int = 1800,
    history: list[dict[str, str]] | None = None,
    system_prompt: str | None = NEW_RENDERING_SYSTEM,
    request_id: str | None = None,
):
    final_prompt = final_prompt.strip()
    req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_API_KEY":
        logger.error(f"[LLM ERROR] request_id={req_id} error=Missing OPENROUTER_API_KEY")
        yield f"data: {json.dumps({'error': 'Missing OpenRouter API Key'})}\n\n"
        return

    models = get_model_chain()
    primary_model = models[0] if models else "google/gemini-2.5-flash"
    fallback_model = models[1] if len(models) > 1 else None

    logger.info(f"[LLM STREAM REQUEST] request_id={req_id} model={primary_model}")

    # Try primary model
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            messages = (history or []) + [
                {
                    "role": "user",
                    "content": _format_prompt(final_prompt, system_prompt),
                }
            ]
            async with client.stream(
                "POST",
                OPENROUTER_URL,
                headers=_openrouter_headers(),
                json={
                    "model": primary_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_output_tokens,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response:
                if response.status_code == 402:
                    logger.warning(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} status_code=402 error_type=BILLING_CREDIT_LIMIT error=Payment Required")
                    # Fall through to attempt fallback model
                elif response.status_code == 401:
                    logger.error(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} status_code=401 error_type=AUTH_ERROR error=Unauthorized")
                    yield f"data: {json.dumps({'error': 'OpenRouter authentication failed (HTTP 401). Invalid API key.'})}\n\n"
                    return
                elif response.status_code >= 400:
                    logger.warning(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} status_code={response.status_code} error={_sanitize_error(response.text[:150])}")
                    # Fall through to fallback
                else:
                    response.raise_for_status()
                    emitted_chunk = False

                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: "):
                            data_str = chunk[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {}).get("content", "")
                                    if delta:
                                        emitted_chunk = True
                                        yield f"data: {json.dumps({'content': delta})}\n\n"
                            except json.JSONDecodeError:
                                continue

                    if emitted_chunk:
                        logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={primary_model}")
                        return

    except Exception as e:
        logger.warning(f"[LLM PRIMARY FAILURE] request_id={req_id} model={primary_model} error={_sanitize_error(str(e))}")

    # Fallback model (if primary failed)
    if fallback_model and fallback_model != primary_model:
        logger.info(f"[LLM FALLBACK ATTEMPT] request_id={req_id} model={fallback_model} reason=\"Primary stream failed\"")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                messages = (history or []) + [
                    {
                        "role": "user",
                        "content": _format_prompt(final_prompt, system_prompt),
                    }
                ]
                async with client.stream(
                    "POST",
                    OPENROUTER_URL,
                    headers=_openrouter_headers(),
                    json={
                        "model": fallback_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_output_tokens,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    },
                ) as response:
                    if response.status_code >= 400:
                        err_text = _sanitize_error(response.text[:150])
                        logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} status_code={response.status_code} error={err_text}")
                        yield f"data: {json.dumps({'error': f'Fallback model failed (HTTP {response.status_code})'})}\n\n"
                        return

                    response.raise_for_status()
                    emitted_chunk = False
                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: "):
                            data_str = chunk[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {}).get("content", "")
                                    if delta:
                                        emitted_chunk = True
                                        yield f"data: {json.dumps({'content': delta})}\n\n"
                            except json.JSONDecodeError:
                                continue
                    if emitted_chunk:
                        logger.info(f"[LLM FALLBACK SUCCESS] request_id={req_id} model={fallback_model}")
                        logger.info(f"[LLM STATUS] request_id={req_id} status=SUCCESS model={fallback_model}")
                        return
        except Exception as e:
            logger.error(f"[LLM FALLBACK FAILURE] request_id={req_id} model={fallback_model} error={_sanitize_error(str(e))}")

    logger.error(f"[LLM STATUS] request_id={req_id} status=FAILED error=\"All OpenRouter stream models failed\"")
    yield f"data: {json.dumps({'error': 'All OpenRouter models failed'})}\n\n"


def is_topic_change(query: str, history: list[dict[str, str]] | None) -> bool:
    if not history:
        return False
        
    # Stop words to filter out completely
    stop_words = {
        'what', 'is', 'why', 'how', 'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 
        'else', 'to', 'for', 'of', 'in', 'on', 'at', 'by', 'with', 'about', 'against', 
        'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 
        'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 
        'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 
        'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 
        'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 
        't', 'can', 'will', 'just', 'don', 'should', 'now', 'give', 'me', 'us', 'tell',
        'explain', 'describe', 'list', 'show', 'write', 'define', 'meaning', 'concept',
        'topic', 'please', 'we', 'go', 'back', 'its'
    }
    
    # Generic question words that represent intents rather than topics
    generic_query_words = {
        'formula', 'formulas', 'equation', 'equations', 'numerical', 'numericals', 
        'example', 'examples', 'definition', 'definitions', 'diagram', 'diagrams', 
        'advantages', 'disadvantages', 'pros', 'cons', 'difference', 'differences', 
        'compare', 'contrast', 'relationship', 'relations', 'working', 'process', 
        'explain', 'explanation', 'detail', 'details', 'more', 'less', 'why', 'how', 
        'show', 'list', 'tell', 'wt', 'what', 'define', 'meaning', 'illustration'
    }
    
    def extract_keywords(text: str):
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return {w for w in words if w not in stop_words}
        
    current_keywords = extract_keywords(query)
    if not current_keywords:
        return False
        
    # If the remaining keywords are all generic, it is not a topic change
    non_generic = current_keywords - generic_query_words
    if not non_generic:
        return False
        
    # Extract last 2 user messages
    user_messages = [msg.get("content", "") for msg in history if msg.get("role") == "user"]
    if not user_messages:
        return False
        
    history_text = " ".join(user_messages[-2:])
    history_keywords = extract_keywords(history_text)
    
    overlap = non_generic.intersection(history_keywords)
    if not overlap:
        # Check if pronouns are present in query to reference previous topic
        pronouns = {'it', 'its', 'this', 'that', 'they', 'them', 'these', 'those', 'he', 'she', 'his', 'her'}
        query_words = set(re.findall(r'\b[a-z]+\b', query.lower()))
        if query_words.intersection(pronouns):
            return False
        return True
        
    return False


# =========================================================
# PREMIUM EDUCATIONAL RESPONSE GENERATOR
# =========================================================
def get_tutor_prompt(context: str, question: str, fallback_mode: bool = False, history: list[dict[str, str]] | None = None) -> str:
    from .topic_type import detect_topic_type, get_dynamic_sections
    from ..tutor.query_intent import detect_query_intent, get_intent_structure

    # Detect simulation query
    is_simulation = "physics sandbox simulation" in context.lower() or "simulation" in context.lower()

    topic_type = detect_topic_type(question, context)
    intent = detect_query_intent(question)

    is_follow_up = history and any(msg.get("role") == "user" for msg in history)
    if is_follow_up and is_topic_change(question, history):
        is_follow_up = False

    if is_follow_up:
        if intent == "definition":
            dynamic_structure = """
# Introduction

## Definition
"""
        elif intent == "formula":
            dynamic_structure = """
# Formulas & Characteristics

## Core Formulas
"""
        elif intent == "characteristics":
            dynamic_structure = """
# Formulas & Characteristics

## Key Properties
"""
        elif intent == "numerical":
            dynamic_structure = """
# Practice Example

## Solved Numerical
"""
        elif intent == "advantages" or intent == "comparison":
            dynamic_structure = """
# Advantages

# Disadvantages
"""
        elif intent == "examples" or intent == "applications":
            dynamic_structure = """
# Applications

## Everyday Applications
"""
        else:
            dynamic_structure = """
# Introduction

## Explanation
"""
    else:
        topic_structure = get_dynamic_sections(topic_type)

        # =========================================================
        # VALIDATION LOGIC: PREVENT INVALID SECTIONS
        # =========================================================
        if topic_type in ["history", "social_science"]:
            # Strictly prevent formulas and calculations for history/social science
            if intent in ["formula", "numerical"]:
                intent = "detailed"

        elif topic_type == "biology":
            # Avoid unnecessary calculations in biology unless explicitly a formula
            if intent == "numerical":
                intent = "detailed"

        dynamic_structure = get_intent_structure(intent, topic_structure)

    if fallback_mode:
        context_instruction = "Answer based on your general knowledge. Do NOT claim the explanation came from a textbook."
        context_section = ""
    else:
        context_instruction = "Use the provided TEXTBOOK CONTEXT to ground your explanation accurately."
        context_section = f"""
=========================================================
TEXTBOOK CONTEXT
=========================================================

{context}
"""

    follow_up_instruction = ""
    follow_up_final_override = ""
    if is_follow_up:
        follow_up_instruction = """
=========================================================
STRICT FOLLOW-UP CONSTRAINTS:
=========================================================
This is a follow-up chat message. To maintain extreme conciseness and target the user's specific query, you MUST ONLY output the section(s) listed under the REQUIRED RESPONSE STRUCTURE. Do NOT output any other H1 or H2 headings. Keep your response focused entirely on the requested section.
Additionally, when writing explanations (e.g., under "## Explanation"), you MUST present the content in a neat, concise bulleted list (using * or -). The number of bullet points should scale dynamically based on the complexity of the query: keep it brief (2-3 concise points) for simple questions, and allow more points for complex, multi-faceted queries so the explanation remains comprehensive yet focused.
"""
        follow_up_final_override = f"""
=========================================================
CRITICAL FOLLOW-UP RULE:
=========================================================
You are in follow-up mode. You MUST NOT generate any other H1 sections or cards. Generate ONLY the single H1 section:
{dynamic_structure.strip().splitlines()[0]}
Do NOT repeat the H2 sub-heading more than once. Write exactly one H1 section with its content.
If the subheading is "## Explanation", you MUST write the entire explanation as a neat, concise bulleted list (using * or -). The length and number of bullet points MUST scale dynamically based on the complexity of the query (e.g., 2-3 short points for simpler questions, and more points for complex queries). Do NOT write it as a long, continuous paragraph.
"""

    if is_simulation:
        return f"""
You are the EduSim AI Tutor — a real-time physics tutor embedded directly inside an interactive simulation sandbox.

{context_instruction}

{follow_up_instruction}

=========================================================
STRICT FORMATTING RULES
=========================================================
1. Mathematical formulas MUST ALWAYS use LaTeX wrapped inside $$ ... $$ or $ ... $.
2. Avoid excessive bold text. Remaining content should be plain readable text.
3. Be highly engaging, visual, student-friendly, and educational.

{context_section}

=========================================================
ACTIVE SIMULATION STATE / EVENT INFO
=========================================================

{question}

=========================================================
STRICT OUTPUT FORMAT RULES:
=========================================================
- You MUST structure your entire response using the following headers and sections:
  ### ❖ LIVE EXPLANATION
  ### ❖ WHY IT HAPPENS
  ### ❖ WHAT TO NOTICE
  ### ❖ FORMULA
  ### ❖ DEEPER UNDERSTANDING
  ### ❖ TRY THIS
- Do NOT use other headers. Avoid robotic engine descriptions; sound like a live physics teacher.
"""
    else:
        return f"""
You are the EduSim AI Physics Tutor and Live Narrator.
Analyze the following active simulation event and provide an in-depth, structured educational response.

{context_instruction}

{follow_up_instruction}

=========================================================
STRICT FORMATTING RULES
=========================================================

1. Main headings MUST:
   - Use Markdown H1 (#)
   - Be bold
   - No emojis

Example:
# Heading

2. Subheadings MUST:
   - Use Markdown H2 (##)
   - Be bold
   - No emojis

Example:
## Subheading

3. Do NOT use emojis anywhere.

4. Use proper spacing and indentation.

5. Use bullet points where needed.

6. Paragraphs should be short and readable.

7. Use professional textbook-style formatting.

8. Mathematical formulas MUST ALWAYS use LaTeX.

Examples:

$$F = ma$$

$$v = u + at$$

$$E = mc^2$$

9. Never output formulas as plain text.

10. Advantages and Disadvantages MUST be presented under two separate H1 headings: `# Advantages` and `# Disadvantages`. List each point as a bullet with the title bolded (e.g. `* **Point Name:** Description.`). Do NOT use markdown tables for advantages/disadvantages.

11. Use horizontal separators:

---

between major sections.

12. ONLY headings and subheadings may be bold.

13. Do NOT use excessive bold text.

14. Remaining content should be plain readable text.

15. Add detailed educational explanations.

16. Include:
- Definitions
- Characteristics
- Types
- Formulas
- Derivations (if applicable)
- Applications
- Real-world examples
- Advantages
- Disadvantages
- Summary

17. Maintain clean textbook formatting.

18. Use proper markdown indentation.

19. Avoid repeating concepts or duplicating math equations.

20. Keep explanations student-friendly.

21. Keep formatting visually premium.

22. Use professional academic language.

23. Every solved numerical, step-by-step example, or calculation MUST follow this exact sub-section structure using H3 (###) headers:
    - ### Problem
      A clear statement of the question or problem.
    - ### Given
      A list of all known variables, symbols, and values with units (e.g. *Mass ($m$) = $5 \\text{{kg}}$*).
    - ### Formula
      The equation or mathematical relation used to solve the problem (rendered in display LaTeX, e.g. $$F = ma$$).
    - ### Substitution
      Showing the plugging-in of the given values into the formula.
    - ### Calculation
      The step-by-step arithmetic steps showing how the calculation is performed.
    - ### Final Answer
      The final value of the calculation with proper units, clearly highlighted (e.g. **Force ($F$) = $10 \\text{{N}}$**).
    - ### Interpretation
      A brief statement of what the result physically means.

24. NEVER stack mathematical fractions or equations vertically on separate single-character lines (e.g. numerator on line 1, denominator on line 3). ALWAYS use proper LaTeX syntax like \\frac{{a}}{{b}} and wrap it inside $$ ... $$ or $ ... $ (e.g. Write $$\\frac{{1}}{{f}} = \\frac{{1}}{{v}} - \\frac{{1}}{{u}}$$).

25. NEVER write plain text on the same line as display math delimiters ($$). Always start a new paragraph on a new line for any text explanation that follows a formula.

26. All characteristics and properties (e.g., under ## Key Properties or ## Characteristics) MUST be presented as a clear, concise bulleted list (using * or -). Do NOT write them as paragraphs.

27. The `# Introduction` card MUST always be detailed, comprehensive, and highly structured. Under the `# Introduction` header, you MUST include:
    - A subheading `## Definition` containing a detailed, clear overview paragraph explaining the physical concept in simple, premium academic terms.
    - Directly below the overview paragraph (still within the `## Definition` section, and with NO other subheading), you MUST include a clean, concise bulleted list (using * or -) detailing 2-3 key aspects or features of the definition. Bold the name of each aspect (e.g., `* **Aspect Name:** Brief description.`).
    - You MUST NOT generate any subheading like `## Key Concepts`, `## Core Pillars`, or `## Key Aspects` inside the `# Introduction` card. All contents of this card must reside under the single `## Definition` subheading.

{context_section}

=========================================================
STUDENT QUESTION / TOPIC
=========================================================

{question}

=========================================================
REQUIRED RESPONSE STRUCTURE
=========================================================
You MUST structure your entire response using the following textbook structure. Use EXACTLY these headings (e.g., `# Introduction`, `## Definition`, etc.) as applicable to the topic to allow our rendering engine to structure them as separate interactive cards:

{dynamic_structure}

Ensure each section has rich, detailed, and highly educational explanation content.
Do NOT output headers like '### ❖ LIVE EXPLANATION' or other simulation event headers. Use the textbook H1 and H2 structure above.

{follow_up_final_override}
"""


RAG_SYSTEM_PROMPT = (
    "You are an educational assistant for EduSim.\n\n"
    "CRITICAL CONSTRAINTS:\n"
    "1. Answer the question using ONLY the provided Textbook Context.\n"
    "2. Do NOT use outside knowledge, extrapolate, or invent details not directly stated in the context.\n"
    "3. If the provided context is insufficient or does not contain the answer, state clearly: "
    "'The provided textbook context does not contain enough information to answer this question.'\n"
    "4. Present explanations clearly and student-friendly, formatting formulas with LaTeX ($...$ or $$...$$)."
)


async def generate_response(
    context: str,
    question: str,
    user_preference: str = "student_friendly",
    fallback_mode: bool = False,
    model: str = "gemma3:4b",
) -> str:
    """
    Generates educational response grounded in textbook context using local Ollama (gemma3:4b).
    OpenRouter is only used if opt-in env var RAG_ENABLE_OPENROUTER_FALLBACK=true is set.
    """
    from app.src.services.ai_router import call_ai

    allow_cloud_fallback = os.getenv("RAG_ENABLE_OPENROUTER_FALLBACK", "false").lower() in ("true", "1", "yes")

    rag_user_prompt = f"""=========================================================
TEXTBOOK CONTEXT
=========================================================

{context}

=========================================================
STUDENT QUESTION / TOPIC
=========================================================

{question}

Please answer the student's question using ONLY the textbook context above. If the context does not contain enough information to answer, state that clearly."""

    result = await call_ai(
        prompt=rag_user_prompt,
        system_prompt=RAG_SYSTEM_PROMPT,
        model=model,
        temperature=0.2,
        allow_fallback=allow_cloud_fallback,
    )
    return result.get("text", "")


def generate_response_sync(
    context: str,
    question: str,
    user_preference: str = "student_friendly",
    fallback_mode: bool = False,
    model: str = "gemma3:4b",
) -> str:
    import asyncio
    return asyncio.run(generate_response(context, question, user_preference, fallback_mode, model))