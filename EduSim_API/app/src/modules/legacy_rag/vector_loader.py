import logging
logger = logging.getLogger("EduSim.modules.legacy_rag.vector_loader")

import os
import faiss
import pickle
from pathlib import Path
from typing import Dict, Any, Tuple

from .embedder import get_embeddings
from .retriever import get_retriever
from .vector_store import INDEX_PATH, INDEX_FILE, METADATA_FILE, is_index_ready

VECTORSTORE_DIR = Path("vectorstore")

class VectorStoreManager:
    """
    Singleton manager for loading FAISS indices per subject globally on startup.
    Never load FAISS inside API endpoints!
    """
    _instance = None
    _is_loaded = False
    
    _indices: Dict[str, Any] = {}
    _metadata: Dict[str, list] = {}
    _retrievers: Dict[str, Any] = {}
    _embeddings_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance

    def load_all(self):
        """Load all subject indices from the vectorstore directory."""
        if self._is_loaded:
            return
            
        logger.info("\n=========================================")
        logger.info("Preloading FAISS Vector Databases")
        logger.info("=========================================")
        
        try:
            self._embeddings_model = get_embeddings()
        except Exception as e:
            logger.warning(f"Could not initialize embeddings model: {e}")
            self._is_loaded = True
            return

        loaded_subjects = []

        # 1. Check INDEX_PATH first
        if INDEX_FILE.exists() and METADATA_FILE.exists():
            try:
                logger.info(f"Loading FAISS index from {INDEX_PATH}...")
                index = faiss.read_index(str(INDEX_FILE))
                with open(METADATA_FILE, "rb") as f:
                    metadata = pickle.load(f)
                self._indices["physics"] = index
                self._metadata["physics"] = metadata
                self._retrievers["physics"] = get_retriever(
                    index, metadata, self._embeddings_model, k=5
                )
                loaded_subjects.append("physics")
            except Exception as e:
                logger.error(f"[ERROR] Failed to load index from {INDEX_PATH}: {e}")

        # 2. Check VECTORSTORE_DIR if exists
        if VECTORSTORE_DIR.exists():
            for subject_dir in VECTORSTORE_DIR.iterdir():
                if subject_dir.is_dir():
                    subject = subject_dir.name
                    index_path = subject_dir / "index.faiss"
                    meta_path = subject_dir / "index.pkl"
                    
                    if index_path.exists() and meta_path.exists() and subject not in self._retrievers:
                        try:
                            logger.info(f"Loading '{subject}' index...")
                            index = faiss.read_index(str(index_path))
                            with open(meta_path, "rb") as f:
                                metadata = pickle.load(f)
                                
                            self._indices[subject] = index
                            self._metadata[subject] = metadata
                            
                            self._retrievers[subject] = get_retriever(
                                index, metadata, self._embeddings_model, k=5
                            )
                            loaded_subjects.append(subject)
                        except Exception as e:
                            logger.error(f"[ERROR] Failed to load index for {subject}: {e}")

        if not loaded_subjects:
            logger.warning(
                f"[WARNING] FAISS vector index not found at {INDEX_PATH} or {VECTORSTORE_DIR}. "
                "RAG search endpoints will return 503 'index not built' until built."
            )
        else:
            logger.info(f"[SUCCESS] Successfully preloaded subjects: {', '.join(loaded_subjects)}")
            
        self._is_loaded = True

    def get_retriever(self, subject: str = None):

        """
        Get the preloaded retriever for a specific subject. 
        If subject is None or not found, defaults to 'physics' or the first available.
        """
        if not self._is_loaded:
            self.load_all()
            
        if not self._retrievers:
            return None
            
        if subject and subject in self._retrievers:
            return self._retrievers[subject]
            
        # Fallbacks
        if "physics" in self._retrievers:
            return self._retrievers["physics"]
            
        # Return first available
        first_subject = list(self._retrievers.keys())[0]
        return self._retrievers[first_subject]

# Global singleton instance
vector_store = VectorStoreManager()