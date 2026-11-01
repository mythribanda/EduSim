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
from .retriever import CurriculumRetriever, get_retriever, normalize_subject, parse_class_name
from typing import Set

logger = logging.getLogger("EduSim.modules.legacy_rag.vector_loader")

EDUSIM_API_DIR = Path(__file__).resolve().parents[4]
INDEX_V2_DIR = Path(os.getenv("FAISS_INDEX_V2_DIR", str(EDUSIM_API_DIR / "faiss_index_v2"))).resolve()

def get_index_dir() -> Path:
    return Path(os.getenv("FAISS_INDEX_V2_DIR", str(INDEX_V2_DIR))).resolve()


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

        # 1. Load FAISS V2 (unified multi-subject curriculum index)
        index_dir = get_index_dir()
        v2_index_file = index_dir / "index.faiss"
        v2_meta_file = index_dir / "metadata.json"
        manifest_file = index_dir / "index_manifest.json"

        if v2_index_file.exists() and v2_meta_file.exists():
            try:
                logger.info(f"Loading FAISS V2 index from {index_dir}...")
                index = faiss.read_index(str(v2_index_file))
                with open(v2_meta_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)

                # Validate index manifest and dimensions against configured embedder
                configured_model = getattr(self._embeddings_model, "model_name", "all-MiniLM-L6-v2")
                configured_dim = getattr(self._embeddings_model, "dimension", 384)

                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as mf:
                            manifest = json.load(mf)
                        manifest_model = manifest.get("model_name")
                        manifest_dim = manifest.get("dimension")

                        if manifest_dim is not None and manifest_dim != configured_dim:
                            raise ValueError(
                                f"[CRITICAL] Embedding dimension mismatch for index at {index_dir}: "
                                f"index was built with dimension {manifest_dim} ({manifest_model}), "
                                f"but configured embedder '{configured_model}' has dimension {configured_dim}. "
                                "Please re-index using 'python rebuild_index.py --model ...' or set EMBEDDING_MODEL to match."
                            )

                        if manifest_model and manifest_model != configured_model:
                            raise ValueError(
                                f"[CRITICAL] Embedding model mismatch for index at {index_dir}: "
                                f"index was built with model '{manifest_model}', "
                                f"but configured embedder is '{configured_model}'. "
                                "Please re-index using 'python rebuild_index.py --model ...' or set EMBEDDING_MODEL to match."
                            )
                    except ValueError:
                        raise
                    except Exception as e:
                        logger.warning(f"Could not parse index_manifest.json: {e}")

                if index.d != configured_dim:
                    raise ValueError(
                        f"[CRITICAL] Embedding dimension mismatch for index at {index_dir}: "
                        f"FAISS index dimension is {index.d}, but configured embedder '{configured_model}' "
                        f"produces {configured_dim}-dim vectors. "
                        "Please re-index using 'python rebuild_index.py --model ...' or set EMBEDDING_MODEL to match."
                    )

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
                subject_count = len(self.get_valid_subjects())
                logger.info(
                    f"[SUCCESS] Loaded FAISS index from {index_dir} "
                    f"(vectors: {index.ntotal}, subjects: {subject_count})."
                )
                return
            except Exception as e:
                logger.error(f"[ERROR] Failed to load FAISS V2 index from {index_dir}: {e}", exc_info=True)
                raise e

        # Fail loudly if no index is found
        err_msg = (
            f"[CRITICAL] No FAISS vector index found at {index_dir}. "
            f"Required files 'index.faiss' and 'metadata.json' are missing. "
            "Please build the index using 'python rebuild_index.py' or ensure "
            "FAISS_INDEX_V2_DIR points to a valid index directory."
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

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

    def get_valid_subjects(self) -> Set[str]:
        """Returns the set of valid subject slugs present in the loaded vector index."""
        if not self._is_loaded:
            self.load_all()
        if self._unified_retriever and hasattr(self._unified_retriever, "valid_subjects"):
            return self._unified_retriever.valid_subjects
        if self._unified_metadata:
            valid = set()
            for m in self._unified_metadata:
                s = m.get("subject")
                if s:
                    sn = normalize_subject(str(s))
                    if sn:
                        valid.add(sn)
            return valid
        return set()

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

        norm_subject = normalize_subject(subject) if subject else None

        def _bound_retriever(q: str, **kwargs):
            filter_kwargs = {
                "subject": norm_subject,
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
    def resolved_index_dir(self) -> str:
        return str(get_index_dir())

    @property
    def vector_count(self) -> int:
        return self._unified_index.ntotal if self._unified_index else 0

    @property
    def subject_count(self) -> int:
        return len(self.get_valid_subjects())

    @property
    def is_ready(self) -> bool:
        if not self._is_loaded:
            self.load_all()
        return self._unified_retriever is not None


# Global singleton instance
vector_store = VectorStoreManager()
