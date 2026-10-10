import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.loader")

import os
from .vector_store import TEXTBOOKS_DIR
from langchain_community.document_loaders import PyPDFLoader

def load_pdf(pdf_path: str):
    """Load a single PDF document."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")
    
    try:
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        logger.info(f"[LOADER] Loaded {len(docs)} pages from {os.path.basename(pdf_path)}")
        return docs
    except Exception as e:
        raise Exception(f"Error loading {pdf_path}: {e}")

def load_all_pdfs(directory_path: str = None):
    """Load all PDF documents from a directory."""
    if directory_path is None:
        directory_path = str(TEXTBOOKS_DIR)
    all_docs = []
    if not os.path.isdir(directory_path):
        logger.warning(f"[LOADER] Directory not found: {directory_path}")
        return []

        
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(directory_path, filename)
            try:
                docs = load_pdf(pdf_path)
                all_docs.extend(docs)
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
                
    if not all_docs:
        logger.warning("[LOADER] Warning: No PDFs found or loaded in the directory.")
        
    return all_docs

# Alias for backward compatibility if needed
load_pdfs = load_all_pdfs