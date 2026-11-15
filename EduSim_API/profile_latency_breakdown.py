"""
Profile and reconcile Ollama latency breakdown across:
1. Benchmark mode (compact prompt, 200 tokens output)
2. Full AI Tutor mode (system prompt + simulation schema + textbook chunks, 500 tokens output)
3. Streaming mode (Time-To-First-Token and chunk distribution)
"""

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

import httpx
from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import analyze_tutor_query
from app.src.services.ai_router import OLLAMA_GENERATE_URL, call_ai_stream

async def run_latency_profile():
    print("=" * 80)
    print("PHASE 1: DETAILED INFERENCE LATENCY RECONCILIATION")
    print("=" * 80)
    
    vector_store.load_all()
    
    # 1. Hardware Inspection
    import platform
    print("\n[Hardware & System Environment]")
    print(f"  OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"  Processor: {platform.processor()}")
    print(f"  Machine: {platform.machine()}")
    print(f"  Python: {sys.version.split()[0]}")
    
    # 2. Benchmark Query Profile (compact prompt)
    compact_system = "You are a physics tutor. Explain clearly with formulas in standard JSON format: {'title': str, 'explanation': str, 'formulas': [{'formula': str, 'name': str}], 'concepts': [str]}."
    compact_prompt = "State Newton's second law of motion and explain its mathematical formula F=ma."
    
    print("\n[Mode A: Benchmark Profile (Compact Prompt & ~200 Tokens Output)]")
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(OLLAMA_GENERATE_URL, json={
            "model": "gemma3:4b",
            "prompt": compact_prompt,
            "system": compact_system,
            "stream": False,
            "keep_alive": "24h",
            "format": "json",
            "options": {
                "num_ctx": 2048,
                "num_thread": 8,
                "num_predict": 250,
                "temperature": 0.2
            }
        })
    wall_a = time.perf_counter() - t0
    
    data_a = resp.json()
    load_a = data_a.get("load_duration", 0) / 1e9
    pe_count_a = data_a.get("prompt_eval_count", 0)
    pe_dur_a = data_a.get("prompt_eval_duration", 0) / 1e9
    eval_count_a = data_a.get("eval_count", 0)
    eval_dur_a = data_a.get("eval_duration", 0) / 1e9
    total_dur_a = data_a.get("total_duration", 0) / 1e9
    pe_tps_a = pe_count_a / pe_dur_a if pe_dur_a > 0 else 0
    eval_tps_a = eval_count_a / eval_dur_a if eval_dur_a > 0 else 0
    
    print(f"  Wall-clock Time: {wall_a:.2f}s")
    print(f"  Model Load Time: {load_a:.2f}s")
    print(f"  Prompt Eval: {pe_count_a} tokens in {pe_dur_a:.2f}s ({pe_tps_a:.1f} tok/s) -> TTFT: {pe_dur_a:.2f}s")
    print(f"  Generation: {eval_count_a} tokens in {eval_dur_a:.2f}s ({eval_tps_a:.1f} tok/s)")
    
    # 3. Real Full AI Tutor Query Profile (unified tutor with 6-step simulation guide + 2 retrieved chunks)
    print("\n[Mode B: Real AI Tutor Profile (Full System Prompt + 2 Chunks + Simulation Schema)]")
    t_ret_0 = time.perf_counter()
    tutor_res = await analyze_tutor_query(
        query="State Newton's second law of motion and explain its mathematical formula.",
        subject="physics",
        class_name="11"
    )
    wall_b = time.perf_counter() - t_ret_0
    
    print(f"  Wall-clock Time: {wall_b:.2f}s")
    print(f"  Provider: {tutor_res.get('provider')}")
    print(f"  Sources Found: {len(tutor_res.get('sources', []))}")
    print(f"  Response Keys: {list(tutor_res.keys())}")
    
    # 4. Streaming Profile: Measure TTFT on Streaming
    print("\n[Mode C: Streaming Response Profile]")
    stream_prompt = "Explain why acceleration due to gravity is constant near Earth's surface."
    t_s0 = time.perf_counter()
    first_token_time = None
    token_count = 0
    
    async for chunk in call_ai_stream(stream_prompt, system_prompt="You are an expert tutor. Answer in 3 sentences."):
        if "data: " in chunk:
            try:
                d = json.loads(chunk.replace("data: ", "").strip())
                if d.get("content"):
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - t_s0
                    token_count += 1
            except Exception:
                pass
    wall_c = time.perf_counter() - t_s0
    print(f"  Stream Wall-clock Time: {wall_c:.2f}s")
    print(f"  Time To First Token (TTFT): {first_token_time:.2f}s" if first_token_time else "  TTFT: N/A")
    print(f"  Streamed Chunks Count: {token_count}")
    
    breakdown_report = {
        "benchmark_mode": {
            "wall_clock_sec": round(wall_a, 2),
            "model_load_sec": round(load_a, 2),
            "prompt_tokens": pe_count_a,
            "prompt_eval_sec": round(pe_dur_a, 2),
            "prompt_eval_tok_per_sec": round(pe_tps_a, 1),
            "ttft_sec": round(pe_dur_a, 2),
            "generation_tokens": eval_count_a,
            "generation_sec": round(eval_dur_a, 2),
            "generation_tok_per_sec": round(eval_tps_a, 1),
        },
        "full_tutor_mode": {
            "wall_clock_sec": round(wall_b, 2),
            "provider": tutor_res.get("provider"),
            "sources_count": len(tutor_res.get("sources", [])),
        },
        "streaming_mode": {
            "wall_clock_sec": round(wall_c, 2),
            "ttft_sec": round(first_token_time, 2) if first_token_time else None,
            "tokens_streamed": token_count,
        }
    }
    
    with open(api_dir / "latency_reconciliation_report.json", "w", encoding="utf-8") as f:
        json.dump(breakdown_report, f, indent=2)
    print("\nProfile report written to latency_reconciliation_report.json")

if __name__ == "__main__":
    asyncio.run(run_latency_profile())
