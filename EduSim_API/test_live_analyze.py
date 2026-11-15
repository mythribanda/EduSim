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
    print("KEYS IN RES:", list(res.keys()))
    print("TITLE:", res.get("title"))
    print("QUERY_TYPE:", res.get("queryType"))
    print("CONCEPTS:", res.get("concepts"))
    print("FORMULA:", res.get("formula"))
    print("FORMULAS:", res.get("formulas"))
    print("RAG_CONTENT LEN:", len(res.get("ragContent", [])))
    print("SOURCES LEN:", len(res.get("sources", [])))
    print("EXPLANATION TYPE:", type(res.get("explanation")))
    print("EXPLANATION PREVIEW:", str(res.get("explanation"))[:300])
    print("STATUS:", res.get("generation_status"))

if __name__ == "__main__":
    asyncio.run(main())
