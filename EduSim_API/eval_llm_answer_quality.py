import asyncio
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import analyze_tutor_query

async def evaluate_answer_quality():
    print("=== EVALUATING LLM MULTILINGUAL ANSWER QUALITY (12 REPRESENTATIVE QUESTIONS) ===")
    vector_store.load_all()

    test_samples = [
        # English
        {"lang": "en", "subj": "physics", "cls": "11", "q": "State Newton's second law of motion and write formula F=ma."},
        {"lang": "en", "subj": "chemistry", "cls": "11", "q": "Explain the difference between ionic bond and covalent bond."},
        {"lang": "en", "subj": "biology", "cls": "11", "q": "What is the function of chloroplast and chlorophyll in photosynthesis?"},
        {"lang": "en", "subj": "maths", "cls": "10", "q": "What is the quadratic formula to solve ax^2 + bx + c = 0?"},

        # Telugu
        {"lang": "te", "subj": "physics", "cls": "11", "q": "న్యూటన్ రెండవ గమన నియమం సూత్రం F=ma వివరించండి."},
        {"lang": "te", "subj": "chemistry", "cls": "11", "q": "అయానిక బంధం మరియు సమయోజనీయ బంధం మధ్య తేడా ఏమిటి?"},
        {"lang": "te", "subj": "biology", "cls": "11", "q": "కిరణజన్య సంయోగక్రియ మరియు హరితరేణువు పాత్ర ఏమిటి?"},
        {"lang": "te", "subj": "maths", "cls": "10", "q": "వర్గ సమీకరణం మూలాలు కనుగొనే సూత్రం ఏమిటి?"},

        # Hindi
        {"lang": "hi", "subj": "physics", "cls": "11", "q": "न्यूटन का गति का द्वितीय नियम और सूत्र F=ma समझाइए।"},
        {"lang": "hi", "subj": "chemistry", "cls": "11", "q": "आयनिक आबंध और सहसंयोजक आबंध में क्या अंतर है?"},
        {"lang": "hi", "subj": "biology", "cls": "11", "q": "प्रकाश संश्लेषण की प्रक्रिया और क्लोरोफिल की भूमिका समझाइए।"},
        {"lang": "hi", "subj": "maths", "cls": "10", "q": "द्विघात समीकरण के मूल ज्ञात करने का सूत्र क्या है?"},
    ]

    results = []

    for item in test_samples:
        q = item["q"]
        lang = item["lang"]
        subj = item["subj"]
        cls = item["cls"]

        print(f"\n--- Testing [{lang.upper()}] {subj.capitalize()}: {q[:50]}... ---")
        t0 = time.perf_counter()
        resp = await analyze_tutor_query(
            query=q,
            subject=subj,
            class_name=cls
        )
        elapsed = time.perf_counter() - t0

        explanation = resp.get("ai_explanation") or resp.get("explanation") or ""
        sources = resp.get("sources", [])
        formulas = resp.get("formulas", [])
        concepts = resp.get("concepts", [])
        provider = resp.get("provider", "unknown")

        # Language correctness check
        if lang == "te":
            lang_match = bool(any(0x0C00 <= ord(ch) <= 0x0C7F for ch in explanation))
        elif lang == "hi":
            lang_match = bool(any(0x0900 <= ord(ch) <= 0x097F for ch in explanation))
        else:
            lang_match = True

        # Formula check
        has_formula = bool(formulas and len(formulas) > 0) or any(s in explanation for s in ["=", "\\frac", "F", "ma", "ax^2", "x ="])
        is_grounded = bool(sources and len(sources) > 0)

        print(f"  Provider: {provider} | Time: {elapsed:.2f}s")
        print(f"  Target Lang Match: {lang_match}")
        print(f"  Grounded in Sources: {is_grounded} ({len(sources)} sources)")
        print(f"  Formula Present: {has_formula}")
        print(f"  Preview: {explanation[:180].replace(chr(10), ' ')}...")

        results.append({
            "language": lang,
            "subject": subj,
            "query": q,
            "provider": provider,
            "latency_sec": round(elapsed, 2),
            "language_correctness": lang_match,
            "grounded": is_grounded,
            "has_formula": has_formula,
            "sources_count": len(sources),
            "concepts_extracted": concepts[:3],
            "response_preview": explanation[:220].replace("\n", " ")
        })

    with open(api_dir / "multilingual_answer_quality_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("ANSWER QUALITY EVALUATION SUMMARY:")
    print("=" * 70)
    print(f"Total Evaluated: {len(results)}")
    print(f"Language Correctness: {sum(1 for r in results if r['language_correctness'])}/{len(results)} ({sum(1 for r in results if r['language_correctness'])/len(results)*100:.1f}%)")
    print(f"Formula Correctness: {sum(1 for r in results if r['has_formula'])}/{len(results)} ({sum(1 for r in results if r['has_formula'])/len(results)*100:.1f}%)")
    print(f"Average Latency: {sum(r['latency_sec'] for r in results)/len(results):.2f}s")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(evaluate_answer_quality())
