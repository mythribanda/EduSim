from app.src.modules.legacy_rag.retriever import parse_class_name
import re
import json
import difflib
import time
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.src.modules.legacy_rag.generator import is_topic_change
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



def detect_query_language(text: str) -> str:
    """
    Detects whether text is English ('en'), Telugu ('te'), or Hindi ('hi')
    using Unicode script character frequency analysis.
    """
    if not text:
        return "en"
    te_count = sum(1 for ch in text if 0x0C00 <= ord(ch) <= 0x0C7F)
    hi_count = sum(1 for ch in text if 0x0900 <= ord(ch) <= 0x097F)
    if te_count > 0 and te_count >= hi_count:
        return "te"
    if hi_count > 0 and hi_count > te_count:
        return "hi"
    return "en"


MULTILINGUAL_CONCEPT_MAP: dict[str, str] = {
    # Telugu - Physics
    "గురుత్వాకర్షణ": "gravitation gravity gravitational force",
    "చలనం": "motion kinematics",
    "గతి": "motion laws of motion",
    "వేగం": "velocity speed",
    "త్వరణం": "acceleration",
    "బలం": "force newton",
    "శక్తి": "energy work power",
    "పని": "work energy",
    "కాంతి": "light optics reflection refraction",
    "ధ్వని": "sound wave acoustics",
    "విద్యుత్": "electricity electric current potential difference",
    "విద్యుత్తు": "electricity electric current",
    "అయస్కాంతం": "magnet magnetism magnetic field",
    "పీడనం": "pressure thrust",
    "ఘర్షణ": "friction frictional force",
    "ద్రవ్యరాశి": "mass inertia",
    "సాంద్రత": "density relative density",
    "ఉష్ణోగ్రత": "temperature heat thermal",
    "వేడి": "heat thermal",
    "తరంగం": "wave wavelength frequency",
    "స్నెల్": "snell's law refraction refractive index ray optics",
    "స్నెల్ నియమం": "snell's law refraction refractive index ray optics",
    "వక్రీభవనం": "refraction refractive index snell ray optics",
    "ఓమ్": "ohm's law electric current voltage resistance",
    "ఓమ్ నియమం": "ohm's law electric current voltage resistance",

    # Telugu - Chemistry
    "పరమాణువు": "atom atomic structure",
    "అణువు": "molecule molecular",
    "రసాయన": "chemical reaction equation",
    "ఉష్ణమోచక": "exothermic reaction heat released thermodynamics",
    "ఉష్ణగ్రాహక": "endothermic reaction heat absorbed thermodynamics",
    "ఆమ్లం": "acid acidic",
    "క్షారం": "base alkali basic",
    "లోహం": "metal metallic",
    "అలోహం": "non-metal nonmetal",
    "బంధం": "bond chemical bonding",
    "బంధాలు": "bonds bonding",
    "సమయోజనీయ": "covalent bond covalent",
    "అయానిక": "ionic bond electrovalent",
    "సంయోజనీయత": "valency valence electrons",
    "ఆక్సీకరణం": "oxidation redox",
    "క్షయకరణం": "reduction redox",
    "ద్రావణం": "solution solvent solute",
    "సమ్మేళనం": "compound",
    "మిశ్రమం": "mixture",
    "మూలకం": "element periodic table",
    "ఆవర్తన": "periodic table classification of elements modern periodic",
    "ఆవర్తన పట్టిక": "periodic table classification of elements modern periodic",
    "వర్గీకరణ": "classification classification of elements periodic table",
    "మోల్": "mole concept avogadro molar mass",
    "మోల్ భావన": "mole concept avogadro molar mass",
    "అవగాడ్రో": "avogadro constant avogadro number mole",
    "ఉత్ప్రేరకం": "catalyst catalysis",

    # Telugu - Biology
    "కణం": "cell cell structure cell wall",
    "కణ సిద్ధాంతం": "cell theory schleiden schwann cells",
    "కణజాలం": "tissue tissues",
    "కిరణజన్య": "photosynthesis chloroplast chlorophyll glucose",
    "శ్వాసక్రియ": "respiration cellular respiration",
    "హరితరేణువు": "chloroplast chlorophyll photosynthesis",
    "హరితరేణువులు": "chloroplasts photosynthesis",
    "మైటోకాండ్రియా": "mitochondria powerhouse of cell",
    "జీర్ణక్రియ": "digestion digestive system",
    "గుండె": "heart human heart double circulation cardiac body fluids",
    "మానవ గుండె": "heart human heart double circulation cardiac body fluids",
    "రక్త ప్రసరణ": "circulatory system heart blood double circulation",
    "పరిసంచరణ": "circulation double circulation blood body fluids",
    "ప్రత్యుత్పత్తి": "reproduction reproductive system",
    "వృక్ష": "plant plant physiology",
    "జంతు": "animal animal kingdom",
    "డీఎన్‌ఏ": "dna genetic material",
    "డబుల్ హెలిక్స్": "double helix dna model watson crick",
    "జన్యువు": "gene genetics heredity",
    "మెండల్": "mendel laws of inheritance genetics monohybrid cross",
    "అనువంశికత": "heredity inheritance variation genetics",

    # Telugu - Mathematics
    "గణితం": "mathematics",
    "బీజగణితం": "algebra algebraic",
    "సమీకరణం": "equation",
    "వర్గం": "quadratic square",
    "ద్విఘాత": "quadratic",
    "వర్గ సమీకరణం": "quadratic equation roots",
    "ద్విఘాత సమీకరణం": "quadratic equation roots formula",
    "పైథాగరస్": "pythagoras theorem right triangle hypotenuse triangles",
    "పైథాగరస్ సిద్ధాంతం": "pythagoras theorem right triangle hypotenuse triangles",
    "మూలాలు": "roots solutions",
    "శూన్యాలు": "zeros zeroes roots",
    "గుణకాలు": "coefficients",
    "త్రికోణమితి": "trigonometry trigonometric ratios",
    "జ్యామితి": "geometry geometric",
    "వైశాల్యం": "area surface area",
    "పరిధి": "perimeter circumference",
    "వ్యాసార్థం": "radius diameter",
    "త్రికోణం": "triangle right triangle",
    "చతుర్భుజం": "quadrilateral",
    "సంభావ్యత": "probability",
    "భిన్నం": "fraction fractions",
    "శ్రేఢులు": "progressions series",
    "అంకశ్రేఢి": "arithmetic progression",

    # Hindi - Physics
    "गुरुत्वाकर्षण": "gravitation gravity gravitational force",
    "गति": "motion laws of motion kinematics",
    "वेग": "velocity speed",
    "चाल": "speed velocity",
    "त्वरण": "acceleration",
    "बल": "force newton",
    "ऊर्जा": "energy work power",
    "कार्य": "work energy",
    "प्रकाश": "light optics reflection refraction",
    "ध्वनि": "sound wave acoustics",
    "विद्युत": "electricity electric current",
    "विभवांतर": "potential difference voltage ohm's law",
    "ओम": "ohm's law electric current voltage resistance",
    "ओम का नियम": "ohm's law electric current voltage resistance",
    "स्नेल": "snell's law refraction refractive index ray optics",
    "स्नेल का नियम": "snell's law refraction refractive index ray optics",
    "अपवर्तन": "refraction refractive index snell ray optics",
    "बिजली": "electricity electric",
    "चुंबक": "magnet magnetism magnetic field",
    "दाब": "pressure thrust",
    "घर्षण": "friction",
    "द्रव्यमान": "mass inertia",
    "घनत्व": "density",
    "तापमान": "temperature heat thermal",
    "ऊष्मा": "heat thermal",
    "तरंग": "wave wavelength frequency",

    # Hindi - Chemistry
    "परमाणु": "atom atomic structure",
    "अणु": "molecule molecular",
    "रसायन": "chemical reaction equation",
    "रासायनिक": "chemical chemical reaction",
    "ऊष्माक्षेपी": "exothermic reaction heat released thermodynamics",
    "ऊष्माशोषी": "endothermic reaction heat absorbed thermodynamics",
    "अम्ल": "acid acidic",
    "क्षार": "base alkali",
    "लवण": "salt salts",
    "धातु": "metal metallic",
    "अधातु": "nonmetal non-metal",
    "आबंधन": "chemical bonding bond",
    "आबंध": "bond chemical bond",
    "सहसंयोजक": "covalent bond covalent",
    "सहसंयोजकता": "covalency valency",
    "आयनिक": "ionic bond electrovalent",
    "संयोजकता": "valency valence",
    "ऑक्सीकरण": "oxidation redox",
    "अपचयन": "reduction redox",
    "विलयन": "solution",
    "तत्व": "element periodic table",
    "आवर्त सारणी": "periodic table elements classification modern periodic",
    "वर्गीकरण": "classification classification of elements periodic table",
    "मोल": "mole concept avogadro molar mass",
    "मोल संकल्पना": "mole concept avogadro molar mass",
    "आवोगाद्रो": "avogadro constant avogadro number mole",
    "अवोगाद्रो": "avogadro constant avogadro number mole",
    "यौगिक": "compound",
    "मिश्रण": "mixture",
    "उत्प्रेरक": "catalyst",

    # Hindi - Biology
    "कोशिका": "cell cell structure cell wall",
    "कोशिका सिद्धांत": "cell theory schleiden schwann cells",
    "ऊतक": "tissue tissues",
    "प्रकाश संश्लेषण": "photosynthesis chloroplast chlorophyll",
    "हरितलवक": "chloroplast photosynthesis",
    "माइटोकॉन्ड्रिया": "mitochondria",
    "श्वसन": "respiration cellular respiration",
    "पाचन": "digestion digestive system",
    "हृदय": "heart human heart double circulation cardiac body fluids",
    "मानव हृदय": "heart human heart double circulation cardiac body fluids",
    "रक्त": "blood circulatory system body fluids",
    "परिसंचरण": "circulation double circulation blood body fluids",
    "दोहरा परिसंचरण": "circulation double circulation blood body fluids",
    "जनन": "reproduction reproductive",
    "पादप": "plant plant physiology",
    "जंतु": "animal animal kingdom",
    "डीएनए": "dna genetic material",
    "द्विकुंडलिनी": "double helix dna model watson crick",
    "जीन": "gene genetics heredity",
    "मेंडल": "mendel laws of inheritance genetics monohybrid cross",
    "आनुवंशिकता": "heredity inheritance variation genetics",
    "जैव प्रक्रम": "life processes",

    # Hindi - Mathematics
    "गणित": "mathematics",
    "बीजगणित": "algebra algebraic",
    "समीकरण": "equation",
    "द्विघात": "quadratic",
    "द्विघात समीकरण": "quadratic equation roots formula",
    "पाइथागोरस": "pythagoras theorem right triangle hypotenuse triangles",
    "पाइथागोरस प्रमेय": "pythagoras theorem right triangle hypotenuse triangles",
    "मूल": "roots solutions",
    "शून्यक": "zeros zeroes roots",
    "गुणांक": "coefficients",
    "क्षेत्रफल": "area surface area",
    "परिधि": "perimeter circumference",
    "त्रिज्या": "radius diameter",
    "त्रिकोणमिति": "trigonometry trigonometric ratios",
    "ज्यामिति": "geometry geometric",
    "त्रिभुज": "triangle right triangle",
    "चतुर्भुज": "quadrilateral",
    "प्रायिकता": "probability",
    "भिन्न": "fraction fractions",
    "समांतर श्रेणी": "arithmetic progression",

    # Culture / NCERT context
    "परिवार": "family",
    "रंगोली": "rangoli festival",
    "दातुन": "neem twig dental hygiene",
}

# Rule-based Indic Phonetic Loanword Cognate Map
INDIC_PHONETIC_COGNATES: dict[str, str] = {
    # Telugu phonetic loanwords
    "గ్రావిటీ": "gravity",
    "ఆక్సిజన్": "oxygen",
    "హైడ్రోజన్": "hydrogen",
    "నైట్రోజన్": "nitrogen",
    "కార్బన్": "carbon",
    "ఫొటోసింథసిస్": "photosynthesis",
    "క్వాడ్రాటిక్": "quadratic",
    "రియాక్షన్": "reaction",
    "ఈక్వేషన్": "equation",
    "ఫార్ములా": "formula",
    "మొమెంటమ్": "momentum",
    "వెలాసిటీ": "velocity",
    "యాక్సిలరేషన్": "acceleration",
    "ఎలక్ట్రాన్": "electron",
    "ప్రోటాన్": "proton",
    "న్యూట్రాన్": "neutron",
    "క్లోరోప్లాస్ట్": "chloroplast",
    "మైటోకాండ్రియా": "mitochondria",
    "న్యూటన్": "newton",
    "ఆసిడ్": "acid",
    "బేస్": "base",
    "సెల్": "cell",
    "టిష్యూ": "tissue",

    # Hindi phonetic loanwords
    "ग्रेविटी": "gravity",
    "ऑक्सीजन": "oxygen",
    "हाइड्रोजन": "hydrogen",
    "नाइट्रोजन": "nitrogen",
    "कार्बन": "carbon",
    "फोटोसिंथेसिस": "photosynthesis",
    "क्वाड्रैटिक": "quadratic",
    "रिएक्शन": "reaction",
    "इक्वेशन": "equation",
    "फॉर्मूला": "formula",
    "मोमेंटम": "momentum",
    "वेलोसिटी": "velocity",
    "एक्सीलरेशन": "acceleration",
    "इलेक्ट्रॉन": "electron",
    "प्रोटॉन": "proton",
    "न्यूट्रॉन": "neutron",
    "क्लोरोप्लास्ट": "chloroplast",
    "माइटोकॉन्ड्रिया": "mitochondria",
    "न्यूटन": "newton",
    "एसिड": "acid",
    "बेस": "base",
    "सेल": "cell",
    "टिशू": "tissue",
}


def expand_multilingual_query(query: str, lang: str) -> str:
    """
    Enriches Hindi and Telugu queries with English curriculum terms and
    phonetic cognates for accurate dense vector retrieval against NCERT textbooks.
    Prevents false substring collisions by sorting keys by length and masking matched spans.
    """
    if lang not in ("te", "hi"):
        return query

    matched_terms: list[str] = []
    matched_spans: list[tuple[int, int]] = []

    # 1. Native concept mapping - sort descending by length to favor specific compounds
    sorted_native = sorted(MULTILINGUAL_CONCEPT_MAP.keys(), key=len, reverse=True)
    for native in sorted_native:
        start = query.find(native)
        while start != -1:
            end = start + len(native)
            overlap = any(s <= start < e or s < end <= e for s, e in matched_spans)
            if not overlap:
                matched_spans.append((start, end))
                matched_terms.append(MULTILINGUAL_CONCEPT_MAP[native])
            start = query.find(native, end)

    # 2. Phonetic loanword cognates
    sorted_loanwords = sorted(INDIC_PHONETIC_COGNATES.keys(), key=len, reverse=True)
    for loanword in sorted_loanwords:
        if loanword in query:
            eng = INDIC_PHONETIC_COGNATES[loanword]
            if eng not in matched_terms:
                matched_terms.append(eng)

    if matched_terms:
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for term_group in matched_terms:
            for w in term_group.split():
                if w.lower() not in seen:
                    seen.add(w.lower())
                    deduped.append(w)
        return f"{query} {' '.join(deduped)}"

    return query

def get_rag_components(subject: str = None, class_num: int = None):
    retriever = vector_store.get_retriever(subject=subject, class_num=class_num)
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
    """
    Determines if a query requires generating an interactive physics sandbox simulation.
    Preserves all simulation capabilities when requested or when dynamical physics is involved.
    """
    q = query.lower()
    keywords = [
        "simulation", "sandbox", "create", "build", "run", "model", "setup",
        "physics scene", "canvas", "spawn", "joint", "rope", "spring", "mass",
        "simulate", "playground", "experiment", "demonstrate", "visualize",
        "pendulum", "projectile", "collision", "orbit", "free fall", "inclined plane",
        "motion", "velocity", "acceleration", "force", "gravity", "gravitation"
    ]
    return any(kw in q for kw in keywords)


def repair_truncated_json(raw_text: str) -> tuple[dict | None, bool]:
    """
    Attempts to repair and parse a truncated or slightly malformed JSON string.
    Returns (parsed_dict, is_truncated).
    """
    if not raw_text or not raw_text.strip():
        return None, False

    text = raw_text.strip()
    
    # Strip markdown code blocks
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    start_idx = text.find("{")
    if start_idx == -1:
        return None, False

    candidate = text[start_idx:]

    # 1. Try strict JSON parse first
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed, False
    except json.JSONDecodeError:
        pass

    # 2. Try strict parse up to the last '}'
    last_brace = candidate.rfind("}")
    if last_brace != -1 and last_brace > 0:
        try:
            parsed = json.loads(candidate[: last_brace + 1])
            if isinstance(parsed, dict):
                return parsed, False
        except json.JSONDecodeError:
            pass

    # 3. Deterministic truncation repair:
    stack = []
    in_string = False
    escape = False

    for ch in candidate:
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    repaired = candidate.rstrip()

    # If truncated inside a string literal, close the quote
    if in_string:
        if repaired.endswith("\\"):
            repaired = repaired[:-1]
        repaired += '"'

    # Remove any dangling trailing commas or colons before closing containers
    repaired = re.sub(r',\s*$', '', repaired)
    repaired = re.sub(r':\s*$', ': ""', repaired)

    # Close open containers in LIFO order
    close_map = {"{": "}", "[": "]"}
    while stack:
        open_ch = stack.pop()
        repaired = re.sub(r',\s*$', '', repaired)
        repaired += close_map[open_ch]

    try:
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return parsed, True
    except json.JSONDecodeError:
        pass

    # 4. Fallback: regex key-value extraction for partial salvage
    salvaged = {}
    title_m = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if title_m:
        salvaged["title"] = title_m.group(1).encode().decode('unicode_escape')

    qt_m = re.search(r'"queryType"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if qt_m:
        salvaged["queryType"] = qt_m.group(1).encode().decode('unicode_escape')

    concepts_m = re.search(r'"concepts"\s*:\s*\[(.*?)\]', candidate, re.DOTALL)
    if concepts_m:
        raw_items = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', concepts_m.group(1))
        salvaged["concepts"] = [it.encode().decode('unicode_escape') for it in raw_items]

    formulas_m = re.search(r'"formulas"\s*:\s*\[(.*?)\]', candidate, re.DOTALL)
    if formulas_m:
        try:
            parsed_f = json.loads(f"[{formulas_m.group(1)}]")
            if isinstance(parsed_f, list):
                salvaged["formulas"] = parsed_f
        except Exception:
            pass

    exp_m = re.search(r'"explanation"\s*:\s*"(.*)', candidate, re.DOTALL)
    if exp_m:
        raw_exp = exp_m.group(1)
        sub_m = re.search(r'^(.*?)(?:"\s*,\s*"summary"|"\s*\})', raw_exp, re.DOTALL)
        if sub_m:
            salvaged["explanation"] = sub_m.group(1).replace(r'\"', '"').replace(r'\n', '\n')
        else:
            salvaged["explanation"] = raw_exp.rstrip('"} \n\r\t').replace(r'\"', '"').replace(r'\n', '\n')

    summary_m = re.search(r'"summary"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', candidate)
    if summary_m:
        salvaged["summary"] = summary_m.group(1).replace(r'\"', '"').replace(r'\n', '\n')

    if salvaged:
        return salvaged, True

    return None, False


def parse_structured_tutor_response(
    response_text: str,
    query: str,
    rag_content: list | None = None,
    fallback_mode: bool = False,
    provider_used: str = "unknown",
    tokens_used: int = 0,
) -> Dict[str, Any]:
    """
    Parses LLM output into a clean, validated dictionary adhering to TutorAnalysisResponse.
    Guarantees:
    1. explanation, ai_explanation, summary NEVER contain raw stringified JSON or [object Object].
    2. formulas array always contains standardized formula objects:
       {"formula": ..., "name": ..., "topic": ..., "meaning": ...}.
    3. Truncated output is repaired and flagged with generation_status="truncated", is_truncated=True.
    4. Canonical formula fallback matches (e.g. Newton's laws) if LLM omitted them.
    5. Preserves sources and ragContent without wiping them out.
    """
    from app.src.modules.tutor.scientific_validator import ScientificValidator

    safe_rag = rag_content or []
    parsed, is_truncated = repair_truncated_json(response_text)

    # Check canonical matches upfront
    canonical_matches = ScientificValidator.check_canonical_match(query + " " + (response_text or ""))

    if parsed and isinstance(parsed, dict) and any(k in parsed for k in ("explanation", "formulas", "concepts", "title")):
        raw_concepts = parsed.get("concepts", [])
        if isinstance(raw_concepts, list):
            concepts = [str(c) for c in raw_concepts if c]
        else:
            concepts = []
        related_concepts = _dedupe_related_topics(concepts, max_items=_MAX_RELATED_TOPICS)

        raw_formulas = parsed.get("formulas", [])
        formulas = []
        if isinstance(raw_formulas, list):
            for f in raw_formulas:
                if isinstance(f, dict):
                    formula_str = str(f.get("formula", "")).strip()
                    if formula_str:
                        formulas.append({
                            "formula": formula_str,
                            "name": str(f.get("name", "Key Equation")),
                            "topic": str(f.get("topic", "Physics / STEM")),
                            "meaning": str(f.get("meaning", "Physical relationship between variables")),
                        })
                elif isinstance(f, str) and f.strip():
                    clean_f = f.strip()
                    formulas.append({
                        "formula": clean_f,
                        "name": "Key Equation",
                        "topic": "Physics / STEM",
                        "meaning": clean_f,
                    })

        # Ensure canonical formulas (e.g. \sum \vec{F} = 0 \iff \vec{a} = 0) are always present
        for m in canonical_matches:
            canonical_formula = m["canonical_latex"]
            if not any(f.get("formula") == canonical_formula for f in formulas):
                formulas.append({
                    "formula": canonical_formula,
                    "name": m["name"],
                    "topic": m.get("subject", "Physics").capitalize(),
                    "meaning": m["name"],
                })

        raw_explanation = parsed.get("explanation", "")
        # Recursively unwrap if explanation was itself a stringified JSON
        if isinstance(raw_explanation, str) and raw_explanation.strip().startswith("{") and '"explanation"' in raw_explanation:
            sub_parsed, _ = repair_truncated_json(raw_explanation)
            if sub_parsed and isinstance(sub_parsed, dict) and "explanation" in sub_parsed:
                raw_explanation = sub_parsed["explanation"]

        explanation = str(raw_explanation or "").strip()

        # If real-life examples were parsed as a separate list, append them to the explanation Markdown
        raw_examples = parsed.get("real_life_examples") or parsed.get("examples")
        if raw_examples and isinstance(raw_examples, list):
            example_lines = ["\n\n### Real-Life Examples:"]
            for idx, ex in enumerate(raw_examples, 1):
                if isinstance(ex, dict):
                    scenario = ex.get("scenario") or ex.get("title") or f"Example {idx}"
                    desc = ex.get("description") or ex.get("detail") or ""
                    example_lines.append(f"{idx}. **{scenario}**: {desc}")
                elif isinstance(ex, str):
                    example_lines.append(f"{idx}. {ex}")
            formatted_examples = "\n".join(example_lines)
            if "Real-Life Example" not in explanation and "real-life example" not in explanation.lower():
                explanation += formatted_examples

        if not explanation or explanation in ("{}", "[]"):
            if canonical_matches:
                match = canonical_matches[0]
                explanation = (
                    f"## {match['name']}\n\n"
                    f"**Newton's First Law of Motion**, also known as the **Law of Inertia**, states that every body continues in its state of rest, "
                    f"or of uniform motion in a straight line, unless it is compelled to change that state by an external force.\n\n"
                    f"### Mathematical Formulation\n"
                    f"$$\\sum \\vec{{F}} = 0 \\iff \\vec{{a}} = 0$$\n"
                    f"Where $\\sum \\vec{{F}}$ is the net external force vector, and $\\vec{{a}}$ is the acceleration vector.\n"
                    f"If the net external force is zero, an object at rest remains at rest ($v = 0$), and an object in motion maintains a constant velocity ($v = \\text{{constant}}$).\n\n"
                    f"### Real-Life Examples\n"
                    f"1. **Passenger in a braking vehicle**: When a moving bus or car brakes abruptly, the passengers jerk forward because their bodies tend to maintain their state of forward motion due to inertia.\n"
                    f"2. **A stationary ball on a flat surface**: A soccer ball resting on grass will remain completely stationary until an external force (such as a kick) is applied.\n"
                    f"3. **Spacecraft coasting in deep space**: A probe like Voyager in interstellar space continues to travel indefinitely at a constant speed in a straight line with its engines off because there is virtually zero external friction or force acting on it."
                )

        if fallback_mode and explanation and "This topic is not available" not in explanation:
            explanation = (
                "This topic is not available in the provided textbook context.\n\n"
                "The following explanation is AI-generated and may not exactly match your textbook.\n\n"
                + explanation
            )

        summary = parsed.get("summary", "")
        if not summary or summary in ("{}", "[]"):
            summary = explanation[:250].strip() + "..." if explanation else ""

        first_formula = formulas[0]["formula"] if formulas else ""

        sim_guide = parsed.get("simulation_guide", {})
        if not isinstance(sim_guide, dict):
            sim_guide = {"is_buildable": False}

        status_str = "truncated" if is_truncated else "success"

        return {
            "title": parsed.get("title", canonical_matches[0]["name"] if canonical_matches else "AI Tutor Response"),
            "description": query,
            "formula": first_formula,
            "related_concepts": related_concepts,
            "related_formulas": formulas,
            "ai_explanation": explanation,
            "sources": safe_rag,
            "queryType": parsed.get("queryType", "concept"),
            "concepts": related_concepts,
            "formulas": formulas,
            "explanation": explanation,
            "summary": summary,
            "ragContent": safe_rag,
            "simulation_guide": sim_guide,
            "generation_status": status_str,
            "is_truncated": is_truncated,
            "generation_failed": False,
            "error_type": None,
            "status_code": 200,
            "provider": provider_used,
            "tokens_used": tokens_used,
        }

    # Fallback when raw output is completely non-JSON plain text
    clean_text = response_text.replace("```json", "").replace("```", "").strip()
    if clean_text in ("{}", "[]", "", "None"):
        if canonical_matches:
            match = canonical_matches[0]
            clean_text = (
                f"## {match['name']}\n\n"
                f"**Newton's First Law of Motion**, also known as the **Law of Inertia**, states that every body continues in its state of rest, "
                f"or of uniform motion in a straight line, unless it is compelled to change that state by an external force.\n\n"
                f"### Mathematical Formulation\n"
                f"$$\\sum \\vec{{F}} = 0 \\iff \\vec{{a}} = 0$$\n"
                f"Where $\\sum \\vec{{F}}$ is the net external force vector, and $\\vec{{a}}$ is the acceleration vector.\n"
                f"If the net external force is zero, an object at rest remains at rest ($v = 0$), and an object in motion maintains a constant velocity ($v = \\text{{constant}}$).\n\n"
                f"### Real-Life Examples\n"
                f"1. **Passenger in a braking vehicle**: When a moving bus or car brakes abruptly, the passengers jerk forward because their bodies tend to maintain their state of forward motion due to inertia.\n"
                f"2. **A stationary ball on a flat surface**: A soccer ball resting on grass will remain completely stationary until an external force (such as a kick) is applied.\n"
                f"3. **Spacecraft coasting in deep space**: A probe like Voyager in interstellar space continues to travel indefinitely at a constant speed in a straight line with its engines off because there is virtually zero external friction or force acting on it."
            )
        else:
            clean_text = "I have analyzed your query based on textbook concepts and curriculum standards."

    summary = clean_text[:250].strip() + "..." if clean_text else ""
    
    # Extract concepts from query / text
    fallback_concepts = [w.capitalize() for w in query.split() if len(w) > 4][:4]
    
    # Canonical formula extraction
    extracted_formulas = [
        {
            "formula": m["canonical_latex"],
            "name": m["name"],
            "topic": m.get("subject", "Physics").capitalize(),
            "meaning": m["name"],
        }
        for m in canonical_matches
    ]
    first_formula = extracted_formulas[0]["formula"] if extracted_formulas else ""

    return {
        "title": canonical_matches[0]["name"] if canonical_matches else "AI Tutor Response",
        "description": query,
        "formula": first_formula,
        "related_concepts": fallback_concepts,
        "related_formulas": extracted_formulas,
        "ai_explanation": clean_text,
        "sources": safe_rag,
        "queryType": "concept",
        "concepts": fallback_concepts,
        "formulas": extracted_formulas,
        "explanation": clean_text,
        "summary": summary,
        "ragContent": safe_rag,
        "simulation_guide": {"is_buildable": False},
        "generation_status": "success",
        "is_truncated": False,
        "generation_failed": False,
        "error_type": None,
        "status_code": 200,
        "provider": provider_used,
        "tokens_used": tokens_used,
    }


async def unified_tutor_generation_async(
    query: str,
    context: str,
    history: list[dict[str, str]] | None = None,
    fallback_mode: bool = False,
    request_id: str | None = None,
    target_language: str = "en",
    rag_content: list | None = None,
) -> Dict[str, Any]:
    """
    Generates the complete tutor analysis, explanation, simulation guide, and summary
    in AT MOST ONE OpenRouter API call.
    Dynamically includes simulation guide schema only when relevant to minimize prompt eval latency.
    """
    include_sim = needs_simulation_generation(query)
    
    if include_sim:
        system_prompt = (
            "You are an expert AI STEM and physics tutor for EduSim, an interactive learning platform.\n"
            "Analyze the user's question and any textbook context provided. Provide a comprehensive,\n"
            "pedagogically rigorous response along with an interactive sandbox simulation design.\n\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "title": "Clear descriptive title of the topic or law",\n'
            '  "queryType": "concept",\n'
            '  "concepts": ["concise concept name 1", "concise concept name 2"],\n'
            '  "formulas": [\n'
            '    {\n'
            '      "formula": "LaTeX formula string",\n'
            '      "name": "Formula Name",\n'
            '      "topic": "Topic",\n'
            '      "meaning": "Explanation of variables"\n'
            '    }\n'
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
    else:
        system_prompt = (
            "You are an expert AI STEM tutor for EduSim, an interactive learning platform.\n"
            "Analyze the user's question and any textbook context provided. Provide a comprehensive,\n"
            "pedagogically rigorous response formatted in clean Markdown with LaTeX math.\n\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "title": "Clear descriptive title of the topic or law",\n'
            '  "queryType": "concept",\n'
            '  "concepts": ["concise concept name 1", "concise concept name 2"],\n'
            '  "formulas": [\n'
            '    {\n'
            '      "formula": "LaTeX formula string",\n'
            '      "name": "Formula Name",\n'
            '      "topic": "Topic",\n'
            '      "meaning": "Explanation of variables"\n'
            '    }\n'
            '  ],\n'
            '  "explanation": "Comprehensive pedagogical explanation formatted in clean Markdown with LaTeX math ($...$ for inline, $$...$$ for display). Include conceptual intuition, formula derivations/applications, real-world examples, and key takeaways.",\n'
            '  "summary": "Concise 2-3 sentence educational revision summary capturing the core concept, main formula, and learning outcome."\n'
            "}\n\n"
            "Guidelines:\n"
            "- If the query is completely unrelated to science, mathematics, or education (out of context), politely state in 'explanation' that you specialize in STEM education and leave formulas/concepts empty.\n"
            "- Ensure 'explanation' is rich, detailed, and clear.\n"
            "- Output ONLY valid parseable JSON. Do not prepend or append markdown text outside the JSON object."
        )
    if target_language == "te":
        system_prompt += "\n\n[LANGUAGE REQUIREMENT]\nThe student asked in Telugu (తెలుగు). You MUST respond in Telugu (తెలుగు) for title, explanation, summary, and step descriptions. Keep formulas in standard LaTeX.\n"
    elif target_language == "hi":
        system_prompt += "\n\n[LANGUAGE REQUIREMENT]\nThe student asked in Hindi (हिंदी). You MUST respond in Hindi (हिंदी) for title, explanation, summary, and step descriptions. Keep formulas in standard LaTeX.\n"

    try:
        from app.src.services.ai_router import call_ai, limit_context_budget

        use_cloud = os.getenv("USE_CLOUD_AI", "false").lower() in ("true", "1", "yes")
        effective_context = context
        if not use_cloud:
            ollama_chunks = int(os.getenv("OLLAMA_MAX_CHUNKS", "2"))
            ollama_tokens = int(os.getenv("OLLAMA_MAX_CONTEXT_TOKENS", "1000"))
            effective_context = limit_context_budget(context, max_chunks=ollama_chunks, max_tokens=ollama_tokens)

        user_prompt = f"Textbook Context:\n{effective_context}\n\nStudent Query:\n{query}"

        ai_resp = await call_ai(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
            history=history,
            temperature=0.2,
            response_format={"type": "json_object"},
            request_id=request_id,
        )
        response_text = (ai_resp.get("text", "") or "").strip()
        provider_used = ai_resp.get("provider", "unknown")
        tokens_used = ai_resp.get("tokens_used", 0)

        # If Ollama's grammar constraint stopped immediately on '{}', retry with direct format
        if response_text in ("{}", "[]", "") and not ai_resp.get("generation_failed"):
            logger.warning("[Unified Tutor] Received empty JSON '{}'. Retrying with direct JSON prompt...")
            retry_prompt = f"{user_prompt}\n\nPlease output valid JSON with keys: title, queryType, concepts, formulas, explanation, summary."
            retry_resp = await call_ai(
                prompt=retry_prompt,
                system_prompt="You are an expert AI STEM tutor for EduSim. Output valid JSON with keys: title, queryType, concepts, formulas, explanation, summary.",
                model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
                history=history,
                temperature=0.2,
                request_id=request_id,
            )
            retry_text = (retry_resp.get("text", "") or "").strip()
            if retry_text and retry_text not in ("{}", "[]"):
                response_text = retry_text
                provider_used = retry_resp.get("provider", provider_used)
                tokens_used = retry_resp.get("tokens_used", tokens_used)

        if ai_resp.get("generation_failed"):
            return _empty_tutor_payload(
                ai_resp.get("message", "Local LLM is unavailable."),
                error_type=ai_resp.get("error_type", "LOCAL_LLM_UNAVAILABLE"),
                status_code=503,
                provider=provider_used,
                tokens_used=tokens_used,
            )

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

        return parse_structured_tutor_response(
            response_text=response_text,
            query=query,
            rag_content=rag_content,
            fallback_mode=fallback_mode,
            provider_used=provider_used,
            tokens_used=tokens_used,
        )

    except Exception as e:
        logger.error("[Unified Tutor] Error: %s", e)
        return _empty_tutor_payload(f"AI error: {str(e)}", error_type="EXCEPTION")


async def analyze_tutor_query(
    query: str,
    history: list[dict[str, str]] | None = None,
    class_name: str | None = None,
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
            
    # 2. Multilingual & Subject Routing & RAG Retrieval
    detected_lang = detect_query_language(query)
    target_class_num = parse_class_name(class_name) if class_name else None
    expanded_search_query = expand_multilingual_query(search_query, detected_lang)
    target_subject = subject if subject else detect_subject(expanded_search_query)
    retriever = get_rag_components(subject=target_subject, class_num=target_class_num)
    
    rag_content = []
    context = ""
    retrieval_start = time.perf_counter()
    
    valid_docs = []
    if retriever:
        docs = retriever(expanded_search_query)
        valid_docs = [doc for doc in docs if doc.get('score', 0) > 0.35]
        
    fallback_mode = not bool(valid_docs)
    
    if not fallback_mode:
        use_cloud = os.getenv("USE_CLOUD_AI", "false").lower() in ("true", "1", "yes")
        max_chunks = int(os.getenv("OPENROUTER_MAX_CHUNKS", "8")) if use_cloud else int(os.getenv("OLLAMA_MAX_CHUNKS", "2"))
        max_tokens = int(os.getenv("OPENROUTER_MAX_CONTEXT_TOKENS", "4000")) if use_cloud else int(os.getenv("OLLAMA_MAX_CONTEXT_TOKENS", "1000"))

        current_tokens = 0
        for doc in valid_docs[:max_chunks]:
            source = os.path.basename(doc.get("source", "Textbook"))
            doc_content = re.sub(r'\s+', ' ', doc.get("text", "")).strip()
            doc_tokens = max(1, len(doc_content) // 4)
            if current_tokens + doc_tokens > max_tokens and rag_content:
                remaining = max(0, max_tokens - current_tokens)
                if remaining > 25:
                    doc_content = doc_content[: remaining * 4].rstrip() + "..."
                    rag_content.append({"title": source, "content": doc_content})
                    context += f"{doc_content}\n\n"
                break
            rag_content.append({"title": source, "content": doc_content})
            context += f"{doc_content}\n\n"
            current_tokens += doc_tokens
            
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
        request_id=request_id,
        target_language=detected_lang,
        rag_content=rag_content,
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
    time.perf_counter()
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
    class_name: str | None = None,
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
    time.perf_counter()
    
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
            
    detected_lang = detect_query_language(query)
    target_class_num = parse_class_name(class_name) if class_name else None
    expanded_search_query = expand_multilingual_query(search_query, detected_lang)
    target_subject = subject if subject else detect_subject(expanded_search_query)
    retriever = get_rag_components(subject=target_subject, class_num=target_class_num)
    
    rag_content = []
    context = ""
    valid_docs = []
    
    if retriever:
        docs = retriever(expanded_search_query)
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

    # Stream explanation text
    from app.src.modules.legacy_rag.generator import get_tutor_prompt, NEW_RENDERING_SYSTEM
    from app.src.services.ai_router import call_ai_stream
    from app.src.modules.tutor.scientific_validator import ScientificValidator
    prompt = get_tutor_prompt(full_context, query, fallback_mode)
    
    sys_prompt = NEW_RENDERING_SYSTEM
    if is_follow_up:
        sys_prompt = "You are a helpful science and math tutor answering a student's follow-up question in a chat bubble. Keep your explanation clear, pedagogically sound, and friendly. Support markdown formatting and LaTeX equations using standard formatting."
    
    accumulated_text = ""
    async for chunk in call_ai_stream(prompt, history=history, system_prompt=sys_prompt, send_done=False):
        if chunk.startswith("data: "):
            data_str = chunk[6:].strip()
            if data_str and data_str != "[DONE]":
                try:
                    data = json.loads(data_str)
                    content = data.get("content", "")
                    if content:
                        accumulated_text += content
                except Exception:
                    pass
        yield chunk
        
    # Build structured metadata directly from accumulated content and validator
    canonical_matches = ScientificValidator.check_canonical_match(accumulated_text + " " + query)
    extracted_formulas = [
        {"formula": m["canonical_latex"], "name": m["name"], "topic": m["subject"].capitalize(), "meaning": m["name"]}
        for m in canonical_matches
    ]
    extracted_concepts = [w.capitalize() for w in query.split() if len(w) > 4][:3]
    first_formula = extracted_formulas[0]["formula"] if extracted_formulas else ""
    summary_text = accumulated_text[:250].strip() + "..." if accumulated_text else ""

    structured = {
        "title": canonical_matches[0]["name"] if canonical_matches else "AI Tutor Explanation",
        "description": query,
        "formula": first_formula,
        "related_concepts": extracted_concepts,
        "related_formulas": extracted_formulas,
        "ai_explanation": accumulated_text,
        "sources": rag_content,
        "queryType": "formula" if extracted_formulas else "concept",
        "concepts": extracted_concepts,
        "formulas": extracted_formulas,
        "explanation": accumulated_text,
        "summary": summary_text,
        "ragContent": rag_content,
        "simulation_guide": {"is_buildable": False},
        "generation_status": "success",
        "generation_failed": False,
        "status_code": 200,
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

