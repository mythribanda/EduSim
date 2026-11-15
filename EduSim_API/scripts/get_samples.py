import json
import random
import fitz
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

def get_evidence():
    # 1. 10 random chunks
    chunk_files = glob.glob("EduSim_API/data/chunks/*.jsonl")
    all_chunks = []
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_chunks.append(json.loads(line))

    random.seed(42)
    sample_10 = random.sample(all_chunks, 10)
    
    with open("EduSim_API/data/sample_10_chunks.json", "w", encoding="utf-8") as f:
        json.dump(sample_10, f, indent=2)

    # 2. Formula chunks from keph107 and maths
    keph_chunks = []
    with open("EduSim_API/data/chunks/keph107.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            keph_chunks.append(json.loads(line))

    # find chunks with delta or Greek or formulas
    formula_chunks = []
    for c in keph_chunks:
        if any(sym in c["text"] for sym in ["Δ", "θ", "π", "×", "≡", "ω", "α", "β"]):
            formula_chunks.append(c)

    # also check a maths chapter
    math_chunks = []
    if os.path.exists("EduSim_API/data/chunks/lemh103.jsonl"):
        with open("EduSim_API/data/chunks/lemh103.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                math_chunks.append(json.loads(line))
    for c in math_chunks:
        if any(sym in c["text"] for sym in ["π", "√", "±", "≤", "≥", "≠", "²", "³"]):
            formula_chunks.append(c)

    with open("EduSim_API/data/formula_chunks.json", "w", encoding="utf-8") as f:
        json.dump(formula_chunks[:5], f, indent=2)

    print(f"Extracted 10 sample chunks and {len(formula_chunks[:5])} formula chunks")

if __name__ == "__main__":
    get_evidence()
