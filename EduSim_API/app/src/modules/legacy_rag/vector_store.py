import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.vector_store")

import faiss
import numpy as np
import pickle
import shutil
from pathlib import Path

import os
from pathlib import Path

# =========================================================
# VECTOR STORE PATHS
# =========================================================
EDUSIM_API_DIR = Path(__file__).resolve().parents[4]

FAISS_INDEX_DIR_ENV = os.getenv("FAISS_INDEX_DIR")
if FAISS_INDEX_DIR_ENV:
    INDEX_PATH = Path(FAISS_INDEX_DIR_ENV).resolve()
else:
    INDEX_PATH = (EDUSIM_API_DIR / "faiss_index").resolve()

TEXTBOOKS_DIR_ENV = os.getenv("TEXTBOOKS_DIR")
if TEXTBOOKS_DIR_ENV:
    TEXTBOOKS_DIR = Path(TEXTBOOKS_DIR_ENV).resolve()
else:
    TEXTBOOKS_DIR = (EDUSIM_API_DIR / "textbooks").resolve()

INDEX_FILE = INDEX_PATH / "index.faiss"
METADATA_FILE = INDEX_PATH / "metadata.pkl"


def is_index_ready() -> bool:
    """Check if the FAISS index and metadata files are present."""
    return INDEX_FILE.exists() and METADATA_FILE.exists()



# =========================================================
# CREATE / LOAD VECTOR STORE
# =========================================================
def create_vector_store(
    chunks,
    embeddings_model,
    force_rebuild=False
):
    """
    Create or load a FAISS vector store.

    Args:
        chunks: List of document chunks
        embeddings_model: SentenceTransformer model
        force_rebuild: If True, rebuild vector store

    Returns:
        (index, metadata)
    """

    # =====================================================
    # FORCE REBUILD
    # =====================================================
    if force_rebuild and INDEX_PATH.exists():

        import shutil

        logger.info("\n🔄 Force rebuilding FAISS index...")

        shutil.rmtree(INDEX_PATH)

    # =====================================================
    # LOAD EXISTING INDEX
    # =====================================================
    if INDEX_FILE.exists() and METADATA_FILE.exists():

        try:

            logger.info("\n✓ Loading existing FAISS index...")

            index = faiss.read_index(str(INDEX_FILE))
            with open(METADATA_FILE, "rb") as f:

                metadata = pickle.load(f)

            logger.info(f"✓ Loaded {len(metadata)} chunks")

            return index, metadata
        except Exception as e:

            logger.error(f"\n⚠ Failed to load existing index: {e}")

            logger.info("🔄 Rebuilding vector store...")

            import shutil

            shutil.rmtree(INDEX_PATH)

    # =====================================================
    # CREATE NEW INDEX
    # =====================================================
    logger.info("\n✓ Creating new FAISS index...")

    INDEX_PATH.mkdir(exist_ok=True)

    # =====================================================
    # EXTRACT TEXTS
    # =====================================================
    texts = [
        chunk.page_content
        for chunk in chunks
    ]

    logger.info(f"✓ Total chunks for embeddings: {len(texts)}")

    # =====================================================
    # CREATE EMBEDDINGS
    # =====================================================
    embeddings = embeddings_model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # =====================================================
    # CONVERT TO FLOAT32
    # =====================================================
    embeddings = embeddings.astype(np.float32)

    # =====================================================
    # NORMALIZE FOR COSINE SIMILARITY
    # =====================================================
    faiss.normalize_L2(embeddings)

    # =====================================================
    # CREATE FAISS INDEX
    # =====================================================
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    logger.info("✓ FAISS index created")

    # =====================================================
    # CREATE METADATA
    # =====================================================
    metadata = []

    for chunk in chunks:

        source = chunk.metadata.get("source", "")

        path_obj = Path(source)

        # =================================================
        # SUBJECT
        # =================================================
        # Example:
        # data/physics/mechanics.pdf
        # subject = physics
        # chapter = mechanics
        # =================================================
        subject = path_obj.parent.name.lower()

        # Fallback if PDFs are directly inside /data
        if subject == "data":
            subject = path_obj.stem.lower()

        chapter = path_obj.stem.lower()

        metadata.append({

            "text": chunk.page_content,

            "source": source,

            "subject": subject,

            "chapter": chapter,

            "page": chunk.metadata.get("page", 0),

        })

    # =====================================================
    # DEBUG SAMPLE
    # =====================================================
    if metadata:

        logger.info("\n===== SAMPLE METADATA =====")

        logger.info(f"Subject : {metadata[0]['subject']}")
        logger.info(f"Chapter : {metadata[0]['chapter']}")
        logger.info(f"Source  : {metadata[0]['source']}")
        logger.info(f"Page    : {metadata[0]['page']}")

        logger.info("-" * 50)

    # =====================================================
    # SAVE INDEX
    # =====================================================
    faiss.write_index(index, str(INDEX_FILE))

    with open(METADATA_FILE, "wb") as f:

        pickle.dump(metadata, f)

    # =====================================================
    # FINAL LOGS
    # =====================================================
    logger.info(f"\n✓ Saved FAISS index")

    logger.info(f"✓ Total indexed chunks: {len(metadata)}")

    return index, metadata