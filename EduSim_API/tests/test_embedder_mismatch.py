import json
import shutil
import tempfile
from pathlib import Path
import pytest
import faiss

from app.src.modules.legacy_rag.vector_loader import vector_store
import app.src.modules.legacy_rag.vector_loader as vl_module


class DummyEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dimension: int = 384):
        self.model_name = model_name
        self.dimension = dimension
        self.is_e5 = "e5" in model_name.lower()

    def encode(self, texts, **kwargs):
        import numpy as np
        if isinstance(texts, str):
            return np.zeros(self.dimension, dtype=np.float32)
        return np.zeros((len(texts), self.dimension), dtype=np.float32)


@pytest.fixture
def mock_index_dir(monkeypatch):
    """Creates a temporary index directory and points vector_loader to it."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_faiss_")).resolve()
    monkeypatch.setattr(vl_module, "INDEX_V2_DIR", tmp_dir)
    monkeypatch.setenv("FAISS_INDEX_V2_DIR", str(tmp_dir))
    
    # Default dummy embedder to avoid loading PyTorch / HF weights in unit tests
    monkeypatch.setattr(vl_module, "get_embeddings", lambda: DummyEmbedder("all-MiniLM-L6-v2", 384))
    
    # Reset singleton state
    vector_store._is_loaded = False
    vector_store._unified_index = None
    vector_store._unified_metadata = None
    vector_store._unified_retriever = None
    
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_embedder_mismatch_dimension_in_manifest(mock_index_dir, monkeypatch):
    """Vector loader should raise ValueError if manifest dimension does not match configured embedder."""
    # Create 384-dim faiss index
    index = faiss.IndexFlatIP(384)
    faiss.write_index(index, str(mock_index_dir / "index.faiss"))
    
    with open(mock_index_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([{"text": "sample text", "subject": "physics"}], f)
        
    # Write manifest with conflicting 1024 dimension
    manifest = {
        "model_name": "BAAI/bge-m3",
        "dimension": 1024,
        "vector_count": 1
    }
    with open(mock_index_dir / "index_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)
        
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        vector_store.load_all(force_reload=True)


def test_embedder_mismatch_model_name_in_manifest(mock_index_dir, monkeypatch):
    """Vector loader should raise ValueError if manifest model_name does not match configured embedder."""
    index = faiss.IndexFlatIP(384)
    faiss.write_index(index, str(mock_index_dir / "index.faiss"))
    
    with open(mock_index_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([{"text": "sample text", "subject": "physics"}], f)
        
    # Write manifest with matching dimension 384 but different model name
    manifest = {
        "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "dimension": 384,
        "vector_count": 1
    }
    with open(mock_index_dir / "index_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)
        
    with pytest.raises(ValueError, match="Embedding model mismatch"):
        vector_store.load_all(force_reload=True)


def test_embedder_mismatch_index_dim_without_manifest(mock_index_dir, monkeypatch):
    """Vector loader should check index.d directly even if manifest is missing."""
    # Create 768-dim faiss index
    index = faiss.IndexFlatIP(768)
    faiss.write_index(index, str(mock_index_dir / "index.faiss"))
    
    with open(mock_index_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([{"text": "sample text", "subject": "physics"}], f)
        
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        vector_store.load_all(force_reload=True)


def test_embedder_matching_manifest_succeeds(mock_index_dir, monkeypatch):
    """Vector loader should successfully load when model and dimension match."""
    index = faiss.IndexFlatIP(384)
    faiss.write_index(index, str(mock_index_dir / "index.faiss"))
    
    with open(mock_index_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump([{"text": "sample text", "subject": "physics", "class_num": 10}], f)
        
    manifest = {
        "model_name": "all-MiniLM-L6-v2",
        "dimension": 384,
        "vector_count": 1
    }
    with open(mock_index_dir / "index_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)
        
    vector_store.load_all(force_reload=True)
    assert vector_store.is_ready is True
    assert "physics" in vector_store.get_valid_subjects()
