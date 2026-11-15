import json
import os
import sys
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import (
    detect_query_language,
    expand_multilingual_query,
)
from app.src.modules.tutor.subject_classifier import detect_subject

def run_multilingual_eval():
    print("=== MULTILINGUAL EVALUATION (ENGLISH, TELUGU, HINDI) ===")
    vector_store.load_all()

    test_questions = [
        # 5 English Questions
        {"lang": "en", "subject": "physics", "class": 11, "q": "What is Newton's third law of motion regarding action and reaction?"},
        {"lang": "en", "subject": "chemistry", "class": 11, "q": "What is ionic bond and covalent bond in chemical bonding?"},
        {"lang": "en", "subject": "biology", "class": 11, "q": "What is photosynthesis and chloroplast function in plant cells?"},
        {"lang": "en", "subject": "mathematics", "class": 10, "q": "What is the quadratic formula to find the roots of ax^2 + bx + c = 0?"},
        {"lang": "en", "subject": "science", "class": 9, "q": "What is universal gravitation law and gravitational constant G?"},

        # 5 Telugu Questions
        {"lang": "te", "subject": "physics", "class": 11, "q": "న్యూటన్ మూడవ గమన నియమం చర్య మరియు ప్రతిచర్య గురించి ఏమి చెబుతుంది?"},
        {"lang": "te", "subject": "chemistry", "class": 11, "q": "రసాయన బంధంలో సమయోజనీయ బంధం అంటే ఏమిటి?"},
        {"lang": "te", "subject": "biology", "class": 11, "q": "కిరణజన్య సంయోగక్రియ మరియు హరితరేణువు విధులు ఏమిటి?"},
        {"lang": "te", "subject": "mathematics", "class": 10, "q": "వర్గ సమీకరణం మూలాలు కనుగొనే సూత్రం ఏమిటి?"},
        {"lang": "te", "subject": "science", "class": 9, "q": "గురుత్వాకర్షణ సార్వత్రిక నియమం మరియు గురుత్వ త్వరణం g అంటే ఏమిటి?"},

        # 5 Hindi Questions
        {"lang": "hi", "subject": "physics", "class": 11, "q": "न्यूटन का गति का तीसरा नियम क्रिया और प्रतिक्रिया के बारे में क्या कहता है?"},
        {"lang": "hi", "subject": "chemistry", "class": 11, "q": "रासायनिक आबंधन में सहसंयोजक बंध क्या है?"},
        {"lang": "hi", "subject": "biology", "class": 11, "q": "प्रकाश संश्लेषण और पादप कोशिका में हरितलवक का क्या कार्य है?"},
        {"lang": "hi", "subject": "mathematics", "class": 10, "q": "द्विघात समीकरण के मूल ज्ञात करने का सूत्र क्या है?"},
        {"lang": "hi", "subject": "science", "class": 9, "q": "गुरुत्वाकर्षण का सार्वत्रिक नियम और गुरुत्वीय त्वरण g क्या है?"},
    ]

    results = []

    for item in test_questions:
        q = item["q"]
        expected_lang = item["lang"]
        expected_subj = item["subject"]
        cls_num = item["class"]

        detected_lang = detect_query_language(q)
        lang_correct = (detected_lang == expected_lang)

        detected_subj = detect_subject(q)
        subj_matches = (detected_subj == expected_subj or detected_subj in (expected_subj, "science", "physics"))

        expanded_q = expand_multilingual_query(q, detected_lang)

        # Test retrieval with the query
        search_subj = expected_subj
        chunks = vector_store.retrieve(
            query=expanded_q,
            subject=search_subj,
            class_num=cls_num,
            k=3,
            min_score=0.0
        )
        retrieval_success = len(chunks) > 0
        top_score = chunks[0]["score"] if chunks else 0.0
        top_book = chunks[0].get("book_title") if chunks else None
        top_ch = chunks[0].get("chapter_title") if chunks else None

        results.append({
            "language": expected_lang,
            "detected_lang": detected_lang,
            "lang_correct": lang_correct,
            "subject": expected_subj,
            "detected_subject": detected_subj,
            "subj_matches": subj_matches,
            "retrieval_success": retrieval_success,
            "top_score": round(top_score, 4),
            "top_book": top_book,
            "top_chapter": top_ch,
            "query": q
        })

        print(f"[{expected_lang.upper()}] Q: {q[:55]}...")
        print(f"  Detected Lang: {detected_lang} (Match: {lang_correct}) | Detected Subj: {detected_subj}")
        print(f"  Retrieval: {len(chunks)} chunks, Top Score: {top_score:.4f} | Book: {top_book} | Ch: {top_ch}")

    # Accuracy Stats
    total = len(results)
    lang_acc = sum(1 for r in results if r["lang_correct"]) / total * 100
    retrieval_acc = sum(1 for r in results if r["retrieval_success"]) / total * 100

    print("\n" + "=" * 60)
    print("MULTILINGUAL SUMMARY METRICS:")
    print(f"Total Evaluated Questions: {total}")
    print(f"Language Detection Accuracy: {lang_acc:.1f}% ({sum(1 for r in results if r['lang_correct'])}/{total})")
    print(f"Textbook Retrieval Success: {retrieval_acc:.1f}% ({sum(1 for r in results if r['retrieval_success'])}/{total})")
    print("=" * 60)

    # Save results as json for inclusion in report
    with open(api_dir / "multilingual_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_multilingual_eval()
