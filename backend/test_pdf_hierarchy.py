import time
import uuid
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db
from main import app


db.init_db()
client = TestClient(app)


@pytest.fixture
def hierarchy_headers():
    headers = {"X-Local-User-Id": f"hierarchy_{uuid.uuid4().hex}"}
    yield headers
    for roadmap in client.get("/roadmaps", headers=headers).json():
        client.delete(f"/roadmaps/{roadmap['id']}", headers=headers)


def test_noncontiguous_duplicate_labels_create_distinct_timeframe_occurrences(hierarchy_headers):
    imported = client.post(
        "/roadmaps/import",
        json={
            "name": f"Repeated sections {time.time_ns()}",
            "tasks": [
                {"title": "BST medium task", "timeframe": "Medium"},
                {"title": "BST FAQ task", "timeframe": "FAQs"},
                {"title": "Heap medium task", "timeframe": "Medium"},
                {"title": "Heap FAQ task", "timeframe": "FAQs"},
                {"title": "Graph hard task", "timeframe": "Hard"},
            ],
        },
        headers=hierarchy_headers,
    )
    assert imported.status_code == 200, imported.text
    roadmap_id = imported.json()["id"]

    timeframes = client.get(
        f"/roadmaps/{roadmap_id}/timeframes",
        headers=hierarchy_headers,
    ).json()
    assert [timeframe["label"] for timeframe in timeframes] == [
        "Medium",
        "FAQs",
        "Medium",
        "FAQs",
        "Hard",
    ]
    assert len({timeframe["id"] for timeframe in timeframes}) == 5

    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=hierarchy_headers).json()
    assert tasks[0]["timeframe_id"] != tasks[2]["timeframe_id"]
    assert tasks[1]["timeframe_id"] != tasks[3]["timeframe_id"]


def test_export_and_smart_update_preserve_duplicate_label_timeframe_ids(hierarchy_headers):
    roadmap_id = db.save_imported_roadmap(
        f"Occurrence round trip {time.time_ns()}",
        [
            {"title": "First medium", "timeframe": "Medium"},
            {"title": "Boundary", "timeframe": "FAQs"},
            {"title": "Second medium", "timeframe": "Medium"},
        ],
        hierarchy_headers["X-Local-User-Id"],
    )
    exported = client.get(f"/roadmaps/{roadmap_id}/export", headers=hierarchy_headers)
    assert exported.status_code == 200, exported.text
    exported_tasks = exported.json()["tasks"]
    assert exported_tasks[0]["timeframe_id"] != exported_tasks[2]["timeframe_id"]

    updated = client.put(
        f"/roadmaps/{roadmap_id}/smart",
        json={"name": exported.json()["name"], "tasks": exported_tasks},
        headers=hierarchy_headers,
    )
    assert updated.status_code == 200, updated.text
    refreshed = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=hierarchy_headers).json()
    assert refreshed[0]["timeframe_id"] != refreshed[2]["timeframe_id"]


def test_create_task_can_target_an_exact_timeframe_occurrence(hierarchy_headers):
    roadmap_id = db.save_imported_roadmap(
        f"Exact occurrence {time.time_ns()}",
        [
            {"title": "First medium", "timeframe": "Medium"},
            {"title": "Boundary", "timeframe": "FAQs"},
            {"title": "Second medium", "timeframe": "Medium"},
        ],
        hierarchy_headers["X-Local-User-Id"],
    )
    medium_timeframes = [
        timeframe
        for timeframe in client.get(
            f"/roadmaps/{roadmap_id}/timeframes",
            headers=hierarchy_headers,
        ).json()
        if timeframe["label"] == "Medium"
    ]
    assert len(medium_timeframes) == 2

    created = client.post(
        "/tasks",
        json={
            "roadmap_id": roadmap_id,
            "timeframe_id": medium_timeframes[1]["id"],
            "title": "Attach to the second occurrence",
        },
        headers=hierarchy_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["timeframe_id"] == medium_timeframes[1]["id"]

    rejected = client.post(
        "/tasks",
        json={
            "roadmap_id": roadmap_id,
            "timeframe_id": 2_147_483_647,
            "title": "Do not attach",
        },
        headers=hierarchy_headers,
    )
    assert rejected.status_code == 404


def test_smart_update_rejects_a_timeframe_id_from_another_roadmap(hierarchy_headers):
    owner = hierarchy_headers["X-Local-User-Id"]
    first_id = db.save_imported_roadmap(
        f"Protected roadmap {time.time_ns()}",
        [{"title": "Keep me", "timeframe": "Protected"}],
        owner,
    )
    second_id = db.save_imported_roadmap(
        f"Other roadmap {time.time_ns()}",
        [{"title": "Other task", "timeframe": "Other"}],
        owner,
    )
    foreign_timeframe_id = client.get(
        f"/roadmaps/{second_id}/timeframes",
        headers=hierarchy_headers,
    ).json()[0]["id"]

    rejected = client.put(
        f"/roadmaps/{first_id}/smart",
        json={
            "name": client.get(f"/roadmaps/{first_id}", headers=hierarchy_headers).json()["name"],
            "tasks": [
                {
                    "title": "Do not move me",
                    "timeframe": "Protected",
                    "timeframe_id": foreign_timeframe_id,
                }
            ],
        },
        headers=hierarchy_headers,
    )

    assert rejected.status_code == 400, rejected.text
    assert rejected.json()["detail"] == "Timeframe does not belong to this roadmap."
    remaining = client.get(f"/roadmaps/{first_id}/tasks", headers=hierarchy_headers).json()
    assert [(task["title"], task["timeframe_label"]) for task in remaining] == [
        ("Keep me", "Protected")
    ]


def test_local_tuf_duplicate_section_labels_are_distinct_occurrences(hierarchy_headers):
    from pdf_importer import parse_pdf_document

    sample = Path(r"D:\Download\DSA 400 Days Challenge.pdf")
    if not sample.exists():
        pytest.skip("Local TUF+ checklist fixture is unavailable")

    result = parse_pdf_document(sample.read_bytes())
    roadmap_id = db.save_imported_roadmap(
        f"Real occurrence check {time.time_ns()}",
        result.tasks,
        hierarchy_headers["X-Local-User-Id"],
    )
    timeframes = client.get(
        f"/roadmaps/{roadmap_id}/timeframes",
        headers=hierarchy_headers,
    ).json()
    counts = Counter(timeframe["label"] for timeframe in timeframes)

    assert len(result.tasks) == 328
    assert counts["Medium"] >= 2
    assert counts["FAQs"] >= 2
    assert len(timeframes) > len(counts)
