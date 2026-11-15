from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.tutor.service import detect_query_language, expand_multilingual_query, get_rag_components
from app.src.modules.tutor.subject_classifier import detect_subject

vector_store.load_all()
query = "Explain Newton's first law with its mathematical representation and three real-life examples."
lang = detect_query_language(query)
expanded = expand_multilingual_query(query, lang)
subject = detect_subject(expanded)
print(f"Query: {query}")
print(f"Detected Lang: {lang}")
print(f"Expanded Query: {expanded}")
print(f"Detected Subject: {subject}")

# Check with subject='physics' and class_num=None
retriever = get_rag_components(subject=subject, class_num=None)
docs = retriever(expanded)
print(f"\nTotal docs returned (class_num=None): {len(docs)}")
for i, d in enumerate(docs):
    print(f"[{i}] Score: {d.get('score', 0):.4f} | Chapter: {d.get('chapter')} | Class: {d.get('class')} | Book: {d.get('book_title')}")
    print(f"    Text: {d.get('text', '')[:100]}...")

# What if class_num was passed from the request? (e.g. class_name="11" or None or from frontend)
print("\n--- Testing with class_num=11 ---")
retriever_11 = get_rag_components(subject=subject, class_num=11)
docs_11 = retriever_11(expanded)
print(f"Total docs returned (class_num=11): {len(docs_11)}")
for i, d in enumerate(docs_11):
    print(f"[{i}] Score: {d.get('score', 0):.4f} | Chapter: {d.get('chapter')} | Class: {d.get('class')}")
