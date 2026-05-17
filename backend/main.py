from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import db
import roadmap_parser as parser
from models import (
    RoadmapCreate,
    RoadmapImport,
    RoadmapNameUpdate,
    RoadmapResponse,
    RoadmapUpdate,
    TaskCreate,
    TaskTitleUpdate,
    TaskUpdate,
    TimeframeDateUpdate,
)


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(
    x_local_user_id: str = Header(None, alias="X-Local-User-Id"),
    x_legacy_user_id: str = Header(None, alias="X-Clerk-User-Id"),
):
    return x_local_user_id or x_legacy_user_id or "public_user"


@app.get("/")
def read_root():
    return {"message": "Welcome to Roadmap Tracer API"}


def _normalize_name(name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Roadmap name is required.")
    return normalized


def _ensure_unique_name(name: str, user_id: str):
    existing = db.get_roadmaps(user_id)
    if any(roadmap["name"].strip().lower() == name.lower() for roadmap in existing):
        raise HTTPException(status_code=400, detail="Roadmap with this name already exists.")


def _tasks_from_text(text: str):
    tasks = parser.parse_tasks(text)
    if not tasks:
        raise HTTPException(status_code=400, detail="No trackable tasks were found in this roadmap.")
    return tasks


def _tasks_from_import(roadmap: RoadmapImport):
    tasks = []
    for task in roadmap.tasks:
        title = task.title.strip()
        timeframe = task.timeframe.strip() or "General"
        if title:
            tasks.append(
                {
                    "title": title,
                    "timeframe": timeframe,
                    "is_done": task.is_done,
                    "granularity": "section",
                }
            )

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


def _extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document
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
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    text = "\n".join(blocks)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text was found in this DOCX file.")
    return text


async def _extract_upload_text(upload: UploadFile) -> str:
    filename = upload.filename or ""
    extension = Path(filename).suffix.lower()
    content = await upload.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Roadmap file must be 8 MB or smaller.")

    if extension == ".pdf" or upload.content_type == "application/pdf":
        return _extract_pdf_text(content)

    if extension in DOCX_EXTENSIONS:
        return _extract_docx_text(content)

    if extension in TEXT_EXTENSIONS or (upload.content_type or "").startswith("text/"):
        return _decode_text_bytes(content)

    try:
        return _decode_text_bytes(content)
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
    roadmap_id = db.save_imported_roadmap(name, tasks, user_id, raw_text=text)
    return {"id": roadmap_id, "message": "Roadmap created successfully", "tasks": len(tasks)}


@app.post("/roadmaps/import", response_model=dict)
def import_roadmap(roadmap: RoadmapImport, user_id: str = Depends(get_current_user)):
    name = _normalize_name(roadmap.name)
    _ensure_unique_name(name, user_id)
    tasks = _tasks_from_import(roadmap)
    roadmap_id = db.save_imported_roadmap(name, tasks, user_id)
    return {"id": roadmap_id, "message": "Roadmap imported successfully", "tasks": len(tasks)}


@app.post("/roadmaps/import-file", response_model=dict)
async def import_roadmap_file(
    name: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    roadmap_name = _normalize_name(name)
    _ensure_unique_name(roadmap_name, user_id)
    text = parser.normalize_text(await _extract_upload_text(file))
    tasks = _tasks_from_text(text)
    roadmap_id = db.save_imported_roadmap(roadmap_name, tasks, user_id, raw_text=text)
    return {
        "id": roadmap_id,
        "message": "Roadmap file imported successfully",
        "tasks": len(tasks),
        "filename": file.filename,
    }


@app.get("/roadmaps", response_model=List[RoadmapResponse])
def get_roadmaps(user_id: str = Depends(get_current_user)):
    return db.get_roadmaps(user_id)


@app.get("/roadmaps/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(roadmap_id: int, user_id: str = Depends(get_current_user)):
    roadmap = db.get_roadmap(roadmap_id, user_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


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


@app.post("/tasks")
def create_task(task: TaskCreate, user_id: str = Depends(get_current_user)):
    title = task.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")

    created = db.create_task(task.roadmap_id, task.timeframe_label, title, user_id)
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
    tasks = _tasks_from_import(roadmap)
    if not db.update_roadmap_smart(roadmap_id, _normalize_name(roadmap.name), tasks, user_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "Roadmap updated successfully"}


@app.put("/roadmaps/{roadmap_id}/name")
def rename_roadmap(
    roadmap_id: int,
    update: RoadmapNameUpdate,
    user_id: str = Depends(get_current_user),
):
    name = _normalize_name(update.name)
    existing = [item for item in db.get_roadmaps(user_id) if item["id"] != roadmap_id]
    if any(roadmap["name"].strip().lower() == name.lower() for roadmap in existing):
        raise HTTPException(status_code=400, detail="Roadmap with this name already exists.")
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
    if not db.update_timeframe_dates(timeframe_id, update.start_date, update.end_date, user_id):
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
