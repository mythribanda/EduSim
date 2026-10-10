import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.src.models.persistence import Subject, Chapter, Topic, CurriculumClass

logger = logging.getLogger("EduSim.curriculum_loader")


def populate_curriculum(db: Session) -> None:
    # Check if subjects is empty
    if db.query(Subject).first() is not None:
        return

    curriculum_path = Path(__file__).resolve().parents[1] / "data" / "curriculum.json"
    if not curriculum_path.exists():
        logger.warning("[Curriculum Loader] File not found at %s", curriculum_path)
        return

    with open(curriculum_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("[Curriculum Loader] Populating database from curriculum.json...")
    for class_item in data.get("classes", []):
        class_id = class_item.get("id")
        class_name = class_item.get("name")
        class_desc = class_item.get("description")

        # Get or create CurriculumClass
        curriculum_class = db.query(CurriculumClass).filter(CurriculumClass.id == class_id).first()
        if not curriculum_class:
            curriculum_class = CurriculumClass(
                id=class_id,
                name=class_name,
                description=class_desc
            )
            db.add(curriculum_class)
            db.flush()

        for sub_item in class_item.get("subjects", []):
            code = sub_item.get("id")
            subject = db.query(Subject).filter(Subject.code == code, Subject.class_id == class_id).first()
            if not subject:
                subject = Subject(
                    class_id=class_id,
                    code=code,
                    name=sub_item.get("name"),
                    description=sub_item.get("description"),
                    icon=sub_item.get("icon")
                )
                db.add(subject)
                db.flush()

            chapters = sub_item.get("chapters", [])
            if isinstance(chapters, list):
                subject_chapters = set()
                for chap_item in chapters:
                    chap_name = chap_item.get("name")
                    if chap_name in subject_chapters:
                        continue
                    subject_chapters.add(chap_name)

                    chapter = Chapter(
                        subject_id=subject.id,
                        name=chap_name,
                        description=chap_item.get("description")
                    )
                    db.add(chapter)
                    db.flush()

                    chapter_topics = set()
                    for top_item in chap_item.get("topics", []):
                        top_name = top_item.get("name")
                        if top_name in chapter_topics:
                            continue
                        chapter_topics.add(top_name)

                        has_sim = top_item.get("hasSimulation", top_item.get("has_simulation", False))
                        sim_route = top_item.get("simulationRoute", top_item.get("simulation_route", None))
                        if not sim_route and (code == "physics" or "physic" in str(sub_item.get("name", "")).lower() or "science" in str(sub_item.get("name", "")).lower()):
                            has_sim = True
                            sim_route = f"/simulation/{top_name}"

                        topic = Topic(
                            chapter_id=chapter.id,
                            name=top_name,
                            description=top_item.get("description"),
                            has_simulation=has_sim,
                            simulation_route=sim_route
                        )
                        db.add(topic)
            elif isinstance(chapters, (int, float)):
                # Just mock some numbered chapters
                for i in range(1, int(chapters) + 1):
                    chapter = Chapter(
                        subject_id=subject.id,
                        name=f"Chapter {i}"
                    )
                    db.add(chapter)
                    db.flush()

                    topic = Topic(
                        chapter_id=chapter.id,
                        name="Introduction"
                    )
                    db.add(topic)
    db.commit()
    logger.info("[Curriculum Loader] Database curriculum population complete.")
