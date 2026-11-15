import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import analyze_tutor_query

async def run_tests():
    print("=== REAL OLLAMA INFERENCE & TUTOR PIPELINE VERIFICATION ===")
    
    # Preload vector store
    print("Preloading vector store...")
    vector_store.load_all()

    test_cases = [
        {
            "id": "EN_QUESTION",
            "name": "English Textbook Question",
            "query": "State Newton's second law of motion and explain its mathematical formula.",
            "subject": "physics",
            "class_name": "11",
            "history": None,
        },
        {
            "id": "TE_QUESTION",
            "name": "Telugu Question",
            "query": "న్యూటన్ రెండవ గమన నియమం ఏమిటి? దాని సూత్రాన్ని వివరించండి.",
            "subject": "physics",
            "class_name": "11",
            "history": None,
        },
        {
            "id": "HI_QUESTION",
            "name": "Hindi Question",
            "query": "न्यूटन के गति का दूसरा नियम क्या है? इसका सूत्र समझाइए।",
            "subject": "physics",
            "class_name": "11",
            "history": None,
        },
        {
            "id": "FOLLOWUP_QUESTION",
            "name": "Follow-up Question",
            "query": "Can you give a simple real-life example illustrating this law?",
            "subject": "physics",
            "class_name": "11",
            "history": [
                {
                    "role": "user",
                    "content": "State Newton's second law of motion and explain its mathematical formula."
                },
                {
                    "role": "assistant",
                    "content": "Newton's second law states that the rate of change of momentum of a body is directly proportional to the applied force. F = ma."
                }
            ],
        },
        {
            "id": "MISSING_CONTEXT",
            "name": "Question with Missing Textbook Context (Out-of-Syllabus)",
            "query": "Explain how quantum entanglement and Bell inequalities violate local realism in quantum mechanics.",
            "subject": "science",
            "class_name": "9",
            "history": None,
        }
    ]

    results = []

    for tc in test_cases:
        print(f"\n" + "=" * 70)
        print(f"TEST: {tc['name']} ({tc['id']})")
        print(f"Query: {tc['query']}")
        print(f"Subject: {tc['subject']} | Class: {tc['class_name']}")
        if tc["history"]:
            print(f"History turns: {len(tc['history'])}")

        t0 = time.perf_counter()
        res = await analyze_tutor_query(
            query=tc["query"],
            subject=tc["subject"],
            class_name=tc["class_name"],
            history=tc["history"]
        )
        elapsed = time.perf_counter() - t0

        provider = res.get("provider", "unknown")
        status_code = res.get("status_code", 200)
        status = res.get("generation_status", "unknown")
        sources = res.get("sources", [])
        explanation = res.get("ai_explanation") or res.get("explanation") or ""
        tokens = res.get("tokens_used", 0)
        
        # Check grounding
        is_grounded = bool(sources and len(sources) > 0)
        has_out_of_syllabus_disclaimer = "This topic is not available" in explanation

        print(f"HTTP Status: {status_code}")
        print(f"Provider: {provider}")
        print(f"Status: {status}")
        print(f"Response Time: {elapsed:.2f}s")
        print(f"Tokens Used: {tokens}")
        print(f"Sources count: {len(sources)}")
        for idx, src in enumerate(sources[:3], 1):
            print(f"  Source [{idx}]: {src.get('book_title')} | Ch: {src.get('chapter')} | Page: {src.get('page')}")
        print(f"Grounded in textbook: {is_grounded}")
        print(f"Has out-of-context disclaimer: {has_out_of_syllabus_disclaimer}")
        print(f"Response Preview:\n{explanation[:280]}...")

        results.append({
            "test": tc["name"],
            "query": tc["query"],
            "provider": provider,
            "status_code": status_code,
            "response_time_sec": round(elapsed, 2),
            "tokens_used": tokens,
            "sources_count": len(sources),
            "is_grounded": is_grounded,
            "disclaimer": has_out_of_syllabus_disclaimer,
            "preview": explanation[:250].replace("\n", " "),
        })

    print("\n" + "=" * 70)
    print("SUMMARY OF REAL OLLAMA INFERENCE RUN:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(run_tests())
