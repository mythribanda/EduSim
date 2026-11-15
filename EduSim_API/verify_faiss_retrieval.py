import json
import sys
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.src.modules.legacy_rag.vector_loader import vector_store, get_index_dir

def main():
    print("=== FAISS INDEX V2 VERIFICATION ===")
    index_dir = get_index_dir()
    manifest_file = index_dir / "index_manifest.json"
    faiss_file = index_dir / "index.faiss"
    metadata_file = index_dir / "metadata.json"

    print(f"Index dir: {index_dir}")
    print(f"index.faiss exists: {faiss_file.exists()} ({faiss_file.stat().st_size} bytes)")
    print(f"metadata.json exists: {metadata_file.exists()} ({metadata_file.stat().st_size} bytes)")
    print(f"index_manifest.json exists: {manifest_file.exists()}")

    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            print("Manifest content:\n", json.dumps(manifest, indent=2))

    # Preload vector store
    vector_store.load_all()

    ntotal = vector_store._unified_index.ntotal if vector_store._unified_index else 0
    d = vector_store._unified_index.d if vector_store._unified_index else 0
    meta_len = len(vector_store._unified_metadata) if vector_store._unified_metadata else 0

    print(f"\nFAISS index.ntotal (vector count): {ntotal}")
    print(f"FAISS index.d (embedding dimension): {d}")
    print(f"Metadata entries count: {meta_len}")
    print(f"Valid indexed subjects ({len(vector_store.get_valid_subjects())}): {sorted(list(vector_store.get_valid_subjects()))}")

    assert ntotal == 17789, f"Expected 17789 vectors, got {ntotal}"
    assert meta_len == 17789, f"Expected 17789 metadata entries, got {meta_len}"
    assert d == 384, f"Expected 384 dimensions, got {d}"

    print("\nSample metadata record (item 0):")
    sample_item = vector_store._unified_metadata[0] if vector_store._unified_metadata else {}
    sample_summary = {k: sample_item.get(k) for k in [
        "chunk_id", "book_code", "book_title", "subject", "class", "chapter_number", "chapter_title", "source_file"
    ]}
    print(json.dumps(sample_summary, indent=2))

    # Test retrieval across 4 distinct subjects: Physics, Chemistry, Biology, Mathematics (+ Science)
    print("\n=== TESTING REAL TEXTBOOK RETRIEVAL ===")
    test_queries = [
        {
            "subject": "physics",
            "class_num": 11,
            "query": "What is Newton's second law of motion and momentum?"
        },
        {
            "subject": "chemistry",
            "class_num": 11,
            "query": "What is chemical bonding and molecular structure?"
        },
        {
            "subject": "biology",
            "class_num": 11,
            "query": "What is the cell theory and structure of eukaryotic plant cell?"
        },
        {
            "subject": "mathematics",
            "class_num": 10,
            "query": "What is the quadratic formula and roots of quadratic equation?"
        },
        {
            "subject": "science",
            "class_num": 9,
            "query": "What is universal law of gravitation and free fall?"
        }
    ]

    for tq in test_queries:
        print(f"\n--- Query: '{tq['query']}' | Subject: {tq['subject']} | Class: {tq['class_num']} ---")
        results = vector_store.retrieve(
            query=tq["query"],
            subject=tq["subject"],
            class_num=tq["class_num"],
            k=3,
            min_score=0.0
        )
        print(f"Retrieved {len(results)} chunks:")
        for idx, res in enumerate(results, 1):
            score = res.get("score")
            text_snippet = res.get("text", "")[:130].replace("\n", " ").encode("ascii", "replace").decode("ascii")
            print(f"  [{idx}] Score: {score:.4f} | Book: {res.get('book_title')} ({res.get('book_code')}) | Ch: {res.get('chapter_number')} - {res.get('chapter_title')} | Page: {res.get('page') or res.get('page_start')} | File: {res.get('source_file')}")
            print(f"      Text: {text_snippet}...")

    print("\nFAISS index verification and multi-subject retrieval completed successfully!")

if __name__ == "__main__":
    main()
