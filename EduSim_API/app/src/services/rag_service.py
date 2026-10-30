import logging
import re
from typing import List, Dict, Any, Optional, Union
from app.src.modules.legacy_rag.vector_loader import vector_store

logger = logging.getLogger("EduSim.rag_service")

class RagService:
    @staticmethod
    def search_chunks(
        subject: str = "physics",
        chapter: Optional[Union[str, int]] = None,
        query: str = "",
        chapter_number: Optional[Union[int, str]] = None,
        chapter_title: Optional[str] = None,
        class_num: Optional[int] = None,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        # Map string subjects properly, fallback to physics if missing or unsupported
        subject = subject.lower() if subject else "physics"
        retriever = vector_store.get_retriever(subject)
        
        if not retriever:
            logger.info("No retriever found for subject '%s', falling back to physics", subject)
            retriever = vector_store.get_retriever("physics")
            
        if not retriever:
            return []

        # Resolve chapter parameters for backward compatibility
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
            class_num=class_num,
        )

        if not results:
            return []

        # Post-filter verification to guarantee exact chapter filtering even with fallback/mock retrievers
        if has_chapter_filter:
            filtered = []
            for r in results:
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

            return filtered[:k]

        return results[:k]
