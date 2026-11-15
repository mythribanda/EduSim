import asyncio
import json
import sys
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.controller import analyze_tutor_controller, TutorQueryRequest, ChatMessage

async def test_followup_conversation():
    print("=== TESTING 4-TURN CONVERSATION & STUDENT ISOLATION ===")
    vector_store.load_all()

    # Student A: 4-turn conversation about gravity
    student_a_history = []
    
    turns = [
        "What is gravity and the universal law of gravitation?",
        "Can you give an example of it in everyday life?",
        "Why is the acceleration constant during free fall near Earth?",
        "Can you give a simple numerical problem to calculate gravitational force between two masses?"
    ]

    print("\n--- Running Student A Conversation ---")
    for turn_idx, turn_query in enumerate(turns, 1):
        print(f"\n[Turn {turn_idx}] Student A: '{turn_query}'")
        
        req = TutorQueryRequest(
            query=turn_query,
            class_name="9",
            subject="science",
            history=[ChatMessage(role=m["role"], content=m["content"]) for m in student_a_history],
            session_id="session_student_A_123"
        )

        res = await analyze_tutor_controller(req)
        data = res.get("data", {})
        explanation = data.get("ai_explanation") or data.get("explanation") or ""
        sources = data.get("sources", [])
        provider = data.get("provider", "unknown")

        print(f"  Provider: {provider}")
        print(f"  Sources Count: {len(sources)}")
        for s in sources[:2]:
            print(f"    - Book: {s.get('book_title')} | Ch: {s.get('chapter')} | Page: {s.get('page')}")
        print(f"  Response Preview: {explanation[:180].replace(chr(10), ' ')}...")

        # Append to history for next turn
        student_a_history.append({"role": "user", "content": turn_query})
        student_a_history.append({"role": "assistant", "content": explanation[:300]})

    print(f"\nStudent A completed 4 turns. Total history items: {len(student_a_history)}")

    # Student B: Isolation verification
    # Student B sends an unrelated or ambiguous question ("What is it?") with NO history
    print("\n--- Running Student B Isolation Check ---")
    req_b = TutorQueryRequest(
        query="What is it?",
        class_name="10",
        subject="mathematics",
        history=[],
        session_id="session_student_B_456"
    )
    res_b = await analyze_tutor_controller(req_b)
    data_b = res_b.get("data", {})
    explanation_b = data_b.get("ai_explanation") or ""
    print(f"Student B query: 'What is it?' with empty history")
    print(f"Student B response title: '{data_b.get('title')}'")
    print(f"Student B response: {explanation_b[:200].replace(chr(10), ' ')}...")
    
    # Verify that Student B does NOT see gravity from Student A
    has_leak = "gravity" in explanation_b.lower() or "gravitation" in explanation_b.lower()
    is_clarification = "clarification" in data_b.get("title", "").lower() or "not sure" in explanation_b.lower()
    print(f"Isolation check: Student A gravity context leaked to Student B? {has_leak} (Expected: False)")
    print(f"Clarification requested for ambiguous pronoun without history? {is_clarification} (Expected: True)")
    assert not has_leak, "CRITICAL ERROR: Student A context leaked to Student B!"
    assert is_clarification, "Expected clarification prompt for ambiguous pronoun without history"

    print("\nSession isolation and 4-turn follow-up successfully verified!")

if __name__ == "__main__":
    asyncio.run(test_followup_conversation())
