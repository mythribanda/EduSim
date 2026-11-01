import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.create_embeddings")

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import faiss
import numpy as np
import pickle
import shutil

from .loader import load_pdf
from .splitter import split_docs
from .embedder import get_embeddings

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
VECTORSTORE_DIR = ROOT_DIR / "vectorstore"

def create_embeddings_for_subject(pdf_path: Path, subject: str, embeddings_model):
    logger.info("\n=========================================")
    logger.info(f"Processing Subject: {subject.upper()}")
    logger.info("=========================================")
    
    subject_dir = VECTORSTORE_DIR / subject
    
    # 1. Load PDF
    logger.info(f"[1/4] Loading PDF: {pdf_path.name}")
    try:
        docs = load_pdf(str(pdf_path))
    except Exception as e:
        logger.error(f"Error loading {pdf_path}: {e}")
        return
        
    if not docs:
        logger.info(f"No documents loaded for {subject}.")
        return

    # 2. Split Docs
    logger.info("[2/4] Splitting documents into chunks...")
    chunks = split_docs(docs)
    logger.info(f"      Total chunks: {len(chunks)}")
    
    texts = [chunk.page_content for chunk in chunks]

    # 3. Create Embeddings
    logger.info("[3/4] Generating embeddings...")
    embeddings = embeddings_model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    embeddings = embeddings.astype(np.float32)
    faiss.normalize_L2(embeddings)
    
    # 4. Create FAISS Index & Metadata
    logger.info("[4/4] Creating and saving FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    
    metadata = []
    for chunk in chunks:
        metadata.append({
            "text": chunk.page_content,
            "source": str(pdf_path.name),
            "subject": subject,
            "page": chunk.metadata.get("page", 0),
        })
        
    # Save to subject folder
    if subject_dir.exists():
        shutil.rmtree(subject_dir)
    subject_dir.mkdir(parents=True, exist_ok=True)
    
    faiss.write_index(index, str(subject_dir / "index.faiss"))
    with open(subject_dir / "index.pkl", "wb") as f:
        pickle.dump(metadata, f)
        
    logger.info(f"✓ Saved index for {subject} at {subject_dir}")

def main():
    logger.info("Initializing Embeddings Generator...")
    if not DATA_DIR.exists():
        logger.info(f"Data directory {DATA_DIR} not found.")
        return
        
    VECTORSTORE_DIR.mkdir(exist_ok=True)
    
    embeddings_model = get_embeddings()
    
    # Iterate through all PDFs in data/
    for file in os.listdir(DATA_DIR):
        if file.lower().endswith(".pdf"):
            subject = file.replace(".pd", "").lower()
            # If the filename has spaces/dashes, extract base subject if possible.
            # Example: "physics_grade9.pd" -> "physics". 
            # We'll just split by space or underscore and take the first word as a heuristic,
            # or just use the whole filename minus pdf.
            base_subject = subject.replace("-", " ").replace("_", " ").split()[0]
            if "math" in base_subject: base_subject = "maths" # Normalize
            
            pdf_path = DATA_DIR / file
            create_embeddings_for_subject(pdf_path, base_subject, embeddings_model)
            
    logger.info("\n✅ All embeddings created successfully.")

if __name__ == "__main__":
    main()