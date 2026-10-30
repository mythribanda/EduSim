import logging
import os
from typing import List, Dict, Any, Optional
from .vector_loader import vector_store
from .generator import generate_response

logger = logging.getLogger("EduSim.RAGService")

REFUSAL_MESSAGE = "I couldn't find this in the textbooks."

async def query_rag_service(
    query: str,
    subject: Optional[str] = None,
    class_num: Optional[int] = None,
    board: Optional[str] = None,
    book_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Core RAG service logic: retrieve context with metadata filters and generate grounded response.
    """
    try:
        threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.35"))

        # 1. Retrieve documents using unified vector store with metadata filtering
        results = vector_store.retrieve(
            query=query,
            k=5,
            class_num=class_num,
            subject=subject,
            board=board,
            book_code=book_code,
            min_score=threshold,
        )

        # 2. Refuse immediately if no chunks pass threshold
        if not results:
            logger.info(
                f"[RAG] No chunks passed similarity threshold ({threshold}) for query='{query[:50]}'. "
                "Refusing immediately without calling LLM."
            )
            return {
                "answer": REFUSAL_MESSAGE,
                "sources": [],
                "context": [],
                "fallback_mode": True,
            }

        # 3. Extract rich sources
        sources = []
        for r in results:
            book_title = r.get("book_title") or r.get("book_code") or r.get("book") or "unknown"
            ch_title = r.get("chapter_title") or r.get("chapter") or "unknown"
            sources.append({
                "book": book_title,
                "chapter": ch_title,
                "page": r.get("page_start", r.get("page", 0)),
                "score": round(float(r.get("score", 0.0)), 4),
                "board": r.get("board"),
                "class": r.get("class"),
                "subject": r.get("subject"),
                "topic_subtopic_path": r.get("topic_subtopic_path"),
            })

        # 4. Build context
        context_blocks = []
        for r, s in zip(results, sources):
            header = f"[BOOK]: {s['book']}\n[CHAPTER]: {s['chapter']}\n[PAGE]: {s['page']}"
            if s.get("topic_subtopic_path"):
                header += f"\n[TOPIC]: {s['topic_subtopic_path']}"
            context_blocks.append(f"{header}\n\n{r.get('text', '')}")

        context = "\n\n---\n\n".join(context_blocks)

        # 5. Generate response via local Ollama
        answer = await generate_response(
            context=context,
            question=query,
            fallback_mode=False,
        )

        return {
            "answer": answer,
            "sources": sources,
            "context": results,
            "fallback_mode": False,
        }

    except Exception as e:
        logger.error(f"Error in query_rag_service: {e}", exc_info=True)
        raise e
