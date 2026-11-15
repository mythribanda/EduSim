"""
tests/test_tutor_multilingual.py
================================
Unit tests verifying multilingual language detection, Indic concept mapping,
subject routing, and class_name parameter forwarding in the AI Tutor.
"""

import pytest
from app.src.modules.tutor.service import (
    detect_query_language,
    expand_multilingual_query,
    get_rag_components,
)
from app.src.modules.tutor.subject_classifier import detect_subject
from app.src.modules.legacy_rag.retriever import parse_class_name


def test_detect_query_language():
    # English
    assert detect_query_language("What is Newton's second law of motion?") == "en"
    assert detect_query_language("Calculate the kinetic energy of a 2kg mass.") == "en"

    # Telugu
    assert detect_query_language("గురుత్వాకర్షణ శక్తి అంటే ఏమిటి?") == "te"
    assert detect_query_language("చలన సమీకరణాలు వివరించండి.") == "te"

    # Hindi
    assert detect_query_language("गुरुत्वाकर्षण बल क्या है?") == "hi"
    assert detect_query_language("न्यूटन के गति के नियमों को समझाइए।") == "hi"

    # Empty / whitespace
    assert detect_query_language("") == "en"
    assert detect_query_language("   ") == "en"


def test_expand_multilingual_query():
    # Telugu term expansion
    te_expanded = expand_multilingual_query("గురుత్వాకర్షణ సిద్ధాంతం", "te")
    assert "gravitation" in te_expanded or "gravity" in te_expanded

    # Hindi term expansion
    hi_expanded = expand_multilingual_query("प्रकाश का परावर्तन", "hi")
    assert "light" in hi_expanded or "optics" in hi_expanded

    # English query should remain unchanged
    en_query = "What is acceleration due to gravity?"
    assert expand_multilingual_query(en_query, "en") == en_query


def test_multilingual_subject_classification():
    # Telugu classification
    assert detect_subject("గురుత్వాకర్షణ శక్తి అంటే ఏమిటి?") == "physics"
    assert detect_subject("వృత్తం యొక్క వైశాల్యం ఎంత?") == "maths"
    assert detect_subject("కణం యొక్క నిర్మాణం వివరించండి") == "biology"

    # Hindi classification
    assert detect_subject("गुरुत्वाकर्षण का नियम क्या है?") == "physics"
    assert detect_subject("त्रिभुज का क्षेत्रफल कैसे निकालें?") == "maths"
    assert detect_subject("अम्ल और क्षार में क्या अंतर है?") == "chemistry"
    assert detect_subject("कोशिका के मुख्य भाग कौन से हैं?") == "biology"


def test_class_name_parsing_and_retriever():
    assert parse_class_name("Class 10") == 10
    assert parse_class_name("10th") == 10
    assert parse_class_name("X") == 10
    assert parse_class_name("Class 9") == 9
    assert parse_class_name("IX") == 9

    # Verify get_rag_components accepts class_num
    retriever = get_rag_components(subject="physics", class_num=10)
    assert retriever is not None
    assert callable(retriever)
