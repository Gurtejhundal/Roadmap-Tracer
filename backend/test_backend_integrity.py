import time
import uuid

import pytest
from fastapi.testclient import TestClient

import db
import models_db as models
from database import SessionLocal
from main import app


db.init_db()
client = TestClient(app)


@pytest.fixture
def audit_headers():
    headers = {"X-Local-User-Id": f"backend_audit_{uuid.uuid4().hex}"}
    yield headers
    for roadmap in client.get("/roadmaps", headers=headers).json():
        client.delete(f"/roadmaps/{roadmap['id']}", headers=headers)


def _create_roadmap(headers, text="Phase 1\n- First task", name=None):
    response = client.post(
        "/roadmaps",
        json={"name": name or f"Backend audit {time.time_ns()}", "text": text},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_smart_update_preserves_timeframe_metadata_and_export_round_trips_it(audit_headers):
    response = client.post(
        "/roadmaps/import",
        json={
            "name": f"Metadata round trip {time.time_ns()}",
            "tasks": [
                {
                    "title": "Preserve the schedule",
                    "timeframe": "Phase 1",
                    "granularity": "week",
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-31",
                }
            ],
        },
        headers=audit_headers,
    )
    assert response.status_code == 200, response.text
    roadmap_id = response.json()["id"]

    exported = client.get(f"/roadmaps/{roadmap_id}/export", headers=audit_headers)
    assert exported.status_code == 200
    exported_task = exported.json()["tasks"][0]
    assert {
        key: exported_task[key]
        for key in ("granularity", "start_date", "end_date")
    } == {
        "granularity": "week",
        "start_date": "2026-08-01",
        "end_date": "2026-08-31",
    }

    updated = client.put(
        f"/roadmaps/{roadmap_id}/smart",
        json={"name": exported.json()["name"], "tasks": exported.json()["tasks"]},
        headers=audit_headers,
    )
    assert updated.status_code == 200, updated.text

    timeframes = client.get(f"/roadmaps/{roadmap_id}/timeframes", headers=audit_headers).json()
    assert timeframes == [
        {
            "id": timeframes[0]["id"],
            "label": "Phase 1",
            "granularity": "week",
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        }
    ]


def test_smart_update_without_date_fields_keeps_existing_dates(audit_headers):
    roadmap = _create_roadmap(audit_headers)
    roadmap_id = roadmap["id"]
    timeframe = client.get(f"/roadmaps/{roadmap_id}/timeframes", headers=audit_headers).json()[0]
    saved = client.put(
        f"/timeframes/{timeframe['id']}/dates",
        json={"start_date": "2026-09-01", "end_date": "2026-09-30"},
        headers=audit_headers,
    )
    assert saved.status_code == 200

    task = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=audit_headers).json()[0]
    updated = client.put(
        f"/roadmaps/{roadmap_id}/smart",
        json={
            "name": f"Updated {time.time_ns()}",
            "tasks": [{"title": task["title"], "timeframe": task["timeframe_label"]}],
        },
        headers=audit_headers,
    )
    assert updated.status_code == 200

    refreshed = client.get(f"/roadmaps/{roadmap_id}/timeframes", headers=audit_headers).json()[0]
    assert (refreshed["start_date"], refreshed["end_date"]) == (
        "2026-09-01",
        "2026-09-30",
    )


def test_raw_text_update_preserves_state_for_matching_tasks(audit_headers):
    roadmap = _create_roadmap(audit_headers)
    roadmap_id = roadmap["id"]
    task = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=audit_headers).json()[0]
    timeframe = client.get(f"/roadmaps/{roadmap_id}/timeframes", headers=audit_headers).json()[0]
    assert client.put(
        f"/tasks/{task['id']}/status", json={"is_done": True}, headers=audit_headers
    ).status_code == 200
    assert client.put(
        f"/tasks/{task['id']}/properties",
        json={"properties": {"Priority": "High"}},
        headers=audit_headers,
    ).status_code == 200
    assert client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "note", "data": {"text": "Keep this context"}},
        headers=audit_headers,
    ).status_code == 201
    assert client.put(
        f"/timeframes/{timeframe['id']}/dates",
        json={"start_date": "2026-10-01", "end_date": "2026-10-31"},
        headers=audit_headers,
    ).status_code == 200

    updated = client.put(
        f"/roadmaps/{roadmap_id}",
        json={"text": "Phase 1\n- First task\n- Newly added task"},
        headers=audit_headers,
    )
    assert updated.status_code == 200, updated.text

    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=audit_headers).json()
    preserved = next(item for item in tasks if item["title"] == "First task")
    added = next(item for item in tasks if item["title"] == "Newly added task")
    assert preserved["is_done"] is True
    assert preserved["properties"] == {"Priority": "High"}
    assert [(block["type"], block["data"]) for block in preserved["blocks"]] == [
        ("note", {"text": "Keep this context"})
    ]
    assert added["is_done"] is False
    assert added["properties"] == {}
    assert added["blocks"] == []
    refreshed_timeframe = client.get(
        f"/roadmaps/{roadmap_id}/timeframes", headers=audit_headers
    ).json()[0]
    assert (refreshed_timeframe["start_date"], refreshed_timeframe["end_date"]) == (
        "2026-10-01",
        "2026-10-31",
    )


@pytest.mark.parametrize(
    "payload, expected_detail",
    [
        ({"start_date": "not-a-date", "end_date": None}, "Start date must use YYYY-MM-DD format."),
        ({"start_date": "2026-02-30", "end_date": None}, "Start date is not a valid date."),
        (
            {"start_date": "2026-09-30", "end_date": "2026-09-01"},
            "Start date cannot be after end date.",
        ),
    ],
)
def test_timeframe_dates_reject_invalid_ranges_without_mutating(
    audit_headers, payload, expected_detail
):
    roadmap = _create_roadmap(audit_headers)
    timeframe = client.get(
        f"/roadmaps/{roadmap['id']}/timeframes", headers=audit_headers
    ).json()[0]
    assert client.put(
        f"/timeframes/{timeframe['id']}/dates",
        json={"start_date": "2026-08-01", "end_date": "2026-08-31"},
        headers=audit_headers,
    ).status_code == 200

    rejected = client.put(
        f"/timeframes/{timeframe['id']}/dates",
        json=payload,
        headers=audit_headers,
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == expected_detail
    refreshed = client.get(
        f"/roadmaps/{roadmap['id']}/timeframes", headers=audit_headers
    ).json()[0]
    assert (refreshed["start_date"], refreshed["end_date"]) == (
        "2026-08-01",
        "2026-08-31",
    )


def test_smart_update_rejects_duplicate_name_without_replacing_tasks(audit_headers):
    first = _create_roadmap(audit_headers, name=f"First {time.time_ns()}")
    second = _create_roadmap(audit_headers, name=f"Second {time.time_ns()}")
    second_name = client.get(f"/roadmaps/{second['id']}", headers=audit_headers).json()["name"]

    rejected = client.put(
        f"/roadmaps/{first['id']}/smart",
        json={
            "name": second_name.upper(),
            "tasks": [{"title": "This must not replace the original", "timeframe": "Changed"}],
        },
        headers=audit_headers,
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "Roadmap with this name already exists."
    tasks = client.get(f"/roadmaps/{first['id']}/tasks", headers=audit_headers).json()
    assert [(task["timeframe_label"], task["title"]) for task in tasks] == [
        ("Phase 1", "First task")
    ]


def test_invalid_imported_block_is_a_400_and_rolls_back_the_roadmap(audit_headers):
    name = f"Invalid imported block {time.time_ns()}"
    rejected = client.post(
        "/roadmaps/import",
        json={
            "name": name,
            "tasks": [
                {
                    "title": "Do not partially import",
                    "timeframe": "Phase 1",
                    "blocks": [{"type": "Bad Type", "data": {}}],
                }
            ],
        },
        headers=audit_headers,
    )
    assert rejected.status_code == 400
    assert "Block type" in rejected.json()["detail"]
    assert all(
        roadmap["name"] != name
        for roadmap in client.get("/roadmaps", headers=audit_headers).json()
    )


def test_non_finite_json_is_rejected_without_overwriting_saved_data(audit_headers):
    roadmap = _create_roadmap(audit_headers)
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=audit_headers).json()[0]

    properties = client.put(
        f"/tasks/{task['id']}/properties",
        content='{"properties":{"score":NaN}}',
        headers={**audit_headers, "Content-Type": "application/json"},
    )
    assert properties.status_code == 400
    block = client.post(
        f"/tasks/{task['id']}/blocks",
        content='{"type":"counter","data":{"value":Infinity}}',
        headers={**audit_headers, "Content-Type": "application/json"},
    )
    assert block.status_code == 400

    refreshed = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=audit_headers).json()[0]
    assert refreshed["properties"] == {}
    assert refreshed["blocks"] == []


def test_roadmap_list_uses_summary_shape_but_detail_keeps_raw_text(audit_headers):
    roadmap = _create_roadmap(
        audit_headers,
        text="Phase 1\n- First task\n- Second task",
    )
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=audit_headers).json()[0]
    assert client.put(
        f"/tasks/{task['id']}/status",
        json={"is_done": True},
        headers=audit_headers,
    ).status_code == 200

    summary = next(
        item
        for item in client.get("/roadmaps", headers=audit_headers).json()
        if item["id"] == roadmap["id"]
    )
    assert "raw_text" not in summary
    assert (summary["total_tasks"], summary["completed_tasks"]) == (2, 1)
    detail = client.get(f"/roadmaps/{roadmap['id']}", headers=audit_headers).json()
    assert detail["raw_text"] == "Phase 1\n- First task\n- Second task"


def test_cors_allows_local_frontend_and_rejects_unconfigured_web_origins():
    local = client.options(
        "/roadmaps",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Local-User-Id",
        },
    )
    assert local.status_code == 200
    assert local.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    external = client.options(
        "/roadmaps",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Local-User-Id",
        },
    )
    assert external.status_code == 400
    assert "access-control-allow-origin" not in external.headers


def test_block_insert_repairs_sparse_legacy_positions(audit_headers):
    roadmap = _create_roadmap(audit_headers)
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=audit_headers).json()[0]
    first = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "note", "data": {"text": "First"}},
        headers=audit_headers,
    ).json()
    second = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "note", "data": {"text": "Second"}},
        headers=audit_headers,
    ).json()
    session = SessionLocal()
    try:
        session.query(models.TaskBlock).filter(models.TaskBlock.id == first["id"]).update(
            {models.TaskBlock.position: 5}
        )
        session.query(models.TaskBlock).filter(models.TaskBlock.id == second["id"]).update(
            {models.TaskBlock.position: 10}
        )
        session.commit()
    finally:
        session.close()

    inserted = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "label", "data": {"value": "Inserted"}, "position": 1},
        headers=audit_headers,
    )
    assert inserted.status_code == 201
    blocks = client.get(f"/tasks/{task['id']}/blocks", headers=audit_headers).json()
    assert [block["position"] for block in blocks] == [0, 1, 2]
    assert [block["data"] for block in blocks] == [
        {"text": "First"},
        {"value": "Inserted"},
        {"text": "Second"},
    ]


def test_bulk_block_rejects_excessive_amplified_write_before_lookup(audit_headers):
    response = client.post(
        "/task-blocks/bulk",
        json={
            "task_ids": list(range(1, 301)),
            "type": "note",
            "data": {"text": "x" * 60_000},
        },
        headers=audit_headers,
    )
    assert response.status_code == 400
    assert "16 MB write limit" in response.json()["detail"]
