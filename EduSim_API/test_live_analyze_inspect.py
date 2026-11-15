import os
import sys
import asyncio
import json

api_dir = r"c:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API"
os.chdir(api_dir)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.src.modules.tutor.service import analyze_tutor_query

async def main():
    q = "Explain Newton's first law with its mathematical representation and three real-life examples."
    res = await analyze_tutor_query(q)
    print("Full result dump:")
    print("EXPLANATION LENGTH:", len(res.get("explanation", "")))
    print("EXPLANATION REPR:", repr(res.get("explanation", ""))[:500])
    print("AI_EXPLANATION REPR:", repr(res.get("ai_explanation", ""))[:500])
    print("SUMMARY REPR:", repr(res.get("summary", ""))[:200])

if __name__ == "__main__":
    asyncio.run(main())
