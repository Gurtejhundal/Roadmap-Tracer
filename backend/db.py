import json
from collections import defaultdict, deque
from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, inspect, text
from sqlalchemy.orm import selectinload

from database import SessionLocal, engine
import models_db as models


def init_db():
    models.Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    _migrate_legacy_task_properties()


def _run_lightweight_migrations():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    migrations = {
        "roadmaps": {
            "user_id": "user_id VARCHAR DEFAULT 'public_user'",
            "document_json": "document_json TEXT DEFAULT '[]'",
        },
        "timeframes": {
            "start_date": "start_date VARCHAR",
            "end_date": "end_date VARCHAR",
        },
        "tasks": {
            "properties_json": "properties_json TEXT DEFAULT '{}'",
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


def _legacy_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "x",
        "done",
        "checked",
    }


def _legacy_falsey(value: Any) -> bool:
    if value is False or value is None:
        return True
    return str(value).strip().lower() in {"", "0", "false", "no", "n", "off", "unchecked"}


def _legacy_revision_count(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    raw = str(value or "").strip()
    return int(raw) if re.fullmatch(r"\+?\d+", raw) and int(raw) > 0 else None


def _migrate_legacy_task_properties() -> None:
    """Move meaningful revision/revisit values into optional task blocks.

    Empty defaults are removed without creating blocks. The migration is
    idempotent because migrated keys are removed from properties_json.
    """
    db = SessionLocal()
    try:
        changed = False
        for task in db.query(models.Task).all():
            properties = _decode_properties(task.properties_json)
            revision_keys = [key for key in properties if key.strip().lower() in {"revision", "revision count", "revisions"}]
            revisit_keys = [key for key in properties if key.strip().lower() in {"revisit", "visit again"}]
            if not revision_keys and not revisit_keys:
                continue

            next_position = (
                max(
                    (
                        block.position
                        for block in task.blocks
                        if isinstance(block.position, int) and block.position >= 0
                    ),
                    default=-1,
                )
                + 1
            )
            task_changed = False
            for key in revision_keys:
                value = properties[key]
                count = _legacy_revision_count(value)
                if count is not None:
                    properties.pop(key)
                    task_changed = True
                    task.blocks.append(
                        models.TaskBlock(
                            type="counter",
                            data_json=json.dumps(
                                {"label": "Revision", "value": count, "step": 1},
                                ensure_ascii=False,
                            ),
                            position=next_position,
                        )
                    )
                    next_position += 1
                elif _legacy_falsey(value):
                    properties.pop(key)
                    task_changed = True

            for key in revisit_keys:
                revisit = properties[key]
                if _legacy_truthy(revisit):
                    properties.pop(key)
                    task_changed = True
                    task.blocks.append(
                        models.TaskBlock(
                            type="bookmark",
                            data_json=json.dumps(
                                {"label": "Revisit", "bookmarked": True},
                                ensure_ascii=False,
                            ),
                            position=next_position,
                        )
                    )
                    next_position += 1
                elif _legacy_falsey(revisit):
                    properties.pop(key)
                    task_changed = True

            if task_changed:
                task.properties_json = _encode_properties(properties)
                changed = True

        if changed:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _roadmap_task_counts(db, roadmap_ids: List[int]) -> Dict[int, tuple[int, int]]:
    if not roadmap_ids:
        return {}

    rows = (
        db.query(
            models.Timeframe.roadmap_id,
            func.count(models.Task.id),
            func.coalesce(
                func.sum(case((models.Task.is_done.is_(True), 1), else_=0)),
                0,
            ),
        )
        .outerjoin(models.Task, models.Task.timeframe_id == models.Timeframe.id)
        .filter(models.Timeframe.roadmap_id.in_(roadmap_ids))
        .group_by(models.Timeframe.roadmap_id)
        .all()
    )
    return {
        int(roadmap_id): (int(total or 0), int(completed or 0))
        for roadmap_id, total, completed in rows
    }


def _roadmap_to_dict(
    roadmap: models.Roadmap,
    counts: tuple[int, int] = (0, 0),
    *,
    include_raw_text: bool = True,
) -> Dict[str, Any]:
    result = {
        "id": roadmap.id,
        "name": roadmap.name,
        "created_at": roadmap.created_at,
        "total_tasks": counts[0],
        "completed_tasks": counts[1],
    }
    if include_raw_text:
        result["raw_text"] = roadmap.raw_text
    return result


def get_roadmaps(user_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmaps = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.user_id == user_id)
            .order_by(models.Roadmap.created_at.desc())
            .all()
        )
        counts = _roadmap_task_counts(db, [roadmap.id for roadmap in roadmaps])
        return [
            _roadmap_to_dict(
                roadmap,
                counts.get(roadmap.id, (0, 0)),
                include_raw_text=False,
            )
            for roadmap in roadmaps
        ]
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
        counts = _roadmap_task_counts(db, [roadmap.id])
        return _roadmap_to_dict(roadmap, counts.get(roadmap.id, (0, 0)))
    finally:
        db.close()


def roadmap_name_exists(
    name: str,
    user_id: str,
    *,
    exclude_roadmap_id: Optional[int] = None,
) -> bool:
    db = SessionLocal()
    try:
        query = db.query(models.Roadmap.id).filter(
            models.Roadmap.user_id == user_id,
            func.lower(func.trim(models.Roadmap.name)) == name.strip().lower(),
        )
        if exclude_roadmap_id is not None:
            query = query.filter(models.Roadmap.id != exclude_roadmap_id)
        return query.first() is not None
    finally:
        db.close()


def roadmap_exists(roadmap_id: int, user_id: str) -> bool:
    db = SessionLocal()
    try:
        return (
            db.query(models.Roadmap.id)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
            is not None
        )
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
    existing_timeframes_by_id = {
        row.id: {
            "granularity": row.granularity,
            "start_date": row.start_date,
            "end_date": row.end_date,
        }
        for row in db.query(
            models.Timeframe.id,
            models.Timeframe.label,
            models.Timeframe.granularity,
            models.Timeframe.start_date,
            models.Timeframe.end_date,
        )
        .filter(models.Timeframe.roadmap_id == roadmap_id)
        .all()
    }
    existing_timeframes_by_label: Dict[str, Dict[str, Any]] = {}
    for row in db.query(
        models.Timeframe.label,
        models.Timeframe.granularity,
        models.Timeframe.start_date,
        models.Timeframe.end_date,
    ).filter(models.Timeframe.roadmap_id == roadmap_id).all():
        existing_timeframes_by_label.setdefault(
            row.label,
            {
                "granularity": row.granularity,
                "start_date": row.start_date,
                "end_date": row.end_date,
            },
        )

    task_ids = (
        db.query(models.Task.id)
        .join(models.Timeframe)
        .filter(models.Timeframe.roadmap_id == roadmap_id)
    )
    db.query(models.TaskBlock).filter(models.TaskBlock.task_id.in_(task_ids)).delete(
        synchronize_session=False
    )
    db.query(models.Task).filter(
        models.Task.timeframe_id.in_(
            db.query(models.Timeframe.id).filter(models.Timeframe.roadmap_id == roadmap_id)
        )
    ).delete(synchronize_session=False)

    db.query(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id).delete(
        synchronize_session=False
    )

    timeframe_map: Dict[tuple, models.Timeframe] = {}
    fallback_run = 0
    previous_fallback_label: Optional[str] = None
    previous_used_fallback = False
    for task in tasks:
        title = str(task.get("title", "")).strip()
        if not title:
            continue

        label = str(task.get("timeframe") or task.get("timeframe_label") or "General").strip() or "General"
        raw_timeframe_id = task.get("timeframe_id")
        timeframe_id = (
            raw_timeframe_id
            if isinstance(raw_timeframe_id, int)
            and not isinstance(raw_timeframe_id, bool)
            and raw_timeframe_id > 0
            else None
        )
        if timeframe_id is not None:
            if timeframe_id not in existing_timeframes_by_id:
                raise ValueError("Timeframe does not belong to this roadmap.")
            timeframe_key = ("id", timeframe_id)
            previous_timeframe = existing_timeframes_by_id[timeframe_id]
            previous_used_fallback = False
            previous_fallback_label = None
        else:
            if not previous_used_fallback or label != previous_fallback_label:
                fallback_run += 1
            timeframe_key = ("run", fallback_run)
            previous_timeframe = existing_timeframes_by_label.get(label, {})
            previous_used_fallback = True
            previous_fallback_label = label
        granularity = str(
            task.get("granularity") or previous_timeframe.get("granularity") or "section"
        ).strip() or "section"

        if timeframe_key not in timeframe_map:
            timeframe = models.Timeframe(
                roadmap_id=roadmap_id,
                label=label,
                granularity=granularity,
                start_date=(
                    task["start_date"]
                    if "start_date" in task
                    else previous_timeframe.get("start_date")
                ),
                end_date=(
                    task["end_date"]
                    if "end_date" in task
                    else previous_timeframe.get("end_date")
                ),
            )
            db.add(timeframe)
            db.flush()
            timeframe_map[timeframe_key] = timeframe

        db_task = models.Task(
            timeframe_id=timeframe_map[timeframe_key].id,
            title=title,
            is_done=bool(task.get("is_done", False)),
            properties_json=_encode_properties(task.get("properties") or {}),
        )
        db.add(db_task)
        db.flush()
        raw_blocks = task.get("blocks") or []
        if not isinstance(raw_blocks, list) or any(
            not isinstance(block, dict) for block in raw_blocks
        ):
            raise ValueError("Task blocks must be a list of objects.")
        ordered_blocks = sorted(
            enumerate(raw_blocks),
            key=lambda item: (
                item[1].get("position")
                if isinstance(item[1].get("position"), int) and item[1].get("position") >= 0
                else item[0]
            ),
        )
        for position, (_, block) in enumerate(ordered_blocks):
            block_type = _normalize_block_type(str(block.get("type") or ""))
            block_data = block.get("data") if isinstance(block.get("data"), dict) else {}
            db.add(
                models.TaskBlock(
                    task_id=db_task.id,
                    type=block_type,
                    data_json=_encode_block_data(block_data),
                    position=position,
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

        existing_task_rows = (
            db.query(
                models.Task.id,
                models.Timeframe.id.label("timeframe_id"),
                models.Timeframe.label,
                models.Task.title,
                models.Task.is_done,
                models.Task.properties_json,
            )
            .join(models.Timeframe)
            .filter(models.Timeframe.roadmap_id == roadmap_id)
            .order_by(models.Timeframe.id.asc(), models.Task.id.asc())
            .all()
        )
        task_ids = [row.id for row in existing_task_rows]
        blocks_by_task = defaultdict(list)
        if task_ids:
            block_rows = (
                db.query(
                    models.TaskBlock.task_id,
                    models.TaskBlock.type,
                    models.TaskBlock.data_json,
                    models.TaskBlock.position,
                    models.TaskBlock.id,
                )
                .filter(models.TaskBlock.task_id.in_(task_ids))
                .order_by(
                    models.TaskBlock.task_id.asc(),
                    models.TaskBlock.position.asc(),
                    models.TaskBlock.id.asc(),
                )
                .all()
            )
            for block_row in block_rows:
                blocks_by_task[block_row.task_id].append(
                    {
                        "type": block_row.type,
                        "data": _decode_block_data(block_row.data_json),
                        "position": block_row.position,
                    }
                )

        existing_by_key = defaultdict(deque)
        for row in existing_task_rows:
            existing_by_key[(row.label, row.title)].append(
                {
                    "timeframe_id": row.timeframe_id,
                    "is_done": row.is_done,
                    "properties": _decode_properties(row.properties_json),
                    "blocks": blocks_by_task[row.id],
                }
            )

        parsed = parser_func(new_text)
        tasks = [
            {
                "title": item["title"],
                "timeframe": item.get("timeframe_label", "General"),
                **(
                    {"timeframe_id": item["timeframe_id"]}
                    if item.get("timeframe_id") is not None
                    else {}
                ),
                "granularity": item.get("granularity", "section"),
                "is_done": item.get("is_done", False),
            }
            for item in parsed
            if item.get("type") == "task"
        ]
        for task in tasks:
            key = (task["timeframe"], task["title"])
            if not existing_by_key[key]:
                continue
            existing_task = existing_by_key[key].popleft()
            task.update(existing_task)

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
    document: Optional[List[Dict[str, Any]]] = None,
) -> int:
    db = SessionLocal()
    try:
        roadmap = models.Roadmap(
            name=name,
            raw_text=raw_text,
            user_id=user_id,
            document_json=json.dumps(document or [], ensure_ascii=False, allow_nan=False),
        )
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


MAX_PROPERTIES_DATA_BYTES = 256 * 1024


def _reject_non_finite_json(value: str):
    raise ValueError(f"Non-finite JSON number is not supported: {value}")


def _encode_json_object(value: Dict[str, Any], label: str, max_bytes: int) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be valid JSON.") from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError(f"{label} must be {max_bytes // 1024} KB or smaller.")
    return encoded


def _decode_json_object(value: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(value or "{}", parse_constant=_reject_non_finite_json)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _encode_properties(value: Dict[str, Any]) -> str:
    return _encode_json_object(value, "Task properties", MAX_PROPERTIES_DATA_BYTES)


def _decode_properties(value: str) -> Dict[str, Any]:
    return _decode_json_object(value)


def _decode_document(value: str) -> List[Dict[str, Any]]:
    try:
        parsed = json.loads(value or "[]", parse_constant=_reject_non_finite_json)
        from roadmap_parser import sanitize_document_elements

        return sanitize_document_elements(parsed)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def get_roadmap_document(roadmap_id: int, user_id: str) -> Optional[List[Dict[str, Any]]]:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return None
        return _decode_document(roadmap.document_json)
    finally:
        db.close()


BLOCK_TYPE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
MAX_BLOCK_DATA_BYTES = 64 * 1024
MAX_BULK_BLOCK_TASKS = 5000
MAX_BULK_BLOCK_TOTAL_BYTES = 16 * 1024 * 1024
BULK_TASK_QUERY_CHUNK_SIZE = 500


def _normalize_block_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not BLOCK_TYPE_RE.fullmatch(normalized):
        raise ValueError(
            "Block type must start with a letter and contain only lowercase letters, numbers, underscores, or hyphens."
        )
    return normalized


def _encode_block_data(value: Dict[str, Any]) -> str:
    return _encode_json_object(value, "Block data", MAX_BLOCK_DATA_BYTES)


def _decode_block_data(value: str) -> Dict[str, Any]:
    return _decode_json_object(value)


def _block_to_dict(block: models.TaskBlock) -> Dict[str, Any]:
    return {
        "id": block.id,
        "task_id": block.task_id,
        "type": block.type,
        "data": _decode_block_data(block.data_json),
        "position": block.position,
        "created_at": block.created_at,
        "updated_at": block.updated_at,
    }


def _task_blocks(task: models.Task) -> List[Dict[str, Any]]:
    return [_block_to_dict(block) for block in sorted(task.blocks, key=lambda item: (item.position, item.id))]


def get_tasks(roadmap_id: int, user_id: str, timeframe_id: Optional[int] = None) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = (
            db.query(models.Task)
            .options(selectinload(models.Task.blocks), selectinload(models.Task.timeframe))
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
                "properties": _decode_properties(task.properties_json),
                "blocks": _task_blocks(task),
            }
            for task in tasks
        ]
    finally:
        db.close()


def _task_to_dict(task: models.Task) -> Dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "is_done": task.is_done,
        "timeframe_id": task.timeframe_id,
        "timeframe_label": task.timeframe.label,
        "created_at": task.created_at,
        "properties": _decode_properties(task.properties_json),
        "blocks": _task_blocks(task),
    }


def create_task(
    roadmap_id: int,
    timeframe_label: str,
    title: str,
    user_id: str,
    timeframe_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmap = (
            db.query(models.Roadmap)
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return None

        label = timeframe_label.strip() or "General"
        if timeframe_id is not None:
            timeframe = (
                db.query(models.Timeframe)
                .filter(
                    models.Timeframe.id == timeframe_id,
                    models.Timeframe.roadmap_id == roadmap_id,
                )
                .first()
            )
            if timeframe is None:
                return None
        else:
            timeframe = (
                db.query(models.Timeframe)
                .filter(models.Timeframe.roadmap_id == roadmap_id, models.Timeframe.label == label)
                .first()
            )
        if not timeframe:
            timeframe = models.Timeframe(roadmap_id=roadmap_id, label=label, granularity="section")
            db.add(timeframe)
            db.flush()

        task = models.Task(timeframe_id=timeframe.id, title=title.strip(), is_done=False)
        db.add(task)
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    except Exception:
        db.rollback()
        raise
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


def update_task_title(task_id: int, title: str, user_id: str) -> Optional[Dict[str, Any]]:
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
            return None
        task.title = title.strip()
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_task_properties(task_id: int, properties: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
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
            return None
        task.properties_json = _encode_properties(properties or {})
        db.commit()
        db.refresh(task)
        return _task_to_dict(task)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_task_blocks(task_id: int, user_id: str) -> Optional[List[Dict[str, Any]]]:
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
            return None
        return _task_blocks(task)
    finally:
        db.close()


def create_task_block(
    task_id: int,
    block_type: str,
    data: Dict[str, Any],
    position: Optional[int],
    user_id: str,
) -> Optional[Dict[str, Any]]:
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
            return None

        siblings = (
            db.query(models.TaskBlock)
            .filter(models.TaskBlock.task_id == task_id)
            .order_by(models.TaskBlock.position.asc(), models.TaskBlock.id.asc())
            .all()
        )
        insert_at = len(siblings) if position is None else min(position, len(siblings))
        block = models.TaskBlock(
            task_id=task_id,
            type=_normalize_block_type(block_type),
            data_json=_encode_block_data(data),
            position=insert_at,
        )
        siblings.insert(insert_at, block)
        for sibling_position, sibling in enumerate(siblings):
            sibling.position = sibling_position
        db.add(block)
        db.commit()
        db.refresh(block)
        return _block_to_dict(block)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_task_blocks_bulk(
    task_ids: List[int],
    block_type: str,
    data: Dict[str, Any],
    user_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """Append one cloned block to every requested task in a single transaction.

    ``None`` means at least one task was missing, was not owned by ``user_id``,
    or belonged to a different roadmap. No blocks are written until the complete,
    de-duplicated target set passes those checks.
    """
    unique_task_ids = list(dict.fromkeys(task_ids))
    if not unique_task_ids:
        raise ValueError("At least one task is required.")
    if len(unique_task_ids) > MAX_BULK_BLOCK_TASKS:
        raise ValueError(f"A bulk block can target at most {MAX_BULK_BLOCK_TASKS} tasks.")

    normalized_type = _normalize_block_type(block_type)
    encoded_data = _encode_block_data(data)
    if len(encoded_data.encode("utf-8")) * len(unique_task_ids) > MAX_BULK_BLOCK_TOTAL_BYTES:
        raise ValueError(
            "Bulk block data would exceed the 16 MB write limit. Use a smaller block or fewer tasks."
        )
    db = SessionLocal()
    try:
        tasks_by_id: Dict[int, models.Task] = {}
        for offset in range(0, len(unique_task_ids), BULK_TASK_QUERY_CHUNK_SIZE):
            task_id_chunk = unique_task_ids[offset : offset + BULK_TASK_QUERY_CHUNK_SIZE]
            tasks = (
                db.query(models.Task)
                .options(
                    selectinload(models.Task.blocks),
                    selectinload(models.Task.timeframe),
                )
                .join(models.Timeframe)
                .join(models.Roadmap)
                .filter(
                    models.Task.id.in_(task_id_chunk),
                    models.Roadmap.user_id == user_id,
                )
                .with_for_update()
                .all()
            )
            tasks_by_id.update({task.id: task for task in tasks})

        if len(tasks_by_id) != len(unique_task_ids):
            db.rollback()
            return None

        roadmap_ids = {
            task.timeframe.roadmap_id
            for task in tasks_by_id.values()
        }
        if len(roadmap_ids) != 1:
            db.rollback()
            return None

        created_blocks: List[models.TaskBlock] = []
        for task_id in unique_task_ids:
            task = tasks_by_id[task_id]
            next_position = (
                max((block.position for block in task.blocks), default=-1) + 1
            )
            block = models.TaskBlock(
                task_id=task_id,
                type=normalized_type,
                data_json=encoded_data,
                position=next_position,
            )
            db.add(block)
            created_blocks.append(block)

        db.flush()
        result = [_block_to_dict(block) for block in created_blocks]
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_task_block(
    block_id: int,
    updates: Dict[str, Any],
    user_id: str,
) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        block = (
            db.query(models.TaskBlock)
            .join(models.Task)
            .join(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.TaskBlock.id == block_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not block:
            return None

        if "type" in updates:
            block.type = _normalize_block_type(updates["type"])
        if "data" in updates:
            block.data_json = _encode_block_data(updates["data"])
        if "position" in updates:
            siblings = (
                db.query(models.TaskBlock)
                .filter(models.TaskBlock.task_id == block.task_id)
                .order_by(models.TaskBlock.position.asc(), models.TaskBlock.id.asc())
                .all()
            )
            ordered = [sibling for sibling in siblings if sibling.id != block.id]
            new_position = min(int(updates["position"]), len(ordered))
            ordered.insert(new_position, block)
            for position, sibling in enumerate(ordered):
                sibling.position = position

        block.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(block)
        return _block_to_dict(block)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_task_block(block_id: int, user_id: str) -> bool:
    db = SessionLocal()
    try:
        block = (
            db.query(models.TaskBlock)
            .join(models.Task)
            .join(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.TaskBlock.id == block_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not block:
            return False
        task_id = block.task_id
        db.delete(block)
        db.flush()
        siblings = (
            db.query(models.TaskBlock)
            .filter(models.TaskBlock.task_id == task_id)
            .order_by(models.TaskBlock.position.asc(), models.TaskBlock.id.asc())
            .all()
        )
        for position, sibling in enumerate(siblings):
            sibling.position = position
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_task(task_id: int, user_id: str) -> bool:
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
        db.delete(task)
        db.commit()
        return True
    finally:
        db.close()


def update_timeframe_task_status(timeframe_id: int, is_done: bool, user_id: str) -> Optional[int]:
    db = SessionLocal()
    try:
        timeframe = (
            db.query(models.Timeframe)
            .join(models.Roadmap)
            .filter(models.Timeframe.id == timeframe_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not timeframe:
            return None

        updated = (
            db.query(models.Task)
            .filter(models.Task.timeframe_id == timeframe_id)
            .update({models.Task.is_done: is_done}, synchronize_session=False)
        )
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
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
                "granularity": timeframe.granularity,
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
            .options(
                selectinload(models.Roadmap.timeframes)
                .selectinload(models.Timeframe.tasks)
                .selectinload(models.Task.blocks)
            )
            .filter(models.Roadmap.id == roadmap_id, models.Roadmap.user_id == user_id)
            .first()
        )
        if not roadmap:
            return None

        export_tasks = []
        for timeframe in sorted(roadmap.timeframes, key=lambda item: item.id):
            for task in sorted(timeframe.tasks, key=lambda item: item.id):
                export_tasks.append(
                    {
                        "title": task.title,
                        "timeframe": timeframe.label,
                        "timeframe_id": timeframe.id,
                        "granularity": timeframe.granularity,
                        "start_date": timeframe.start_date,
                        "end_date": timeframe.end_date,
                        "is_done": task.is_done,
                        "properties": _decode_properties(task.properties_json),
                        "blocks": _task_blocks(task),
                    }
                )

        return {
            "name": roadmap.name,
            "tasks": export_tasks,
            "document": _decode_document(roadmap.document_json),
        }
    finally:
        db.close()
