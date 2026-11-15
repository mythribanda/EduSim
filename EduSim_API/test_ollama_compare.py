import os
import sys
import asyncio
import json
import httpx

async def test_ollama_format(use_format_json: bool, system: str, prompt: str):
    payload = {
        "model": "gemma3:4b",
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 1024,
        }
    }
    if use_format_json:
        payload["format"] = "json"
    
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post("http://localhost:11434/api/generate", json=payload)
        res = r.json()
        resp_text = res.get("response", "")
        print(f"use_format_json={use_format_json}, len={len(resp_text)}, response preview:\n{resp_text[:200]}")

async def main():
    q = "Explain Newton's first law with its mathematical representation and three real-life examples."
    context = "In simple terms, the First Law is “If external force on a body is zero, its acceleration is zero”."
    user_prompt = f"Textbook Context:\n{context}\n\nStudent Query:\n{q}"
    
    sys_prompt = """You are an expert AI STEM tutor for EduSim. Analyze the student's query and textbook context.
Respond with a JSON object with these keys:
- title: string
- queryType: string
- concepts: list of strings
- formulas: list of objects with formula, name, topic, meaning
- explanation: comprehensive markdown explanation with LaTeX math and 3 real-life examples
- summary: 2-3 sentence summary

Output ONLY valid JSON."""

    print("--- Test 1: format='json' ---")
    await test_ollama_format(True, sys_prompt, user_prompt)
    
    print("\n--- Test 2: format=None ---")
    await test_ollama_format(False, sys_prompt, user_prompt)

if __name__ == "__main__":
    asyncio.run(main())
