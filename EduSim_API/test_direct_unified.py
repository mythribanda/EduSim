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
    resp = await unified_tutor_generation_async(
        query=q,
        context="In simple terms, the First Law is “If external force on a body is zero, its acceleration is zero”.",
        fallback_mode=False
    )
    print("KEYS:", list(resp.keys()))
    print("TITLE:", repr(resp.get("title")))
    print("CONCEPTS:", resp.get("concepts"))
    print("FORMULA:", repr(resp.get("formula")))
    print("EXPLANATION REPR:", repr(resp.get("explanation")))
    print("STATUS:", resp.get("generation_status"))
    print("FAILED:", resp.get("generation_failed"))
    print("STATUS_CODE:", resp.get("status_code"))
    print("ERROR_TYPE:", resp.get("error_type"))
    print("PROVIDER:", resp.get("provider"))
    print("TOKENS_USED:", resp.get("tokens_used"))

if __name__ == "__main__":
    asyncio.run(main())
