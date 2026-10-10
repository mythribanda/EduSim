"""
app/src/api/assignments_router.py

Full Assignment system endpoints:
  POST   /assignments                                       — teacher creates assignment
  GET    /assignments/class/{class_id}                      — list assignments for a class
  GET    /assignments/mine                                   — student: pending/submitted assignments
  POST   /assignments/{assignment_id}/submit                 — student submits
  PATCH  /assignments/{assignment_id}/submissions/{sub_id}/grade  — teacher grades
"""

import uuid
import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.src.config.database import get_db
from app.src.models.user import User
from app.src.api.auth import get_current_user
from app.src.middleware.rbac import normalize_role, require_role, check_class_membership
from app.src.models.school import (
    Assignment,
    Submission,
    Class,
    StudentEnrollment,
)

logger = logging.getLogger("EduSim.assignments")

router = APIRouter(prefix="/assignments", tags=["Assignments"])

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    class_id: uuid.UUID = Field(..., description="UUID of the target class section")
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    module_id: Optional[str] = Field(None, max_length=255, description="Curriculum module/topic key")
    due_date: Optional[datetime.datetime] = Field(None, description="ISO 8601 deadline (UTC)")
    max_score: float = Field(default=100.0, ge=0.0, le=10000.0)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    class_name: Optional[str] = None
    teacher_id: uuid.UUID
    teacher_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    module_id: Optional[str] = None
    due_date: Optional[datetime.datetime] = None
    due_date_ist: Optional[str] = None       # human-friendly IST timestamp
    max_score: float
    created_at: datetime.datetime
    submission_count: int = 0                # submitted or graded
    graded_count: int = 0
    total_students: int = 0                  # total active enrolled students in class
    average_score: Optional[float] = None    # average score of graded submissions

    class Config:
        from_attributes = True


class SubmissionOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_title: Optional[str] = None
    student_id: uuid.UUID
    student_name: Optional[str] = None
    submitted_at: Optional[datetime.datetime] = None
    submitted_at_ist: Optional[str] = None
    score: Optional[float] = None
    feedback: Optional[str] = None
    status: str
    max_score: Optional[float] = None
    due_date: Optional[datetime.datetime] = None
    due_date_ist: Optional[str] = None
    is_overdue: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class GradeRequest(BaseModel):
    score: float = Field(..., ge=0.0, description="Score awarded (must be <= assignment max_score)")
    feedback: Optional[str] = Field(None, max_length=5000, description="Teacher feedback text")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _to_ist_str(dt: Optional[datetime.datetime]) -> Optional[str]:
    """Convert a UTC (or tz-aware) datetime to an IST ISO-8601 string."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(IST).isoformat()


def _is_enrolled(student_id: uuid.UUID, class_id: uuid.UUID, db: Session) -> bool:
    return db.query(StudentEnrollment).filter(
        StudentEnrollment.student_id == student_id,
        StudentEnrollment.class_id == class_id,
        StudentEnrollment.status == "active",
    ).first() is not None


def _build_assignment_out(a: Assignment, db: Session) -> AssignmentOut:
    """Convert an Assignment ORM object into AssignmentOut, adding aggregated counts."""
    teacher_name = getattr(a.teacher, "name", None) or getattr(a.teacher, "email", "Teacher")
    class_name = getattr(a.class_, "name", None)
    
    sub_count = db.query(Submission).filter(
        Submission.assignment_id == a.id,
        Submission.status.in_(["submitted", "graded"]),
    ).count()
    
    graded_count = db.query(Submission).filter(
        Submission.assignment_id == a.id,
        Submission.status == "graded",
    ).count()

    total_students = db.query(StudentEnrollment).filter(
        StudentEnrollment.class_id == a.class_id,
        StudentEnrollment.status == "active",
    ).count()

    avg_score_val = db.query(func.avg(Submission.score)).filter(
        Submission.assignment_id == a.id,
        Submission.status == "graded",
        Submission.score.isnot(None),
    ).scalar()
    avg_score = round(float(avg_score_val), 1) if avg_score_val is not None else None

    return AssignmentOut(
        id=a.id,
        class_id=a.class_id,
        class_name=class_name,
        teacher_id=a.teacher_id,
        teacher_name=teacher_name,
        title=a.title,
        description=a.description,
        module_id=a.module_id,
        due_date=a.due_date,
        due_date_ist=_to_ist_str(a.due_date),
        max_score=a.max_score,
        created_at=a.created_at,
        submission_count=sub_count,
        graded_count=graded_count,
        total_students=total_students,
        average_score=avg_score,
    )


def _build_submission_out(sub: Submission, db: Session) -> SubmissionOut:
    """Convert a Submission ORM object into SubmissionOut with denormalised fields."""
    assignment = sub.assignment
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    due = getattr(assignment, "due_date", None) if assignment else None
    is_overdue = False
    if due and sub.status == "pending":
        due_aware = due if due.tzinfo else due.replace(tzinfo=datetime.timezone.utc)
        is_overdue = now_utc > due_aware

    student_name = getattr(sub.student, "name", None) or getattr(sub.student, "email", "Student")

    return SubmissionOut(
        id=sub.id,
        assignment_id=sub.assignment_id,
        assignment_title=getattr(assignment, "title", None),
        student_id=sub.student_id,
        student_name=student_name,
        submitted_at=sub.submitted_at,
        submitted_at_ist=_to_ist_str(sub.submitted_at),
        score=sub.score,
        feedback=sub.feedback,
        status=sub.status,
        max_score=getattr(assignment, "max_score", None),
        due_date=due,
        due_date_ist=_to_ist_str(due),
        is_overdue=is_overdue,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_assignment(
    payload: AssignmentCreate,
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Teacher creates a new assignment for one of their class sections.
    Requires educator or admin role, and must be a member of the target class.
    """
    # Verify the class exists
    cls = db.query(Class).filter(Class.id == payload.class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class '{payload.class_id}' not found.",
        )

    # Only members (teacher/admin) of the class can assign to it
    if not check_class_membership(current_user, payload.class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to create assignments for this class.",
        )

    assignment = Assignment(
        class_id=payload.class_id,
        teacher_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description,
        module_id=payload.module_id,
        due_date=payload.due_date,
        max_score=payload.max_score,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    logger.info(
        "Assignment created: id=%s class=%s teacher=%s title=%r",
        assignment.id, assignment.class_id, current_user.id, assignment.title,
    )
    return _build_assignment_out(assignment, db)


@router.get("/class/{class_id}", response_model=List[AssignmentOut])
def list_assignments_for_class(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all assignments for a given class section.
    Accessible by the class teacher/admin OR any actively enrolled student.
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    role = normalize_role(getattr(current_user, "role", None))

    # Educators/admins must be members of the class
    if role in ("educator", "admin"):
        if not check_class_membership(current_user, class_id, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised.")
    else:
        # Students must be enrolled
        if not _is_enrolled(current_user.id, class_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not enrolled in this class.",
            )

    assignments = (
        db.query(Assignment)
        .filter(Assignment.class_id == class_id)
        .order_by(Assignment.due_date.asc().nullslast(), Assignment.created_at.desc())
        .all()
    )
    return [_build_assignment_out(a, db) for a in assignments]


@router.get("/mine", response_model=List[SubmissionOut])
def get_my_assignments(
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """
    Student sees all their assignment submissions (pending, submitted, graded)
    across every class they are enrolled in.
    Results are ordered: overdue pending first, then by due date ascending.
    """
    # Get all active class IDs for this student
    enrolled_class_ids = [
        row[0]
        for row in db.query(StudentEnrollment.class_id)
        .filter(
            StudentEnrollment.student_id == current_user.id,
            StudentEnrollment.status == "active",
        )
        .all()
    ]

    if not enrolled_class_ids:
        return []

    # Get all assignment IDs for those classes
    assignment_ids = [
        row[0]
        for row in db.query(Assignment.id)
        .filter(Assignment.class_id.in_(enrolled_class_ids))
        .all()
    ]

    if not assignment_ids:
        return []

    # Upsert pending submissions for any assignment that doesn't have one yet
    existing_sub_assignment_ids = {
        row[0]
        for row in db.query(Submission.assignment_id)
        .filter(
            Submission.student_id == current_user.id,
            Submission.assignment_id.in_(assignment_ids),
        )
        .all()
    }

    for aid in assignment_ids:
        if aid not in existing_sub_assignment_ids:
            db.add(Submission(
                assignment_id=aid,
                student_id=current_user.id,
                status="pending",
            ))

    if assignment_ids and len(assignment_ids) != len(existing_sub_assignment_ids):
        db.commit()

    # Fetch all submissions for this student across those assignments
    subs = (
        db.query(Submission)
        .filter(
            Submission.student_id == current_user.id,
            Submission.assignment_id.in_(assignment_ids),
        )
        .all()
    )

    return sorted(
        [_build_submission_out(s, db) for s in subs],
        key=lambda s: (
            # Show overdue pending first, then pending, then submitted, then graded
            0 if (s.is_overdue and s.status == "pending") else
            1 if s.status == "pending" else
            2 if s.status == "submitted" else 3,
            # Within each group, sort by due_date ascending (earliest deadline first)
            s.due_date or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
        ),
    )


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(
    assignment_id: uuid.UUID = Path(..., description="Assignment UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single assignment by ID.
    Accessible by class educator/admin or enrolled students.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    role = normalize_role(getattr(current_user, "role", None))
    if role in ("educator", "admin"):
        if not check_class_membership(current_user, assignment.class_id, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this class.")
    else:
        if not _is_enrolled(current_user.id, assignment.class_id, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class.")

    return _build_assignment_out(assignment, db)


@router.get("/{assignment_id}/submissions", response_model=List[SubmissionOut])
def get_assignment_submissions(
    assignment_id: uuid.UUID = Path(..., description="Assignment UUID"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Teacher view of all submissions for an assignment.
    Ensures every actively enrolled student has a submission record (pending, submitted, or graded).
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    if not check_class_membership(current_user, assignment.class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to view submissions for this class.",
        )

    # 1. Fetch all active student enrollments for this class
    enrollments = (
        db.query(StudentEnrollment)
        .filter(
            StudentEnrollment.class_id == assignment.class_id,
            StudentEnrollment.status == "active",
        )
        .all()
    )
    enrolled_student_ids = [e.student_id for e in enrollments]

    # 2. Existing submissions
    existing_subs = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id)
        .all()
    )
    existing_by_student = {s.student_id: s for s in existing_subs}

    # 3. Ensure any enrolled student without a submission gets a pending record
    created_any = False
    for sid in enrolled_student_ids:
        if sid not in existing_by_student:
            new_sub = Submission(
                assignment_id=assignment_id,
                student_id=sid,
                status="pending",
            )
            db.add(new_sub)
            existing_by_student[sid] = new_sub
            created_any = True

    if created_any:
        db.commit()

    all_subs = list(existing_by_student.values())

    # Sort: submitted (needs grading) first, then graded, then pending
    status_order = {"submitted": 0, "graded": 1, "pending": 2}
    return sorted(
        [_build_submission_out(s, db) for s in all_subs],
        key=lambda s: (
            status_order.get(s.status, 3),
            s.student_name or "",
        ),
    )


@router.post("/{assignment_id}/submit", response_model=SubmissionOut)
def submit_assignment(
    assignment_id: uuid.UUID = Path(..., description="Assignment UUID"),
    current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """
    Student submits an assignment.
    - Records the timestamp.
    - Warns if past due but still accepts (late submissions are allowed; teacher can see the timestamp).
    - Idempotent: calling twice returns the existing submitted record.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    # Must be enrolled in the assignment's class
    if not _is_enrolled(current_user.id, assignment.class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in the class for this assignment.",
        )

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Check due date (warn via log; still accept late submission)
    if assignment.due_date:
        due_aware = assignment.due_date if assignment.due_date.tzinfo else \
            assignment.due_date.replace(tzinfo=datetime.timezone.utc)
        if now_utc > due_aware:
            logger.warning(
                "Late submission: student=%s assignment=%s due=%s submitted_at=%s",
                current_user.id, assignment_id, due_aware.isoformat(), now_utc.isoformat(),
            )

    # Get or create the submission record
    sub = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.student_id == current_user.id,
    ).first()

    if sub is None:
        sub = Submission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            status="pending",
        )
        db.add(sub)
        db.flush()

    if sub.status == "graded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment has already been graded and cannot be re-submitted.",
        )

    if sub.status == "submitted":
        # Idempotent — return the existing submission
        return _build_submission_out(sub, db)

    sub.status = "submitted"
    sub.submitted_at = now_utc
    db.commit()
    db.refresh(sub)

    logger.info(
        "Submission recorded: id=%s assignment=%s student=%s",
        sub.id, assignment_id, current_user.id,
    )
    return _build_submission_out(sub, db)


@router.patch("/{assignment_id}/submissions/{submission_id}/grade", response_model=SubmissionOut)
def grade_submission(
    assignment_id: uuid.UUID = Path(..., description="Assignment UUID"),
    submission_id: uuid.UUID = Path(..., description="Submission UUID"),
    payload: GradeRequest = Body(...),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Teacher grades a student submission.
    - Sets score, feedback, and status to 'graded'.
    - Score must not exceed the assignment's max_score.
    - Only the teacher of the class (or admin) can grade.
    """
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    if not check_class_membership(current_user, assignment.class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to grade submissions for this class.",
        )

    sub = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.assignment_id == assignment_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")

    if sub.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot grade a pending submission — student has not submitted yet.",
        )

    if payload.score > assignment.max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Score {payload.score} exceeds max_score {assignment.max_score}.",
        )

    sub.score = payload.score
    sub.feedback = payload.feedback
    sub.status = "graded"
    sub.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(sub)

    logger.info(
        "Submission graded: id=%s assignment=%s student=%s score=%.1f/%s",
        sub.id, assignment_id, sub.student_id, sub.score, assignment.max_score,
    )
    return _build_submission_out(sub, db)
