import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "EduSim_API"))

from app.src.modules.tutor.service import get_rag_components

query = "Explain Newton's first law with its mathematical representation and three real-life examples."

for subj in ["physics", "science", "Physics", "Science"]:
    for c in [None, 9, 10, 11]:
        r = get_rag_components(subject=subj, class_num=c)
        if r:
            docs = r(query)
            valid = [d for d in docs if d.get('score', 0) > 0.35]
            if valid:
                print(f"Subj={subj}, Class={c}: {len(valid)} valid docs. Top: {valid[0]['source']} ({valid[0]['score']:.4f})")
            else:
                print(f"Subj={subj}, Class={c}: 0 valid docs (total returned: {len(docs)})")
        else:
            print(f"Subj={subj}, Class={c}: No retriever")
