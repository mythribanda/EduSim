import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.persistence import CurriculumClass, Subject, Chapter, Topic
from app.src.models.user import User
from app.src.middleware.rbac import require_admin

# TODO: [Curriculum V2 Migration] Legacy curriculum router (/api/curriculum/*).
# Frontend routes now query /api/curriculum/v2/*. Retained for backward compatibility
# and RBAC tests (e.g. POST /api/curriculum/seed in test_auth_roles.py).
router = APIRouter(prefix="/curriculum", tags=["Curriculum"])

@router.get("/classes")
def get_classes(db: Session = Depends(get_db)):
    classes = db.query(CurriculumClass).order_by(CurriculumClass.display_order.asc()).all()
    return classes

@router.get("/classes/{class_id}/subjects")
def get_subjects(class_id: int, db: Session = Depends(get_db)):
    subjects = db.query(Subject).filter(Subject.class_id == class_id).order_by(Subject.display_order.asc()).all()
    if not subjects:
        # Check if the class exists
        cls = db.query(CurriculumClass).filter(CurriculumClass.id == class_id).first()
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")
    return subjects

@router.get("/subjects/{subject_id}/chapters")
def get_chapters(subject_id: uuid.UUID, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).filter(Chapter.subject_id == subject_id).order_by(Chapter.display_order.asc()).all()
    if not chapters:
        sub = db.query(Subject).filter(Subject.id == subject_id).first()
        if not sub:
            raise HTTPException(status_code=404, detail="Subject not found")
    return chapters

@router.get("/chapters/{chapter_id}/topics")
def get_topics(chapter_id: uuid.UUID, db: Session = Depends(get_db)):
    topics = db.query(Topic).filter(Topic.chapter_id == chapter_id).order_by(Topic.display_order.asc()).all()
    if not topics:
        chap = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chap:
            raise HTTPException(status_code=404, detail="Chapter not found")
    return topics

@router.get("/all-topics")
def get_all_topics(db: Session = Depends(get_db)):
    """Return all topics flattened with subject and chapter info for easy dropdown selection."""
    topics = (
        db.query(Topic, Chapter.name.label("chapter_name"), Subject.name.label("subject_name"))
        .join(Chapter, Topic.chapter_id == Chapter.id)
        .join(Subject, Chapter.subject_id == Subject.id)
        .order_by(Subject.name.asc(), Chapter.name.asc(), Topic.display_order.asc())
        .all()
    )
    result = []
    for t, ch_name, sub_name in topics:
        result.append({
            "id": str(t.id),
            "name": t.name,
            "chapter_name": ch_name,
            "subject_name": sub_name,
            "has_simulation": getattr(t, "has_simulation", False),
            "simulation_route": getattr(t, "simulation_route", None),
        })
    return result


@router.get("/search")
def search_curriculum(q: str, db: Session = Depends(get_db)):
    q_lower = f"%{q.lower()}%"
    matches = []
    
    # Search chapters
    chapters = db.query(Chapter).filter(Chapter.name.ilike(q_lower)).all()
    for ch in chapters:
        s = db.query(Subject).filter(Subject.id == ch.subject_id).first()
        matches.append({ "title": f"{ch.name} - {s.name if s else ''}", "type": "Chapter PDF", "url": "#" })
        
    # Search topics
    topics = db.query(Topic).filter(Topic.name.ilike(q_lower)).all()
    for t in topics:
        ch = db.query(Chapter).filter(Chapter.id == t.chapter_id).first()
        ch_name = ch.name if ch else ""
        matches.append({ "title": f"{t.name} — {ch_name}", "type": "Notes", "url": "#" })
        matches.append({ "title": f"{t.name} — Practice Questions", "type": "Practice", "url": "#" })
        matches.append({ "title": f"{t.name} — Intro Video", "type": "Video", "url": f"https://www.youtube.com/results?search_query={t.name}" })
        
    # Dedupe based on title+type
    seen = set()
    uniq = []
    for m in matches:
        key = m["title"] + m["type"]
        if key not in seen:
            seen.add(key)
            uniq.append(m)
            
    return uniq[:12]

from pydantic import BaseModel
from typing import Optional, Union, List
from sqlalchemy.dialects.postgresql import insert

class TopicPayload(BaseModel):
    name: str
    hasSimulation: Optional[bool] = False
    simulationRoute: Optional[str] = None

class ChapterPayload(BaseModel):
    name: str
    topics: List[TopicPayload] = []

class SubjectPayload(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    description: str = ""
    chapters: Union[int, List[ChapterPayload]] = []

class ClassPayload(BaseModel):
    id: int
    name: str
    description: str = ""
    subjects: List[SubjectPayload] = []

@router.post("/seed")
def seed_curriculum(
    payload: List[ClassPayload],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    for c_order, c in enumerate(payload):
        # Upsert Class
        stmt_class = insert(CurriculumClass).values({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "display_order": c_order
        }).on_conflict_do_update(
            index_elements=["id"],
            set_={"name": c.name, "description": c.description, "display_order": c_order}
        )
        db.execute(stmt_class)
        
        for s_order, s in enumerate(c.subjects):
            # Upsert Subject
            stmt_sub = insert(Subject).values({
                "class_id": c.id,
                "code": s.id,
                "name": s.name,
                "description": s.description,
                "icon": s.icon,
                "display_order": s_order
            }).on_conflict_do_update(
                constraint="uq_class_subject_code",
                set_={
                    "name": s.name, 
                    "description": s.description, 
                    "icon": s.icon, 
                    "display_order": s_order
                }
            ).returning(Subject.id)
            sub_id = db.execute(stmt_sub).scalar()
            
            if isinstance(s.chapters, list):
                for ch_order, ch in enumerate(s.chapters):
                    # Upsert Chapter
                    stmt_chap = insert(Chapter).values({
                        "subject_id": sub_id,
                        "name": ch.name,
                        "description": "",
                        "display_order": ch_order
                    }).on_conflict_do_update(
                        constraint="uq_subject_chapter_name",
                        set_={
                            "display_order": ch_order
                        }
                    ).returning(Chapter.id)
                    chap_id = db.execute(stmt_chap).scalar()
                    
                    for t_order, t in enumerate(ch.topics):
                        # Upsert Topic
                        stmt_top = insert(Topic).values({
                            "chapter_id": chap_id,
                            "name": t.name,
                            "has_simulation": t.hasSimulation,
                            "simulation_route": t.simulationRoute,
                            "display_order": t_order
                        }).on_conflict_do_update(
                            constraint="uq_chapter_topic_name",
                            set_={
                                "has_simulation": t.hasSimulation,
                                "simulation_route": t.simulationRoute,
                                "display_order": t_order
                            }
                        )
                        db.execute(stmt_top)
    
    db.commit()
    return {"status": "success", "message": "Curriculum seeded successfully."}
