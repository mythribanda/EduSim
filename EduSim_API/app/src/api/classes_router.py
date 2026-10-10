import uuid
import datetime
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.src.config.database import get_db
from app.src.models.user import User
from app.src.api.auth import get_current_user
from app.src.middleware.rbac import (
    normalize_role,
    require_role,
    check_class_membership,
)
from app.src.models.school import (
    Class,
    TeacherClassSubject,
    StudentEnrollment,
    generate_join_code,
)

router = APIRouter(prefix="/classes", tags=["Classes"])


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------

class TeacherClassSubjectOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_name: Optional[str] = None
    class_id: uuid.UUID
    subject: str
    is_primary: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Class name, e.g., '10-A'")
    grade_level: str = Field(..., min_length=1, max_length=50, description="Grade level, e.g., '10'")
    institution_id: Optional[uuid.UUID] = None
    join_code: Optional[str] = Field(None, max_length=20, description="Optional custom join code")
    subject: Optional[str] = Field(None, description="Initial subject to associate with teacher")
    subjects: Optional[List[str]] = Field(default_factory=list, description="List of subjects to associate")


class ClassOut(BaseModel):
    id: uuid.UUID
    name: str
    grade_level: str
    institution_id: Optional[uuid.UUID] = None
    created_by: uuid.UUID
    created_by_name: Optional[str] = None
    join_code: str
    created_at: datetime.datetime
    subjects: List[str] = Field(default_factory=list)
    teacher_subjects: List[TeacherClassSubjectOut] = Field(default_factory=list)
    enrolled_student_count: int = 0

    class Config:
        from_attributes = True


class EnrollRequest(BaseModel):
    join_code: str = Field(..., min_length=1, max_length=20, description="Class join code")


class EnrollmentOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    grade_level: str
    enrolled_at: datetime.datetime
    status: str

    class Config:
        from_attributes = True


class AddSubjectRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=100)
    is_primary: bool = False
    teacher_id: Optional[uuid.UUID] = None


class EnrolledStudentOut(BaseModel):
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    name: str
    email: str
    enrolled_at: datetime.datetime
    status: str
    mastery_percentage: float = 0.0
    last_active: Optional[datetime.datetime] = None
    weakest_topic: Optional[str] = None
    weakest_topic_score: Optional[float] = None
    has_critical_weakness: bool = False

    class Config:
        from_attributes = True



def _format_class_out(cls: Class, db: Session) -> ClassOut:
    """Helper to convert a Class model instance into ClassOut schema."""
    # Fetch active student count
    count = db.query(func.count(StudentEnrollment.id)).filter(
        StudentEnrollment.class_id == cls.id,
        StudentEnrollment.status == "active",
    ).scalar() or 0

    # Format teacher subjects
    teacher_subs = []
    subject_names = []
    for ts in cls.teacher_subjects:
        teacher_name = getattr(ts.teacher, "name", None) or getattr(ts.teacher, "email", "Teacher")
        teacher_subs.append(TeacherClassSubjectOut(
            id=ts.id,
            teacher_id=ts.teacher_id,
            teacher_name=teacher_name,
            class_id=ts.class_id,
            subject=ts.subject,
            is_primary=ts.is_primary,
            created_at=ts.created_at,
        ))
        if ts.subject not in subject_names:
            subject_names.append(ts.subject)

    creator_name = getattr(cls.teacher, "name", None) or getattr(cls.teacher, "email", "Teacher")

    return ClassOut(
        id=cls.id,
        name=cls.name,
        grade_level=cls.grade_level,
        institution_id=cls.institution_id,
        created_by=cls.created_by,
        created_by_name=creator_name,
        join_code=cls.join_code,
        created_at=cls.created_at,
        subjects=subject_names,
        teacher_subjects=teacher_subs,
        enrolled_student_count=count,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ClassOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_class(
    payload: ClassCreate,
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Create a new class section (e.g. '10-A').
    Automatically generates a join code if not supplied, and associates initial subject(s).
    Requires 'educator' or 'admin' role.
    """
    join_code = payload.join_code.strip().upper() if payload.join_code else None

    # Verify uniqueness of join_code if provided
    if join_code:
        existing = db.query(Class).filter(Class.join_code == join_code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Join code '{join_code}' is already in use by another class.",
            )
    else:
        # Generate unique code
        for _ in range(10):
            code = generate_join_code()
            if not db.query(Class).filter(Class.join_code == code).first():
                join_code = code
                break
        if not join_code:
            join_code = generate_join_code()

    new_class = Class(
        name=payload.name.strip(),
        grade_level=payload.grade_level.strip(),
        institution_id=payload.institution_id,
        created_by=current_user.id,
        join_code=join_code,
    )
    db.add(new_class)
    db.flush()

    # Associate primary subject if provided
    subjects_to_add = set()
    if payload.subject and payload.subject.strip():
        subjects_to_add.add(payload.subject.strip())
    if payload.subjects:
        for s in payload.subjects:
            if s and s.strip():
                subjects_to_add.add(s.strip())

    for idx, sub in enumerate(subjects_to_add):
        is_primary = (sub == payload.subject) or (idx == 0 and not payload.subject)
        tcs = TeacherClassSubject(
            teacher_id=current_user.id,
            class_id=new_class.id,
            subject=sub,
            is_primary=is_primary,
        )
        db.add(tcs)

    db.commit()
    db.refresh(new_class)
    return _format_class_out(new_class, db)


@router.get("/mine", response_model=List[ClassOut])
def get_my_classes(
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Retrieve all classes taught or created by the requesting teacher.
    Admins see all classes in the system.
    """
    user_role = normalize_role(getattr(current_user, "role", None))

    if user_role == "admin":
        classes = db.query(Class).order_by(Class.created_at.desc()).all()
        return [_format_class_out(c, db) for c in classes]

    # Find classes created by current_user OR where current_user is in TeacherClassSubject
    sub_class_ids = (
        db.query(TeacherClassSubject.class_id)
        .filter(TeacherClassSubject.teacher_id == current_user.id)
        .scalar_subquery()
    )

    classes = (
        db.query(Class)
        .filter(
            (Class.created_by == current_user.id) | (Class.id.in_(sub_class_ids))
        )
        .order_by(Class.created_at.desc())
        .all()
    )

    return [_format_class_out(c, db) for c in classes]


@router.post("/{class_id}/enroll", response_model=EnrollmentOut)
def enroll_student_in_class(
    class_id: uuid.UUID = Path(..., description="Target class UUID"),
    payload: EnrollRequest = Body(...),
    current_user: User = Depends(require_role("student", "admin")),
    db: Session = Depends(get_db),
):
    """
    Student self-enrollment into a class using the teacher's join code.
    Requires 'student' or 'admin' role.
    """
    target_class = db.query(Class).filter(Class.id == class_id).first()
    if not target_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    # Validate join code (case-insensitive)
    submitted_code = payload.join_code.strip().upper()
    if target_class.join_code.upper() != submitted_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid join code for this class.",
        )

    # Check if student is already enrolled
    existing = db.query(StudentEnrollment).filter(
        StudentEnrollment.student_id == current_user.id,
        StudentEnrollment.class_id == class_id,
    ).first()

    if existing:
        if existing.status == "active":
            return EnrollmentOut(
                id=existing.id,
                student_id=existing.student_id,
                class_id=existing.class_id,
                class_name=target_class.name,
                grade_level=target_class.grade_level,
                enrolled_at=existing.enrolled_at,
                status=existing.status,
            )
        else:
            # Reactivate
            existing.status = "active"
            existing.enrolled_at = datetime.datetime.now(datetime.timezone.utc)
            enrollment = existing
    else:
        enrollment = StudentEnrollment(
            student_id=current_user.id,
            class_id=class_id,
            status="active",
        )
        db.add(enrollment)

    # Also update current_user's class_id and educator_id for legacy system compatibility
    current_user.class_id = str(class_id)
    if getattr(target_class, "created_by", None):
        current_user.educator_id = target_class.created_by

    db.commit()
    db.refresh(enrollment)

    return EnrollmentOut(
        id=enrollment.id,
        student_id=enrollment.student_id,
        class_id=enrollment.class_id,
        class_name=target_class.name,
        grade_level=target_class.grade_level,
        enrolled_at=enrollment.enrolled_at,
        status=enrollment.status,
    )


@router.get("/{class_id}", response_model=ClassOut)
def get_class_by_id(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get class details. Accessible by class teacher, enrolled students, or admin.
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    # Check permission
    if not check_class_membership(current_user, class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in or authorized to view this class.",
        )

    return _format_class_out(cls, db)


@router.post("/{class_id}/subjects", response_model=TeacherClassSubjectOut, status_code=status.HTTP_201_CREATED)
def add_class_subject(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    payload: AddSubjectRequest = Body(...),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Assign a teacher and subject to a class (e.g. Teacher T1 teaches Physics to 10-A).
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    teacher_id = payload.teacher_id or current_user.id
    subject_name = payload.subject.strip()

    # Check if this assignment already exists
    existing = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id,
        TeacherClassSubject.class_id == class_id,
        TeacherClassSubject.subject == subject_name,
    ).first()

    if existing:
        existing.is_primary = payload.is_primary
        db.commit()
        db.refresh(existing)
        teacher_name = getattr(existing.teacher, "name", None) or "Teacher"
        return TeacherClassSubjectOut(
            id=existing.id,
            teacher_id=existing.teacher_id,
            teacher_name=teacher_name,
            class_id=existing.class_id,
            subject=existing.subject,
            is_primary=existing.is_primary,
            created_at=existing.created_at,
        )

    tcs = TeacherClassSubject(
        teacher_id=teacher_id,
        class_id=class_id,
        subject=subject_name,
        is_primary=payload.is_primary,
    )
    db.add(tcs)
    db.commit()
    db.refresh(tcs)

    teacher_name = getattr(tcs.teacher, "name", None) or "Teacher"
    return TeacherClassSubjectOut(
        id=tcs.id,
        teacher_id=tcs.teacher_id,
        teacher_name=teacher_name,
        class_id=tcs.class_id,
        subject=tcs.subject,
        is_primary=tcs.is_primary,
        created_at=tcs.created_at,
    )


@router.get("/{class_id}/students", response_model=List[EnrolledStudentOut])
def get_class_students(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    List all students enrolled in a class.
    Only accessible by the teacher who created/teaches the class, or an admin.
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    if not check_class_membership(current_user, class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view students for this class.",
        )

    enrollments = (
        db.query(StudentEnrollment)
        .filter(StudentEnrollment.class_id == class_id)
        .order_by(StudentEnrollment.enrolled_at.desc())
        .all()
    )

    # 1. Fetch mastery records for all students in this class in one batch query
    student_ids = [enr.student_id for enr in enrollments]
    mastery_by_student: Dict[uuid.UUID, list] = {}
    if student_ids:
        from app.src.models.school import StudentTopicMastery
        all_masteries = (
            db.query(StudentTopicMastery)
            .filter(StudentTopicMastery.student_id.in_(student_ids))
            .all()
        )
        for m in all_masteries:
            mastery_by_student.setdefault(m.student_id, []).append(m)

    # 2. Fetch last active timestamp for each student in one batch query
    last_active_by_student: Dict[uuid.UUID, datetime.datetime] = {}
    if student_ids:
        from app.src.models.persistence import SessionEvent, UserSession
        event_max = (
            db.query(SessionEvent.student_id, func.max(SessionEvent.created_at))
            .filter(SessionEvent.student_id.in_(student_ids))
            .group_by(SessionEvent.student_id)
            .all()
        )
        for sid, max_dt in event_max:
            if max_dt:
                last_active_by_student[sid] = max_dt

        session_max = (
            db.query(UserSession.user_id, func.max(UserSession.created_at))
            .filter(UserSession.user_id.in_(student_ids))
            .group_by(UserSession.user_id)
            .all()
        )
        for uid, max_dt in session_max:
            if max_dt and (uid not in last_active_by_student or max_dt > last_active_by_student[uid]):
                last_active_by_student[uid] = max_dt

    from app.src.api.students_router import resolve_topic_name

    result = []
    for enr in enrollments:
        student = enr.student
        sid = enr.student_id

        # Compute student mastery and weakest topic
        stud_mastery = mastery_by_student.get(sid, [])
        if stud_mastery:
            scores = [m.mastery_score for m in stud_mastery]
            avg_mastery = round(float(sum(scores) / len(scores)), 1)
            sorted_m = sorted(stud_mastery, key=lambda m: m.mastery_score)
            weakest_rec = sorted_m[0]
            weakest_topic_name = resolve_topic_name(weakest_rec.topic_id, db)
            weakest_topic_score = round(float(weakest_rec.mastery_score), 1)
            has_critical = any(m.mastery_score < 40.0 for m in stud_mastery)
        else:
            avg_mastery = 0.0
            weakest_topic_name = None
            weakest_topic_score = None
            has_critical = False

        # Last active timestamp
        last_act = last_active_by_student.get(sid)
        if not last_act and student and getattr(student, "last_active_at", None):
            last_act = student.last_active_at

        result.append(EnrolledStudentOut(
            enrollment_id=enr.id,
            student_id=sid,
            name=getattr(student, "name", "Student") if student else "Unknown",
            email=getattr(student, "email", "") if student else "",
            enrolled_at=enr.enrolled_at,
            status=enr.status,
            mastery_percentage=avg_mastery,
            last_active=last_act,
            weakest_topic=weakest_topic_name,
            weakest_topic_score=weakest_topic_score,
            has_critical_weakness=has_critical,
        ))

    return result


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Delete a class. Accessible by creator or admin.
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    user_role = normalize_role(getattr(current_user, "role", None))
    if user_role != "admin" and cls.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the class creator or an admin can delete this class.",
        )

    db.delete(cls)
    db.commit()
    return None


# -----------------------------------------------------------------------------
# Class Analytics Endpoint
# -----------------------------------------------------------------------------

class TopicAnalytics(BaseModel):
    topic: str
    average_score: float
    student_count: int


class ClassAnalyticsOut(BaseModel):
    class_id: uuid.UUID
    class_name: str
    grade_level: str
    student_count: int
    active_this_week: int
    average_mastery: float
    weakest_topic: Optional[str] = None
    strongest_topic: Optional[str] = None
    topic_breakdown: List[TopicAnalytics] = Field(default_factory=list)


@router.get("/{class_id}/analytics", response_model=ClassAnalyticsOut)
def get_class_analytics(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Get aggregated analytics for a specific class section:
    - student count
    - active students this week
    - average mastery %
    - weakest topic across students in this class
    - topic breakdown
    """
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    if not check_class_membership(current_user, class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view analytics for this class.",
        )

    # 1. Enrolled student IDs
    enrollments = db.query(StudentEnrollment.student_id).filter(
        StudentEnrollment.class_id == class_id,
        StudentEnrollment.status == "active",
    ).all()
    student_ids = [row[0] for row in enrollments]
    student_count = len(student_ids)

    # 2. Active students this week (activity within last 7 days)
    seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    active_this_week = 0

    if student_ids:
        from app.src.models.persistence import SessionEvent, UserSession
        active_event_students = {
            row[0]
            for row in db.query(SessionEvent.student_id)
            .filter(
                SessionEvent.student_id.in_(student_ids),
                SessionEvent.created_at >= seven_days_ago,
            )
            .all()
        }
        active_session_students = {
            row[0]
            for row in db.query(UserSession.user_id)
            .filter(
                UserSession.user_id.in_(student_ids),
                UserSession.created_at >= seven_days_ago,
            )
            .all()
        }
        active_this_week = len(active_event_students | active_session_students)

    # 3. Topic Mastery scores
    from app.src.models.school import StudentTopicMastery
    average_mastery = 0.0
    weakest_topic = None
    strongest_topic = None
    topic_breakdown: List[TopicAnalytics] = []

    if student_ids:
        topic_stats = (
            db.query(
                StudentTopicMastery.topic_id,
                func.avg(StudentTopicMastery.mastery_score),
                func.count(StudentTopicMastery.student_id),
            )
            .filter(StudentTopicMastery.student_id.in_(student_ids))
            .group_by(StudentTopicMastery.topic_id)
            .all()
        )

        if topic_stats:
            overall_avg = (
                db.query(func.avg(StudentTopicMastery.mastery_score))
                .filter(StudentTopicMastery.student_id.in_(student_ids))
                .scalar()
            )
            average_mastery = round(float(overall_avg or 0.0), 1)

            sorted_topics = sorted(topic_stats, key=lambda t: float(t[1] or 0.0))
            from app.src.api.students_router import resolve_topic_name

            for t_id, avg_s, s_cnt in sorted_topics:
                resolved_name = resolve_topic_name(t_id, db)
                topic_breakdown.append(TopicAnalytics(
                    topic=resolved_name,
                    average_score=round(float(avg_s or 0.0), 1),
                    student_count=int(s_cnt),
                ))

            if sorted_topics:
                weakest_topic = resolve_topic_name(sorted_topics[0][0], db)
                strongest_topic = resolve_topic_name(sorted_topics[-1][0], db)

    return ClassAnalyticsOut(
        class_id=cls.id,
        class_name=cls.name,
        grade_level=cls.grade_level,
        student_count=student_count,
        active_this_week=active_this_week,
        average_mastery=average_mastery,
        weakest_topic=weakest_topic,
        strongest_topic=strongest_topic,
        topic_breakdown=topic_breakdown,
    )


# -----------------------------------------------------------------------------
# Recent Class Activity Endpoint
# -----------------------------------------------------------------------------

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Human-readable event type labels
_EVENT_LABELS: Dict[str, str] = {
    "quiz_answer_correct": "answered a question correctly",
    "quiz_answer_incorrect": "answered a question incorrectly",
    "quiz_answer": "answered a question",
    "simulation_opened": "opened a simulation",
    "simulation_completed": "completed a simulation",
    "tutor_question": "asked the AI tutor",
    "tutor_asked": "asked the AI tutor",
    "session_started": "started a session",
    "session_ended": "ended a session",
    "video_watched": "watched a video",
    "document_opened": "opened a document",
    "exercise_started": "started an exercise",
    "exercise_completed": "completed an exercise",
}


def _humanize_event(event_type: str, payload: dict) -> str:
    """Convert raw event_type + payload into a human-readable verb phrase."""
    label = _EVENT_LABELS.get(event_type)
    if label:
        return label
    # Fallback: convert snake_case to words
    return event_type.replace("_", " ")


class RecentActivityItem(BaseModel):
    event_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    event_type: str
    event_label: str
    topic: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    occurred_at_ist: str   # ISO-8601 string with +05:30 offset, e.g. "2026-09-07T18:15:00+05:30"
    occurred_at_utc: datetime.datetime


@router.get("/{class_id}/recent-activity", response_model=List[RecentActivityItem])
def get_class_recent_activity(
    class_id: uuid.UUID = Path(..., description="Class UUID"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role("educator", "admin")),
    db: Session = Depends(get_db),
):
    """
    Return the last `limit` (default 20) session events for students
    enrolled in the given class section.

    Events are joined with users to include the student name.
    Timestamps are returned in both UTC and IST (Asia/Kolkata, UTC+5:30).
    """
    from app.src.models.persistence import SessionEvent

    # 1. Verify the class exists
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{class_id}' not found.",
        )

    # 2. Authorisation — teacher or admin for this class
    if not check_class_membership(current_user, class_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorised to view activity for this class.",
        )

    # 3. Collect enrolled student IDs (active only)
    student_ids = [
        row[0]
        for row in db.query(StudentEnrollment.student_id)
        .filter(
            StudentEnrollment.class_id == class_id,
            StudentEnrollment.status == "active",
        )
        .all()
    ]

    if not student_ids:
        return []

    # 4. Query most-recent events for those students, newest first
    events = (
        db.query(SessionEvent)
        .filter(SessionEvent.student_id.in_(student_ids))
        .order_by(SessionEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    # 5. Batch-load student name map to avoid N+1
    student_map: Dict[uuid.UUID, User] = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(student_ids)).all()
    }

    result = []
    for ev in events:
        student = student_map.get(ev.student_id)
        student_name = (
            getattr(student, "name", None)
            or getattr(student, "email", "Student")
        )

        payload = ev.payload or {}
        # Derive topic from payload — supports multiple payload key conventions
        topic: Optional[str] = (
            payload.get("topic")
            or payload.get("topic_name")
            or payload.get("chapter")
            or payload.get("subject")
            or payload.get("question_topic")
            or None
        )

        # Convert UTC → IST for display
        utc_dt = ev.created_at
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
        ist_dt = utc_dt.astimezone(IST)
        ist_str = ist_dt.isoformat()  # e.g. "2026-09-07T18:15:00+05:30"

        result.append(RecentActivityItem(
            event_id=ev.id,
            student_id=ev.student_id,
            student_name=student_name,
            event_type=ev.event_type,
            event_label=_humanize_event(ev.event_type, payload),
            topic=topic,
            payload=payload,
            occurred_at_ist=ist_str,
            occurred_at_utc=utc_dt,
        ))

    return result
