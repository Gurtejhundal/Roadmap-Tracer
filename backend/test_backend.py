import time

from fastapi.testclient import TestClient

import db
from main import app


db.init_db()
client = TestClient(app)
headers = {"X-Local-User-Id": "test_user"}


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Roadmap Tracer API"}


def test_create_roadmap_from_text():
    name = f"Text Roadmap {time.time()}"
    text = "Week 1: Foundations\n- Learn Python basics\n- Build a small script"

    response = client.post("/roadmaps", json={"name": name, "text": text}, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["tasks"] == 2

    tasks = client.get(f"/roadmaps/{data['id']}/tasks", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) == 2


def test_import_text_file():
    name = f"File Roadmap {time.time()}"
    files = {"file": ("roadmap.md", b"Phase 1: Setup\n- Install tooling\n- Create repo", "text/markdown")}
    response = client.post(
        "/roadmaps/import-file",
        data={"name": name},
        files=files,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == 2


def test_long_revision_roadmap_creates_more_than_day_groups():
    name = f"RDBMS Roadmap {time.time()}"
    text = """
2-day full RDBMS revision roadmap for 30/30
core strategy
40% theory
60% SQL / coding / query practice
day 1 - Unit I, II, III + SQL coding base
7:00 AM - 8:30 AM
Unit I - Introduction to Database
Cover these topics properly
purpose of database systems
components of DBMS
Unit I revision notes
1. Purpose of database systems
reduce data redundancy
improve data consistency
8:30 AM - 11:30 AM
Unit II - Relational Query Language
DDL
DML
Coding practice for Unit II
CREATE TABLE Department
Practice inserting
INSERT INTO Department VALUES (1, 'CSE');
day 2 - Unit IV, V, VI + final mock
7:00 AM - 10:00 AM
Unit IV - Relational Database Design
functional dependency
normalization
7:30 PM - 10:30 PM
Final full mock
Which DBMS level describes physical storage?
Internal level
"""

    response = client.post("/roadmaps", json={"name": name, "text": text}, headers=headers)
    assert response.status_code == 200

    roadmap_id = response.json()["id"]
    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=headers).json()
    groups = {task["timeframe_label"] for task in tasks}

    assert response.json()["tasks"] > 10
    assert len(groups) > 2
    assert any("Unit I - Introduction to Database" in group for group in groups)
    assert any("Unit II - Relational Query Language" in group for group in groups)
    assert any("Final full mock" in group for group in groups)


def test_parser_keeps_pdf_lines_without_page_artifacts():
    from roadmap_parser import parse_tasks

    text = """
AI Product Engineer Roadmap v2.0
Version 2.0 upgrades
- Fewer shallow projects; one flagship starts by month 9 instead of waiting until the end.
Page 1 of 28
AI Product Engineer Roadmap v2.0
1. The honest target
A Rs 15-25 LPA fresher role is not won by being average.
Target profile by month 24
Area                       Minimum proof                                        Strong proof
DSA                        250 serious problems + timed revision                300+ with cold re-solves
2. Non-negotiable operating rules
- No tutorial-only weeks. Learning must create code, notes, tests, diagrams, or deployed features.
"""

    tasks = parse_tasks(text)
    titles = [task["title"] for task in tasks]
    groups = {task["timeframe"] for task in tasks}

    assert "Page 1 of 28" not in titles
    assert "AI Product Engineer Roadmap v2.0" not in titles
    assert "Version 2.0 upgrades" in groups
    assert "1. The honest target" in groups
    assert "Target profile by month 24" in groups
    assert any("250 serious problems" in title for title in titles)


def test_task_crud_and_group_status():
    name = f"Manage Tasks Roadmap {time.time()}"
    response = client.post(
        "/roadmaps",
        json={"name": name, "text": "Phase 1\n- First task\n- Second task"},
        headers=headers,
    )
    assert response.status_code == 200
    roadmap_id = response.json()["id"]

    created = client.post(
        "/tasks",
        json={"roadmap_id": roadmap_id, "timeframe_label": "Phase 1", "title": "Added task"},
        headers=headers,
    )
    assert created.status_code == 200
    created_task = created.json()
    assert created_task["title"] == "Added task"

    updated = client.put(
        f"/tasks/{created_task['id']}",
        json={"title": "Updated task"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated task"

    timeframes = client.get(f"/roadmaps/{roadmap_id}/timeframes", headers=headers)
    assert timeframes.status_code == 200
    timeframe_id = timeframes.json()[0]["id"]

    group_update = client.put(
        f"/timeframes/{timeframe_id}/tasks/status",
        json={"is_done": True},
        headers=headers,
    )
    assert group_update.status_code == 200
    assert group_update.json()["updated"] == 3

    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=headers).json()
    assert all(task["is_done"] for task in tasks)

    deleted = client.delete(f"/tasks/{created_task['id']}", headers=headers)
    assert deleted.status_code == 200

    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=headers).json()
    assert all(task["title"] != "Updated task" for task in tasks)


def test_get_roadmaps():
    response = client.get("/roadmaps", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
