import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "EduSim_API"))

from app.src.modules.tutor.service import get_rag_components

query = "Explain Newton's first law with its mathematical representation and three real-life examples."

for c in [None, 9, 10, 11, 12]:
    r = get_rag_components(subject="physics", class_num=c)
    if r:
        docs = r(query)
        valid = [d for d in docs if d.get('score', 0) > 0.35]
        print(f"Class {c}: {len(docs)} docs, {len(valid)} valid (>0.35)")
        if valid:
            print(f"  Top doc: {valid[0].get('source')} score={valid[0].get('score')}")
    else:
        print(f"Class {c}: No retriever")
