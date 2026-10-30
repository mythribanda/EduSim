"""
EduSim Legacy RAG — Vector Loader
=================================
Preloads and manages the unified FAISS vector index and metadata globally on startup.
Loads from EduSim_API/faiss_index_v2/ (index.faiss + metadata.json) with fallback to legacy.

Never loads FAISS inside API endpoints.
Provides unified semantic retrieval with full metadata filtering:
(class_num, subject, board, book_code, min_score).
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import faiss

from .embedder import get_embeddings
from .retriever import CurriculumRetriever, get_retriever

logger = logging.getLogger("EduSim.modules.legacy_rag.vector_loader")

EDUSIM_API_DIR = Path(__file__).resolve().parents[4]
INDEX_V2_DIR = Path(os.getenv("FAISS_INDEX_V2_DIR", str(EDUSIM_API_DIR / "faiss_index_v2")))
INDEX_V1_DIR = Path(os.getenv("FAISS_INDEX_DIR", str(EDUSIM_API_DIR / "faiss_index")))


class VectorStoreManager:
    """
    Singleton manager for loading FAISS index and metadata globally on startup.
    Supports unified multi-subject curriculum index with metadata filtering.
    """
    _instance = None
    _is_loaded = False

    _unified_index: Optional[faiss.Index] = None
    _unified_metadata: Optional[List[Dict[str, Any]]] = None
    _unified_retriever: Optional[CurriculumRetriever] = None
    _embeddings_model: Any = None
    _index_version: str = "none"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance

    def load_all(self, force_reload: bool = False):
        """Loads unified FAISS index and metadata into memory."""
        if self._is_loaded and not force_reload:
            return

        logger.info("\n=========================================")
        logger.info("Preloading FAISS Vector Database")
        logger.info("=========================================")

        try:
            self._embeddings_model = get_embeddings()
        except Exception as e:
            logger.warning(f"Could not initialize embeddings model: {e}")
            self._is_loaded = True
            return

        # 1. Prefer FAISS V2 (unified multi-subject curriculum index)
        v2_index_file = INDEX_V2_DIR / "index.faiss"
        v2_meta_file = INDEX_V2_DIR / "metadata.json"

        if v2_index_file.exists() and v2_meta_file.exists():
            try:
                logger.info(f"Loading FAISS V2 index from {INDEX_V2_DIR}...")
                index = faiss.read_index(str(v2_index_file))
                with open(v2_meta_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                self._unified_index = index
                self._unified_metadata = metadata
                self._unified_retriever = CurriculumRetriever(
                    index=index,
                    metadata=metadata,
                    embeddings_model=self._embeddings_model,
                    default_k=5,
                )
                self._index_version = "v2"
                self._is_loaded = True
                logger.info(
                    f"[SUCCESS] Loaded FAISS V2 index ({index.ntotal} vectors, "
                    f"{len(metadata)} metadata rows) across all subjects."
                )
                return
            except Exception as e:
                logger.error(f"[ERROR] Failed to load FAISS V2 index from {INDEX_V2_DIR}: {e}", exc_info=True)

        # 2. Fallback to legacy index (V1)
        v1_index_file = INDEX_V1_DIR / "index.faiss"
        v1_meta_file = INDEX_V1_DIR / "metadata.pkl"

        if v1_index_file.exists() and v1_meta_file.exists():
            try:
                logger.info(f"Loading legacy FAISS V1 index from {INDEX_V1_DIR}...")
                index = faiss.read_index(str(v1_index_file))
                with open(v1_meta_file, "rb") as f:
                    metadata = pickle.load(f)

                self._unified_index = index
                self._unified_metadata = metadata
                self._unified_retriever = CurriculumRetriever(
                    index=index,
                    metadata=metadata,
                    embeddings_model=self._embeddings_model,
                    default_k=5,
                )
                self._index_version = "v1"
                self._is_loaded = True
                logger.info(f"[SUCCESS] Loaded legacy FAISS V1 index ({index.ntotal} vectors).")
                return
            except Exception as e:
                logger.error(f"[ERROR] Failed to load legacy index from {INDEX_V1_DIR}: {e}", exc_info=True)

        logger.warning(
            f"[WARNING] No FAISS vector index found at {INDEX_V2_DIR} or {INDEX_V1_DIR}. "
            "RAG search endpoints will return 503 until index is built."
        )
        self._is_loaded = True

    def retrieve(
        self,
        query: str,
        k: int = 5,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        board: Optional[str] = None,
        book_code: Optional[str] = None,
        chapter_number: Optional[Any] = None,
        chapter_title: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Direct search interface on the unified vector store with metadata filtering.
        """
        if not self._is_loaded:
            self.load_all()

        if not self._unified_retriever:
            return []

        return self._unified_retriever.retrieve(
            query=query,
            k=k,
            class_num=class_num,
            subject=subject,
            board=board,
            book_code=book_code,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            min_score=min_score,
        )

    def get_retriever(
        self,
        subject: Optional[str] = None,
        class_num: Optional[int] = None,
        board: Optional[str] = None,
        book_code: Optional[str] = None,
        chapter_number: Optional[Any] = None,
        chapter_title: Optional[str] = None,
        k: int = 5,
    ) -> Optional[Callable[..., List[Dict[str, Any]]]]:
        """
        Returns a retriever callable configured with optional default subject/class filters.
        Fully backward compatible with legacy code that calls vector_store.get_retriever(subject).
        """
        if not self._is_loaded:
            self.load_all()

        if not self._unified_retriever:
            return None

        def _bound_retriever(q: str, **kwargs):
            filter_kwargs = {
                "subject": subject,
                "class_num": class_num,
                "board": board,
                "book_code": book_code,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "k": k,
            }
            filter_kwargs.update(kwargs)
            return self._unified_retriever.retrieve(q, **filter_kwargs)

        return _bound_retriever

    @property
    def is_ready(self) -> bool:
        if not self._is_loaded:
            self.load_all()
        return self._unified_retriever is not None


# Global singleton instance
vector_store = VectorStoreManager()
