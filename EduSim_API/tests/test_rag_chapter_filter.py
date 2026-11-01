"""
EduSim_API/tests/test_rag_chapter_filter.py
===========================================
Tests proving the resolution of the silent chapter-filter bug:
1. Chapter filter by chapter_number (int and string) returns ONLY that chapter's chunks.
2. Chapter filter by chapter_title (case-insensitive substring) returns ONLY matching chunks.
3. Backward compatibility: passing "chapter" as an integer, digit string, "Chapter N", or title resolves properly.
4. Nonexistent chapter filter (number or title) returns an empty list [].
5. No filter returns chunks across chapters (behaves as before).
6. CurriculumRetriever pre-filters via IDSelectorBatch and sets legacy metadata keys ("chapter" and "chapter_title").
7. FastAPI endpoint /api/rag/search respects chapter_number, chapter_title, and legacy chapter parameters.
"""

import os
import sys
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["JWT_SECRET"] = "01234567890123456789012345678901"
os.environ["JWT_SECRET_KEY"] = "01234567890123456789012345678901"
os.environ["SUPABASE_URL"] = "https://qhdkgvthkktovccdyase.supabase.co"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.src.config.database import Base, get_db
from app.src.models.user import User
from app.src.utils.auth import create_access_token, hash_password
from app.src.modules.legacy_rag.retriever import CurriculumRetriever, normalize_subject, parse_class_name
from app.src.services.rag_service import RagService
from main import app


MOCK_CHUNKS: List[Dict[str, Any]] = [
    {
        "chunk_id": "phy_c1_001",
        "board": "NCERT",
        "class": 11,
        "subject": "physics",
        "book_code": "keph1",
        "book_title": "Physics Part 1",
        "chapter_number": "1",
        "chapter_title": "Units and Measurements",
        "text": "Measurement of physical quantities and SI units.",
        "score": 0.88,
    },
    {
        "chunk_id": "phy_c1_002",
        "board": "NCERT",
        "class": 11,
        "subject": "physics",
        "book_code": "keph1",
        "book_title": "Physics Part 1",
        "chapter_number": "1",
        "chapter_title": "Units and Measurements",
        "text": "Dimensional analysis and errors in measurement.",
        "score": 0.85,
    },
    {
        "chunk_id": "phy_c2_001",
        "board": "NCERT",
        "class": 11,
        "subject": "physics",
        "book_code": "keph1",
        "book_title": "Physics Part 1",
        "chapter_number": "2",
        "chapter_title": "Motion in a Straight Line",
        "text": "Position, path length, displacement and velocity.",
        "score": 0.91,
    },
    {
        "chunk_id": "phy_c2_002",
        "board": "NCERT",
        "class": 11,
        "subject": "physics",
        "book_code": "keph1",
        "book_title": "Physics Part 1",
        "chapter_number": "2",
        "chapter_title": "Motion in a Straight Line",
        "text": "Instantaneous velocity, acceleration, and kinematic equations.",
        "score": 0.89,
    },
    {
        "chunk_id": "phy_c3_001",
        "board": "NCERT",
        "class": 11,
        "subject": "physics",
        "book_code": "keph1",
        "book_title": "Physics Part 1",
        "chapter_number": "3",
        "chapter_title": "Motion in a Plane",
        "text": "Scalars, vectors, and projectile motion.",
        "score": 0.82,
    },
]


def test_rag_service_filter_by_chapter_number_int():
    """Verify chapter_number=2 returns only chunks from chapter 2."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(subject="physics", query="velocity", chapter_number=2)

    assert len(results) == 2
    assert all(r["chapter_number"] == "2" for r in results)
    assert all("Motion in a Straight Line" in r["chapter_title"] for r in results)


def test_rag_service_filter_by_chapter_number_str_backward_compat():
    """Verify legacy parameter chapter='2' resolves to chapter_number=2."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(subject="physics", chapter="2", query="velocity")

    assert len(results) == 2
    assert all(r["chapter_number"] == "2" for r in results)


def test_rag_service_filter_by_chapter_prefix_str_backward_compat():
    """Verify legacy parameter chapter='Chapter 2' resolves to chapter_number=2."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(subject="physics", chapter="Chapter 2", query="velocity")

    assert len(results) == 2
    assert all(r["chapter_number"] == "2" for r in results)


def test_rag_service_filter_by_chapter_title_exact_and_case_insensitive():
    """Verify chapter_title matches case-insensitively against chapter_title metadata."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(
            subject="physics",
            query="units",
            chapter_title="units and measurements",
        )

    assert len(results) == 2
    assert all(r["chapter_number"] == "1" for r in results)
    assert all("Units and Measurements" in r["chapter_title"] for r in results)


def test_rag_service_filter_by_chapter_title_legacy_arg():
    """Verify legacy chapter='Motion in a Plane' matches by title."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(
            subject="physics",
            chapter="Motion in a Plane",
            query="vectors",
        )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "phy_c3_001"
    assert results[0]["chapter_number"] == "3"


def test_rag_service_nonexistent_chapter_number_returns_empty():
    """Verify querying a nonexistent chapter number returns empty list []."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(subject="physics", query="motion", chapter_number=999)

    assert results == []


def test_rag_service_nonexistent_chapter_title_returns_empty():
    """Verify querying a nonexistent chapter title returns empty list []."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(
            subject="physics",
            query="motion",
            chapter_title="Nonexistent Cosmic String Theory 404",
        )

    assert results == []


def test_rag_service_no_filter_returns_all_chapters():
    """Verify omitting chapter filters returns chunks across chapters (behaves as before)."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        results = RagService.search_chunks(subject="physics", query="physics concepts")

    assert len(results) == 5
    chapter_numbers = {r["chapter_number"] for r in results}
    assert chapter_numbers == {"1", "2", "3"}


def test_curriculum_retriever_prefiltering_via_id_selector():
    """Unit test CurriculumRetriever pre-filtering using mock FAISS index."""
    mock_index = MagicMock()
    # Mock FAISS search returning distance matrix and index matrix for allowed ID
    mock_index.search.return_value = (
        np.array([[0.95]], dtype=np.float32),
        np.array([[2]], dtype=np.int64),  # index 2 corresponds to phy_c2_001
    )
    mock_index.ntotal = len(MOCK_CHUNKS)

    mock_embeddings = MagicMock()
    mock_embeddings.encode.return_value = np.zeros((384,), dtype=np.float32)

    retriever = CurriculumRetriever(
        index=mock_index,
        metadata=MOCK_CHUNKS,
        embeddings_model=mock_embeddings,
        default_k=5,
        default_threshold=0.3,
    )

    # 1. Retrieve with chapter_number=2
    res = retriever.retrieve("velocity", chapter_number=2)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "phy_c2_001"
    # Verify legacy keys set
    assert res[0]["chapter"] == "Motion in a Straight Line"
    assert res[0]["chapter_title"] == "Motion in a Straight Line"

    # Verify IDSelectorBatch was called with allowed IDs [2, 3] (chapter 2 rows)
    assert mock_index.search.called
    call_args, call_kwargs = mock_index.search.call_args
    params = call_kwargs.get("params") or call_args[2]
    assert params is not None

    # 2. Retrieve with nonexistent chapter -> empty without FAISS search
    mock_index.reset_mock()
    empty_res = retriever.retrieve("velocity", chapter_number=888)
    assert empty_res == []
    mock_index.search.assert_not_called()


@pytest.fixture(scope="module")
def api_test_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    user = User(
        id=uuid.uuid4(),
        email="rag_filter_tester@test.com",
        name="Filter Tester",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    db.add(user)
    db.commit()

    token = create_access_token({"sub": str(user.id), "role": "student"})

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {"client": client, "token": token}
    app.dependency_overrides.pop(get_db, None)


def test_api_rag_search_chapter_filtering(api_test_client):
    """Integration test: verify POST /api/rag/search endpoint with chapter filtering."""
    client = api_test_client["client"]
    token = api_test_client["token"]

    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever), \
         patch("app.src.api.rag_router.require_vector_index"):

        # 1. Search with chapter_number=2
        resp = client.post(
            "/api/rag/search",
            json={"subject": "physics", "chapter_number": 2, "query": "velocity"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chunks"]) == 2
        assert all(c["chapter_number"] == "2" for c in data["chunks"])

        # 2. Search with legacy chapter="1"
        resp = client.post(
            "/api/rag/search",
            json={"subject": "physics", "chapter": "1", "query": "units"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chunks"]) == 2
        assert all(c["chapter_number"] == "1" for c in data["chunks"])

        # 3. Search with nonexistent chapter
        resp = client.post(
            "/api/rag/search",
            json={"subject": "physics", "chapter_number": 999, "query": "units"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks"] == []

        # 4. Search with no chapter filter
        resp = client.post(
            "/api/rag/search",
            json={"subject": "physics", "query": "concepts"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["chunks"]) == 5


def test_subject_normalizer_and_aliases():
    """Verify subject aliases normalize to canonical metadata slugs."""
    assert normalize_subject("Maths") == "mathematics"
    assert normalize_subject("math") == "mathematics"
    assert normalize_subject("Social Science") == "social-science"
    assert normalize_subject("SST") == "social-science"
    assert normalize_subject("cs") == "computer-science"
    assert normalize_subject("Computer Science") == "computer-science"
    assert normalize_subject("Physics") == "physics"
    assert normalize_subject("unknown-subject") == "unknown-subject"
    assert normalize_subject(None) is None


def test_parse_class_name():
    """Verify class_name variations parse to integer grade numbers."""
    assert parse_class_name(10) == 10
    assert parse_class_name("10") == 10
    assert parse_class_name("Class 10") == 10
    assert parse_class_name("class 10th") == 10
    assert parse_class_name("10th") == 10
    assert parse_class_name("Grade 12") == 12
    assert parse_class_name("X") == 10
    assert parse_class_name("XII") == 12
    assert parse_class_name("ix") == 9
    assert parse_class_name("invalid") is None
    assert parse_class_name(None) is None


def test_rag_service_unknown_subject_triggers_fallback_and_warning(caplog):
    """Verify unknown subject logs a warning, falls back to unfiltered retrieval, and sets subject_fallback flag."""
    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_valid_subjects", return_value={"physics", "mathematics"}),          patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever) as mock_get_ret:
        
        with caplog.at_level("WARNING"):
            results = RagService.search_chunks(subject="Astrology", query="stars")

    assert getattr(results, "subject_fallback", False) is True
    assert len(results) == 5
    assert all(r.get("subject_fallback") is True for r in results)
    mock_get_ret.assert_called_with(None)
    assert any("Astrology" in record.message for record in caplog.records)


def test_rag_service_maths_alias_normalizes_to_mathematics():
    """Verify 'Maths' alias resolves to 'mathematics' retriever."""
    mock_retriever = MagicMock(return_value=[{"text": "mock math", "score": 0.9, "class": 10}])
    with patch("app.src.services.rag_service.vector_store.get_valid_subjects", return_value={"physics", "mathematics"}),          patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever) as mock_get_ret:
        
        results = RagService.search_chunks(subject="Maths", query="calculus")

    mock_get_ret.assert_called_with("mathematics")
    assert getattr(results, "subject_fallback", False) is False
    assert len(results) == 1


def test_rag_service_class_name_filter_respected():
    """Verify class_name ('Class 11' or '11th') is respected and filters results."""
    mock_chunks = [
        {"chunk_id": "c1", "class": 10, "text": "grade 10"},
        {"chunk_id": "c2", "class": 11, "text": "grade 11"},
    ]
    mock_retriever = MagicMock(return_value=mock_chunks)
    with patch("app.src.services.rag_service.vector_store.get_valid_subjects", return_value={"physics"}),          patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever):
        
        results = RagService.search_chunks(subject="physics", query="motion", class_name="Class 11")
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c2"

        # Also with Roman numeral
        results_x = RagService.search_chunks(subject="physics", query="motion", class_name="X")
        assert len(results_x) == 1
        assert results_x[0]["chunk_id"] == "c1"


def test_curriculum_retriever_inverted_index_filtering():
    """Verify CurriculumRetriever precomputes inverted index and filters by class and subject."""
    chunks = [
        {"chunk_id": "c1", "class": 9, "subject": "science", "board": "NCERT", "book_code": "b1", "text": "c1"},
        {"chunk_id": "c2", "class": 10, "subject": "science", "board": "NCERT", "book_code": "b1", "text": "c2"},
        {"chunk_id": "c3", "class": 10, "subject": "mathematics", "board": "NCERT", "book_code": "b2", "text": "c3"},
    ]
    mock_index = MagicMock()
    mock_index.search.return_value = (
        np.array([[0.95]], dtype=np.float32),
        np.array([[1]], dtype=np.int64),
    )
    mock_index.ntotal = len(chunks)

    mock_embeddings = MagicMock()
    mock_embeddings.encode.return_value = np.zeros((384,), dtype=np.float32)

    retriever = CurriculumRetriever(
        index=mock_index,
        metadata=chunks,
        embeddings_model=mock_embeddings,
    )

    # Inverted index check
    assert 10 in retriever._class_index
    assert "science" in retriever._subject_index
    assert retriever.valid_subjects == {"science", "mathematics"}

    # Intersected search for class 10 and science -> row 1 only
    res = retriever.retrieve("test", class_num=10, subject="science")
    assert len(res) == 1
    assert res[0]["chunk_id"] == "c2"


def test_api_rag_search_unknown_subject_and_class_name(api_test_client):
    """Verify /api/rag/search endpoint returns subject_fallback=True on unknown subject and respects class_name."""
    client = api_test_client["client"]
    token = api_test_client["token"]

    mock_retriever = MagicMock(return_value=list(MOCK_CHUNKS))
    with patch("app.src.services.rag_service.vector_store.get_valid_subjects", return_value={"physics"}),          patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever),          patch("app.src.api.rag_router.require_vector_index"):

        resp = client.post(
            "/api/rag/search",
            json={"subject": "QuantumWarping", "class_name": "11th", "query": "units"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("subject_fallback") is True
        assert len(data["chunks"]) == 5


def test_api_empty_result_messaging(api_test_client):
    """Verify empty result messaging across search and query endpoints."""
    client = api_test_client["client"]
    token = api_test_client["token"]

    # 1. /api/rag/search with no matching chunks
    mock_retriever = MagicMock(return_value=[])
    with patch("app.src.services.rag_service.vector_store.get_valid_subjects", return_value={"physics"}),          patch("app.src.services.rag_service.vector_store.get_retriever", return_value=mock_retriever),          patch("app.src.api.rag_router.require_vector_index"):

        resp = client.post(
            "/api/rag/search",
            json={"subject": "physics", "query": "nothing here"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks"] == []
        assert len(data["chunks"]) == 0

    # 2. /api/rag/query with no matching chunks -> returns standard refusal message without LLM call
    with patch("app.src.modules.legacy_rag.service.vector_store.get_valid_subjects", return_value={"physics"}),          patch("app.src.modules.legacy_rag.service.vector_store.retrieve", return_value=[]):

        resp = client.post(
            "/api/rag/query",
            json={"query": "something not in textbooks", "subject": "physics"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["answer"] == "I couldn't find this in the textbooks."
        assert data["sources"] == []
        assert data["fallback_mode"] is True


def test_vector_store_fails_loudly_when_index_missing():
    """Verify vector_store.load_all raises FileNotFoundError with clear message when index is missing."""
    import tempfile
    from pathlib import Path
    from app.src.modules.legacy_rag.vector_loader import VectorStoreManager

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.src.modules.legacy_rag.vector_loader.INDEX_V2_DIR", Path(tmpdir)):
            mgr = VectorStoreManager()
            with pytest.raises(FileNotFoundError) as exc_info:
                mgr.load_all(force_reload=True)

            assert "No FAISS vector index found" in str(exc_info.value)
            assert "rebuild_index.py" in str(exc_info.value)
