import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
BOOKS_DIR = API_DIR / "curriculum_pipeline" / "output" / "curriculum" / "books"

# Load index metadata
with open(API_DIR / "faiss_index_v2" / "metadata.json", "r", encoding="utf-8") as f:
    meta = json.load(f)

# Focus on the top gap subjects: social-science, english, mathematics, hindi, chemistry, history
target_subjects = ["social-science", "english", "mathematics", "hindi", "chemistry", "history"]

# Sample chapters for each subject
subj_books = defaultdict(lambda: defaultdict(list))
for m in meta:
    s = m.get("subject", "unknown")
    if s in target_subjects:
        b = m.get("book_code", "unknown")
        ch = str(m.get("chapter_number", "0"))
        subj_books[s][b].append(m)

print("=== DEEP DIAGNOSTIC: CHAPTERS & BOOK JSONS ===")

for s in target_subjects:
    print(f"\n==================== SUBJECT: {s} ====================")
    book_codes = list(subj_books[s].keys())[:4]
    for b in book_codes:
        book_json_path = BOOKS_DIR / f"{b}.json"
        has_book_json = book_json_path.exists()
        
        # Check chunks in index
        all_chunks = subj_books[s][b]
        chunks_by_ch = defaultdict(list)
        for c in all_chunks:
            chunks_by_ch[str(c.get("chapter_number", "0"))].append(c)
            
        print(f"\nBook {b} (book.json exists: {has_book_json}, total chunks: {len(all_chunks)}):")
        
        b_data = {}
        if has_book_json:
            with open(book_json_path, "r", encoding="utf-8") as bf:
                b_data = json.load(bf)
                
        b_chapters = {str(c.get("official_number") or idx+1): c for idx, c in enumerate(b_data.get("chapters", []))}
        
        for ch_num, ch_chunks in sorted(chunks_by_ch.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)[:3]:
            with_p = sum(1 for c in ch_chunks if c.get("topic_subtopic_path"))
            cov = with_p / len(ch_chunks) if ch_chunks else 0
            ch_node = b_chapters.get(ch_num)
            
            nodes_count = len(ch_node.get("nodes", [])) if ch_node else -1
            node_levels = [n.get("level") for n in ch_node.get("nodes", [])] if ch_node else []
            node_titles = [n.get("official_title") for n in ch_node.get("nodes", [])] if ch_node else []
            
            first_chunks_text = [c.get("text", "")[:70].replace("\n", " ") for c in ch_chunks[:2]]
            
            print(f"  Ch {ch_num} ({ch_chunks[0].get('chapter_title', '')[:30]}): {with_p}/{len(ch_chunks)} chunks with path ({cov*100:.0f}%) | book.json nodes: {nodes_count} (levels: {node_levels[:5]})")
            if node_titles:
                print(f"    Sample book.json node titles: {node_titles[:3]}")
            print(f"    Sample chunk 1: {first_chunks_text[0] if first_chunks_text else ''}")
