import re
import json
import difflib
import time
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.src.modules.legacy_rag.retriever import get_retriever
from app.src.modules.legacy_rag.generator import generate_llm_text, is_topic_change
import pickle
import faiss
from sentence_transformers import SentenceTransformer
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger("EduSim.tutor")


load_dotenv(Path(__file__).resolve().parents[4] / ".env")

# RAG Setup
from app.src.modules.legacy_rag.vector_loader import vector_store
try:
    from app.src.modules.tutor.subject_classifier import detect_subject
except ImportError:
    from tutor.subject_classifier import detect_subject

import asyncio

# Curriculum Index Cache
_curriculum_data = None
_curriculum_index = None


async def _summarize_chat_history_async(turns_to_summarize: list[dict[str, str]]) -> str:
    """Summarizes conversation history using the OpenRouter LLM."""
    if not turns_to_summarize:
        return ""
    
    # Format turns as text
    history_text = ""
    for msg in turns_to_summarize:
        role = "Student" if msg["role"] == "user" else "Tutor"
        history_text += f"{role}: {msg['content']}\n"
        
    prompt = f"""
    Please generate a very concise summary (2 sentences maximum) of the following educational conversation history.
    Focus on:
    1. The physics concepts/formulas discussed.
    2. Any specific student achievements or active misconceptions identified.
    3. Keep it brief and objective.
    
    Conversation:
    {history_text}
    """
    try:
        from app.src.modules.legacy_rag.generator import generate_llm_text_async
        summary = await generate_llm_text_async(
            prompt,
            temperature=0.2,
            max_output_tokens=150,
            system_prompt="You are a helpful education summarizer."
        )
        return summary.strip() if summary else ""
    except Exception as e:
        logger.error("[Summarizer] Failed to generate history summary: %s", e)
        return ""


def update_profile_from_interaction(db_session_factory, user_id, concepts: list[str] | None):
    """
    Directly updates student profile mastered topics from extracted concepts
    without firing extra LLM requests.
    """
    if not user_id or not concepts:
        return
    import uuid
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except Exception:
            return
    db = db_session_factory()
    try:
        from app.src.repositories.student_repository import StudentRepository
        profile = StudentRepository.get_or_create_profile(db, user_id)
        mastered_topics = list(profile.mastered_topics or [])
        updated = False
        for c in concepts:
            if isinstance(c, str) and c.strip() and c.strip() not in mastered_topics:
                mastered_topics.append(c.strip())
                updated = True
        if updated:
            StudentRepository.update_profile(db, user_id, mastered_topics=mastered_topics)
            logger.info("[Profile Update] Added mastered topics %s for user: %s", concepts[:3], user_id)
    except Exception as e:
        logger.error("[Profile Update] Failed to update profile: %s", e)
    finally:
        db.close()


async def analyze_and_update_profile_task(db_session_factory, user_id, query: str, response_text: str, concepts: list[str] | None = None):
    """
    Non-LLM background task that updates the student profile safely.
    """
    if concepts is None:
        concepts = [w.capitalize() for w in query.split() if len(w) > 4][:2]
    update_profile_from_interaction(db_session_factory, user_id, concepts)


def _empty_tutor_payload(message: str, error_type: str = "GENERATION_FAILED", status_code: int | None = None, provider: str = "unknown", tokens_used: int = 0) -> Dict[str, Any]:
    return {
        "title": "Generation Failed",
        "description": "",
        "formula": "",
        "related_concepts": [],
        "related_formulas": [],
        "ai_explanation": message,
        "sources": [],
        "queryType": "concept",
        "concepts": [],
        "formulas": [],
        "explanation": message,
        "ragContent": [],
        "simulation_guide": {"is_buildable": False},
        "generation_status": "failed",
        "generation_failed": True,
        "error_type": error_type,
        "status_code": status_code,
        "provider": provider,
        "tokens_used": tokens_used,
    }


def is_conversational_query(query: str) -> bool:
    q = query.strip().lower().rstrip("!?.")
    greetings = {
        "hi", "hello", "hey", "hola", "namaste", "good morning", "good afternoon",
        "good evening", "how are you", "who are you", "what are you", "what can you do",
        "help", "thanks", "thank you", "thx", "ok", "okay", "bye", "goodbye",
        "start", "restart", "test"
    }
    if q in greetings:
        return True
    tokens = q.split()
    if len(tokens) <= 3 and any(t in ["hi", "hello", "hey", "thanks", "thank"] for t in tokens):
        return True
    return False


async def check_query_subject_relevance(query: str) -> str:
    """
    Classifies a query deterministically without firing extra LLM requests.
    Returns: "academic", "conversational", or "out_of_context"
    """
    if is_conversational_query(query):
        return "conversational"
    return "academic"


def get_rag_components(subject: str = None):
    retriever = vector_store.get_retriever(subject)
    return retriever

async def analyze_with_llm_async(query: str, context: str, history: list[dict[str, str]] | None = None) -> Dict[str, Any]:
    system_prompt = (
        "You are an intelligent physics tutor. Analyze the query and textbook context to determine scientific properties and design a custom interactive physics sandbox simulation that demonstrates, explores, or proves the concept in the query (e.g., if they ask about Newton's Second Law, design a block-impulse collision system; if they ask about simple harmonic motion, design a spring oscillator; if they ask about gravity, design a falling-mass setup; if they ask about orbits, design planetary radial motion; etc.). The goal is to ALWAYS design an interactive, playable sandbox layout demonstrating their query.\n"
        "1. Determine 'queryType': 'concept', 'formula', or 'mixed'.\n"
        "2. Extract 'concepts': list of simple, concise topic names (e.g. ['Gravity', 'Orbital Velocity', 'Centripetal Force']). Do NOT output nested dictionaries.\n"
        "3. Extract 'formulas': [{formula, name, topic, meaning}]. Include fundamental ones if omitted in text.\n"
        "4. Generate a brief 'explanation': a short summary string (max 2 sentences).\n"
        "5. The 'simulation_guide' object MUST ALWAYS be included and have 'is_buildable': true.\n"
        "The 'simulation_guide' object MUST contain:\n"
        "   - 'is_buildable': true\n"
        "   - 'title': A beautiful short title (e.g. 'Double Pendulum Setup')\n"
        "   - 'steps': A list of exactly 6 step card objects, representing customized instructions. Each step object MUST contain:\n"
        "       * 'step_number': 1 to 6\n"
        "       * 'title': The title of the step, which must strictly match the following 6-step curriculum template:\n"
        "           - Step 1: 'Concept & Goal' (Explain the physical concept and the goal of the simulation)\n"
        "           - Step 2: 'Mass Setup' (Spawn the main physical masses like Circle or Rectangle at specific canvas coordinates)\n"
        "           - Step 3: 'Joints & Constraints' (Connect the masses using constraints like Rope, Spring, or Pivot)\n"
        "           - Step 4: 'Parameter Tuning' (Fine-tune values like gravity presets, mass, stiffness, or apply initial forces)\n"
        "           - Step 5: 'Run & Observe' (Explain how to run the simulation using the Play button and what active telemetry indicators like velocities, mechanical clock, or Kinetic Energy to inspect)\n"
        "           - Step 6: 'Physics Conclusion' (Provide a rigorous, definitive scientific summary and conclusion explaining the physical principles, equations, and outcomes proved or demonstrated by the simulation, e.g. how potential energy converts to kinetic energy, how acceleration is net force over mass, or how centripetal orbit scales with constant gravity)\n"
        "       * 'description': Clear, beginner-friendly instructions starting with a brief scientific explanation. Keep this description extremely brief and compact (exactly 1-2 short sentences). Explicitly mention and highlight the relevant sandbox assets (e.g., 'Circle', 'Rectangle', 'Rope', 'Spring', 'Pivot') and sandbox controllers (e.g. 'Play button', 'Gravity presets', 'Simulation Speed slider') that the user needs to use in this step. Suggest exact sizes, coordinates, mass values, and placement on the canvas. Keep workspace limits in mind (x between 100-700, y between 100-500).\n"
        "       * 'icon': A relevant emoji (e.g. '🏮', '🔴', '➰', '🪐', '🚀', '🤼')\n"
        "   - 'tips': A list of 3 scientific, inquiry-based tips matching the query (e.g. ['Try changing mass to see if swing period scales', 'Increase linear gravity preset to verify acceleration increases'])\n"
        "   - 'spawn_config': A procedural physics setup object describing the simulation layout so the frontend can auto-build it! It MUST contain:\n"
        "       * 'bodies': A list of shapes. Each body config MUST contain: 'id' (string, e.g. 'c1', 'rect1'), 'type' ('circle' or 'rectangle'), 'x' (number), 'y' (number), 'radius' (number, only if circle), 'width' (number, only if rectangle), 'height' (number, only if rectangle), 'isStatic' (boolean), 'mass' (number, optional), 'restitution' (number, optional), 'fillColor' (hex string, e.g. '0x38bdf8'), 'label' (string)\n"
        "       * 'constraints': A list of joints. Each constraint MUST contain: 'id' (string), 'type' ('rope' or 'spring'), 'bodyIdA' (string, source body ID), 'bodyIdB' (string, destination body ID), 'length' (number, optional), 'stiffness' (number, optional), 'damping' (number, optional)\n"
        "       * 'gravityMode': 'linear' or 'radial'\n"
        "       * 'gravityPreset': 'zero', 'moon', 'earth', or 'jupiter'\n"
        "       * 'forces': A list of initial forces to apply. Each force config contains: 'bodyId' (string), 'vector' ({x, y}, force components, small numbers e.g. 0.01 to 0.05)\n"
        "Return ONLY valid, parseable JSON matching the requested schema."
    )
    user_prompt = f"Context:\n{context}\n\nQuery:\n{query}"
    
    from app.src.modules.legacy_rag.generator import generate_llm_text_async
    try:
        response_text = await generate_llm_text_async(
            final_prompt=user_prompt,
            temperature=0.1,
            system_prompt=system_prompt,
            history=history,
        )
        if not response_text or "Error:" in response_text:
            return _empty_tutor_payload("AI failed to extract concepts.")
            
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                related_concepts = _dedupe_related_topics(parsed.get("concepts", []), max_items=_MAX_RELATED_TOPICS)
                return {
                    **parsed,
                    "title": parsed.get("title", "AI Tutor"),
                    "formula": parsed.get("formula", ""),
                    "related_concepts": related_concepts,
                    "related_formulas": parsed.get("formulas", []),
                    "ai_explanation": parsed.get("explanation", ""),
                    "simulation_guide": parsed.get("simulation_guide", {"is_buildable": False}),
                }
            except json.JSONDecodeError:
                pass
        return _empty_tutor_payload("Invalid JSON returned.")
    except Exception as e:
        return _empty_tutor_payload(f"AI error: {str(e)}")


async def generate_explanation_async(query: str, context: str, fallback_mode: bool = False, history: list[dict[str, str]] | None = None) -> str:
    from app.src.modules.legacy_rag.generator import generate_llm_text_async, get_tutor_prompt, NEW_RENDERING_SYSTEM
    prompt = get_tutor_prompt(context, query, fallback_mode, history=history)
    
    is_follow_up = history and any(msg["role"] == "user" for msg in history)
    sys_prompt = NEW_RENDERING_SYSTEM
    if is_follow_up:
        sys_prompt = "You are a helpful science and math tutor answering a student's follow-up question in a chat bubble. Keep your explanation clear, pedagogically sound, and friendly. Support markdown formatting and LaTeX equations using standard formatting."
        
    res = await generate_llm_text_async(prompt, temperature=0.3, system_prompt=sys_prompt, history=history)
    
    if not res:
        return "Failed to generate explanation."
        
    if fallback_mode:
        warning_msg = (
            "This topic is not available in the provided textbook context.\n\n"
            "The following explanation is AI-generated and may not exactly match your textbook.\n\n"
        )
        return warning_msg + res
    return res


async def analyze_concepts_with_llm_async(query: str, context: str) -> Dict[str, Any]:
    system_prompt = (
        "You are an intelligent physics tutor. Analyze the query and textbook context to determine scientific properties.\n"
        "1. Determine 'queryType': 'concept', 'formula', or 'mixed'.\n"
        "2. Extract 'concepts': list of simple, concise topic names (e.g. ['Gravity', 'Orbital Velocity', 'Centripetal Force']). Do NOT output nested dictionaries.\n"
        "3. Extract 'formulas': [{formula, name, topic, meaning}]. Include fundamental ones if omitted in text.\n"
        "4. Generate a brief 'explanation': a short summary string of the physics concepts.\n"
        "Return ONLY valid, parseable JSON matching the requested schema."
    )
    user_prompt = f"Context:\n{context}\n\nQuery:\n{query}"
    
    from app.src.modules.legacy_rag.generator import generate_llm_text_async
    try:
        response_text = await generate_llm_text_async(
            final_prompt=user_prompt,
            temperature=0.1,
            system_prompt=system_prompt
        )
        if not response_text or "Error:" in response_text:
            return {
                "queryType": "concept",
                "concepts": [],
                "formulas": [],
                "explanation": "AI failed to extract concepts."
            }
            
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                related_concepts = _dedupe_related_topics(parsed.get("concepts", []), max_items=_MAX_RELATED_TOPICS)
                return {
                    **parsed,
                    "title": parsed.get("title", "AI Tutor"),
                    "formula": parsed.get("formula", ""),
                    "related_concepts": related_concepts,
                    "related_formulas": parsed.get("formulas", []),
                    "explanation": parsed.get("explanation", ""),
                }
            except json.JSONDecodeError:
                pass
        return {
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": "Invalid JSON returned."
        }
    except Exception as e:
        return {
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": f"AI error: {str(e)}"
        }


def needs_simulation_generation(query: str) -> bool:
    q = query.lower()
    keywords = ["simulation", "sandbox", "create", "build", "run", "model", "setup", "physics scene", "canvas", "spawn", "joint", "rope", "spring", "mass", "simulate", "playground"]
    return any(kw in q for kw in keywords)


async def unified_tutor_generation_async(
    query: str,
    context: str,
    history: list[dict[str, str]] | None = None,
    fallback_mode: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """
    Generates the complete tutor analysis, explanation, simulation guide, and summary
    in AT MOST ONE OpenRouter API call.
    """
    from app.src.modules.legacy_rag.generator import generate_llm_text_async

    system_prompt = (
        "You are an expert AI STEM and physics tutor for EduSim, an interactive learning platform.\n"
        "Analyze the user's question and any textbook context provided. You must provide a comprehensive,\n"
        "pedagogically rigorous response along with an interactive sandbox simulation design.\n\n"
        "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "title": "Clear descriptive title of the topic or law",\n'
        '  "queryType": "concept" | "formula" | "mixed",\n'
        '  "concepts": ["concise concept name 1", "concise concept name 2"],\n'
        '  "formulas": [\n'
        '    {"formula": "LaTeX formula string", "name": "Formula Name", "topic": "Topic", "meaning": "Explanation of variables"}\n'
        '  ],\n'
        '  "explanation": "Comprehensive pedagogical explanation formatted in clean Markdown with LaTeX math ($...$ for inline, $$...$$ for display). Include conceptual intuition, formula derivations/applications, real-world examples, and key takeaways.",\n'
        '  "summary": "Concise 2-3 sentence educational revision summary capturing the core concept, main formula, and learning outcome.",\n'
        '  "simulation_guide": {\n'
        '    "is_buildable": true,\n'
        '    "title": "Short title for the simulation layout (e.g. Free Fall Dynamics)",\n'
        '    "steps": [\n'
        '      {"step_number": 1, "title": "Concept & Goal", "description": "1-2 brief sentences explaining the concept and sandbox goal.", "icon": "🎯"},\n'
        '      {"step_number": 2, "title": "Mass Setup", "description": "1-2 brief sentences instructing user to spawn Circle or Rectangle with coordinates and mass.", "icon": "🔴"},\n'
        '      {"step_number": 3, "title": "Joints & Constraints", "description": "1-2 brief sentences on connecting masses with Rope, Spring, or Pivot if needed.", "icon": "➰"},\n'
        '      {"step_number": 4, "title": "Parameter Tuning", "description": "1-2 brief sentences tuning gravity preset, stiffness, or initial impulse.", "icon": "⚙️"},\n'
        '      {"step_number": 5, "title": "Run & Observe", "description": "1-2 brief sentences on hitting Play and observing velocities, trajectories, or energies.", "icon": "▶️"},\n'
        '      {"step_number": 6, "title": "Physics Conclusion", "description": "1-2 brief sentences summarizing what the simulation demonstrates and proves.", "icon": "💡"}\n'
        '    ],\n'
        '    "tips": ["Tip 1", "Tip 2", "Tip 3"],\n'
        '    "spawn_config": {\n'
        '      "bodies": [\n'
        '        {"id": "b1", "type": "circle", "x": 400, "y": 200, "radius": 25, "isStatic": false, "mass": 2.0, "restitution": 0.8, "fillColor": "0x38bdf8", "label": "Body 1"}\n'
        '      ],\n'
        '      "constraints": [],\n'
        '      "gravityMode": "linear",\n'
        '      "gravityPreset": "earth",\n'
        '      "forces": []\n'
        '    }\n'
        '  }\n'
        "}\n\n"
        "Guidelines:\n"
        "- If the query is completely unrelated to science, mathematics, or education (out of context), politely state in 'explanation' that you specialize in STEM education, set 'is_buildable': false, and leave formulas/concepts empty.\n"
        "- Ensure 'explanation' is rich, detailed, and clear.\n"
        "- Output ONLY valid parseable JSON. Do not prepend or append markdown text outside the JSON object."
    )

    try:
        user_prompt = f"Textbook Context:\n{context}\n\nStudent Query:\n{query}"
        from app.src.services.ai_router import call_ai

        ai_resp = await call_ai(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            history=history,
            temperature=0.2,
            response_format={"type": "json_object"},
            request_id=request_id,
        )
        response_text = ai_resp.get("text", "")
        provider_used = ai_resp.get("provider", "unknown")
        tokens_used = ai_resp.get("tokens_used", 0)

        if not response_text:
            return _empty_tutor_payload(
                "Failed to generate tutor response.",
                error_type="EMPTY_RESPONSE",
                provider=provider_used,
                tokens_used=tokens_used,
            )

        if response_text.startswith("Error:"):
            is_402 = "HTTP 402" in response_text or "BILLING_CREDIT_LIMIT" in response_text or "payment required" in response_text.lower()
            return _empty_tutor_payload(
                response_text,
                error_type="BILLING_CREDIT_LIMIT" if is_402 else "API_ERROR",
                status_code=402 if is_402 else 500,
                provider=provider_used,
                tokens_used=tokens_used,
            )

        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                raw_concepts = parsed.get("concepts", [])
                if isinstance(raw_concepts, list):
                    concepts = [c for c in raw_concepts if isinstance(c, str)]
                else:
                    concepts = []
                related_concepts = _dedupe_related_topics(concepts, max_items=_MAX_RELATED_TOPICS)

                formulas = parsed.get("formulas", [])
                if not isinstance(formulas, list):
                    formulas = []
                first_formula = formulas[0].get("formula", "") if formulas and isinstance(formulas[0], dict) else (formulas[0] if formulas else "")

                explanation = parsed.get("explanation", "")
                if fallback_mode and explanation and "This topic is not available" not in explanation:
                    explanation = (
                        "This topic is not available in the provided textbook context.\n\n"
                        "The following explanation is AI-generated and may not exactly match your textbook.\n\n"
                        + explanation
                    )

                summary = parsed.get("summary", "")
                if not summary:
                    summary = explanation[:250].strip() + "..." if explanation else ""

                sim_guide = parsed.get("simulation_guide", {})
                if not isinstance(sim_guide, dict):
                    sim_guide = {"is_buildable": False}

                return {
                    "title": parsed.get("title", "AI Tutor Response"),
                    "description": query,
                    "formula": first_formula,
                    "related_concepts": related_concepts,
                    "related_formulas": formulas,
                    "ai_explanation": explanation,
                    "sources": [],
                    "queryType": parsed.get("queryType", "concept"),
                    "concepts": related_concepts,
                    "formulas": formulas,
                    "explanation": explanation,
                    "summary": summary,
                    "simulation_guide": sim_guide,
                    "generation_status": "success",
                    "generation_failed": False,
                    "error_type": None,
                    "status_code": 200,
                    "provider": provider_used,
                    "tokens_used": tokens_used,
                }
            except json.JSONDecodeError:
                pass

        return {
            "title": "AI Tutor Response",
            "description": query,
            "formula": "",
            "related_concepts": [],
            "related_formulas": [],
            "ai_explanation": response_text,
            "sources": [],
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": response_text,
            "summary": response_text[:250].strip() + "...",
            "simulation_guide": {"is_buildable": False},
            "generation_status": "success",
            "generation_failed": False,
            "error_type": None,
            "status_code": 200,
            "provider": provider_used,
            "tokens_used": tokens_used,
        }

    except Exception as e:
        logger.error("[Unified Tutor] Error: %s", e)
        return _empty_tutor_payload(f"AI error: {str(e)}", error_type="EXCEPTION")


async def analyze_tutor_query(
    query: str,
    history: list[dict[str, str]] | None = None,
    subject: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    student_profile: dict | None = None,
    request_id: str | None = None,
) -> Dict[str, Any]:
    request_started = time.perf_counter()
    
    # 1. Quick greetings / conversational check (0 LLM requests)
    if is_conversational_query(query):
        greeting_text = (
            "Hello! I am your EduSim AI Tutor, specialized in Science and Mathematics. "
            "I can help explain physics concepts, derive formulas step-by-step, and automatically design "
            "interactive sandbox simulations for you to test and explore! What topic or problem would you like to investigate?"
        )
        return {
            "title": "EduSim AI Tutor",
            "description": query,
            "formula": "",
            "related_concepts": ["Physics", "Mathematics", "Simulation"],
            "related_formulas": [],
            "ai_explanation": greeting_text,
            "sources": [],
            "queryType": "concept",
            "concepts": ["Physics", "Simulation"],
            "formulas": [],
            "explanation": greeting_text,
            "summary": "AI Tutor greeting and session initialization.",
            "ragContent": [],
            "simulation_guide": {"is_buildable": False},
            "generation_status": "success",
            "generation_failed": False,
            "status_code": 200,
        }
    
    dependent_pronouns = re.compile(
        r"\b(it|its|this|that|these|those|they|them|their|theirs)\b", 
        re.IGNORECASE
    )
    has_dependent_pronoun = bool(dependent_pronouns.search(query)) and len(query.split()) < 7
    has_no_history = not history or not any(msg["role"] == "user" for msg in history)
    has_no_context = not topic and not chapter
    
    if has_dependent_pronoun and has_no_history and has_no_context:
        clarification_msg = (
            "I'm not sure which physics concept or formula you are referring to since we don't have "
            "an active topic selected or any conversation history.\n\n"
            "Could you please specify which topic or equation you'd like to explore? "
            "(e.g., Ohm's Law, Newton's Second Law, Simple Pendulum, etc.)"
        )
        return {
            "title": "Clarification Needed",
            "description": query,
            "formula": "",
            "related_concepts": [],
            "related_formulas": [],
            "ai_explanation": clarification_msg,
            "sources": [],
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": clarification_msg,
            "ragContent": [],
            "simulation_guide": {"is_buildable": False},
            "generation_status": "success",
            "generation_failed": False,
            "status_code": 200,
        }

    is_follow_up = history and any(msg["role"] == "user" for msg in history)

    # Lightweight history summarization without extra LLM call
    history_summary = ""
    if history and len(history) > 16:
        user_turns = [msg.get("content", "")[:60] for msg in history[:-6] if isinstance(msg, dict) and msg.get("role") == "user"]
        history_summary = "Earlier discussion: " + ", ".join(user_turns[-3:])
        history = history[-6:]
        
    # Format Student Profile context if provided
    profile_context = ""
    if student_profile:
        profile_context = (
            f"[STUDENT PROFILE]\n"
            f"- Skill Level: {student_profile.get('skill_level', 'beginner')}\n"
            f"- Mastered Topics: {', '.join(student_profile.get('mastered_topics', [])) or 'None'}\n"
            f"- Active Misconceptions: {', '.join(student_profile.get('misconceptions', [])) or 'None'}\n\n"
        )

    # Enrich the RAG search query with history or active topic context
    search_query = query
    resolved_by_history = False
    if history:
        pronoun_pattern = re.compile(
            r"\b(it|its|this|that|these|those|they|them|he|she|him|her|their|theirs|here|there|why|how)\b", 
            re.IGNORECASE
        )
        if pronoun_pattern.search(query):
            context_query = ""
            for msg in reversed(history):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if content and not pronoun_pattern.search(content):
                        context_query = content
                        break
            
            if not context_query:
                for msg in history:
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        content = msg.get("content", "")
                        if content:
                            context_query = content
                            break
                            
            if context_query:
                search_query = f"{context_query} {query}"
                resolved_by_history = True
                
    if not resolved_by_history:
        context_hints = []
        if topic:
            context_hints.append(topic)
        elif chapter:
            context_hints.append(chapter)
            
        if context_hints:
            hints_str = " ".join(context_hints)
            if hints_str.lower() not in query.lower():
                search_query = f"{hints_str} {query}"
            
    # 2. Subject Routing & RAG Retrieval
    target_subject = subject if subject else detect_subject(search_query)
    retriever = get_rag_components(target_subject) if not is_follow_up else None
    
    rag_content = []
    context = ""
    retrieval_start = time.perf_counter()
    
    valid_docs = []
    if retriever:
        docs = retriever(search_query)
        valid_docs = [doc for doc in docs if doc.get('score', 0) > 0.35]
        
    fallback_mode = not bool(valid_docs)
    
    if not fallback_mode:
        for doc in valid_docs[:3]:
            source = os.path.basename(doc.get("source", "Textbook"))
            content = re.sub(r'\s+', ' ', doc.get("text", "")).strip()
            rag_content.append({"title": source, "content": content})
            context += f"{content}\n\n"
            
    retrieval_time = time.perf_counter() - retrieval_start
    logger.info("[RAG] %.2fs (Subject: %s)", retrieval_time, target_subject)
    
    if not context.strip():
        context = "No textbook context available."

    full_context = context
    if history_summary:
        full_context = f"[CONVERSATION MEMORY]\nPreviously: {history_summary}\n\n{full_context}"
    if profile_context:
        full_context = f"{profile_context}{full_context}"

    # 3. Single Unified LLM Execution (At most ONE OpenRouter request)
    llm_start = time.perf_counter()
    unified = await unified_tutor_generation_async(
        query=query,
        context=full_context,
        history=history,
        fallback_mode=fallback_mode,
        request_id=request_id
    )
    llm_time = time.perf_counter() - llm_start
    logger.info("[LLM] %.2fs", llm_time)
    
    total_time = time.perf_counter() - request_started
    logger.info("[TOTAL] %.2fs", total_time)
    
    formulas = unified.get("formulas", [])
    related_concepts = unified.get("related_concepts", [])
    first_formula = unified.get("formula", "")
    explanation_text = unified.get("explanation", "")

    return {
        "title": unified.get("title", "AI Tutor Response"),
        "description": query,
        "formula": first_formula,
        "related_concepts": related_concepts,
        "related_formulas": formulas,
        "ai_explanation": explanation_text,
        "sources": rag_content,
        "queryType": unified.get("queryType", "concept"),
        "concepts": related_concepts,
        "formulas": formulas,
        "explanation": explanation_text,
        "summary": unified.get("summary", ""),
        "ragContent": rag_content,
        "simulation_guide": unified.get("simulation_guide", {"is_buildable": False}),
        "generation_status": unified.get("generation_status", "success"),
        "generation_failed": unified.get("generation_failed", False),
        "error_type": unified.get("error_type"),
        "status_code": unified.get("status_code", 200),
        "provider": unified.get("provider", "unknown"),
        "tokens_used": unified.get("tokens_used", 0),
    }


async def explain_simulation_query(
    query: str,
    history: list[dict[str, str]] | None = None,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """
    Direct, single-LLM explanation for physics sandbox simulation events.
    """
    request_started = time.perf_counter()
    from app.src.modules.legacy_rag.generator import generate_llm_text_async

    prompt = f"""
    You are an expert real-time physics simulation explainer for EduSim.
    A physics event just occurred in the interactive sandbox canvas:
    "{query}"
    
    Provide a concise, scientifically accurate explanation of what physically happened.
    Respond ONLY with a valid JSON object matching:
    {{
        "title": "Short event title (e.g. Inelastic Collision)",
        "explanation": "Clear, informative 1-2 paragraph explanation of the physics dynamics, momentum/energy transitions, and underlying principles.",
        "formula": "Primary relevant formula in LaTeX (e.g. p = m * v or F = -k * x)",
        "concepts": ["Concept 1", "Concept 2"]
    }}
    """
    try:
        raw = await generate_llm_text_async(
            final_prompt=prompt,
            temperature=0.2,
            max_output_tokens=600,
            system_prompt="You are a real-time physics simulation explainer. Respond only in valid JSON.",
            response_format={"type": "json_object"},
            request_id=request_id,
            history=history[-6:] if history else None,
        )

        if not raw or raw.startswith("Error:"):
            msg = raw or "Failed to generate simulation explanation."
            return {
                "title": "Simulation Event",
                "description": query,
                "formula": "",
                "related_concepts": [],
                "related_formulas": [],
                "ai_explanation": msg,
                "sources": [],
                "queryType": "concept",
                "concepts": [],
                "formulas": [],
                "explanation": msg,
                "ragContent": [],
            }

        cleaned = raw.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            exp = parsed.get("explanation", "")
            form = parsed.get("formula", "")
            conc = parsed.get("concepts", [])
            title = parsed.get("title", "Simulation Event")
            return {
                "title": title,
                "description": query,
                "formula": form,
                "related_concepts": conc,
                "related_formulas": [{"formula": form, "name": title, "topic": "Simulation", "meaning": ""}] if form else [],
                "ai_explanation": exp,
                "sources": [],
                "queryType": "concept",
                "concepts": conc,
                "formulas": [{"formula": form, "name": title, "topic": "Simulation", "meaning": ""}] if form else [],
                "explanation": exp,
                "ragContent": [],
            }

        return {
            "title": "Simulation Event",
            "description": query,
            "formula": "",
            "related_concepts": [],
            "related_formulas": [],
            "ai_explanation": raw,
            "sources": [],
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": raw,
            "ragContent": [],
        }
    except Exception as e:
        logger.error("[Explain Sim] Error: %s", e)
        return {
            "title": "Simulation Event",
            "description": query,
            "formula": "",
            "related_concepts": [],
            "related_formulas": [],
            "ai_explanation": f"AI error: {str(e)}",
            "sources": [],
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": f"AI error: {str(e)}",
            "ragContent": [],
        }


async def analyze_tutor_query_stream(
    query: str,
    history: list[dict[str, str]] | None = None,
    subject: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    student_profile: dict | None = None,
    user_id: Any | None = None,
    db_session_factory: Any | None = None
):
    """
    Streaming SSE generator for ultra-fast first token.
    """
    request_started = time.perf_counter()
    
    dependent_pronouns = re.compile(
        r"\b(it|its|this|that|these|those|they|them|their|theirs)\b", 
        re.IGNORECASE
    )
    has_dependent_pronoun = bool(dependent_pronouns.search(query)) and len(query.split()) < 7
    has_no_history = not history or not any(msg["role"] == "user" for msg in history)
    has_no_context = not topic and not chapter
    
    if has_dependent_pronoun and has_no_history and has_no_context:
        clarification_msg = (
            "I'm not sure which physics concept or formula you are referring to since we don't have "
            "an active topic selected or any conversation history.\n\n"
            "Could you please specify which topic or equation you'd like to explore? "
            "(e.g., Ohm's Law, Newton's Second Law, Simple Pendulum, etc.)"
        )
        yield f"data: {json.dumps({'ragContent': []})}\n\n"
        yield f"data: {json.dumps({'content': clarification_msg})}\n\n"
        structured_payload = {
            "title": "Clarification Needed",
            "description": query,
            "formula": "",
            "related_concepts": [],
            "related_formulas": [],
            "ai_explanation": clarification_msg,
            "sources": [],
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "explanation": clarification_msg,
            "ragContent": [],
        }
        yield f"data: {json.dumps({'structured': structured_payload})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Subject relevance guard rail check
    is_follow_up = history and any(msg["role"] == "user" for msg in history)
    is_change = is_topic_change(query, history) if is_follow_up else True
    
    if is_change:
        relevance = await check_query_subject_relevance(query)
        if relevance == "out_of_context":
            refusal_msg = (
                "I am your AI Tutor, designed to help you with school subjects like Physics, Chemistry, Biology, and Mathematics. "
                "I cannot assist with out-of-context queries. Please feel free to ask any academic questions!"
            )
            yield f"data: {json.dumps({'ragContent': []})}\n\n"
            yield f"data: {json.dumps({'content': refusal_msg})}\n\n"
            structured_payload = {
                "title": "Out of Context",
                "description": query,
                "formula": "",
                "related_concepts": [],
                "related_formulas": [],
                "ai_explanation": refusal_msg,
                "sources": [],
                "queryType": "concept",
                "concepts": [],
                "formulas": [],
                "explanation": refusal_msg,
                "ragContent": [],
                "simulation_guide": {"is_buildable": False},
            }
            yield f"data: {json.dumps({'structured': structured_payload})}\n\n"
            yield "data: [DONE]\n\n"
            return

    # Dynamic History Summarization (zero extra LLM calls)
    history_summary = ""
    if history and len(history) > 16:
        user_turns = [msg.get("content", "")[:60] for msg in history[:-6] if isinstance(msg, dict) and msg.get("role") == "user"]
        history_summary = "Earlier discussion: " + ", ".join(user_turns[-3:])
        history = history[-6:]
        
    # Format Student Profile context if provided
    profile_context = ""
    if student_profile:
        profile_context = (
            f"[STUDENT PROFILE]\n"
            f"- Skill Level: {student_profile.get('skill_level', 'beginner')}\n"
            f"- Mastered Topics: {', '.join(student_profile.get('mastered_topics', [])) or 'None'}\n"
            f"- Active Misconceptions: {', '.join(student_profile.get('misconceptions', [])) or 'None'}\n\n"
        )

    # Enrich the RAG search query with history or active topic context
    search_query = query
    resolved_by_history = False
    if history:
        pronoun_pattern = re.compile(
            r"\b(it|its|this|that|these|those|they|them|he|she|him|her|their|theirs|here|there|why|how)\b", 
            re.IGNORECASE
        )
        if pronoun_pattern.search(query):
            last_user_msg = next((msg["content"] for msg in reversed(history) if msg["role"] == "user"), "")
            if last_user_msg:
                search_query = f"{last_user_msg} {query}"
                resolved_by_history = True
                
    if not resolved_by_history:
        context_hints = []
        if topic:
            context_hints.append(topic)
        elif chapter:
            context_hints.append(chapter)
            
        if context_hints:
            hints_str = " ".join(context_hints)
            if hints_str.lower() not in query.lower():
                search_query = f"{hints_str} {query}"
            
    target_subject = subject if subject else detect_subject(search_query)
    retriever = get_rag_components(target_subject) if not is_follow_up else None
    
    rag_content = []
    context = ""
    valid_docs = []
    
    if retriever:
        docs = retriever(search_query)
        valid_docs = [doc for doc in docs if doc.get('score', 0) > 0.35]
        
    fallback_mode = not bool(valid_docs)
    
    if not fallback_mode:
        for doc in valid_docs[:3]: # Optimized to 3
            source = os.path.basename(doc.get("source", "Textbook"))
            content = re.sub(r'\s+', ' ', doc.get("text", "")).strip()
            rag_content.append({"title": source, "content": content})
            context += f"{content}\n\n"
            
    if not context.strip():
        context = "No textbook context available."

    # Yield RAG Content immediately
    yield f"data: {json.dumps({'ragContent': rag_content})}\n\n"
    
    if fallback_mode:
        warning_msg = (
            "This topic is not available in the provided textbook context.\n\n"
            "The following explanation is AI-generated and may not exactly match your textbook.\n\n"
        )
        yield f"data: {json.dumps({'content': warning_msg})}\n\n"
    
    # Build full context by prepending memory and profile state
    full_context = context
    if history_summary:
        full_context = f"[CONVERSATION MEMORY]\nPreviously: {history_summary}\n\n{full_context}"
    if profile_context:
        full_context = f"{profile_context}{full_context}"

    is_follow_up = history and any(msg["role"] == "user" for msg in history)
    run_simulation_gen = not is_follow_up or needs_simulation_generation(query)

    # Start structured task if needed
    structured_task = None
    if run_simulation_gen:
        structured_task = asyncio.create_task(analyze_with_llm_async(query, full_context, history=history))
    
    # Stream explanation text
    from app.src.modules.legacy_rag.generator import generate_llm_stream_async, get_tutor_prompt, NEW_RENDERING_SYSTEM
    prompt = get_tutor_prompt(full_context, query, fallback_mode)
    
    sys_prompt = NEW_RENDERING_SYSTEM
    if is_follow_up:
        sys_prompt = "You are a helpful science and math tutor answering a student's follow-up question in a chat bubble. Keep your explanation clear, pedagogically sound, and friendly. Support markdown formatting and LaTeX equations using standard formatting."
    
    accumulated_text = ""
    async for chunk in generate_llm_stream_async(prompt, history=history, system_prompt=sys_prompt):
        if chunk.startswith("data: "):
            data_str = chunk[6:]
            try:
                data = json.loads(data_str)
                content = data.get("content", "")
                if content:
                    accumulated_text += content
            except Exception:
                pass
        yield chunk
        
    # Wait for structured data to finish
    if structured_task:
        structured = await structured_task
    else:
        structured = {
            "title": "AI Tutor Response",
            "queryType": "concept",
            "concepts": [],
            "formulas": [],
            "simulation_guide": {"is_buildable": False}
        }
    yield f"data: {json.dumps({'structured': structured})}\n\n"
    
    # Trigger background profile update task if parameters are supplied
    if user_id and db_session_factory and accumulated_text:
        asyncio.create_task(
            analyze_and_update_profile_task(
                db_session_factory,
                user_id,
                query,
                accumulated_text
            )
        )

    yield "data: [DONE]\n\n"


# --- Comprehensive Curriculum Search System ---

_TYPE_PRIORITY = {"topic": 0, "chapter": 1, "subject": 2, "class": 3}

_MAX_RELATED_TOPICS = 4

_SUBSCRIPT_TRANSLATION = str.maketrans({
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
})

_FORMULA_TOPIC_MAP: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:f=ma|ma=f|fma|maf)$", re.IGNORECASE), "Newton's Second Law"),
    (re.compile(r"^(?:v=ir|i=v/r)$", re.IGNORECASE), "Ohm's Law"),
    (re.compile(r"^(?:n1sin\(?i\)?=n2sin\(?r\)?|n1sin\(?theta1\)?=n2sin\(?theta2\)?)$", re.IGNORECASE), "Snell's Law"),
    (re.compile(r"^(?:ke=1/2mv\^2|ke=0?\.5mv\^2|1/2mv\^2)$", re.IGNORECASE), "Kinetic Energy"),
    (re.compile(r"^(?:p=mv)$", re.IGNORECASE), "Momentum"),
    (re.compile(r"^(?:f=mg)$", re.IGNORECASE), "Weight"),
    (re.compile(r"^(?:j=fdt|j=fdelta t)$", re.IGNORECASE), "Impulse"),
    (re.compile(r"^(?:ff=mun|f=mun)$", re.IGNORECASE), "Friction"),
    (re.compile(r"^(?:t=2pisqrt\(?l/g\)?|t=2pisqrtl/g)$", re.IGNORECASE), "Simple Pendulum"),
    (re.compile(r"^(?:r=v\^2sin\(?2theta\)?/g)$", re.IGNORECASE), "Projectile Motion"),
    (re.compile(r"^(?:fc=mv\^2/r)$", re.IGNORECASE), "Centripetal Force"),
    (re.compile(r"^(?:fb=rhogv)$", re.IGNORECASE), "Buoyancy"),
    (re.compile(r"^(?:f=kq1q2/r\^2|f=kq_?1q_?2/r\^2)$", re.IGNORECASE), "Coulomb's Law"),
    (re.compile(r"^(?:ke\+pe=constant)$", re.IGNORECASE), "Conservation of Energy"),
    (re.compile(r"^(?:tau=rfsin\(?theta\)?|t=rfsin\(?theta\)?)$", re.IGNORECASE), "Torque"),
    (re.compile(r"^(?:h'?=n\*?h)$", re.IGNORECASE), "Magnification"),
]


def _strip_latex_markup(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(_SUBSCRIPT_TRANSLATION)
    text = text.replace("×", "*").replace("·", "*").replace("÷", "/")
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = text.replace("′", "'").replace("″", '"')
    text = text.replace("$", " ")
    text = re.sub(r"\\(?:left|right|,|;|!|quad|qquad)", " ", text)
    text = re.sub(r"\\([a-zA-Z]+)", r"\1", text)
    text = re.sub(r"[{}]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_related_topic_key(value: Any) -> str:
    text = _strip_latex_markup(value).lower()
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _smart_title_case(text: str) -> str:
    parts = re.split(r"(\s+|[-/])", text.strip())
    normalized_parts: List[str] = []

    for part in parts:
        if not part:
            continue
        if part.isspace() or part in {"-", "/"}:
            normalized_parts.append(part)
            continue

        sub_parts = part.split("'")
        head = sub_parts[0]
        if head:
            head = head[:1].upper() + head[1:].lower()
        rebuilt = [head]
        for tail in sub_parts[1:]:
            rebuilt.append(tail.lower())
        normalized_parts.append("'".join(rebuilt))

    return "".join(normalized_parts).strip()


def _normalize_formula_signature(value: Any) -> str:
    text = _strip_latex_markup(value).lower()
    text = text.replace(" ", "")
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("\u200b", "")
    return text


def _map_formula_to_concept(value: Any) -> Optional[str]:
    signature = _normalize_formula_signature(value)
    if not signature:
        return None

    for pattern, concept in _FORMULA_TOPIC_MAP:
        if pattern.search(signature):
            return concept

    return None


def _looks_like_formula_topic(value: Any) -> bool:
    signature = _normalize_formula_signature(value)
    if not signature:
        return False

    if _map_formula_to_concept(value):
        return True

    if re.fullmatch(r"[a-z]", signature):
        return True

    if re.fullmatch(r"\d+(?:\.\d+)?", signature):
        return True

    if re.search(r"[=+\-*/^<>≤≥≈∑∫√]", signature):
        return True

    if re.search(r"\d", signature) and len(signature) <= 12:
        return True

    if re.search(r"\\|_|\$", str(value or "")):
        return True

    return False


def _clean_related_topic(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = _strip_latex_markup(value)
    if not text:
        return None

    text = re.sub(r"^(?:explain|define|what\s+is|meaning\s+of)\s+", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return None

    concept = _map_formula_to_concept(text)
    if concept:
        return concept

    if _looks_like_formula_topic(text):
        return None

    if re.search(r"[=\\$_{}^]", text):
        return None

    if re.search(r"\d", text):
        return None

    text = re.sub(r"\s+", " ", text).strip(" -–—:;.,")
    if not text:
        return None

    # Reject variable-level, symbol-level, and unit-level fragments.
    if re.fullmatch(r"[A-Za-z]", text):
        return None

    if re.fullmatch(r"[Ω°%]+", text):
        return None

    if re.fullmatch(r"\d+(?:\.\d+)?(?:\s?[A-Za-zΩ/%²³]+)?", text):
        return None

    if re.fullmatch(r"(?:kg|m/s\^?2|m/s|m|s|N|J|Pa|mol|A|V|Ω|ohm|volt|ampere)", text, flags=re.IGNORECASE):
        return None

    single_word_concepts = {
        "current",
        "voltage",
        "resistance",
        "force",
        "mass",
        "acceleration",
        "momentum",
        "inertia",
        "energy",
        "power",
        "pressure",
        "density",
        "temperature",
        "velocity",
        "speed",
        "charge",
        "circuit",
        "circuits",
        "conductors",
        "insulators",
        "gravity",
        "friction",
        "impulse",
        "torque",
        "buoyancy",
        "refraction",
        "reflection",
        "optics",
        "electricity",
        "wavelength",
        "frequency",
    }

    if len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)) < 2 and text.lower() not in single_word_concepts:
        return None

    return _smart_title_case(text)


def _dedupe_related_topics(items: Any, max_items: int = _MAX_RELATED_TOPICS) -> List[str]:
    cleaned: List[str] = []
    seen = set()

    if not isinstance(items, list):
        return cleaned

    for item in items:
        topic = _clean_related_topic(item)
        if not topic:
            continue
        key = _normalize_related_topic_key(topic)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(topic)
        if len(cleaned) >= max_items:
            break

    return cleaned


_QUERY_HINTS = {
    "ele": ["electric", "electro", "electromag", "current", "charge", "voltage", "resistance"],
    "newton": ["newton", "laws of motion", "force", "acceleration"],
    "grav": ["gravitation", "gravity", "centre of gravity"],
    "proj": ["projectile", "projectiles", "projectile motion"],
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _format_class_name(value: Any) -> str:
    text = str(value).strip()
    if text.lower().startswith("class "):
        return text[:6].capitalize() + text[6:]
    return f"Class {text}"


# TODO: [Curriculum V2 Migration] Migrate tutor autocomplete and topic content from static curriculum.json to books and curriculum_nodes (V2)
def _load_curriculum() -> Dict[str, Any]:
    """Load curriculum data from the generated JSON file."""
    global _curriculum_data
    if _curriculum_data is not None:
        return _curriculum_data

    curriculum_path = Path(__file__).resolve().parents[2] / "data" / "curriculum.json"
    try:
        with open(curriculum_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict) and "classes" in loaded:
            _curriculum_data = loaded
        else:
            _curriculum_data = {"classes": []}
    except Exception as e:
        logger.error("Failed to load curriculum: %s", e)
        _curriculum_data = {"classes": []}
    return _curriculum_data


def _iter_class_records() -> List[Dict[str, Any]]:
    data = _load_curriculum()
    classes = data.get("classes", []) if isinstance(data, dict) else []
    if not isinstance(classes, list):
        return []
    return classes


def _flatten_curriculum() -> List[Dict[str, Any]]:
    """Flatten the nested curriculum into searchable records."""
    entries: List[Dict[str, Any]] = []
    seen = set()

    for class_record in _iter_class_records():
        class_name = _format_class_name(class_record.get("name", ""))
        class_id = class_record.get("id")
        class_description = class_record.get("description", "")
        subjects = class_record.get("subjects", []) or []

        class_search_parts = [class_name, class_description]
        for subject in subjects:
            class_search_parts.extend([
                subject.get("name", ""),
                subject.get("description", ""),
            ])
            chapters = subject.get("chapters", []) or []
            if isinstance(chapters, list):
                for chapter in chapters:
                    chapter_name = chapter.get("name", "")
                    class_search_parts.append(chapter_name)
                    topics = chapter.get("topics", []) or []
                    for topic in topics:
                        class_search_parts.append(topic.get("name", ""))

        class_key = ("class", class_name)
        if class_key not in seen:
            seen.add(class_key)
            entries.append(
                {
                    "type": "class",
                    "class_id": class_id,
                    "class_name": class_name,
                    "subject": None,
                    "chapter": None,
                    "topic": None,
                    "search_text": _normalize_text(" ".join(class_search_parts)),
                    "display": class_name,
                }
            )

        for subject in subjects:
            subject_name = subject.get("name", "")
            subject_id = subject.get("id", "")
            subject_description = subject.get("description", "")
            chapters = subject.get("chapters", []) or []

            subject_search_parts = [
                class_name,
                subject_name,
                subject_id,
                subject_description,
            ]

            if isinstance(chapters, list):
                chapter_names = [chapter.get("name", "") for chapter in chapters]
                subject_search_parts.extend(chapter_names)
            else:
                subject_search_parts.append(str(chapters))

            subject_key = ("subject", class_name, subject_name)
            if subject_key not in seen:
                seen.add(subject_key)
                entries.append(
                    {
                        "type": "subject",
                        "class_id": class_id,
                        "class_name": class_name,
                        "subject_id": subject_id,
                        "subject": subject_name,
                        "chapter": None,
                        "topic": None,
                        "search_text": _normalize_text(" ".join(subject_search_parts)),
                        "display": f"{subject_name} • {class_name}",
                    }
                )

            if not isinstance(chapters, list):
                continue

            for chapter in chapters:
                chapter_name = chapter.get("name", "")
                topics = chapter.get("topics", []) or []
                chapter_search_parts = [
                    class_name,
                    subject_name,
                    chapter_name,
                ]
                chapter_search_parts.extend(topic.get("name", "") for topic in topics)

                chapter_key = ("chapter", class_name, subject_name, chapter_name)
                if chapter_key not in seen:
                    seen.add(chapter_key)
                    entries.append(
                        {
                            "type": "chapter",
                            "class_id": class_id,
                            "class_name": class_name,
                            "subject_id": subject_id,
                            "subject": subject_name,
                            "chapter": chapter_name,
                            "topic": None,
                            "topics": [topic.get("name", "") for topic in topics],
                            "search_text": _normalize_text(" ".join(chapter_search_parts)),
                            "display": f"{subject_name} • {class_name}\n{chapter_name}",
                        }
                    )

                for topic in topics:
                    topic_name = topic.get("name", "")
                    topic_key = ("topic", class_name, subject_name, chapter_name, topic_name)
                    if topic_key in seen:
                        continue
                    seen.add(topic_key)
                    entries.append(
                        {
                            "type": "topic",
                            "class_id": class_id,
                            "class_name": class_name,
                            "subject_id": subject_id,
                            "subject": subject_name,
                            "chapter": chapter_name,
                            "topic": topic_name,
                            "search_text": _normalize_text(
                                f"{class_name} {subject_name} {chapter_name} {topic_name}"
                            ),
                            "display": f"{subject_name} • {class_name}\n{chapter_name} → {topic_name}",
                        }
                    )

    return entries


def _build_curriculum_index() -> List[Dict[str, Any]]:
    global _curriculum_index
    if _curriculum_index is None:
        _curriculum_index = _flatten_curriculum()
    return _curriculum_index


def _score_value(query: str, value: str, exact_score: int, prefix_score: int, substring_score: int, fuzzy_score: int) -> float:
    if not value:
        return 0.0

    q = _normalize_text(query)
    v = _normalize_text(value)
    if not q or not v:
        return 0.0

    if q == v:
        return float(exact_score)
    if v.startswith(q):
        return float(prefix_score + min(len(q) / max(len(v), 1), 1.0) * 25)
    if q in v:
        return float(substring_score + min(len(q) / max(len(v), 1), 1.0) * 25)

    if len(q) < 4:
        return 0.0

    ratio = difflib.SequenceMatcher(None, q, v).ratio()
    if ratio >= 0.6:
        return float(fuzzy_score + ratio * 50)
    return 0.0


def _score_match(query: str, entry: Dict[str, Any]) -> Tuple[float, int]:
    q = _normalize_text(query)
    if not q:
        return (0.0, 999)

    score = 0.0
    search_text = entry.get("search_text", "")
    if entry.get("type") == "topic":
        score = max(
            _score_value(q, entry.get("topic", ""), 1200, 1100, 1000, 850),
            _score_value(q, entry.get("chapter", ""), 900, 850, 760, 650),
            _score_value(q, entry.get("subject", ""), 750, 700, 650, 550),
            _score_value(q, entry.get("class_name", ""), 600, 550, 500, 450),
        )
    elif entry.get("type") == "chapter":
        score = max(
            _score_value(q, entry.get("chapter", ""), 1100, 1000, 920, 760),
            _score_value(q, entry.get("subject", ""), 800, 760, 700, 580),
            _score_value(q, entry.get("class_name", ""), 650, 600, 540, 460),
        )
    elif entry.get("type") == "subject":
        score = max(
            _score_value(q, entry.get("subject", ""), 1000, 920, 860, 720),
            _score_value(q, entry.get("class_name", ""), 700, 650, 600, 500),
        )
    else:
        score = max(
            _score_value(q, entry.get("class_name", ""), 900, 840, 780, 650),
            _score_value(q, search_text, 500, 460, 420, 350),
        )

    for hint_key, hint_terms in _QUERY_HINTS.items():
        if q.startswith(hint_key):
            if any(term in search_text for term in hint_terms):
                score += 220
            break

    if score <= 0:
        return (0.0, 999)

    return (score, _TYPE_PRIORITY.get(entry.get("type", "class"), 999))


def search_curriculum(query: str, max_results: int = 30) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    scored_results: List[Tuple[float, int, Dict[str, Any]]] = []
    for entry in _build_curriculum_index():
        score, type_rank = _score_match(q, entry)
        if score > 0:
            scored_results.append((score, type_rank, entry))

    scored_results.sort(key=lambda item: (-item[0], item[1], item[2].get("display", "")))

    results = []
    seen = set()
    for score, _, entry in scored_results:
        key = (
            entry.get("type"),
            entry.get("class_name"),
            entry.get("subject"),
            entry.get("chapter"),
            entry.get("topic"),
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(entry)
        if len(results) >= max_results:
            break
    return results


def autocomplete_curriculum(query: str, max_suggestions: int = _MAX_RELATED_TOPICS) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(max_suggestions, _MAX_RELATED_TOPICS))
    ranked = search_curriculum(q, max_results=limit * 3)
    suggestions: List[Dict[str, Any]] = []
    seen = set()

    for entry in ranked:
        topic_value = entry.get("topic")
        if entry.get("type") == "topic":
            cleaned_topic = _clean_related_topic(topic_value)
            if not cleaned_topic:
                continue
            topic_value = cleaned_topic

        key = (
            entry.get("type"),
            entry.get("class_name"),
            entry.get("subject"),
            entry.get("chapter"),
            topic_value,
        )
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "type": entry.get("type"),
                "class_name": entry.get("class_name"),
                "subject": entry.get("subject"),
                "chapter": entry.get("chapter"),
                "topic": topic_value,
                "display": entry.get("display"),
                "priority": _TYPE_PRIORITY.get(entry.get("type", "class"), 999),
            }
        )
        if len(suggestions) >= limit:
            break

    return suggestions


def get_topic_content(subject: str, class_name: str, chapter: str, topic: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve curriculum content for a selected class/subject/chapter/topic."""
    data = _load_curriculum()
    classes = data.get("classes", []) if isinstance(data, dict) else []

    class_record = None
    for candidate in classes:
        if _normalize_text(candidate.get("name", "")) == _normalize_text(class_name):
            class_record = candidate
            break

    if not class_record:
        return {"error": "class_not_found"}

    subject_record = None
    for candidate in class_record.get("subjects", []) or []:
        candidate_name = candidate.get("name", "")
        candidate_id = candidate.get("id", "")
        if _normalize_text(candidate_name) == _normalize_text(subject) or _normalize_text(candidate_id) == _normalize_text(subject):
            subject_record = candidate
            break

    if not subject_record:
        return {"error": "subject_not_found"}

    chapters = subject_record.get("chapters", []) or []
    chapter_record = None
    if isinstance(chapters, list):
        for candidate in chapters:
            if _normalize_text(candidate.get("name", "")) == _normalize_text(chapter):
                chapter_record = candidate
                break

    if not chapter_record:
        return {"error": "chapter_not_found"}

    raw_topic_list = [item.get("name", "") for item in chapter_record.get("topics", []) or []]
    topic_list = _dedupe_related_topics(raw_topic_list, max_items=_MAX_RELATED_TOPICS)
    matched_topic = topic
    if topic:
        matched_topic = None
        for candidate in raw_topic_list:
            if _normalize_text(candidate) == _normalize_text(topic):
                matched_topic = candidate
                break
        if not matched_topic:
            return {"error": "topic_not_found"}

    response: Dict[str, Any] = {
        "class_name": class_record.get("name", class_name),
        "subject": subject_record.get("name", subject),
        "chapter": chapter_record.get("name", chapter),
        "topic": matched_topic or "",
        "outcomes": chapter_record.get("outcomes", []) or [],
        "prerequisites": chapter_record.get("prerequisites", []) or [],
        "topics": topic_list,
        "ai_explanation": "",
        "related_concepts": topic_list,
        "related_formulas": [],
        "textbook_content": {
            "outcomes": chapter_record.get("outcomes", []) or [],
            "prerequisites": chapter_record.get("prerequisites", []) or [],
            "topics": topic_list,
        },
        "simulation_prompt": None,
    }

    if matched_topic:
        try:
            sims_path = Path(__file__).resolve().parents[4] / "data" / "generated_simulations.json"
            if sims_path.exists():
                with open(sims_path, "r", encoding="utf-8") as f:
                    sims = json.load(f)
                for sim in sims:
                    sim_topic = sim.get("topic") or {}
                    sim_topic_name = sim_topic.get("topic") if isinstance(sim_topic, dict) else None
                    if sim_topic_name and _normalize_text(sim_topic_name) == _normalize_text(matched_topic):
                        response["simulation_prompt"] = sim.get("description") or sim.get("dsl")
                        response["stored_simulation"] = sim
                        break
        except Exception:
            pass

    return response


async def generate_tutor_guide(query: str) -> Dict[str, Any]:
    # 1. Subject Routing & RAG Retrieval
    subject = detect_subject(query)
    retriever = get_rag_components(subject)
    
    context = ""
    valid_docs = []
    if retriever:
        docs = retriever(query)
        valid_docs = [doc for doc in docs if doc.get('score', 0) > 0.35]
        
    fallback_mode = not bool(valid_docs)
    
    if not fallback_mode:
        for doc in valid_docs[:3]:
            content = re.sub(r'\s+', ' ', doc.get("text", "")).strip()
            if len(content) > 400: content = content[:400] + "..."
            context += f"{content}\n\n"
            
    if not context.strip():
        context = "No textbook context available."

    # Call only the structured analyzer to get simulation_guide
    structured = await analyze_with_llm_async(query, context)
    return {
        "title": structured.get("title", "Simulation Guide"),
        "simulation_guide": structured.get("simulation_guide", {"is_buildable": False}),
    }

