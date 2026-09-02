from contextlib import asynccontextmanager
from datetime import date
from io import BytesIO
import os
from pathlib import Path
import re
from typing import Any, List

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import db
from pdf_importer import parse_pdf_document
import roadmap_parser as parser
from models import (
    RoadmapCreate,
    RoadmapImport,
    RoadmapNameUpdate,
    RoadmapResponse,
    RoadmapSummary,
    RoadmapUpdate,
    TaskCreate,
    TaskBlockBulkCreate,
    TaskBlockCreate,
    TaskBlockUpdate,
    TaskPropertiesUpdate,
    TaskTitleUpdate,
    TaskUpdate,
    TimeframeDateUpdate,
)


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".rst",
    ".log",
}
DOCX_EXTENSIONS = {".docx"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Roadmap Tracer API", lifespan=lifespan)


class ApiPrefixMiddleware:
    """Expose the same API under /api when Vercel Services preserves the prefix."""

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope.get("type") in {"http", "websocket"}:
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                raw_path = scope.get("raw_path")
                if isinstance(raw_path, bytes):
                    scope["raw_path"] = raw_path[4:] or b"/"
        await self.application(scope, receive, send)


app.add_middleware(ApiPrefixMiddleware)


def _allowed_cors_origins() -> List[str]:
    origins = {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    }
    configured = os.getenv("TRAQU_CORS_ORIGINS", "")
    origins.update(origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip())
    frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
    if frontend_url:
        origins.add(frontend_url)
    return sorted(origins)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(
    x_local_user_id: str = Header(None, alias="X-Local-User-Id", max_length=200),
    x_legacy_user_id: str = Header(None, alias="X-Clerk-User-Id", max_length=200),
):
    return (x_local_user_id or x_legacy_user_id or "public_user").strip() or "public_user"


@app.get("/")
def read_root():
    return {"message": "Welcome to Roadmap Tracer API"}


def _normalize_name(name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Roadmap name is required.")
    return normalized


def _ensure_unique_name(
    name: str,
    user_id: str,
    *,
    exclude_roadmap_id: int | None = None,
):
    if db.roadmap_name_exists(
        name,
        user_id,
        exclude_roadmap_id=exclude_roadmap_id,
    ):
        raise HTTPException(status_code=400, detail="Roadmap with this name already exists.")


def _normalize_date_range(start_date: str | None, end_date: str | None):
    normalized = []
    for label, value in (("Start date", start_date), ("End date", end_date)):
        if value is None or not value.strip():
            normalized.append(None)
            continue
        candidate = value.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            raise HTTPException(status_code=400, detail=f"{label} must use YYYY-MM-DD format.")
        try:
            parsed = date.fromisoformat(candidate)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{label} is not a valid date.") from exc
        normalized.append(parsed.isoformat())

    normalized_start, normalized_end = normalized
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date.")
    return normalized_start, normalized_end


def _model_updates(model: Any) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


async def _read_upload_limited(upload: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload incrementally and stop as soon as it exceeds the cap."""
    chunks: List[bytes] = []
    total = 0
    while True:
        remaining_with_sentinel = max_bytes - total + 1
        chunk = await upload.read(min(UPLOAD_READ_CHUNK_BYTES, remaining_with_sentinel))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Roadmap file must be {max_bytes // (1024 * 1024)} MB or smaller.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_parsed_tasks(tasks, *, preserve_timeframe_ids: bool = False):
    if not tasks:
        raise HTTPException(status_code=400, detail="No trackable tasks were found in this roadmap.")

    validated = []
    for task in tasks:
        parsed_task = dict(task)
        if not preserve_timeframe_ids:
            parsed_task.pop("timeframe_id", None)
        if "start_date" in parsed_task or "end_date" in parsed_task:
            raw_start = parsed_task.get("start_date")
            raw_end = parsed_task.get("end_date")
            start_date, end_date = _normalize_date_range(
                None if raw_start is None else str(raw_start),
                None if raw_end is None else str(raw_end),
            )
            if "start_date" in parsed_task:
                parsed_task["start_date"] = start_date
            if "end_date" in parsed_task:
                parsed_task["end_date"] = end_date
        validated.append(parsed_task)
    return validated


def _tasks_from_text(text: str):
    return _validate_parsed_tasks(parser.parse_tasks(text))


def _tasks_from_import(roadmap: RoadmapImport, *, preserve_timeframe_ids: bool = True):
    tasks = []
    for index, task in enumerate(roadmap.tasks, start=1):
        title = task.title.strip()
        timeframe = task.timeframe.strip() or "General"
        if not title:
            raise HTTPException(status_code=400, detail=f"Task {index} title is required.")

        start_date, end_date = _normalize_date_range(task.start_date, task.end_date)
        imported_task = {
            "title": title,
            "timeframe": timeframe,
            "is_done": task.is_done,
            "properties": task.properties,
            "blocks": [
                block.model_dump() if hasattr(block, "model_dump") else block.dict()
                for block in task.blocks
            ],
        }
        if preserve_timeframe_ids and task.timeframe_id is not None:
            imported_task["timeframe_id"] = task.timeframe_id
        if task.granularity:
            imported_task["granularity"] = task.granularity.strip() or "section"
        if start_date is not None:
            imported_task["start_date"] = start_date
        if end_date is not None:
            imported_task["end_date"] = end_date
        tasks.append(imported_task)

    if not tasks:
        raise HTTPException(status_code=400, detail="No trackable tasks were found in this roadmap.")
    return tasks


def _decode_text_bytes(content: bytes) -> str:
    if b"\x00" in content[:2048]:
        raise HTTPException(
            status_code=415,
            detail="This file looks binary. Upload a PDF or a text-based roadmap file.",
        )

    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise HTTPException(status_code=415, detail="Could not decode this file as text.")


def _extract_pdf_text(content: bytes) -> str:
    table_text = _extract_pdf_table_text(content)
    if table_text:
        return table_text

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="PDF import is not installed on the backend. Install the pypdf package.",
        ) from exc

    try:
        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                page_text = page.extract_text() or ""
            pages.append(page_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read text from this PDF.") from exc

    text = "\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text was found in this PDF. Scanned image PDFs need OCR first.",
        )
    return text


def _clean_pdf_cell(value) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip()


def _normalize_rotated_topic(value: str, is_rotated: bool) -> str:
    """Restore topic labels that PDF table extractors return backwards."""
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return ""
    if not is_rotated:
        return " ".join(lines)

    restored = [line[::-1].strip() for line in reversed(lines)]
    topic = " ".join(restored)
    topic = re.sub(r"^DP (.+) on$", r"DP on \1", topic, flags=re.IGNORECASE)
    topic = re.sub(r"^DP on (.+) Sub-$", r"DP on Sub-\1", topic, flags=re.IGNORECASE)
    if topic.lower() == "s asked) advance problems(les":
        topic = "Advanced Problems (Less asked)"
    return topic


def _normalize_column_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_pdf_cell(value).lower()).strip()


def _find_column(headers, names, default=None):
    for index, header in enumerate(headers):
        if _normalize_column_name(header) in names:
            return index
    return default


def _extract_pdf_table_document(content: bytes):
    """Convert checklist-style PDF tables into markdown sections and tasks.

    The layout metadata is important here: large rows become roadmap sections,
    first-column labels become topic groups, and second-column rows become tasks.
    Normal prose PDFs fall through to the pypdf extractor above.
    """
    try:
        import pdfplumber
    except ImportError:
        return "", []

    try:
        document = pdfplumber.open(BytesIO(content))
    except Exception:
        return "", []

    output = []
    current_section = "General"
    current_group = "General"
    emitted_group = ""
    task_count = 0
    table_count = 0
    tasks = []
    headers = ["Topic", "Problem Name", "Completed", "Revision Count", "Revisit"]
    topic_index = 0
    title_index = 1
    completed_index = 2
    title_headers = {
        "action",
        "checklist item",
        "description",
        "item",
        "problem",
        "problem name",
        "task",
        "task name",
        "title",
        "to do",
        "todo",
    }
    topic_headers = {"area", "category", "group", "module", "section", "stage", "topic"}
    completed_headers = {"complete", "completed", "done", "finished", "status"}

    try:
        for page in document.pages:
            for table in page.find_tables():
                rows = table.extract()
                if not rows or max((len(row) for row in rows), default=0) < 2:
                    continue

                table_count += 1
                seen_header_on_page = False
                for index, row in enumerate(rows):
                    candidate_headers = [_clean_pdf_cell(cell) for cell in row]
                    detected_title_index = _find_column(candidate_headers, title_headers)
                    if detected_title_index is not None:
                        headers = [
                            header or f"Column {column_index + 1}"
                            for column_index, header in enumerate(candidate_headers)
                        ]
                        title_index = detected_title_index
                        topic_index = _find_column(headers, topic_headers, 0 if title_index != 0 else None)
                        completed_index = _find_column(headers, completed_headers)
                        seen_header_on_page = True
                        continue

                    problem = _clean_pdf_cell(row[title_index] if title_index < len(row) else "")
                    if not problem:
                        continue

                    topic_raw = row[topic_index] if topic_index is not None and topic_index < len(row) else ""
                    completed = (
                        _clean_pdf_cell(row[completed_index])
                        if completed_index is not None and completed_index < len(row)
                        else ""
                    )

                    problem_cell = (
                        table.rows[index].cells[title_index]
                        if index < len(table.rows) and title_index < len(table.rows[index].cells)
                        else None
                    )
                    problem_words = page.crop(problem_cell).extract_words(extra_attrs=["size"]) if problem_cell else []
                    largest_font = max((float(word.get("size", 0)) for word in problem_words), default=0)

                    # Checklist PDFs commonly use a larger, merged-looking row for a major section.
                    if largest_font >= 14 and len(problem) <= 100:
                        current_section = problem
                        current_group = problem
                        emitted_group = ""
                        continue

                    topic = ""
                    topic_cell = (
                        table.rows[index].cells[topic_index]
                        if topic_index is not None
                        and index < len(table.rows)
                        and topic_index < len(table.rows[index].cells)
                        else None
                    )
                    if topic_raw and topic_cell:
                        topic_chars = page.crop(topic_cell).chars
                        rotated = bool(topic_chars) and sum(bool(char.get("upright", True)) for char in topic_chars) < len(topic_chars) / 2
                        topic = _normalize_rotated_topic(str(topic_raw), rotated)

                        if not seen_header_on_page and table_count > 1:
                            known_short_groups = {"DP", "1D DP", "2D DP", "DLL", "BST", "MCM", "FAQ", "FAQS"}
                            is_split_phrase = topic.lower().endswith(" o") and current_group.lower().startswith("n ")
                            if topic and (
                                is_split_phrase
                                or (len(current_group) < 4 and current_group.upper() not in known_short_groups)
                            ):
                                old_group = current_group
                                current_group = f"{topic}{current_group}".strip()
                                for existing_task in reversed(tasks):
                                    if existing_task["timeframe"] != old_group:
                                        break
                                    existing_task["timeframe"] = current_group
                                for output_index in range(len(output) - 1, -1, -1):
                                    if output[output_index] == f"## {old_group}":
                                        output[output_index] = f"## {current_group}"
                                        break
                                emitted_group = current_group
                            topic = ""

                    if topic and topic.lower() not in {"topic", "category", "section"}:
                        if current_section.lower().endswith(topic.lower()) or topic.lower().endswith(current_section.lower()):
                            topic = current_section
                        current_group = topic

                    if current_group != emitted_group:
                        output.append(f"## {current_group}")
                        emitted_group = current_group

                    is_done = completed.lower() in {"x", "yes", "true", "done", "completed", "1", "✓", "✔"}
                    output.append(f"{'[x]' if is_done else '-'} {problem}")
                    properties = {}
                    reserved_columns = {title_index, topic_index, completed_index}
                    for column_index in range(len(row)):
                        if column_index in reserved_columns:
                            continue
                        header = headers[column_index] if column_index < len(headers) else f"Column {column_index + 1}"
                        if header:
                            properties[header] = _clean_pdf_cell(row[column_index])
                    tasks.append(
                        {
                            "title": problem,
                            "timeframe": current_group,
                            "is_done": is_done,
                            "granularity": "section",
                            "properties": properties,
                        }
                    )
                    task_count += 1
    except Exception:
        return "", []
    finally:
        document.close()

    if table_count == 0 or task_count < 3:
        return "", []
    return "\n".join(output), tasks


def _extract_pdf_table_text(content: bytes) -> str:
    text, _ = _extract_pdf_table_document(content)
    return text


DOCX_TABLE_HEADER_LABELS = {
    "action",
    "assignee",
    "category",
    "completed",
    "deadline",
    "description",
    "done",
    "due",
    "due date",
    "item",
    "notes",
    "owner",
    "priority",
    "problem",
    "problem name",
    "section",
    "status",
    "task",
    "task name",
    "title",
    "topic",
}
DOCX_TABLE_TASK_HEADER_LABELS = {
    "action",
    "description",
    "item",
    "problem",
    "problem name",
    "task",
    "task name",
    "title",
}


def _normalize_docx_header_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _is_docx_table_header(row, cells, row_index: int) -> bool:
    # Word can explicitly mark rows that should repeat as table headers.
    if row._tr.xpath("./w:trPr/w:tblHeader"):
        return True
    if row_index != 0 or len(cells) < 2:
        return False

    labels = [_normalize_docx_header_label(cell) for cell in cells]
    recognized = sum(label in DOCX_TABLE_HEADER_LABELS for label in labels)
    return recognized >= 2 or (
        labels[0] in DOCX_TABLE_TASK_HEADER_LABELS and recognized >= 1
    )


def _extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="DOCX import is not installed on the backend. Install the python-docx package.",
        ) from exc

    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read text from this DOCX file.") from exc

    blocks = []
    for body_item in document.iter_inner_content():
        if isinstance(body_item, Paragraph):
            text = body_item.text.strip()
            if text:
                blocks.append(text)
            continue

        if isinstance(body_item, Table):
            for row_index, row in enumerate(body_item.rows):
                cells = [
                    cell.text.strip().replace("\n", " ")
                    for cell in row.cells
                    if cell.text.strip()
                ]
                if cells and not _is_docx_table_header(row, cells, row_index):
                    blocks.append(" | ".join(cells))

    text = "\n".join(blocks)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text was found in this DOCX file.")
    return text


async def _extract_upload_document(upload: UploadFile):
    filename = upload.filename or ""
    extension = Path(filename).suffix.lower()
    content = await _read_upload_limited(upload)

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if extension == ".pdf" or upload.content_type == "application/pdf":
        try:
            result = parse_pdf_document(content)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail="Layout-aware PDF import is not installed on the backend. Install pdfplumber.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not result.text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text was found in this PDF. Scanned image PDFs need OCR first.",
            )
        # An empty list is authoritative: the semantic parser found readable
        # source but intentionally classified none of it as trackable work.
        return result.text, result.tasks, result.outline

    if extension in DOCX_EXTENSIONS:
        return _extract_docx_text(content), None, []

    if extension in TEXT_EXTENSIONS or (upload.content_type or "").startswith("text/"):
        return _decode_text_bytes(content), None, []

    try:
        return _decode_text_bytes(content), None, []
    except HTTPException as exc:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Use PDF, DOCX, or a text-based format such as txt, md, csv, json, yaml, or log.",
        ) from exc


@app.post("/roadmaps", response_model=dict)
def create_roadmap(roadmap: RoadmapCreate, user_id: str = Depends(get_current_user)):
    name = _normalize_name(roadmap.name)
    text = parser.normalize_text(roadmap.text)
    if not text:
        raise HTTPException(status_code=400, detail="Roadmap text is required.")

    _ensure_unique_name(name, user_id)
    tasks = _tasks_from_text(text)
    try:
        roadmap_id = db.save_imported_roadmap(name, tasks, user_id, raw_text=text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": roadmap_id, "message": "Roadmap created successfully", "tasks": len(tasks)}


@app.post("/roadmaps/import", response_model=dict)
def import_roadmap(roadmap: RoadmapImport, user_id: str = Depends(get_current_user)):
    name = _normalize_name(roadmap.name)
    _ensure_unique_name(name, user_id)
    tasks = _tasks_from_import(roadmap, preserve_timeframe_ids=False)
    try:
        roadmap_id = db.save_imported_roadmap(name, tasks, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": roadmap_id, "message": "Roadmap imported successfully", "tasks": len(tasks)}


@app.post("/roadmaps/import-file", response_model=dict)
async def import_roadmap_file(
    name: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    roadmap_name = _normalize_name(name)
    _ensure_unique_name(roadmap_name, user_id)
    extracted_text, extracted_tasks, document = await _extract_upload_document(file)
    text = parser.normalize_text(extracted_text)
    json_roadmap = parser.parse_json_roadmap(text) if extracted_tasks is None else None
    if json_roadmap is not None:
        tasks = _validate_parsed_tasks(json_roadmap["tasks"])
        document = json_roadmap["document"]
    else:
        tasks = _tasks_from_text(text) if extracted_tasks is None else extracted_tasks
    try:
        roadmap_id = db.save_imported_roadmap(
            roadmap_name,
            tasks,
            user_id,
            raw_text=text,
            document=document,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": roadmap_id,
        "message": "Roadmap file imported successfully",
        "tasks": len(tasks),
        "filename": file.filename,
        "document_elements": len(document),
        "no_trackable_items": len(tasks) == 0,
    }


@app.get("/roadmaps", response_model=List[RoadmapSummary])
def get_roadmaps(user_id: str = Depends(get_current_user)):
    return db.get_roadmaps(user_id)


@app.get("/roadmaps/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(roadmap_id: int, user_id: str = Depends(get_current_user)):
    roadmap = db.get_roadmap(roadmap_id, user_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@app.get("/roadmaps/{roadmap_id}/document")
def get_roadmap_document(roadmap_id: int, user_id: str = Depends(get_current_user)):
    document = db.get_roadmap_document(roadmap_id, user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"version": 1, "elements": document}


@app.get("/roadmaps/{roadmap_id}/export")
def export_roadmap(roadmap_id: int, user_id: str = Depends(get_current_user)):
    data = db.export_roadmap_data(roadmap_id, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return data


@app.delete("/roadmaps/{roadmap_id}")
def delete_roadmap(roadmap_id: int, user_id: str = Depends(get_current_user)):
    if not db.delete_roadmap(roadmap_id, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "Roadmap deleted"}


@app.put("/roadmaps/{roadmap_id}")
def update_roadmap(
    roadmap_id: int,
    roadmap: RoadmapUpdate,
    user_id: str = Depends(get_current_user),
):
    text = parser.normalize_text(roadmap.text)
    if not text:
        raise HTTPException(status_code=400, detail="Roadmap text is required.")

    _tasks_from_text(text)
    if not db.update_roadmap_content(roadmap_id, text, parser.parse_roadmap, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "Roadmap updated"}


@app.get("/roadmaps/{roadmap_id}/tasks")
def get_roadmap_tasks(roadmap_id: int, user_id: str = Depends(get_current_user)):
    if not db.get_roadmap(roadmap_id, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return db.get_tasks(roadmap_id, user_id)


@app.get("/tasks/{task_id}/blocks")
def get_task_blocks(task_id: int, user_id: str = Depends(get_current_user)):
    blocks = db.get_task_blocks(task_id, user_id)
    if blocks is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return blocks


@app.post("/tasks/{task_id}/blocks", status_code=201)
def create_task_block(
    task_id: int,
    create: TaskBlockCreate,
    user_id: str = Depends(get_current_user),
):
    try:
        block = db.create_task_block(task_id, create.type, create.data, create.position, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not block:
        raise HTTPException(status_code=404, detail="Task not found")
    return block


@app.post("/task-blocks/bulk", status_code=201)
def create_task_blocks_bulk(
    create: TaskBlockBulkCreate,
    user_id: str = Depends(get_current_user),
):
    try:
        blocks = db.create_task_blocks_bulk(create.task_ids, create.type, create.data, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if blocks is None:
        raise HTTPException(status_code=404, detail="One or more tasks were not found")
    return {"blocks": blocks}


@app.patch("/task-blocks/{block_id}")
def update_task_block(
    block_id: int,
    update: TaskBlockUpdate,
    user_id: str = Depends(get_current_user),
):
    updates = _model_updates(update)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one block field is required")
    if ("type" in updates and updates["type"] is None) or (
        "data" in updates and updates["data"] is None
    ):
        raise HTTPException(status_code=400, detail="Block type and data cannot be null")
    try:
        block = db.update_task_block(block_id, updates, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not block:
        raise HTTPException(status_code=404, detail="Task block not found")
    return block


@app.delete("/task-blocks/{block_id}")
def delete_task_block(block_id: int, user_id: str = Depends(get_current_user)):
    if not db.delete_task_block(block_id, user_id):
        raise HTTPException(status_code=404, detail="Task block not found")
    return {"message": "Task block deleted"}


@app.post("/tasks")
def create_task(task: TaskCreate, user_id: str = Depends(get_current_user)):
    title = task.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")

    timeframe_label = (task.timeframe_label or "").strip()
    if task.timeframe_id is None and not timeframe_label:
        raise HTTPException(status_code=400, detail="Timeframe ID or label is required")
    created = db.create_task(
        task.roadmap_id,
        timeframe_label,
        title,
        user_id,
        timeframe_id=task.timeframe_id,
    )
    if not created:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return created


@app.put("/tasks/{task_id}/status")
def update_task_status(task_id: int, status: TaskUpdate, user_id: str = Depends(get_current_user)):
    if not db.update_task_status(task_id, status.is_done, user_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task status updated"}


@app.put("/tasks/{task_id}")
def update_task_title(task_id: int, update: TaskTitleUpdate, user_id: str = Depends(get_current_user)):
    title = update.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")

    task = db.update_task_title(task_id, title, user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}/properties")
def update_task_properties(
    task_id: int,
    update: TaskPropertiesUpdate,
    user_id: str = Depends(get_current_user),
):
    try:
        task = db.update_task_properties(task_id, update.properties, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, user_id: str = Depends(get_current_user)):
    if not db.delete_task(task_id, user_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}


@app.put("/roadmaps/{roadmap_id}/smart")
def update_roadmap_smart(
    roadmap_id: int,
    roadmap: RoadmapImport,
    user_id: str = Depends(get_current_user),
):
    if not db.roadmap_exists(roadmap_id, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    name = _normalize_name(roadmap.name)
    _ensure_unique_name(name, user_id, exclude_roadmap_id=roadmap_id)
    tasks = _tasks_from_import(roadmap)
    try:
        updated = db.update_roadmap_smart(roadmap_id, name, tasks, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "Roadmap updated successfully"}


@app.put("/roadmaps/{roadmap_id}/name")
def rename_roadmap(
    roadmap_id: int,
    update: RoadmapNameUpdate,
    user_id: str = Depends(get_current_user),
):
    if not db.roadmap_exists(roadmap_id, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    name = _normalize_name(update.name)
    _ensure_unique_name(name, user_id, exclude_roadmap_id=roadmap_id)
    if not db.rename_roadmap(roadmap_id, name, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "Roadmap renamed"}


@app.get("/roadmaps/{roadmap_id}/timeframes")
def get_roadmap_timeframes(roadmap_id: int, user_id: str = Depends(get_current_user)):
    if not db.get_roadmap(roadmap_id, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return db.get_timeframes(roadmap_id, user_id)


@app.put("/timeframes/{timeframe_id}/dates")
def update_timeframe_dates(
    timeframe_id: int,
    update: TimeframeDateUpdate,
    user_id: str = Depends(get_current_user),
):
    start_date, end_date = _normalize_date_range(update.start_date, update.end_date)
    if not db.update_timeframe_dates(timeframe_id, start_date, end_date, user_id):
        raise HTTPException(status_code=404, detail="Timeframe not found")
    return {"message": "Timeframe dates updated"}


@app.put("/timeframes/{timeframe_id}/tasks/status")
def update_timeframe_task_status(
    timeframe_id: int,
    status: TaskUpdate,
    user_id: str = Depends(get_current_user),
):
    updated = db.update_timeframe_task_status(timeframe_id, status.is_done, user_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Timeframe not found")
    return {"message": "Timeframe task status updated", "updated": updated}
