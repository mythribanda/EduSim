"""
EduSim Legacy RAG — Embedder
============================
Encapsulates SentenceTransformer embedding generation.
Supports configurable model via EMBEDDING_MODEL env var (defaults to all-MiniLM-L6-v2).
Handles e5 instruction prefixes ('query: ' / 'passage: ') transparently.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Union

from sentence_transformers import SentenceTransformer

logger = logging.getLogger("EduSim.modules.legacy_rag.embedder")

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)
        self.is_e5 = "e5" in self.model_name.lower()
        logger.info(f"Initializing Embedder with model '{self.model_name}' (is_e5={self.is_e5})...")
        self.model = SentenceTransformer(self.model_name)

        if hasattr(self.model, "get_sentence_embedding_dimension"):
            self.dimension = self.model.get_sentence_embedding_dimension()
        elif hasattr(self.model, "get_embedding_dimension"):
            self.dimension = self.model.get_embedding_dimension()
        else:
            self.dimension = 384

    def encode(
        self,
        texts: Union[str, List[str]],
        convert_to_numpy: bool = True,
        is_query: bool = True,
        **kwargs: Any,
    ) -> Any:
        # Handle e5 instruction prefixes
        if self.is_e5:
            prefix = "query: " if is_query else "passage: "
            if isinstance(texts, str):
                if not texts.startswith("query: ") and not texts.startswith("passage: "):
                    texts = f"{prefix}{texts}"
            elif isinstance(texts, (list, tuple)):
                texts = [
                    f"{prefix}{t}"
                    if isinstance(t, str) and not t.startswith("query: ") and not t.startswith("passage: ")
                    else t
                    for t in texts
                ]

        return self.model.encode(
            texts,
            convert_to_numpy=convert_to_numpy,
            **kwargs,
        )


def get_embeddings(model_name: str | None = None) -> Embedder:
    return Embedder(model_name=model_name)
