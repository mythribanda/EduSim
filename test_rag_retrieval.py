import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "EduSim_API"))

import re
from app.src.modules.tutor.subject_classifier import detect_subject
from app.src.modules.tutor.service import get_rag_components, parse_class_name, expand_multilingual_query, detect_query_language

query = "Explain Newton's first law with its mathematical representation and three real-life examples."

lang = detect_query_language(query)
print("Language detected:", lang)
expanded = expand_multilingual_query(query, lang)
print("Expanded query:", expanded)
subj = detect_subject(expanded)
print("Subject detected:", subj)

retriever = get_rag_components(subject=subj, class_num=None)
print("Retriever obtained:", retriever)

if retriever:
    docs = retriever(expanded)
    print("Total docs retrieved:", len(docs))
    for i, doc in enumerate(docs):
        print(f"--- Doc {i+1} ---")
        print("Score:", doc.get("score"))
        print("Source:", doc.get("source"))
        print("Text snippet:", doc.get("text", "")[:200])
else:
    print("No retriever returned!")
