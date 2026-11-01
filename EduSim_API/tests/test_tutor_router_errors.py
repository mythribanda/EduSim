"""
Tests for tutor router error handling:
(a) When the mocked LLM returns no "summary", /api/tutor/analyze returns 200, not 500.
(b) When a handler raises, the response is JSON 500 AND includes the Access-Control-Allow-Origin header
    for Origin http://localhost:8080.
"""

import os
import sys
import uuid
from unittest.mock import AsyncMock, patch
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
def tutor_error_context():
    """Setup in-memory SQLite database, test user, auth token, and test client."""
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
        email="tutor_student@test.com",
        name="Tutor Student",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    db.add(student)
    db.commit()

    token = create_access_token({"sub": str(student.id), "role": "student"})

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    yield {
        "client": client,
        "token": token,
        "student": student,
    }

    app.dependency_overrides.clear()


def test_tutor_analyze_no_summary_returns_200(tutor_error_context):
    """
    (a) When the mocked LLM response does not include a 'summary' key,
    tutor_router must deterministically generate a learning summary and return 200, not 500.
    """
    client = tutor_error_context["client"]
    token = tutor_error_context["token"]

    mocked_controller_result = {
        "success": True,
        "data": {
            "title": "Newton's Second Law",
            "description": "What is Newton's second law?",
            "formula": "F = ma",
            "related_concepts": ["Force", "Mass", "Acceleration"],
            "related_formulas": [
                {
                    "formula": "F = ma",
                    "name": "Newton's Second Law",
                    "topic": "Classical Mechanics",
                    "meaning": "Force equals mass times acceleration",
                }
            ],
            "explanation": (
                "Newton's second law describes the relationship between an object's mass and the amount "
                "of force needed to accelerate it. It is commonly expressed as F = ma."
            ),
            "ragContent": [],
            "simulation_guide": {"is_buildable": True},
            # Note: No 'summary' key here to reproduce the missing summary condition
        },
        "generation_status": "success",
        "provider": "openrouter",
        "tokens_used": 150,
    }

    with patch(
        "app.src.api.tutor_router.analyze_tutor_controller",
        new=AsyncMock(return_value=mocked_controller_result),
    ):
        response = client.post(
            "/api/tutor/analyze",
            json={"query": "What is Newton's second law?"},
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "http://localhost:8080",
            },
        )

    assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.text}"
    body = response.json()
    assert body.get("success") is True
    assert "data" in body
    assert body["data"]["formula"] == "F = ma"
    assert "Newton's second law" in body["data"]["explanation"]


def test_unhandled_exception_returns_500_with_cors_header(tutor_error_context):
    """
    (b) When a handler raises an unhandled exception, CatchAllExceptionsMiddleware converts it
    to JSON 500 and outermost CORSMiddleware attaches Access-Control-Allow-Origin for Origin http://localhost:8080.
    """
    client = tutor_error_context["client"]

    with patch(
        "app.src.api.tutor_router.analyze_tutor_controller",
        side_effect=RuntimeError("Simulated unhandled tutor handler failure"),
    ):
        response = client.post(
            "/api/tutor/analyze",
            json={"query": "What is Newton's second law?"},
            headers={"Origin": "http://localhost:8080"},
        )

    assert response.status_code == 500, f"Expected 500 but got {response.status_code}: {response.text}"
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "Internal server error"
    assert "request_id" in data
    assert data["request_id"].startswith("req_")
