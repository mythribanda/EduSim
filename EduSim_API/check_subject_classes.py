import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store

vector_store.load_all()

# Check what classes exist for each subject
from collections import defaultdict
subject_classes = defaultdict(set)
subject_counts = defaultdict(int)

for meta in vector_store._unified_metadata:
    subj = meta.get("subject")
    cls = meta.get("class")
    subject_classes[subj].add(cls)
    subject_counts[subj] += 1

print("Subject distribution in index:")
for s, count in sorted(subject_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {count} chunks, classes: {sorted([c for c in subject_classes[s] if c is not None])}")
