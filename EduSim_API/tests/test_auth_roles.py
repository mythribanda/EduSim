"""
EduSim_API/tests/test_auth_roles.py
Pytest suite proving role validation, authentication, and RBAC rules:
1. register role="admin" -> 422
2. register as teacher works -> 200/201
3. login with the wrong role -> 403 ("This account is registered as a {stored_role}")
4. login with the right role -> 200 (including role in token response)
5. a user cannot read another user's data -> 403 (require_self_or_admin)
6. POST /api/curriculum/seed -> 403 for non-admin
"""

import os
import sys
import uuid
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
def auth_test_context():
    """Setup shared in-memory SQLite database and test client."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Pre-populate some users
    student_a = User(
        id=uuid.uuid4(),
        email="student_a@test.com",
        name="Student A",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    student_b = User(
        id=uuid.uuid4(),
        email="student_b@test.com",
        name="Student B",
        password_hash=hash_password("Password123!"),
        role="student",
        is_email_verified=True,
    )
    teacher = User(
        id=uuid.uuid4(),
        email="teacher_existing@test.com",
        name="Teacher User",
        password_hash=hash_password("Password123!"),
        role="teacher",
        is_email_verified=True,
    )
    admin = User(
        id=uuid.uuid4(),
        email="admin_user@test.com",
        name="Admin User",
        password_hash=hash_password("Password123!"),
        role="admin",
        is_email_verified=True,
    )
    db.add_all([student_a, student_b, teacher, admin])
    db.commit()

    student_a_token = create_access_token({"sub": str(student_a.id), "role": "student"})
    student_b_token = create_access_token({"sub": str(student_b.id), "role": "student"})
    teacher_token = create_access_token({"sub": str(teacher.id), "role": "teacher"})
    admin_token = create_access_token({"sub": str(admin.id), "role": "admin"})

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    context = {
        "client": client,
        "student_a": student_a,
        "student_b": student_b,
        "teacher": teacher,
        "admin": admin,
        "student_a_token": student_a_token,
        "student_b_token": student_b_token,
        "teacher_token": teacher_token,
        "admin_token": admin_token,
    }

    yield context

    app.dependency_overrides.clear()
    db.close()


# ============================================================================
# 1. Register with role="admin" -> 422
# ============================================================================

def test_register_role_admin_rejected_422(auth_test_context):
    client = auth_test_context["client"]
    res = client.post(
        "/api/auth/register",
        json={
            "name": "Malicious Admin",
            "email": "hacker_admin@test.com",
            "password": "Password123!",
            "role": "admin",
        },
    )
    assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"


# ============================================================================
# 2. Register as teacher works -> 200 or 201
# ============================================================================

def test_register_as_teacher_succeeds(auth_test_context):
    client = auth_test_context["client"]
    res = client.post(
        "/api/auth/register",
        json={
            "name": "New Teacher",
            "email": "new_teacher@test.com",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert res.status_code in (200, 201), f"Expected 200/201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("success") is True


# ============================================================================
# 3. Login with the wrong role -> 403
# ============================================================================

def test_login_wrong_role_returns_403(auth_test_context):
    client = auth_test_context["client"]

    # Teacher account logging in with role="student"
    res = client.post(
        "/api/auth/login",
        json={
            "email": "teacher_existing@test.com",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
    assert "This account is registered as a teacher" in res.json().get("detail", "")

    # Student account logging in with role="teacher"
    res2 = client.post(
        "/api/auth/login",
        json={
            "email": "student_a@test.com",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert res2.status_code == 403, f"Expected 403, got {res2.status_code}: {res2.text}"
    assert "This account is registered as a student" in res2.json().get("detail", "")


# ============================================================================
# 4. Login with the right role -> 200
# ============================================================================

def test_login_right_role_succeeds_200(auth_test_context):
    client = auth_test_context["client"]

    # Teacher logging in with role="teacher"
    res = client.post(
        "/api/auth/login",
        json={
            "email": "teacher_existing@test.com",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert data.get("role") == "teacher"
    assert data.get("user", {}).get("role") == "teacher"

    # Student logging in without role (or with matching role)
    res_student = client.post(
        "/api/auth/login",
        json={
            "email": "student_a@test.com",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert res_student.status_code == 200, f"Expected 200, got {res_student.status_code}: {res_student.text}"
    data_student = res_student.json()
    assert data_student.get("role") == "student"


# ============================================================================
# 5. A user cannot read another user's data -> 403 (require_self_or_admin)
# ============================================================================

def test_user_cannot_read_another_users_data_403(auth_test_context):
    client = auth_test_context["client"]
    student_a_token = auth_test_context["student_a_token"]
    student_b_id = str(auth_test_context["student_b"].id)
    student_a_id = str(auth_test_context["student_a"].id)
    admin_token = auth_test_context["admin_token"]

    # Student A attempting to read Student B's profile -> 403
    res_forbidden = client.get(
        f"/api/students/{student_b_id}/profile",
        headers={"Authorization": f"Bearer {student_a_token}"},
    )
    assert res_forbidden.status_code == 403, (
        f"Expected 403 when reading another user's profile, got {res_forbidden.status_code}: {res_forbidden.text}"
    )

    # Student A reading their own profile -> 200
    res_self = client.get(
        f"/api/students/{student_a_id}/profile",
        headers={"Authorization": f"Bearer {student_a_token}"},
    )
    assert res_self.status_code == 200, (
        f"Expected 200 when reading own profile, got {res_self.status_code}: {res_self.text}"
    )

    # Admin reading Student B's profile -> 200 (admin bypasses)
    res_admin = client.get(
        f"/api/students/{student_b_id}/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200, (
        f"Expected 200 for admin, got {res_admin.status_code}: {res_admin.text}"
    )


# ============================================================================
# 6. POST /api/curriculum/seed -> 403 for non-admin
# ============================================================================

def test_curriculum_seed_non_admin_forbidden_403(auth_test_context):
    client = auth_test_context["client"]
    student_token = auth_test_context["student_a_token"]
    teacher_token = auth_test_context["teacher_token"]
    admin_token = auth_test_context["admin_token"]

    payload = []

    # Student -> 403
    res_student = client.post(
        "/api/curriculum/seed",
        json=payload,
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student.status_code == 403, (
        f"Expected 403 for student, got {res_student.status_code}: {res_student.text}"
    )

    # Teacher -> 403
    res_teacher = client.post(
        "/api/curriculum/seed",
        json=payload,
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert res_teacher.status_code == 403, (
        f"Expected 403 for teacher, got {res_teacher.status_code}: {res_teacher.text}"
    )

    # Unauthenticated -> 401
    res_unauth = client.post("/api/curriculum/seed", json=payload)
    assert res_unauth.status_code == 401, (
        f"Expected 401 for unauthenticated, got {res_unauth.status_code}: {res_unauth.text}"
    )

    # Admin -> 200
    res_admin = client.post(
        "/api/curriculum/seed",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200, (
        f"Expected 200 for admin, got {res_admin.status_code}: {res_admin.text}"
    )
