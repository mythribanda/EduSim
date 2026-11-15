import os
import sys
import asyncio
import json

api_dir = r"c:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API"
os.chdir(api_dir)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.src.services.ai_router import call_ai

async def main():
    q = "Explain Newton's first law with its mathematical representation and three real-life examples."
    res = await call_ai(
        prompt=f"Student Query:\n{q}",
        system_prompt="You MUST respond ONLY with a valid JSON object with keys: title, queryType, concepts, formulas, explanation, summary.",
        response_format={"type": "json_object"}
    )
    print("RES KEYS:", list(res.keys()))
    print("PROVIDER:", res.get("provider"))
    print("TOKENS:", res.get("tokens_used"))
    print("RAW TEXT LENGTH:", len(res.get("text", "")))
    print("RAW TEXT:")
    print(res.get("text", ""))

if __name__ == "__main__":
    asyncio.run(main())
