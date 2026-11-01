import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "EduSim_API"
pages_dir = API_DIR / "curriculum_pipeline" / "output" / "pages"
files = list(pages_dir.glob("gees101*.jsonl"))
print("Found page files for gees101:", files)

if files:
    with open(files[0], "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i > 5:
                break
            prec = json.loads(line)
            if prec.get("type") == "metadata":
                continue
            print(f"\n--- Page {prec.get('page_no')} ---")
            spans = prec.get("spans", [])
            # Print distinct font sizes and samples
            sizes = set()
            for sp in spans:
                sizes.add((sp.get("size"), sp.get("bold")))
            print(f"Font sizes: {sorted(sizes, reverse=True)[:8]}")
            for sp in spans:
                if sp.get("size", 0) > 11.0:
                    print(f"  [Size {sp.get('size')} bold={sp.get('bold')}]: {sp.get('text', '')[:60]}")
