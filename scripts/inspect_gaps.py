import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
sys.path.insert(0, str(API_DIR))

# Load chunks from index metadata
with open(API_DIR / "faiss_index_v2" / "metadata.json", "r", encoding="utf-8") as f:
    meta = json.load(f)

print(f"Total chunks in faiss_index_v2: {len(meta)}")
with_path = sum(1 for m in meta if m.get("topic_subtopic_path"))
print(f"With topic_subtopic_path: {with_path} ({with_path/len(meta)*100:.1f}%)")
print(f"Without topic_subtopic_path: {len(meta) - with_path} ({(len(meta)-with_path)/len(meta)*100:.1f}%)")

# Group by subject -> book_code -> chapter_number
chapter_chunks = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
for m in meta:
    s = m.get("subject", "unknown")
    b = m.get("book_code", "unknown")
    ch = str(m.get("chapter_number", "0"))
    chapter_chunks[s][b][ch].append(m)

# Classify chapters: 0% coverage vs partial vs 100%
zero_cov = defaultdict(list)
partial_cov = defaultdict(list)
full_cov = defaultdict(list)

for s, books in chapter_chunks.items():
    for b, chapters in books.items():
        for ch, chunks in chapters.items():
            tot = len(chunks)
            has_p = sum(1 for c in chunks if c.get("topic_subtopic_path"))
            cov = has_p / tot if tot else 0.0
            info = {
                "subject": s,
                "book_code": b,
                "chapter_number": ch,
                "chapter_title": chunks[0].get("chapter_title", ""),
                "total_chunks": tot,
                "chunks_with_path": has_p,
                "coverage": cov,
                "chunks": chunks,
            }
            if cov == 0.0:
                zero_cov[s].append(info)
            elif cov < 1.0:
                partial_cov[s].append(info)
            else:
                full_cov[s].append(info)

print("\n=== SUMMARY BY SUBJECT ===")
all_subjects = sorted(set(list(zero_cov.keys()) + list(partial_cov.keys()) + list(full_cov.keys())))
for s in all_subjects:
    z_count = len(zero_cov[s])
    p_count = len(partial_cov[s])
    f_count = len(full_cov[s])
    total_ch = z_count + p_count + f_count
    
    # Chunk stats
    total_chunks = sum(c["total_chunks"] for c in zero_cov[s] + partial_cov[s] + full_cov[s])
    missing_chunks = sum(c["total_chunks"] - c["chunks_with_path"] for c in zero_cov[s] + partial_cov[s] + full_cov[s])
    print(f"{s:<18}: Missing {missing_chunks:>4}/{total_chunks:>5} chunks ({missing_chunks/total_chunks*100:>5.1f}%) | Chapters: {z_count} zero, {p_count} partial, {f_count} full ({total_ch} total)")
