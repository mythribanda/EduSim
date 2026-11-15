import os
import sys
import json
import glob
import fitz

# Set stdout encoding to utf-8 safely
sys.stdout.reconfigure(encoding="utf-8")

def run_evidence():
    # 2. TELUGU & SSC CHECK
    with open("EduSim_API/data/manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    ssc_entries = [e for e in manifest if e["board"] == "SSC"]
    print(f"=== 2. TELUGU / SSC EXAMINATION (Total SSC: {len(ssc_entries)}) ===")
    
    telugu_candidates = []
    for e in ssc_entries:
        fn = os.path.basename(e["file_path"])
        fpath = os.path.join("EduSim_API", e["file_path"])
        doc = fitz.open(fpath)
        sample_lines = []
        total_chars = 0
        non_ascii_chars = 0
        for pno in range(min(5, len(doc))):
            t = doc[pno].get_text()
            for line in t.split("\n"):
                line_str = line.strip()
                if line_str and len(sample_lines) < 2:
                    sample_lines.append(line_str)
            for c in t:
                total_chars += 1
                if ord(c) > 127:
                    non_ascii_chars += 1
        doc.close()
        non_ascii_pct = (non_ascii_chars / total_chars * 100) if total_chars else 0
        
        # Check if telugu in name or flagged
        if "tel" in fn.lower() or "hindi" in fn.lower() or e.get("needs_ocr") or non_ascii_pct > 5.0:
            print(f"File: {fn}")
            print(f"  needs_ocr: {e.get('needs_ocr')}")
            print(f"  % non-ASCII: {non_ascii_pct:.2f}%")
            print(f"  Sample line 1: {sample_lines[0] if len(sample_lines)>0 else 'N/A'}")
            print(f"  Sample line 2: {sample_lines[1] if len(sample_lines)>1 else 'N/A'}")
            print()

    # 3. CHUNKS EVIDENCE
    print("=== 3. CHUNKS EVIDENCE ===")
    chunk_files = glob.glob("EduSim_API/data/chunks/*.jsonl")
    all_chunks = []
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    all_chunks.append(json.loads(line))
    
    print(f"Total trial chunks available: {len(all_chunks)}")

    # 6. TOKEN DISTRIBUTION
    tokens = [c["tokens"] for c in all_chunks]
    total = len(tokens)
    b_under_100 = sum(1 for t in tokens if t < 100)
    b_100_200 = sum(1 for t in tokens if 100 <= t < 200)
    b_200_300 = sum(1 for t in tokens if 200 <= t < 300)
    b_300_400 = sum(1 for t in tokens if 300 <= t < 400)
    b_400_450 = sum(1 for t in tokens if 400 <= t <= 450)
    b_under_150 = sum(1 for t in tokens if t < 150)

    print("\n=== 6. TOKEN DISTRIBUTION ===")
    print(f"  <100:     {b_under_100:4d} ({b_under_100/total*100:5.2f}%)")
    print(f"  100-200:  {b_100_200:4d} ({b_100_200/total*100:5.2f}%)")
    print(f"  200-300:  {b_200_300:4d} ({b_200_300/total*100:5.2f}%)")
    print(f"  300-400:  {b_300_400:4d} ({b_300_400/total*100:5.2f}%)")
    print(f"  400-450:  {b_400_450:4d} ({b_400_450/total*100:5.2f}%)")
    print(f"  <150:     {b_under_150:4d} ({b_under_150/total*100:5.2f}%)")

    sorted_by_len = sorted(all_chunks, key=lambda c: c["tokens"])
    print("\n5 Smallest Chunks:")
    for c in sorted_by_len[:5]:
        print(f"  ID: {c['chunk_id']} | Tokens: {c['tokens']} | File: {c['source_file']}")
        print(f"  Heading: {c['heading_path']}")
        print(f"  Text snippet: {repr(c['text'][:100])}")
        print()

    # 7. METADATA QUALITY
    print("\n=== 7. METADATA QUALITY ===")
    for k in ["chapter_title", "heading_path", "page_start", "subject", "class"]:
        non_empty = sum(1 for c in all_chunks if c.get(k) is not None and str(c.get(k)).strip() != "")
        pct = non_empty / total * 100
        print(f"  {k:15}: {non_empty:4d} / {total} ({pct:5.2f}%)")

if __name__ == "__main__":
    run_evidence()
