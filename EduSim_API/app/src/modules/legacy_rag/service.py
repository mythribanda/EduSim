import logging
from typing import Dict, Any, Optional
from .vector_loader import vector_store
from .generator import generate_response
from .retriever import normalize_subject
from app.src.config.similarity import get_similarity_threshold, evaluate_retrieval_confidence

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
        model_name = getattr(vector_store._embeddings_model, "model_name", None)
        threshold = get_similarity_threshold(model_name)

        norm_subject = normalize_subject(subject) if subject else None
        subject_fallback = False
        valid_subjects = vector_store.get_valid_subjects()
        if norm_subject and valid_subjects and norm_subject not in valid_subjects:
            logger.warning(
                f"[RAG] Subject '{subject}' (normalized: '{norm_subject}') not found in vector index. Falling back to unfiltered retrieval."
            )
            norm_subject = None
            subject_fallback = True

        # 1. Retrieve documents using unified vector store with metadata filtering
        raw_results = vector_store.retrieve(
            query=query,
            k=5,
            class_num=class_num,
            subject=norm_subject,
            board=board,
            book_code=book_code,
            min_score=0.0,
        )

        is_confident, reason = evaluate_retrieval_confidence(raw_results, threshold=threshold)

        # 2. Refuse immediately if no chunks pass threshold / relative confidence
        if not is_confident:
            logger.info(
                f"[RAG] Retrieval refused ({reason}) for query='{query[:50]}'. "
                "Refusing immediately without calling LLM."
            )
            return {
                "answer": REFUSAL_MESSAGE,
                "sources": [],
                "context": [],
                "fallback_mode": True,
                "subject_fallback": subject_fallback,
            }

        # Filter chunks that are sufficiently relevant (score >= threshold or rescued)
        floor = max(0.20, threshold - 0.15) if "rescued" in reason else threshold
        results = [r for r in raw_results if float(r.get("score", 0.0)) >= floor]
        if not results:
            results = raw_results[:2]

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
            topic_str = s.get("topic_subtopic_path") or s.get("chapter")
            if topic_str:
                header += f"\n[TOPIC]: {topic_str}"
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
            "subject_fallback": subject_fallback,
        }

    except Exception as e:
        logger.error(f"Error in query_rag_service: {e}", exc_info=True)
        raise e
