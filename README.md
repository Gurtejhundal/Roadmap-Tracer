# Roadmap Tracer

Roadmap Tracer is a React and FastAPI app for importing learning roadmaps and tracking task progress over time.

It supports pasted roadmap text and uploaded roadmap files. PDF import works when the PDF contains selectable text. Scanned image PDFs need OCR before upload.

## About

Roadmap Tracer is built for personal study plans that are too large to manage as plain text. Import a roadmap from ChatGPT, PDF, DOCX, Markdown, or other text-based files, then track it as a structured checklist with sections, subsections, progress, search, and a contents panel for fast navigation.

The app is designed for single-user local use. It removes hosted sign-in friction and focuses on turning messy roadmap documents into something you can actually follow day by day, month by month, or section by section.

## Features

- Import roadmaps from pasted text.
- Import DOCX and text-based files such as TXT, Markdown, JSON, CSV, YAML, RST, and logs.
- Import readable-text PDFs.
- Parse common ChatGPT roadmap formats into timeframe groups and tasks.
- Navigate large roadmaps with section/subsection contents and current-location context.
- Track task completion per roadmap.
- Show completion progress on roadmap cards and detail pages.
- Edit roadmap task structure after import.
- Export a roadmap to PDF or Word from the roadmap detail page.
- Scope roadmap, task, and timeframe access by a local owner header.

## Tech Stack

- Frontend: React, Vite, React Router, Framer Motion.
- Backend: FastAPI, SQLAlchemy, Pydantic.
- Database: SQLite locally, PostgreSQL-compatible via `DATABASE_URL`.
- Auth: none. The app is configured for single-user local use.
- API ownership: the frontend sends `X-Local-User-Id` so local roadmaps stay scoped to one owner key.

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt pytest
uvicorn main:app --reload
```

The API runs at `http://localhost:8000` by default.

### One-click launcher

On Windows, run:

```bat
launcher.bat
```

The launcher starts the FastAPI backend, starts the Vite frontend, and opens the app at `http://127.0.0.1:5173`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at the Vite URL printed in the terminal, usually `http://localhost:5173`.

Set `VITE_API_URL` if the backend is not running on `http://localhost:8000`.

## Checks

```bash
cd backend
python -m pytest

cd ../frontend
npm run lint
npm run build
```

## Known Limits

- PDF import extracts embedded text only. It uses layout extraction where available to preserve tables and roadmap sections. It does not OCR scanned documents.
- The frontend uses a fixed local owner id. This is deliberate for personal use, not suitable for multi-user deployment.
- Frontend export libraries currently create a large production bundle; split-loading export code is the next performance fix.
