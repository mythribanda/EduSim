"""
EduSim_API/tests/test_rag_auth.py
================================
Tests authentication requirements on RAG endpoints:
1. POST /api/rag/query without token -> 401
2. POST /api/rag/query with valid student token -> 200
3. POST /api/rag/query with valid teacher token -> 200
4. POST /api/rag/search without token -> 401
5. POST /api/rag/search with valid student token -> 200
6. POST /api/rag/search with valid teacher token -> 200
"""

import os
import sys
import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set required environment variables before imports
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
from main import app


@pytest.fixture(scope="module")
def rag_auth_context():
    """Setup in-memory SQLite database, test users, tokens, and test client."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    student = User(
        id=uuid.uuid4(),
        email="rag_student@test.com",
        name="RAG Student",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    teacher = User(
        id=uuid.uuid4(),
        email="rag_teacher@test.com",
        name="RAG Teacher",
        password_hash=hash_password("Password123!"),
        role="teacher",
        is_email_verified=True,
    )
    db.add_all([student, teacher])
    db.commit()

    student_token = create_access_token({"sub": str(student.id), "role": "student"})
    teacher_token = create_access_token({"sub": str(teacher.id), "role": "teacher"})

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "student_token": student_token,
        "teacher_token": teacher_token,
    }

    app.dependency_overrides.clear()


def test_rag_query_unauthenticated_returns_401(rag_auth_context):
    client = rag_auth_context["client"]
    resp = client.post("/api/rag/query", json={"query": "What is photosynthesis?"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_rag_query_with_student_token_returns_200(rag_auth_context):
    client = rag_auth_context["client"]
    token = rag_auth_context["student_token"]

    with patch("app.src.modules.legacy_rag.service.generate_response") as mock_gen:
        mock_gen.return_value = "Mocked answer for testing auth."
        resp = client.post(
            "/api/rag/query",
            json={"query": "What is photosynthesis?", "subject": "biology"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert "answer" in data


def test_rag_query_with_teacher_token_returns_200(rag_auth_context):
    client = rag_auth_context["client"]
    token = rag_auth_context["teacher_token"]

    with patch("app.src.modules.legacy_rag.service.generate_response") as mock_gen:
        mock_gen.return_value = "Mocked teacher answer."
        resp = client.post(
            "/api/rag/query",
            json={"query": "Explain Newton's laws of motion", "subject": "physics"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    assert "answer" in data


def test_rag_search_unauthenticated_returns_401(rag_auth_context):
    client = rag_auth_context["client"]
    resp = client.post("/api/rag/search", json={"query": "photosynthesis", "subject": "biology"})
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"


def test_rag_search_with_student_token_returns_200(rag_auth_context):
    client = rag_auth_context["client"]
    token = rag_auth_context["student_token"]

    resp = client.post(
        "/api/rag/search",
        json={"query": "photosynthesis", "subject": "biology"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "chunks" in data


def test_rag_search_with_teacher_token_returns_200(rag_auth_context):
    client = rag_auth_context["client"]
    token = rag_auth_context["teacher_token"]

    resp = client.post(
        "/api/rag/search",
        json={"query": "Newton's laws", "subject": "physics"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "chunks" in data
