import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.rebuild_index")

from .loader import load_all_pdfs
from .splitter import split_docs
from .embedder import get_embeddings
from .vector_store import create_vector_store, TEXTBOOKS_DIR, INDEX_PATH

def rebuild():
    logger.info("=========================================")
    logger.info("Rebuilding RAG Index")
    logger.info("=========================================")
    
    data_dir = str(TEXTBOOKS_DIR)
    
    logger.info(f"\n1. Loading all PDFs from {data_dir}...")
    docs = load_all_pdfs(data_dir)
    logger.info(f"Total documents loaded: {len(docs)}")
    
    if not docs:
        logger.info(f"No documents found in {data_dir}. Exiting.")
        return
        
    logger.info("\n2. Splitting documents into chunks...")
    chunks = split_docs(docs)
    logger.info(f"Total chunks created: {len(chunks)}")
    
    logger.info("\n3. Loading embedding model...")
    embeddings_model = get_embeddings()
    
    logger.info(f"\n4. Rebuilding vector store at {INDEX_PATH} (Force Rebuild)...")
    index, metadata = create_vector_store(chunks, embeddings_model, force_rebuild=True)
    
    logger.info("\n[REBUILD] Rebuild complete!")

if __name__ == "__main__":
    rebuild()
