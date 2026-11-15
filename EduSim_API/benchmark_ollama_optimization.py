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
from app.src.services.ai_router import limit_context_budget

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

async def test_ollama_raw_options(name, prompt, system_prompt, options, num_ctx=2048):
    print(f"\n--- Testing Raw Ollama: {name} ---")
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "keep_alive": "24h",
        "format": "json",
        "options": {
            "num_ctx": num_ctx,
            "temperature": 0.2,
            **options
        }
    }
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
    elapsed = time.perf_counter() - t0

    if resp.status_code == 200:
        d = resp.json()
        total_dur_s = d.get("total_duration", 0) / 1e9
        load_dur_s = d.get("load_duration", 0) / 1e9
        prompt_eval_count = d.get("prompt_eval_count", 0)
        prompt_eval_dur_s = d.get("prompt_eval_duration", 0) / 1e9
        eval_count = d.get("eval_count", 0)
        eval_dur_s = d.get("eval_duration", 0) / 1e9
        
        prompt_tps = prompt_eval_count / prompt_eval_dur_s if prompt_eval_dur_s > 0 else 0
        eval_tps = eval_count / eval_dur_s if eval_dur_s > 0 else 0

        print(f"  Wall-clock Time: {elapsed:.2f}s")
        print(f"  Total Duration: {total_dur_s:.2f}s")
        print(f"  Model Load Time: {load_dur_s:.2f}s")
        print(f"  Prompt Eval: {prompt_eval_count} tokens in {prompt_eval_dur_s:.2f}s ({prompt_tps:.1f} tok/s)")
        print(f"  Generation: {eval_count} tokens in {eval_dur_s:.2f}s ({eval_tps:.1f} tok/s)")
        return {
            "name": name,
            "wall_time": round(elapsed, 2),
            "load_time": round(load_dur_s, 2),
            "prompt_tokens": prompt_eval_count,
            "prompt_time": round(prompt_eval_dur_s, 2),
            "prompt_tok_per_sec": round(prompt_tps, 1),
            "eval_tokens": eval_count,
            "eval_time": round(eval_dur_s, 2),
            "eval_tok_per_sec": round(eval_tps, 1),
        }
    else:
        print(f"  Failed: HTTP {resp.status_code}: {resp.text}")
        return {"name": name, "error": resp.status_code}

async def run_benchmark():
    print("=== PHASE 1: OLLAMA INFERENCE INVESTIGATION & BENCHMARK ===")
    
    # 1. Warm-up model
    print("\n[Step 1] Warming up model in RAM...")
    warmup_res = await test_ollama_raw_options(
        "Warmup Ping",
        "Hello",
        "Answer 'Ready' in json: {'status': 'Ready'}",
        options={"num_predict": 15},
        num_ctx=1024
    )

    # 2. Test Retrieval Latency
    print("\n[Step 2] Measuring Embedding & Retrieval Latency...")
    vector_store.load_all()
    t_ret_0 = time.perf_counter()
    chunks_4 = vector_store.retrieve(
        query="State Newton's second law of motion and write formula",
        subject="physics",
        class_num=11,
        k=4
    )
    t_ret_4 = time.perf_counter() - t_ret_0
    print(f"  Retrieval time for 4 chunks: {t_ret_4:.4f}s ({len(chunks_4)} chunks retrieved)")

    t_ret_0 = time.perf_counter()
    chunks_2 = vector_store.retrieve(
        query="State Newton's second law of motion and write formula",
        subject="physics",
        class_num=11,
        k=2
    )
    t_ret_2 = time.perf_counter() - t_ret_0
    print(f"  Retrieval time for 2 chunks: {t_ret_2:.4f}s ({len(chunks_2)} chunks retrieved)")

    context_4 = "\n\n---\n\n".join([c.get("text", "") for c in chunks_4])
    context_2 = "\n\n---\n\n".join([c.get("text", "") for c in chunks_2])

    system_prompt = (
        "You are an expert physics tutor. Explain clearly with formulas in standard JSON format: "
        "{'title': str, 'explanation': str, 'formulas': [{'formula': str, 'name': str}], 'concepts': [str]}."
    )
    prompt_query = "State Newton's second law of motion and explain its mathematical formula."

    # Baseline configuration (4 chunks, 4096 context, default threads, num_predict uncapped)
    p_baseline = f"Textbook Context:\n{context_4}\n\nStudent Query:\n{prompt_query}"
    res_baseline = await test_ollama_raw_options(
        "Baseline: 4 Chunks, num_ctx=4096, default threads",
        p_baseline,
        system_prompt,
        options={},
        num_ctx=4096
    )

    # Optimization A: 2 Chunks instead of 4 chunks, num_ctx=2048, num_predict=512
    p_opt_a = f"Textbook Context:\n{context_2}\n\nStudent Query:\n{prompt_query}"
    res_opt_a = await test_ollama_raw_options(
        "Optimized: 2 Chunks, num_ctx=2048, num_predict=512",
        p_opt_a,
        system_prompt,
        options={"num_predict": 512},
        num_ctx=2048
    )

    # Optimization B: 2 Chunks, num_ctx=2048, num_thread=8 (matching physical P/E cores)
    res_opt_b = await test_ollama_raw_options(
        "Optimized: 2 Chunks, num_ctx=2048, num_thread=8, num_predict=512",
        p_opt_a,
        system_prompt,
        options={"num_thread": 8, "num_predict": 512},
        num_ctx=2048
    )

    print("\n" + "=" * 70)
    print("BENCHMARK COMPARISON TABLE:")
    print("=" * 70)
    print(f"{'Configuration':<45} | {'Wall Time':<10} | {'Prompt Tok':<10} | {'Prompt Dur':<10} | {'Gen Tok':<8} | {'Gen Speed'}")
    print("-" * 105)
    for r in [res_baseline, res_opt_a, res_opt_b]:
        if "error" not in r:
            print(f"{r['name']:<45} | {r['wall_time']:<10.2f} | {r['prompt_tokens']:<10} | {r['prompt_time']:<10.2f} | {r['eval_tokens']:<8} | {r['eval_tok_per_sec']} t/s")

    with open(api_dir / "ollama_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump([res_baseline, res_opt_a, res_opt_b], f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
