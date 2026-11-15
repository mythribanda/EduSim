import os
import sys

# Ensure EduSim_API is in path
api_dir = r"c:\Users\Mythri Banda\Desktop\github projects\EduSim\EduSim_API"
os.chdir(api_dir)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from app.src.modules.tutor.service import (
    detect_query_language,
    expand_multilingual_query,
    detect_subject,
    get_rag_components
)

q = "Explain Newton's first law with its mathematical representation and three real-life examples."
lang = detect_query_language(q)
subj = detect_subject(q)
expanded = expand_multilingual_query(q, lang)
print("lang:", lang)
print("subj:", subj)
print("expanded:", expanded)

retriever = get_rag_components(subject=subj, class_num=None)
print("retriever:", retriever)
if retriever:
    docs = retriever(expanded)
    print(f"Docs returned: {len(docs)}")
    for i, d in enumerate(docs):
        print(f"Doc {i}: score={d.get('score')} source={d.get('source')} chapter={d.get('chapter')}")
        print(f"Text snippet: {d.get('text', '')[:100]}...\n")
