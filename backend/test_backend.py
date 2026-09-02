import asyncio
import time
from pathlib import Path

import pytest

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


def test_pdf_with_zero_semantic_tasks_never_falls_back_to_prose(monkeypatch):
    import main
    from pdf_importer import PdfImportResult

    result = PdfImportResult(
        text="Reference material\n- This bullet is descriptive, not a task",
        tasks=[],
        outline=[
            {
                "type": "paragraph",
                "page": 1,
                "text": "Reference material",
                "section_path": [],
            }
        ],
        page_count=1,
    )
    monkeypatch.setattr(main, "parse_pdf_document", lambda _content: result)

    name = f"Reference PDF {time.time()}"
    response = client.post(
        "/roadmaps/import-file",
        data={"name": name},
        files={"file": ("reference.pdf", b"%PDF-reference", "application/pdf")},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == 0
    assert data["no_trackable_items"] is True
    assert data["document_elements"] == 1
    assert client.get(f"/roadmaps/{data['id']}/tasks", headers=headers).json() == []
    assert client.get(f"/roadmaps/{data['id']}/document", headers=headers).json()["elements"] == result.outline
    assert client.delete(f"/roadmaps/{data['id']}", headers=headers).status_code == 200


def test_upload_reader_stops_at_the_configured_byte_limit():
    import main

    class ChunkedUpload:
        def __init__(self, payload):
            self.payload = payload
            self.offset = 0
            self.read_sizes = []

        async def read(self, size):
            self.read_sizes.append(size)
            chunk = self.payload[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

    accepted = ChunkedUpload(b"12345")
    assert asyncio.run(main._read_upload_limited(accepted, max_bytes=5)) == b"12345"
    assert max(accepted.read_sizes) <= 6

    rejected = ChunkedUpload(b"123456")
    with pytest.raises(main.HTTPException) as exc_info:
        asyncio.run(main._read_upload_limited(rejected, max_bytes=5))
    assert getattr(exc_info.value, "status_code", None) == 413
    assert max(rejected.read_sizes) <= 6


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


def test_parser_accepts_non_temporal_todo_sections():
    from roadmap_parser import parse_tasks

    text = """
Docker Setup
- Install Docker Desktop
- Learn images and containers
- Build and run a Docker image

Deployment
- Write a Dockerfile
- Push the image to a registry
"""

    tasks = parse_tasks(text)

    assert [task["title"] for task in tasks] == [
        "Install Docker Desktop",
        "Learn images and containers",
        "Build and run a Docker image",
        "Write a Dockerfile",
        "Push the image to a registry",
    ]
    assert {task["timeframe"] for task in tasks} == {"Docker Setup", "Deployment"}


def test_rotated_pdf_topics_are_restored():
    from main import _find_column, _normalize_rotated_topic
    from pdf_importer import _detect_header_row, _is_instruction_reference_table

    assert _normalize_rotated_topic("muideM\nsyarrA", True) == "Arrays Medium"
    assert _normalize_rotated_topic("noisruceR", True) == "Recursion"
    assert _normalize_rotated_topic("no sdirG\nPD", True) == "DP on Grids"
    assert _normalize_rotated_topic("Introduction", False) == "Introduction"
    assert _find_column(["Module", "Action", "Done", "Priority"], {"action"}) == 1
    assert _find_column(["Module", "Action", "Done", "Priority"], {"done"}) == 2

    protocol = _detect_header_row([["#", "Step", "What to do"]])
    assert protocol is not None
    assert _is_instruction_reference_table(protocol[1], protocol[2], "For every problem")

    schedule = _detect_header_row([["Day", "Concept", "Learn / Implement", "Goal"]])
    assert schedule is not None
    assert not _is_instruction_reference_table(schedule[1], schedule[2], "Days 1-9")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FOUNDATI\nON", "FOUNDATION"),
        ("in-\nplace", "in-place"),
        ("non-\nrepeating", "non-repeating"),
        ("Informat\nion", "Information"),
        ("First principle\nSecond principle", "First principle\nSecond principle"),
        (
            "Longest Substring Without\nRepeating Characters",
            "Longest Substring Without\nRepeating Characters",
        ),
        ("HASH\nMAP", "HASH\nMAP"),
        ("FOUNDATION\nON", "FOUNDATION\nON"),
    ],
)
def test_pdf_cell_reconstruction_is_conservative(raw, expected):
    from pdf_importer import _clean_multiline

    assert _clean_multiline(raw) == expected


def test_pdf_header_detection_rejects_dense_reference_data_rows():
    from pdf_importer import _detect_header_row

    rows = [
        ["ID", "Roadmap", "Primary structure", "Notable extraction challenges"],
        ["1", "DSA", "Week hierarchy", "Nested topic/problem/outcome groups"],
        ["2", "Web", "Phases", "Milestones and exit criteria"],
    ]

    assert _detect_header_row(rows) is None


def test_pdf_dynamic_page_footers_are_removed_from_text_elements():
    from pdf_importer import _margin_signature, _page_text_elements, _recurring_margin_lines

    def line(text, top, size=10):
        return {
            "text": text,
            "x0": 48.0,
            "top": top,
            "bottom": top + size,
            "size": size,
            "bold": False,
            "mono": False,
        }

    page_lines = [
        [line("Useful roadmap content", 100), line(f"Roadmap Guide Page {page}", 810, 7.5)]
        for page in range(1, 4)
    ]
    recurring = _recurring_margin_lines(page_lines, [842.0, 842.0, 842.0])

    assert _margin_signature("Roadmap Guide Page 1") == _margin_signature("Roadmap Guide Page 99")
    assert _margin_signature("Roadmap Guide Page 1") in recurring
    elements = _page_text_elements(page_lines[0], [], 1, 10, recurring)
    assert [element.get("text") for element in elements] == ["Useful roadmap content"]


def test_pdf_safety_limits_fail_explicitly_instead_of_truncating(monkeypatch):
    import pdf_importer

    limits = [
        ("extracted text line", pdf_importer.MAX_PDF_TEXT_LINES),
        ("table row", pdf_importer.MAX_PDF_TABLE_ROWS),
        ("semantic task", pdf_importer.MAX_PDF_TASKS),
        ("document outline element", pdf_importer.MAX_OUTLINE_ELEMENTS),
    ]
    for label, limit in limits:
        with pytest.raises(ValueError, match=label):
            pdf_importer._enforce_pdf_limit(label, limit + 1, limit)

    monkeypatch.setattr(pdf_importer, "MAX_OUTLINE_ELEMENTS", 1)
    with pytest.raises(ValueError, match="document outline element"):
        pdf_importer._add_section_paths(
            [
                {"type": "paragraph", "page": 1, "top": 1, "text": "One"},
                {"type": "paragraph", "page": 1, "top": 2, "text": "Two"},
            ]
        )


def test_pdf_page_limit_is_checked_before_page_extraction(monkeypatch):
    import pdfplumber
    import pdf_importer

    class FakeDocument:
        pages = [object()] * (pdf_importer.MAX_PDF_PAGES + 1)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pdfplumber, "open", lambda _source: FakeDocument())
    with pytest.raises(ValueError, match="page count"):
        pdf_importer.parse_pdf_document(b"%PDF-too-many-pages")


def test_pdf_table_semantics_keep_daily_sequences_matrix_fields_and_cadence():
    from pdf_importer import _table_tasks

    class FakePage:
        def crop(self, _bbox):
            return type("Crop", (), {"chars": []})()

    class FakeTable:
        bbox = (0, 100, 500, 300)
        rows = []

    page = FakePage()
    table = FakeTable()

    daily = _table_tasks(
        page,
        table,
        [
            ["Complete", "Topic", "Required output"],
            ["[ ] Day 1", "Variables", "Write 10 expressions"],
            ["[x] Day 2", "Conditionals", "Build a calculator"],
        ],
        "Python plan",
        1,
    )
    assert [task["title"] for task in daily] == ["Day 1: Variables", "Day 2: Conditionals"]
    assert [task["is_done"] for task in daily] == [False, True]

    matrix = _table_tasks(
        page,
        table,
        [
            ["Stage", "Duration", "Learn", "Practice", "Proof of skill"],
            ["1. Foundations", "4 weeks", "Core theory", "Build examples", "Reviewed project"],
        ],
        "Machine learning roadmap",
        2,
    )
    assert matrix[0]["title"] == "1. Foundations"
    assert matrix[0]["timeframe"] == "Machine learning roadmap"
    assert [block["data"]["label"] for block in matrix[0]["blocks"]] == [
        "Duration",
        "Learn",
        "Practice",
        "Proof of skill",
    ]

    habits = _table_tasks(
        page,
        table,
        [
            ["Habit", "Cadence", "Evidence"],
            ["Code review", "Friday", "List three improvements"],
        ],
        "Recurring habits",
        3,
    )
    assert habits[0]["title"] == "Code review"
    assert [(block["data"]["label"], block["data"]["text"]) for block in habits[0]["blocks"]] == [
        ("Cadence", "Friday"),
        ("Evidence", "List three improvements"),
    ]

    single_column = _table_tasks(
        page,
        table,
        [["Task"], ["Install dependencies"], ["Run the test suite"]],
        "Setup",
        4,
    )
    assert [task["title"] for task in single_column] == [
        "Install dependencies",
        "Run the test suite",
    ]

    step_description = _table_tasks(
        page,
        table,
        [["Step", "Description"], ["1", "Create the project"], ["2", "Ship it"]],
        "Delivery",
        5,
    )
    assert [task["title"] for task in step_description] == [
        "1. Create the project",
        "2. Ship it",
    ]

    action_items = _table_tasks(
        page,
        table,
        [["Action item", "Owner"], ["Review the release", "Asha"]],
        "Launch",
        6,
    )
    assert action_items[0]["title"] == "Review the release"
    assert action_items[0]["blocks"][0]["data"] == {"label": "Owner", "text": "Asha"}


def test_pdf_continued_table_inherits_only_a_compatible_adjacent_schema():
    from pdf_importer import _resolve_table_rows, _table_tasks

    first_rows, schema, section = _resolve_table_rows(
        [["Step", "Description"], ["1", "Create the project"]],
        None,
        document_title="Delivery Roadmap",
        section_label="Phase 1 - Build",
        page_number=1,
        allow_continuation=True,
    )
    assert schema is not None
    assert section == "Phase 1 - Build"

    continued_rows, continued_schema, continued_section = _resolve_table_rows(
        [["2", "Test the project"], ["3", "Deploy the project"]],
        schema,
        document_title="Delivery Roadmap",
        section_label="General",
        page_number=2,
        allow_continuation=True,
    )
    assert continued_rows[0] == ["Step", "Description"]
    assert continued_schema is not None
    assert continued_section == "Phase 1 - Build"

    class FakePage:
        def crop(self, _bbox):
            return type("Crop", (), {"chars": []})()

    class FakeTable:
        bbox = (0, 20, 500, 200)
        rows = [object(), object()]

    tasks = _table_tasks(
        FakePage(),
        FakeTable(),
        continued_rows,
        continued_section,
        2,
    )
    assert [task["title"] for task in tasks] == ["2. Test the project", "3. Deploy the project"]
    assert {task["timeframe"] for task in tasks} == {"Phase 1 - Build"}

    incompatible_rows, incompatible_schema, _ = _resolve_table_rows(
        [["4", "Wrong document"]],
        continued_schema,
        document_title="Different Roadmap",
        section_label="General",
        page_number=3,
        allow_continuation=True,
    )
    assert incompatible_rows == [["4", "Wrong document"]]
    assert incompatible_schema is None

    reference_rows, reference_schema, _ = _resolve_table_rows(
        [["4", "Reference row"]],
        continued_schema,
        document_title="Delivery Roadmap",
        section_label="General",
        page_number=3,
        allow_continuation=False,
    )
    assert reference_rows == [["4", "Reference row"]]
    assert reference_schema is None


def test_pdf_list_tasks_keep_stage_subsection_type_and_reference_boundaries():
    from pdf_importer import _ListTaskContext, _page_list_tasks

    def line(text, top, size=10, bold=False, x0=54):
        return {
            "text": text,
            "x0": x0,
            "top": top,
            "bottom": top + size,
            "size": size,
            "bold": bold,
            "mono": False,
        }

    context = _ListTaskContext()
    lines = [
        line("1. Security Roadmap", 50, size=20, bold=True),
        line("Structure: Levels | Duration: 8 weeks | Goal: Build a lab", 80, size=8.5),
        line("LEVEL 1 - BEGINNER", 120, size=15, bold=True),
        line("Requires: Networking basics", 135, size=8),
        line("Learn", 145, size=9.2, bold=True),
        line("- Networking fundamentals", 160, x0=69),
        line("Hands-on evidence", 180, size=9.2, bold=True),
        line("- [x] Build a local lab", 195, x0=69),
        line("1. Document the result", 212, size=9.2),
        line("Weekly outcome: Explain the lab architecture", 232, size=8),
        line("Priority order", 260, size=15, bold=True),
        line("- P0 - This is metadata, not a task", 280),
    ]

    tasks = _page_list_tasks(lines, [], 1, 10, set(), context)
    assert [task["title"] for task in tasks] == [
        "Networking fundamentals",
        "Build a local lab",
        "Document the result",
        "Explain the lab architecture",
    ]
    assert {task["timeframe"] for task in tasks} == {"LEVEL 1 - BEGINNER"}
    assert [task["properties"].get("Section") for task in tasks] == [
        "Learn",
        "Hands-on evidence",
        "Hands-on evidence",
        None,
    ]
    assert [task["source"]["marker"] for task in tasks] == [
        "bullet",
        "checkbox",
        "numbered",
        "labeled",
    ]
    assert [task["source"]["kind"] for task in tasks] == [
        "learning",
        "evidence",
        "evidence",
        "outcome",
    ]
    assert all(task["properties"]["Requires"] == "Networking basics" for task in tasks)
    assert [task["is_done"] for task in tasks] == [False, True, False, False]

    reference_lines = [
        line("Coverage Summary", 50, size=20, bold=True),
        line("This appendix is not part of any roadmap.", 80, size=9),
        line("- A row that resembles a task", 120),
    ]
    assert _page_list_tasks(reference_lines, [], 2, 10, set(), context) == []


def test_pdf_plain_stage_page_leading_phase_and_resources_are_classified_conservatively():
    from pdf_importer import _ListTaskContext, _is_document_heading, _page_list_tasks

    def line(text, top, size=10, bold=False, x0=54):
        return {
            "text": text,
            "x0": x0,
            "top": top,
            "bottom": top + size,
            "size": size,
            "bold": bold,
            "mono": False,
        }

    context = _ListTaskContext()
    first_page = [
        line("Backend Engineer Roadmap", 50, size=20, bold=True),
        line("Foundations", 120, size=15, bold=True),
        line("- Learn HTTP fundamentals", 150),
        line("Resources", 180, size=9.2, bold=True),
        line("- https://example.com/reference", 200),
    ]
    first_tasks = _page_list_tasks(first_page, [], 1, 10, set(), context)
    assert [(task["timeframe"], task["title"]) for task in first_tasks] == [
        ("Foundations", "Learn HTTP fundamentals")
    ]

    phase_heading = line("Phase 2 - Deployment", 50, size=20, bold=True)
    assert not _is_document_heading(phase_heading)
    second_tasks = _page_list_tasks(
        [phase_heading, line("- Deploy the service", 85)],
        [],
        2,
        10,
        set(),
        context,
    )
    assert [(task["timeframe"], task["title"]) for task in second_tasks] == [
        ("Phase 2 - Deployment", "Deploy the service")
    ]


def test_pdf_outline_preserves_dependency_kpi_and_exit_criterion_metadata():
    from pdf_importer import _page_text_elements

    def line(text, top, size=10, bold=False):
        return {
            "text": text,
            "x0": 54.0,
            "top": top,
            "bottom": top + size,
            "size": size,
            "bold": bold,
            "mono": False,
        }

    lines = [
        line("Node B - Storage", 100, size=15, bold=True),
        line("Requires: Node A", 130, size=9),
        line("KPIs / proof", 155, size=9.2, bold=True),
        line("Milestone: Exit criterion: restore from backup", 180, size=9),
    ]
    elements = _page_text_elements(lines, [], 1, 10, set())
    preserved = "\n".join(
        element.get("text", "") for element in elements if element["type"] in {"heading", "paragraph"}
    )
    assert "Requires: Node A" in preserved
    assert "KPIs / proof" in preserved
    assert "Exit criterion: restore from backup" in preserved


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

    property_update = client.put(
        f"/tasks/{created_task['id']}/properties",
        json={"properties": {"Revision Count": 3, "Revisit": True, "Priority": "High"}},
        headers=headers,
    )
    assert property_update.status_code == 200
    assert property_update.json()["properties"] == {
        "Revision Count": 3,
        "Revisit": True,
        "Priority": "High",
    }

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


def test_task_blocks_are_ordered_extensible_and_user_scoped():
    name = f"Block Roadmap {time.time()}"
    roadmap = client.post(
        "/roadmaps",
        json={"name": name, "text": "Tasks\n- Build the parser"},
        headers=headers,
    ).json()
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]
    assert task["blocks"] == []

    note = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "note", "data": {"text": "Handle table headers"}},
        headers=headers,
    )
    assert note.status_code == 201
    assert note.json()["position"] == 0

    counter = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "counter", "data": {"label": "Attempts", "value": 2}, "position": 0},
        headers=headers,
    )
    assert counter.status_code == 201

    custom = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "code-snippet", "data": {"language": "python", "code": "print('ok')"}},
        headers=headers,
    )
    assert custom.status_code == 201

    blocks = client.get(f"/tasks/{task['id']}/blocks", headers=headers)
    assert blocks.status_code == 200
    assert [block["type"] for block in blocks.json()] == ["counter", "note", "code-snippet"]

    moved = client.patch(
        f"/task-blocks/{custom.json()['id']}",
        json={"position": 0, "data": {"language": "python", "code": "print('done')"}},
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["position"] == 0
    assert moved.json()["data"]["code"] == "print('done')"

    forbidden = client.get(
        f"/tasks/{task['id']}/blocks",
        headers={"X-Local-User-Id": "different_user"},
    )
    assert forbidden.status_code == 404

    invalid = client.post(
        f"/tasks/{task['id']}/blocks",
        json={"type": "Bad Type", "data": {}},
        headers=headers,
    )
    assert invalid.status_code == 400

    deleted = client.delete(f"/task-blocks/{note.json()['id']}", headers=headers)
    assert deleted.status_code == 200
    remaining = client.get(f"/tasks/{task['id']}/blocks", headers=headers).json()
    assert [block["position"] for block in remaining] == list(range(len(remaining)))


def test_bulk_task_blocks_append_in_request_order_and_deduplicate_targets():
    roadmap = client.post(
        "/roadmaps",
        json={
            "name": f"Bulk Block Roadmap {time.time()}",
            "text": "Tasks\n- First target\n- Second target\n- Third target",
        },
        headers=headers,
    ).json()
    tasks = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()
    first, second, third = tasks

    existing = client.post(
        f"/tasks/{first['id']}/blocks",
        json={"type": "note", "data": {"text": "Existing"}},
        headers=headers,
    )
    assert existing.status_code == 201

    response = client.post(
        "/task-blocks/bulk",
        json={
            "task_ids": [second["id"], first["id"], second["id"], third["id"]],
            "type": "bookmark",
            "data": {"label": "Shared reference", "url": "https://example.com"},
        },
        headers=headers,
    )

    assert response.status_code == 201
    blocks = response.json()["blocks"]
    assert [block["task_id"] for block in blocks] == [
        second["id"],
        first["id"],
        third["id"],
    ]
    assert [block["position"] for block in blocks] == [0, 1, 0]
    assert all(block["type"] == "bookmark" for block in blocks)
    assert all(
        block["data"] == {"label": "Shared reference", "url": "https://example.com"}
        for block in blocks
    )

    first_blocks = client.get(f"/tasks/{first['id']}/blocks", headers=headers).json()
    second_blocks = client.get(f"/tasks/{second['id']}/blocks", headers=headers).json()
    assert [block["type"] for block in first_blocks] == ["note", "bookmark"]
    assert [block["type"] for block in second_blocks] == ["bookmark"]


def test_bulk_task_blocks_reject_invalid_type_without_writing():
    roadmap = client.post(
        "/roadmaps",
        json={"name": f"Invalid Bulk Block {time.time()}", "text": "Tasks\n- Keep clean"},
        headers=headers,
    ).json()
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]

    response = client.post(
        "/task-blocks/bulk",
        json={"task_ids": [task["id"]], "type": "Bad Type", "data": {"text": "No"}},
        headers=headers,
    )

    assert response.status_code == 400
    assert client.get(f"/tasks/{task['id']}/blocks", headers=headers).json() == []


def test_bulk_task_blocks_fail_atomically_for_unknown_or_cross_user_tasks():
    owner_roadmap = client.post(
        "/roadmaps",
        json={"name": f"Owned Bulk Block {time.time()}", "text": "Tasks\n- Owned target"},
        headers=headers,
    ).json()
    owner_task = client.get(
        f"/roadmaps/{owner_roadmap['id']}/tasks", headers=headers
    ).json()[0]

    other_headers = {"X-Local-User-Id": "bulk_other_user"}
    other_roadmap = client.post(
        "/roadmaps",
        json={"name": f"Other Bulk Block {time.time()}", "text": "Tasks\n- Other target"},
        headers=other_headers,
    ).json()
    other_task = client.get(
        f"/roadmaps/{other_roadmap['id']}/tasks", headers=other_headers
    ).json()[0]

    for inaccessible_task_id in (other_task["id"], 2_147_483_647):
        response = client.post(
            "/task-blocks/bulk",
            json={
                "task_ids": [owner_task["id"], inaccessible_task_id],
                "type": "note",
                "data": {"text": "Must be atomic"},
            },
            headers=headers,
        )
        assert response.status_code == 404
        assert client.get(
            f"/tasks/{owner_task['id']}/blocks", headers=headers
        ).json() == []

    assert client.get(
        f"/tasks/{other_task['id']}/blocks", headers=other_headers
    ).json() == []


def test_bulk_task_blocks_fail_atomically_across_roadmaps():
    first_roadmap = client.post(
        "/roadmaps",
        json={"name": f"First Bulk Scope {time.time()}", "text": "Tasks\n- First target"},
        headers=headers,
    ).json()
    second_roadmap = client.post(
        "/roadmaps",
        json={"name": f"Second Bulk Scope {time.time()}", "text": "Tasks\n- Second target"},
        headers=headers,
    ).json()
    first_task = client.get(
        f"/roadmaps/{first_roadmap['id']}/tasks", headers=headers
    ).json()[0]
    second_task = client.get(
        f"/roadmaps/{second_roadmap['id']}/tasks", headers=headers
    ).json()[0]

    response = client.post(
        "/task-blocks/bulk",
        json={
            "task_ids": [first_task["id"], second_task["id"]],
            "type": "note",
            "data": {"text": "Must stay inside one roadmap"},
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert client.get(f"/tasks/{first_task['id']}/blocks", headers=headers).json() == []
    assert client.get(f"/tasks/{second_task['id']}/blocks", headers=headers).json() == []


def test_bulk_task_blocks_require_targets_and_enforce_5000_task_cap():
    empty = client.post(
        "/task-blocks/bulk",
        json={"task_ids": [], "type": "note", "data": {}},
        headers=headers,
    )
    assert empty.status_code == 422

    over_cap = client.post(
        "/task-blocks/bulk",
        json={"task_ids": list(range(1, 5002)), "type": "note", "data": {}},
        headers=headers,
    )
    assert over_cap.status_code == 422


def test_smart_update_round_trips_duplicate_ordered_blocks_from_export():
    name = f"Smart Block Round Trip {time.time()}"
    roadmap = client.post(
        "/roadmaps",
        json={"name": name, "text": "Phase 1\n- Preserve block order"},
        headers=headers,
    ).json()
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]

    block_payloads = [
        {"type": "note", "data": {"text": "Read the constraint"}},
        {"type": "note", "data": {"text": "Same reminder"}},
        {"type": "note", "data": {"text": "Same reminder"}},
        {"type": "bookmark", "data": {"label": "Reference", "url": "https://example.com"}},
    ]
    for payload in block_payloads:
        response = client.post(
            f"/tasks/{task['id']}/blocks",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 201

    exported = client.get(f"/roadmaps/{roadmap['id']}/export", headers=headers)
    assert exported.status_code == 200
    exported_tasks = exported.json()["tasks"]
    assert [block["position"] for block in exported_tasks[0]["blocks"]] == [0, 1, 2, 3]

    updated = client.put(
        f"/roadmaps/{roadmap['id']}/smart",
        json={"name": name, "tasks": exported_tasks},
        headers=headers,
    )
    assert updated.status_code == 200

    refreshed = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]
    assert [(block["type"], block["data"]) for block in refreshed["blocks"]] == [
        (payload["type"], payload["data"]) for payload in block_payloads
    ]
    assert [block["position"] for block in refreshed["blocks"]] == [0, 1, 2, 3]
    assert sum(
        block["data"] == {"text": "Same reminder"} for block in refreshed["blocks"]
    ) == 2


def test_legacy_revision_properties_migrate_only_meaningful_values():
    name = f"Legacy Block Roadmap {time.time()}"
    roadmap = client.post(
        "/roadmaps",
        json={"name": name, "text": "Tasks\n- Revisit parser"},
        headers=headers,
    ).json()
    task = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]
    updated = client.put(
        f"/tasks/{task['id']}/properties",
        json={
            "properties": {
                "Revision Count": 3,
                "Revisit": True,
                "Priority": "High",
            }
        },
        headers=headers,
    )
    assert updated.status_code == 200

    db.init_db()
    migrated = client.get(f"/roadmaps/{roadmap['id']}/tasks", headers=headers).json()[0]
    assert migrated["properties"] == {"Priority": "High"}
    assert [(block["type"], block["data"]) for block in migrated["blocks"]] == [
        ("counter", {"label": "Revision", "value": 3, "step": 1}),
        ("bookmark", {"label": "Revisit", "bookmarked": True}),
    ]

    empty_name = f"Empty Legacy Block Roadmap {time.time()}"
    empty_roadmap = client.post(
        "/roadmaps",
        json={"name": empty_name, "text": "Tasks\n- Do not clutter"},
        headers=headers,
    ).json()
    empty_task = client.get(f"/roadmaps/{empty_roadmap['id']}/tasks", headers=headers).json()[0]
    client.put(
        f"/tasks/{empty_task['id']}/properties",
        json={"properties": {"Revision Count": "", "Revisit": False}},
        headers=headers,
    )
    db.init_db()
    migrated_empty = client.get(f"/roadmaps/{empty_roadmap['id']}/tasks", headers=headers).json()[0]
    assert migrated_empty["properties"] == {}
    assert migrated_empty["blocks"] == []


def test_layout_aware_import_of_18_day_pdf():
    sample = Path(r"C:\Users\gurte\Downloads\DSA_18_Day_Arrays_Strings_Foundation_Roadmap.pdf")
    if not sample.exists():
        pytest.skip("Local acceptance PDF is not available")

    name = f"18 Day PDF {time.time()}"
    response = client.post(
        "/roadmaps/import-file",
        data={"name": name},
        files={"file": (sample.name, sample.read_bytes(), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["tasks"] == 18
    assert response.json()["document_elements"] >= 25

    roadmap_id = response.json()["id"]
    tasks = client.get(f"/roadmaps/{roadmap_id}/tasks", headers=headers).json()
    assert len(tasks) == 18
    assert tasks[0]["title"] == "Day 1: Big-O + Python containers"
    assert tasks[17]["title"] == "Day 18: Sliding window"
    assert {task["timeframe_label"] for task in tasks} == {
        "Days 1-9 - Array foundation and first checklist problems",
        "Days 10-14 - Core array patterns used by the checklist",
        "Days 15-18 - String foundation",
    }
    assert all(not task["title"].startswith("1. Read + classify") for task in tasks)
    assert [block["data"]["label"] for block in tasks[0]["blocks"]] == [
        "Learn / Implement",
        "PDF problems / practice",
        "Goal",
    ]
    assert all(block["type"] == "note" for block in tasks[0]["blocks"])
    assert tasks[0]["properties"] == {}

    def imported_note(task, label):
        return next(
            block["data"]["text"]
            for block in task["blocks"]
            if block["type"] == "note" and block["data"]["label"] == label
        )

    assert imported_note(tasks[0], "Goal") == "FOUNDATION"
    assert "O(1),\nO(n)" in imported_note(tasks[0], "Learn / Implement")
    assert "in-place reverse" in imported_note(tasks[5], "Learn / Implement")
    assert "non-repeating char" in imported_note(tasks[15], "PDF problems / practice")

    document = client.get(f"/roadmaps/{roadmap_id}/document", headers=headers)
    assert document.status_code == 200
    assert document.json()["version"] == 1
    element_types = {element["type"] for element in document.json()["elements"]}
    assert {"heading", "paragraph", "list", "table", "callout", "code"} <= element_types


def test_layout_aware_import_of_10_structure_pdf_suite():
    from collections import Counter

    from pdf_importer import parse_pdf_document

    sample = Path(r"C:\Users\gurte\Downloads\Roadmap_Extraction_Test_Suite_10_Structures.pdf")
    if not sample.exists():
        pytest.skip("Local 10-structure acceptance PDF is not available")

    result = parse_pdf_document(sample.read_bytes())
    counts = Counter(task["properties"].get("Roadmap") for task in result.tasks)

    assert result.page_count == 17
    assert len(result.tasks) == 284
    assert "Roadmap Extraction Test Suite Page" not in result.text
    assert counts == {
        "1. DSA Foundations Roadmap": 64,
        "2. Full-Stack Web Development Roadmap": 31,
        "3. Python in 30 Days": 30,
        "4. AI / Machine Learning Roadmap": 6,
        "5. System Design Roadmap": 35,
        "6. Cybersecurity Learning Roadmap": 26,
        "7. UI/UX Product Design Roadmap": 28,
        "8. GATE CSE Preparation Roadmap": 23,
        "9. DevOps / Cloud Roadmap": 26,
        "10. Mobile App Developer Roadmap": 15,
    }
    assert all(task["source"]["page"] < 17 for task in result.tasks)

    outcomes = [task for task in result.tasks if task["source"].get("kind") == "outcome"]
    milestones = [task for task in result.tasks if task["source"].get("kind") == "milestone"]
    deliverables = [task for task in result.tasks if task["source"].get("kind") == "deliverable"]
    assert len(outcomes) == 8
    assert len(milestones) == 6
    assert len(deliverables) == 7

    daily = [task for task in result.tasks if task["source"]["page"] == 7]
    assert daily[0]["title"] == "Day 1: Variables, numbers, strings"
    assert daily[-1]["title"] == "Day 30: Final challenge"

    matrix = [task for task in result.tasks if task["source"]["page"] == 8]
    assert [task["title"] for task in matrix] == [
        "1. Math",
        "2. Python Data Stack",
        "3. Classical ML",
        "4. Deep Learning",
        "5. MLOps",
        "6. Specialization",
    ]
    assert [block["data"]["label"] for block in matrix[0]["blocks"]] == [
        "Duration",
        "Learn",
        "Practice",
        "Proof of skill",
    ]

    node_f = [task for task in result.tasks if task["timeframe"] == "Node F - Reliability"]
    assert [task["title"] for task in node_f] == [
        "SLO/SLA/SLI",
        "Observability",
        "Backpressure",
        "Circuit breakers",
        "Multi-region strategy",
    ]
    node_b = [task for task in result.tasks if task["timeframe"] == "Node B - Data Storage"]
    assert all(task["properties"]["Requires"] == "Node A" for task in node_b)
    phase_one = [task for task in result.tasks if task["timeframe"] == "PHASE 1 - Web Core"]
    assert all(task["properties"]["Schedule"] == "Weeks 1-3" for task in phase_one)
    assert all(task["properties"]["Prerequisite"] == "basic programming" for task in phase_one)
    case_studies = [task for task in result.tasks if task["timeframe"] == "CASE STUDY ORDER"]
    assert [task["title"] for task in case_studies] == [
        "URL shortener",
        "News feed",
        "Chat system",
        "Ride matching",
        "Video streaming",
        "Payment system",
    ]
    assert [task["properties"]["Order"] for task in case_studies] == [1, 2, 3, 4, 5, 6]

    mobile = [
        task
        for task in result.tasks
        if task["properties"].get("Roadmap") == "10. Mobile App Developer Roadmap"
    ]
    assert all(task["timeframe"] != "Priority order" for task in mobile)

    recurring = next(task for task in result.tasks if task["title"] == "Code review")
    assert recurring["timeframe"] == "RECURRING HABITS - EVERY WEEK"
    assert [(block["data"]["label"], block["data"]["text"]) for block in recurring["blocks"]] == [
        ("Cadence", "Friday"),
        ("Evidence", "List 3 improvements in your own code"),
    ]

    outline_text = "\n".join(
        [element.get("text", "") for element in result.outline]
        + [str(cell) for element in result.outline for cell in element.get("columns", [])]
        + [
            str(cell)
            for element in result.outline
            for row in element.get("rows", [])
            for cell in row
        ]
    )
    assert "Milestone: Exit criterion" in outline_text
    assert "Requires: Node A" in outline_text
    assert "KPIs / proof" in outline_text
    assert "Cadence" in outline_text
    assert "Roadmap Extraction Test Suite Page" not in outline_text
