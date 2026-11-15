import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "EduSim_API"))

from app.src.modules.legacy_rag.vector_loader import vector_store

print("Vector store type:", type(vector_store))
if hasattr(vector_store, "metadata"):
    print("Total metadata chunks:", len(vector_store.metadata))
    # Count chunks per class and subject
    from collections import Counter
    classes = Counter()
    subjects = Counter()
    sources = Counter()
    for item in vector_store.metadata:
        c = item.get("class_num") or item.get("class")
        s = item.get("subject")
        src = item.get("source")
        classes[c] += 1
        subjects[s] += 1
        if "newton" in (item.get("text") or "").lower():
            sources[src] += 1
    print("Classes distribution:", classes)
    print("Subjects distribution:", subjects)
    print("Chunks containing 'newton':", sources)
