import logging
import re
from typing import Optional, Union
from app.src.modules.legacy_rag.vector_loader import vector_store
from app.src.modules.legacy_rag.retriever import normalize_subject, parse_class_name

logger = logging.getLogger("EduSim.rag_service")


class SearchResultList(list):
    """
    Subclass of list that carries search metadata attributes (e.g. subject_fallback)
    while maintaining 100% backward compatibility as a native Python list.
    """
    def __init__(self, iterable=(), subject_fallback: bool = False):
        super().__init__(iterable)
        self.subject_fallback = subject_fallback


class RagService:
    @staticmethod
    def search_chunks(
        subject: Optional[str] = None,
        chapter: Optional[Union[str, int]] = None,
        query: str = "",
        chapter_number: Optional[Union[int, str]] = None,
        chapter_title: Optional[str] = None,
        class_name: Optional[Union[str, int]] = None,
        class_num: Optional[int] = None,
        k: int = 5,
    ) -> SearchResultList:
        # 1. Resolve class_num from class_name if not provided directly
        resolved_class = class_num
        if resolved_class is None and class_name is not None and str(class_name).strip():
            resolved_class = parse_class_name(class_name)

        # 2. Normalize subject and check against valid subjects in the index
        norm_subject = normalize_subject(subject) if subject else None
        if not norm_subject and query:
            from app.src.modules.tutor.subject_classifier import detect_subject
            detected = detect_subject(query)
            if detected:
                norm_subject = normalize_subject(detected)
        valid_subjects = vector_store.get_valid_subjects()
        subject_fallback = False

        if norm_subject:
            if valid_subjects and norm_subject not in valid_subjects:
                logger.warning(
                    "[RAG] Subject '%s' (normalized: '%s') not found in vector index. "
                    "Falling back to unfiltered retrieval.",
                    subject,
                    norm_subject,
                )
                subject_fallback = True
                search_subject = None
            else:
                search_subject = norm_subject
        else:
            search_subject = None

        retriever = vector_store.get_retriever(search_subject)
        if not retriever:
            return SearchResultList([], subject_fallback=subject_fallback)

        # 3. Resolve chapter parameters for backward compatibility
        resolved_cnum: Optional[int] = None
        if chapter_number is not None:
            try:
                resolved_cnum = int(chapter_number)
            except (ValueError, TypeError):
                resolved_cnum = None

        resolved_ctitle: Optional[str] = None
        if chapter_title and str(chapter_title).strip():
            resolved_ctitle = str(chapter_title).strip()

        # If legacy 'chapter' argument is provided and explicit fields were not given
        if chapter is not None and str(chapter).strip():
            c_val = str(chapter).strip()
            if resolved_cnum is None and resolved_ctitle is None:
                if isinstance(chapter, int) or c_val.isdigit():
                    resolved_cnum = int(c_val)
                else:
                    m = re.match(r"^chapter\s+(\d+)$", c_val, re.IGNORECASE)
                    if m:
                        resolved_cnum = int(m.group(1))
                    else:
                        resolved_ctitle = c_val

        has_chapter_filter = (resolved_cnum is not None) or (resolved_ctitle is not None)

        # Over-fetch when chapter filtering to guarantee sufficient candidates if a custom/mock retriever is used
        fetch_k = k * 5 if has_chapter_filter else k

        results = retriever(
            query,
            k=fetch_k,
            chapter_number=resolved_cnum,
            chapter_title=resolved_ctitle,
            class_num=resolved_class,
        )

        if not results:
            return SearchResultList([], subject_fallback=subject_fallback)

        # Post-filter verification to guarantee exact filtering even with fallback/mock retrievers
        has_post_filter = has_chapter_filter or (resolved_class is not None)
        filtered = []
        if has_post_filter:
            for r in results:
                # 0. Verify class if filter specified
                if resolved_class is not None:
                    raw_cls = r.get("class")
                    if raw_cls is not None:
                        try:
                            if int(raw_cls) != resolved_class:
                                continue
                        except (ValueError, TypeError):
                            continue

                # 1. Verify chapter_number if filter specified
                if resolved_cnum is not None:
                    raw_cnum = r.get("chapter_number")
                    if raw_cnum is not None:
                        try:
                            if int(raw_cnum) != resolved_cnum:
                                continue
                        except (ValueError, TypeError):
                            if str(raw_cnum).strip() != str(resolved_cnum):
                                continue
                    else:
                        continue

                # 2. Verify chapter_title if filter specified (case-insensitive match)
                if resolved_ctitle is not None:
                    norm_target = resolved_ctitle.lower()
                    chunk_title = str(r.get("chapter_title") or r.get("chapter") or "").lower()
                    if norm_target not in chunk_title and chunk_title not in norm_target:
                        continue

                filtered.append(r)
        else:
            filtered = list(results)

        final_chunks = filtered[:k]
        if subject_fallback:
            for c in final_chunks:
                c["subject_fallback"] = True

        return SearchResultList(final_chunks, subject_fallback=subject_fallback)
