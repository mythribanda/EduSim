import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
sys.path.insert(0, str(API_DIR))

from curriculum_pipeline.extractor_engine import CurriculumExtractorEngine

engine = CurriculumExtractorEngine(resume=False)
inventory_csv = API_DIR / "curriculum_pipeline" / "output" / "inventory" / "textbooks_inventory.csv"

import csv
file_entries = []
with open(inventory_csv, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for r in reader:
        if r.get("file", "").startswith("lemh2"):
            file_entries.append(r)

print(f"Found {len(file_entries)} entries for lemh2")
if file_entries:
    review_q = []
    book_info = {
        "book_code": "lemh2",
        "class": 12,
        "subject": "mathematics",
        "medium": "en",
        "book_title": "Mathematics Part II",
    }
    res = engine.process_ncert_book(book_info, file_entries, review_q)
    print("Result status:", res.get("status"), "chapters:", len(res.get("chapters", [])))
    for ch in res.get("chapters", []):
        nodes = ch.get("nodes", [])
        topics = [n for n in nodes if n.get("level") == "topic"]
        print(f"  Ch {ch.get('official_number')} ({ch.get('official_title')}): {len(nodes)} total nodes ({len(topics)} topics)")
        if topics:
            print(f"    Sample topics: {[t.get('official_title') for t in topics[:3]]}")
