"""
EduSim Curriculum Retriever
===========================
Metadata-filtered semantic retrieval using FAISS IndexFlatIP and SentenceTransformers.

Supports filtering by:
  - class_num (int): e.g. 1, 10
  - subject (str): e.g. "mathematics", "science", "biology"
  - board (str): "NCERT" or "SSC"
  - book_code (str): e.g. "aejm1", "jesc1"

Filter Strategy:
  Builds a row-id allow-list from aligned metadata and queries FAISS using
  faiss.IDSelectorBatch within faiss.SearchParameters.
  
  Why faiss.IDSelectorBatch over post-filtering with oversampling:
  1. Guaranteed Recall / Exact Top-K: Post-filtering with oversampling can easily
     yield 0 hits if the target class/subject is a small percentage of the total corpus.
     IDSelectorBatch restricts the inner product search inside FAISS before ranking,
     guaranteeing exact top-k hits from only the filtered subset.
  2. Computational Efficiency: FAISS evaluates dot products only across allowed vectors
     without having to retrieve, sort, and throw away large arbitrary oversampled candidate sets.
  3. Zero Filter Leakage: It is mathematically impossible for out-of-filter items to be returned.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

import faiss
import numpy as np

logger = logging.getLogger("EduSim.modules.legacy_rag.retriever")


class CurriculumRetriever:
    """
    Unified metadata-filtered retriever for EduSim curriculum FAISS indices.
    """

    def __init__(
        self,
        index: faiss.Index,
        metadata: List[Dict[str, Any]],
        embeddings_model: Any,
        default_k: int = 5,
        default_threshold: Optional[float] = None,
    ):
        self.index = index
        self.metadata = metadata
        self.embeddings_model = embeddings_model
        self.default_k = default_k
        self.default_threshold = default_threshold

    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        board: Optional[str] = None,
        book_code: Optional[str] = None,
        chapter_number: Optional[Any] = None,
        chapter_title: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k chunks matching the semantic query and metadata filters.
        """
        if not query or not query.strip():
            return []

        search_k = k if k is not None else self.default_k

        # Determine similarity threshold
        env_threshold = os.getenv("RAG_SIMILARITY_THRESHOLD")
        if min_score is not None:
            threshold = float(min_score)
        elif self.default_threshold is not None:
            threshold = float(self.default_threshold)
        elif env_threshold is not None:
            try:
                threshold = float(env_threshold)
            except ValueError:
                threshold = 0.35
        else:
            threshold = 0.35

        try:
            # 1. Encode query
            query_embedding = self.embeddings_model.encode(
                query,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            query_embedding = (
                np.ascontiguousarray(query_embedding, dtype=np.float32)
                .reshape(1, -1)
            )
            faiss.normalize_L2(query_embedding)

            # 2. Check metadata filters
            has_filter = (
                class_num is not None
                or subject is not None
                or board is not None
                or book_code is not None
                or chapter_number is not None
                or (chapter_title is not None and bool(str(chapter_title).strip()))
            )

            if has_filter:
                norm_subj = subject.strip().lower() if subject else None
                norm_board = board.strip().upper() if board else None
                norm_bcode = book_code.strip().lower() if book_code else None
                target_cls = int(class_num) if class_num is not None else None

                target_cnum: Optional[str] = None
                if chapter_number is not None:
                    cnum_str = str(chapter_number).strip()
                    if cnum_str:
                        try:
                            target_cnum = str(int(cnum_str))
                        except ValueError:
                            target_cnum = cnum_str.lower()

                norm_ctitle: Optional[str] = None
                if chapter_title is not None and str(chapter_title).strip():
                    norm_ctitle = str(chapter_title).strip().lower()

                # Build row-id allow-list
                allow_ids: List[int] = []
                for idx, meta in enumerate(self.metadata):
                    if target_cls is not None and meta.get("class") != target_cls:
                        continue
                    if norm_subj is not None and str(meta.get("subject", "")).strip().lower() != norm_subj:
                        continue
                    if norm_board is not None and str(meta.get("board", "")).strip().upper() != norm_board:
                        continue
                    if norm_bcode is not None and str(meta.get("book_code", "")).strip().lower() != norm_bcode:
                        continue
                    if target_cnum is not None:
                        raw_cnum = meta.get("chapter_number")
                        if raw_cnum is None:
                            continue
                        meta_cnum_str = str(raw_cnum).strip()
                        matched_cnum = False
                        if meta_cnum_str == target_cnum:
                            matched_cnum = True
                        else:
                            try:
                                if int(meta_cnum_str) == int(target_cnum):
                                    matched_cnum = True
                            except ValueError:
                                if meta_cnum_str.lower() == target_cnum:
                                    matched_cnum = True
                        if not matched_cnum:
                            continue
                    if norm_ctitle is not None:
                        meta_title = str(meta.get("chapter_title") or meta.get("chapter") or "").strip().lower()
                        if not meta_title or (norm_ctitle not in meta_title and meta_title not in norm_ctitle):
                            continue
                    allow_ids.append(idx)

                if not allow_ids:
                    logger.info(
                        f"[RETRIEVER] Filter criteria matched 0 documents in index "
                        f"(class={class_num}, subject={subject}, board={board}, book={book_code}, "
                        f"chapter_number={chapter_number}, chapter_title={chapter_title})."
                    )
                    return []

                # Execute filtered FAISS search using IDSelectorBatch
                sel = faiss.IDSelectorBatch(allow_ids)
                params = faiss.SearchParameters(sel=sel)
                actual_k = min(search_k, len(allow_ids))
                distances, indices = self.index.search(query_embedding, actual_k, params=params)
            else:
                # Unfiltered search across entire index
                actual_k = min(search_k, self.index.ntotal)
                distances, indices = self.index.search(query_embedding, actual_k)

            # 3. Format results and apply similarity threshold
            results: List[Dict[str, Any]] = []
            for i, idx in enumerate(indices[0]):
                if idx < 0 or idx >= len(self.metadata):
                    continue

                score = float(distances[0][i])
                if score < threshold:
                    continue

                meta = self.metadata[idx].copy()
                meta["score"] = round(score, 4)
                # Ensure legacy keys are present for compatibility
                meta.setdefault("source", meta.get("source_pdf", ""))
                meta.setdefault("book", meta.get("book_code", ""))
                meta.setdefault("page", meta.get("page_start", 0))
                meta.setdefault("chapter", meta.get("chapter_title", ""))
                meta.setdefault("chapter_title", meta.get("chapter", ""))

                results.append(meta)

            return results

        except Exception as e:
            logger.error(f"[ERROR] Error during retrieval: {e}", exc_info=True)
            return []

    def __call__(self, query: str, k: Optional[int] = None, **kwargs) -> List[Dict[str, Any]]:
        return self.retrieve(query, k=k, **kwargs)


def get_retriever(
    index: faiss.Index,
    metadata: List[Dict[str, Any]],
    embeddings_model: Any,
    k: int = 5,
    threshold: Optional[float] = None,
    subject: Optional[str] = None,
    class_num: Optional[int] = None,
    board: Optional[str] = None,
    book_code: Optional[str] = None,
    chapter_number: Optional[Any] = None,
    chapter_title: Optional[str] = None,
) -> Callable[..., List[Dict[str, Any]]]:
    """
    Factory creating a retriever callable compatible with legacy interfaces
    while supporting metadata filtering.
    """
    retriever_obj = CurriculumRetriever(
        index=index,
        metadata=metadata,
        embeddings_model=embeddings_model,
        default_k=k,
        default_threshold=threshold,
    )

    def _retrieve_fn(q: str, **override_kwargs):
        filter_kwargs = {
            "subject": subject,
            "class_num": class_num,
            "board": board,
            "book_code": book_code,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
        }
        filter_kwargs.update(override_kwargs)
        return retriever_obj.retrieve(q, **filter_kwargs)

    return _retrieve_fn
