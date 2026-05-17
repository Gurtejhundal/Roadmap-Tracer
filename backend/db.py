from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text

from database import SessionLocal, engine
import models_db as models


def init_db():
    models.Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    migrations = {
        "roadmaps": {
            "user_id": "user_id VARCHAR DEFAULT 'public_user'",
        },
        "timeframes": {
            "start_date": "start_date VARCHAR",
            "end_date": "end_date VARCHAR",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in migrations.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

        if "roadmaps" in table_names:
            connection.execute(
                text("UPDATE roadmaps SET user_id = 'public_user' WHERE user_id IS NULL OR user_id = ''")
            )


def _roadmap_to_dict(db, roadmap: models.Roadmap) -> Dict[str, Any]:
    tasks = (
        db.query(models.Task)
        .join(models.Timeframe)
        .filter(models.Timeframe.roadmap_id == roadmap.id)
        .all()
    )
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task.is_done)

    return {
        "id": roadmap.id,
        "name": roadmap.name,
        "created_at": roadmap.created_at,
        "raw_text": roadmap.raw_text,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
    }


def get_roadmaps(user_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmaps = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.user_id == user_id)
            .order_by(models.Roadmap.created_at.desc())
            .all()
        )
        return [_roadmap_to_dict(db, roadmap) for roadmap in roadmaps]
    finally:
        db.close()


def get_roadmap(roadmap_id: int, user_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return None
        return _roadmap_to_dict(db, roadmap)
    finally:
        db.close()


def save_roadmap(name: str, raw_text: str, user_id: str) -> int:
    db = SessionLocal()
    try:
        roadmap = models.Roadmap(name=name, raw_text=raw_text, user_id=user_id)
        db.add(roadmap)
        db.commit()
        db.refresh(roadmap)
        return roadmap.id
    finally:
        db.close()


def delete_roadmap(roadmap_id: int, user_id: str) -> bool:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return False
        db.delete(roadmap)
        db.commit()
        return True
    finally:
        db.close()


def rename_roadmap(roadmap_id: int, new_name: str, user_id: str) -> bool:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return False
        roadmap.name = new_name
        db.commit()
        return True
    finally:
        db.close()


def _replace_roadmap_tasks(db, roadmap_id: int, tasks: List[Dict[str, Any]]):
    db.query(models.Task).filter(
        models.Task.timeframe_id.in_(
            db.query(models.Timeframe.id).filter(models.Timeframe.roadmap_id == roadmap_id)
        )
    ).delete(synchronize_session=False)

    db.query(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id).delete(
        synchronize_session=False
    )

    timeframe_map: Dict[str, models.Timeframe] = {}
    for task in tasks:
        title = str(task.get("title", "")).strip()
        if not title:
            continue

        label = str(task.get("timeframe") or task.get("timeframe_label") or "General").strip() or "General"
        granularity = str(task.get("granularity") or "section")

        if label not in timeframe_map:
            timeframe = models.Timeframe(
                roadmap_id=roadmap_id,
                label=label,
                granularity=granularity,
            )
            db.add(timeframe)
            db.flush()
            timeframe_map[label] = timeframe

        db.add(
            models.Task(
                timeframe_id=timeframe_map[label].id,
                title=title,
                is_done=bool(task.get("is_done", False)),
            )
        )


def update_roadmap_content(roadmap_id: int, new_text: str, parser_func, user_id: str) -> bool:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return False

        parsed = parser_func(new_text)
        tasks = [
            {
                "title": item["title"],
                "timeframe": item.get("timeframe_label", "General"),
                "granularity": item.get("granularity", "section"),
                "is_done": item.get("is_done", False),
            }
            for item in parsed
            if item.get("type") == "task"
        ]

        roadmap.raw_text = new_text
        _replace_roadmap_tasks(db, roadmap_id, tasks)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_roadmap_smart(
    roadmap_id: int,
    name: str,
    tasks: List[Dict[str, Any]],
    user_id: str,
    raw_text: str = "",
) -> bool:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return False

        roadmap.name = name
        if raw_text:
            roadmap.raw_text = raw_text
        _replace_roadmap_tasks(db, roadmap_id, tasks)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_imported_roadmap(
    name: str,
    tasks: List[Dict[str, Any]],
    user_id: str,
    raw_text: str = "",
) -> int:
    db = SessionLocal()
    try:
        roadmap = models.Roadmap(name=name, raw_text=raw_text, user_id=user_id)
        db.add(roadmap)
        db.flush()
        _replace_roadmap_tasks(db, roadmap.id, tasks)
        db.commit()
        db.refresh(roadmap)
        return roadmap.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_tasks(roadmap_id: int, user_id: str, timeframe_id: Optional[int] = None) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = (
            db.query(models.Task)
            .join(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.Timeframe.roadmap_id == roadmap_id, models.Roadmap.user_id == user_id)
        )

        if timeframe_id:
            query = query.filter(models.Task.timeframe_id == timeframe_id)

        tasks = query.order_by(models.Timeframe.id.asc(), models.Task.id.asc()).all()
        return [
            {
                "id": task.id,
                "title": task.title,
                "is_done": task.is_done,
                "timeframe_id": task.timeframe_id,
                "timeframe_label": task.timeframe.label,
                "created_at": task.created_at,
            }
            for task in tasks
        ]
    finally:
        db.close()


def update_task_status(task_id: int, is_done: bool, user_id: str) -> bool:
    db = SessionLocal()
    try:
        task = (
            db.query(models.Task)
            .join(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.Task.id == task_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not task:
            return False
        task.is_done = is_done
        db.commit()
        return True
    finally:
        db.close()


def get_timeframes(roadmap_id: int, user_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        timeframes = (
            db.query(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.Timeframe.roadmap_id == roadmap_id, models.Roadmap.user_id == user_id)
            .order_by(models.Timeframe.id.asc())
            .all()
        )
        return [
            {
                "id": timeframe.id,
                "label": timeframe.label,
                "start_date": timeframe.start_date,
                "end_date": timeframe.end_date,
            }
            for timeframe in timeframes
        ]
    finally:
        db.close()


def update_timeframe_dates(
    timeframe_id: int,
    start_date: Optional[str],
    end_date: Optional[str],
    user_id: str,
) -> bool:
    db = SessionLocal()
    try:
        timeframe = (
            db.query(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.Timeframe.id == timeframe_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not timeframe:
            return False
        timeframe.start_date = start_date
        timeframe.end_date = end_date
        db.commit()
        return True
    finally:
        db.close()


def export_roadmap_data(roadmap_id: int, user_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return None

        export_tasks = []
        for timeframe in roadmap.timeframes:
            for task in timeframe.tasks:
                export_tasks.append(
                    {
                        "title": task.title,
                        "timeframe": timeframe.label,
                        "is_done": task.is_done,
                    }
                )

        return {
            "name": roadmap.name,
            "tasks": export_tasks,
        }
    finally:
        db.close()
