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
  Precomputes inverted indexes at load time (dict from class/subject/board/book_code -> np.array of row ids)
  and intersects them using NumPy, then queries FAISS using faiss.IDSelectorBatch.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Set, Union

import faiss
import numpy as np
from app.src.config.similarity import get_similarity_threshold

logger = logging.getLogger("EduSim.modules.legacy_rag.retriever")


# Comprehensive Subject Alias Mapping
SUBJECT_ALIASES: Dict[str, str] = {
    "math": "mathematics",
    "maths": "mathematics",
    "mathematics": "mathematics",
    "maths 1": "mathematics",
    "maths 2": "mathematics",
    "applied maths": "mathematics",
    "calc": "mathematics",
    "calculus": "mathematics",
    "algebra": "mathematics",
    "geometry": "mathematics",
    "social science": "social-science",
    "social-science": "social-science",
    "social_science": "social-science",
    "social studies": "social-science",
    "social-studies": "social-science",
    "sst": "social-science",
    "cs": "computer-science",
    "computer science": "computer-science",
    "computer-science": "computer-science",
    "computer_science": "computer-science",
    "comp sci": "computer-science",
    "it": "computer-science",
    "information technology": "computer-science",
    "business studies": "business-studies",
    "business-studies": "business-studies",
    "business_studies": "business-studies",
    "bst": "business-studies",
    "home science": "home-science",
    "home-science": "home-science",
    "home_science": "home-science",
    "political science": "political-science",
    "political-science": "political-science",
    "political_science": "political-science",
    "pol sci": "political-science",
    "polscience": "political-science",
    "civics": "political-science",
    "politics": "political-science",
    "bio": "biology",
    "biology": "biology",
    "chem": "chemistry",
    "chemistry": "chemistry",
    "phy": "physics",
    "physics": "physics",
    "physical science": "physics",
    "econ": "economics",
    "eco": "economics",
    "economics": "economics",
    "geo": "geography",
    "geography": "geography",
    "hist": "history",
    "history": "history",
    "psych": "psychology",
    "psychology": "psychology",
    "soc": "sociology",
    "sociology": "sociology",
    "evs": "evs",
    "environmental studies": "evs",
    "environmental science": "evs",
    "biotech": "biotechnology",
    "biotechnology": "biotechnology",
    "accountancy": "accountancy",
    "accounts": "accountancy",
}


def normalize_subject(subject: Optional[str]) -> Optional[str]:
    """
    Normalizes subject names to lowercase slugs matching index values
    (e.g., 'Maths' -> 'mathematics', 'Social Science' -> 'social-science').
    """
    if subject is None:
        return None
    raw = str(subject).strip()
    if not raw:
        return ""
    clean = raw.lower()
    if clean in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[clean]
    no_punct = re.sub(r"[-_]+", " ", clean).strip()
    if no_punct in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[no_punct]
    slug = re.sub(r"[\s_]+", "-", clean).strip("-")
    if slug in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[slug]
    return slug


ROMAN_TO_INT: Dict[str, int] = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
    "xi": 11,
    "xii": 12,
}


def parse_class_name(val: Any) -> Optional[int]:
    """
    Parses class representation from class_name ("Class 10", "10th", "X", 10) into an int.
    Returns None if unparseable or outside 1..12.
    """
    if val is None:
        return None
    if isinstance(val, int):
        return val if 1 <= val <= 12 else None
    s = str(val).strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None

    # Remove standard prefix like "class", "grade", "std", "standard"
    clean = re.sub(r"^(class|grade|std|standard)\s*[-:_]?\s*", "", s, flags=re.IGNORECASE).strip()

    # Digits with optional ordinal suffix (e.g. 10th, 1st, 2nd)
    m = re.match(r"^(\d+)(?:st|nd|rd|th)?(?:\s*(?:grade|class|standard|std))?$", clean, flags=re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 12 else None

    # Roman numerals (e.g. X, XII, IV)
    clean_lower = clean.lower()
    if clean_lower in ROMAN_TO_INT:
        return ROMAN_TO_INT[clean_lower]

    # Search for standalone number
    m2 = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", s, flags=re.IGNORECASE)
    if m2:
        n = int(m2.group(1))
        return n if 1 <= n <= 12 else None

    # Search for standalone roman numeral tokens
    for token in re.findall(r"\b[a-zA-Z]+\b", s):
        t_low = token.lower()
        if t_low in ROMAN_TO_INT:
            return ROMAN_TO_INT[t_low]

    return None


class CurriculumRetriever:
    """
    Unified metadata-filtered retriever for EduSim curriculum FAISS indices
    with precomputed inverted indexes for high-speed sub-millisecond filtering.
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

        # Precompute inverted indexes at load time
        class_map: Dict[int, List[int]] = {}
        subject_map: Dict[str, List[int]] = {}
        board_map: Dict[str, List[int]] = {}
        book_code_map: Dict[str, List[int]] = {}

        for idx, meta in enumerate(metadata):
            cls_val = meta.get("class")
            if cls_val is not None:
                try:
                    class_map.setdefault(int(cls_val), []).append(idx)
                except (ValueError, TypeError):
                    pass

            subj_val = meta.get("subject")
            if subj_val:
                s_norm = normalize_subject(str(subj_val))
                if s_norm:
                    subject_map.setdefault(s_norm, []).append(idx)

            board_val = meta.get("board")
            if board_val:
                b_norm = str(board_val).strip().upper()
                board_map.setdefault(b_norm, []).append(idx)

            bcode_val = meta.get("book_code")
            if bcode_val:
                bc_norm = str(bcode_val).strip().lower()
                book_code_map.setdefault(bc_norm, []).append(idx)

        self._class_index: Dict[int, np.ndarray] = {
            k: np.array(v, dtype=np.int64) for k, v in class_map.items()
        }
        self._subject_index: Dict[str, np.ndarray] = {
            k: np.array(v, dtype=np.int64) for k, v in subject_map.items()
        }
        self._board_index: Dict[str, np.ndarray] = {
            k: np.array(v, dtype=np.int64) for k, v in board_map.items()
        }
        self._book_code_index: Dict[str, np.ndarray] = {
            k: np.array(v, dtype=np.int64) for k, v in book_code_map.items()
        }

        self.valid_subjects: Set[str] = set(self._subject_index.keys())

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
        Retrieves top-k chunks matching semantic query and metadata filters
        via inverted index intersection and FAISS IDSelectorBatch.
        """
        if not query or not query.strip():
            return []

        search_k = k if k is not None else self.default_k

        # Determine similarity threshold
        if min_score is not None:
            threshold = float(min_score)
        elif self.default_threshold is not None:
            threshold = float(self.default_threshold)
        else:
            model_name = getattr(self.embeddings_model, "model_name", None)
            threshold = get_similarity_threshold(model_name)

        try:
            # 1. Encode query (with e5 query prefix if applicable)
            if hasattr(self.embeddings_model, "is_e5") and self.embeddings_model.is_e5:
                q_to_encode = f"query: {query}" if not query.startswith("query: ") else query
            elif "e5" in str(getattr(self.embeddings_model, "model_name", "")).lower():
                q_to_encode = f"query: {query}" if not query.startswith("query: ") else query
            else:
                q_to_encode = query

            query_embedding = self.embeddings_model.encode(
                q_to_encode,
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
                norm_subj = normalize_subject(subject) if subject else None
                norm_board = board.strip().upper() if board else None
                norm_bcode = book_code.strip().lower() if book_code else None
                target_cls = int(class_num) if class_num is not None else None

                # Intersect precomputed inverted indexes
                candidates: Optional[np.ndarray] = None

                if target_cls is not None:
                    cls_arr = self._class_index.get(target_cls)
                    if cls_arr is None or len(cls_arr) == 0:
                        logger.info(f"[RETRIEVER] Class {target_cls} matched 0 documents in index.")
                        return []
                    candidates = cls_arr

                if norm_subj is not None:
                    subj_arr = self._subject_index.get(norm_subj)
                    if subj_arr is None or len(subj_arr) == 0:
                        logger.info(f"[RETRIEVER] Subject '{norm_subj}' matched 0 documents in index.")
                        return []
                    if candidates is None:
                        candidates = subj_arr
                    else:
                        candidates = np.intersect1d(candidates, subj_arr, assume_unique=True)
                        if len(candidates) == 0:
                            return []

                if norm_board is not None:
                    board_arr = self._board_index.get(norm_board)
                    if board_arr is None or len(board_arr) == 0:
                        logger.info(f"[RETRIEVER] Board '{norm_board}' matched 0 documents in index.")
                        return []
                    if candidates is None:
                        candidates = board_arr
                    else:
                        candidates = np.intersect1d(candidates, board_arr, assume_unique=True)
                        if len(candidates) == 0:
                            return []

                if norm_bcode is not None:
                    bcode_arr = self._book_code_index.get(norm_bcode)
                    if bcode_arr is None or len(bcode_arr) == 0:
                        logger.info(f"[RETRIEVER] Book code '{norm_bcode}' matched 0 documents in index.")
                        return []
                    if candidates is None:
                        candidates = bcode_arr
                    else:
                        candidates = np.intersect1d(candidates, bcode_arr, assume_unique=True)
                        if len(candidates) == 0:
                            return []

                # If no primary filter matched, candidate list is all documents
                if candidates is None:
                    candidates_list = list(range(len(self.metadata)))
                else:
                    candidates_list = candidates.tolist()

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

                if target_cnum is not None or norm_ctitle is not None:
                    filtered_ids = []
                    for idx in candidates_list:
                        meta = self.metadata[idx]
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

                        filtered_ids.append(idx)
                    allow_ids = filtered_ids
                else:
                    allow_ids = candidates_list

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
