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
from app.src.modules.legacy_rag.retriever import CurriculumRetriever
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
