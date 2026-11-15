import os
import sys
import asyncio
import json

api_dir = r"c:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API"
os.chdir(api_dir)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.src.services.ai_router import call_ai
from app.src.modules.tutor.service import unified_tutor_generation_async

async def main():
    q = "Explain Newton's first law with its mathematical representation and three real-life examples."
    context = "In simple terms, the First Law is “If external force on a body is zero, its acceleration is zero”."
    system_prompt = (
        "You are an expert AI STEM tutor for EduSim, an interactive learning platform.\n"
        "Analyze the user's question and any textbook context provided. Provide a comprehensive,\n"
        "pedagogically rigorous response formatted in clean Markdown with LaTeX math.\n\n"
        "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "title": "Clear descriptive title of the topic or law",\n'
        '  "queryType": "concept" | "formula" | "mixed",\n'
        '  "concepts": ["concise concept name 1", "concise concept name 2"],\n'
        '  "formulas": [\n'
        '    {"formula": "LaTeX formula string", "name": "Formula Name", "topic": "Topic", "meaning": "Explanation of variables"}\n'
        '  ],\n'
        '  "explanation": "Comprehensive pedagogical explanation formatted in clean Markdown with LaTeX math ($...$ for inline, $$...$$ for display). Include conceptual intuition, formula derivations/applications, real-world examples, and key takeaways.",\n'
        '  "summary": "Concise 2-3 sentence educational revision summary capturing the core concept, main formula, and learning outcome."\n'
        "}\n\n"
        "Guidelines:\n"
        "- If the query is completely unrelated to science, mathematics, or education (out of context), politely state in 'explanation' that you specialize in STEM education and leave formulas/concepts empty.\n"
        "- Ensure 'explanation' is rich, detailed, and clear.\n"
        "- Output ONLY valid parseable JSON. Do not prepend or append markdown text outside the JSON object."
    )
    user_prompt = f"Textbook Context:\n{context}\n\nStudent Query:\n{q}"

    ai_resp = await call_ai(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model="gemma3:4b",
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    print("ai_resp text length:", len(ai_resp.get("text", "")))
    print("ai_resp provider:", ai_resp.get("provider"))
    print("ai_resp text repr:\n", repr(ai_resp.get("text", "")))

if __name__ == "__main__":
    asyncio.run(main())
