from pathlib import Path

import pytest


class _FakeCrop:
    chars = []

    def __init__(self, size):
        self.size = size

    def extract_words(self, extra_attrs=None):
        del extra_attrs
        return [{"size": self.size}] if self.size else []


class _FakePage:
    def __init__(self, sizes):
        self.sizes = sizes

    def crop(self, bbox):
        return _FakeCrop(self.sizes.get(bbox, 0))


class _FakeRow:
    def __init__(self, row_index, width):
        self.cells = [(row_index, column_index) for column_index in range(width)]


class _FakeTable:
    bbox = (0, 100, 500, 300)

    def __init__(self, row_count, width):
        self.rows = [_FakeRow(row_index, width) for row_index in range(row_count)]


def test_single_cell_table_tasks_use_typography_to_distinguish_section_rows():
    from pdf_importer import _table_tasks

    rows = [
        ["Topic", "Problem Name", "Completed", "Revision Count", "Revisit"],
        ["", "Arrays", "", "", ""],
        ["Arrays Medium", "Majority Element-I", "", "", ""],
        [None, "Leaders in an Array", "", "", ""],
        [None, "Problem Name", "Completed", "Revision Count", "Revisit"],
        [None, "Next Permutation", "", "2", "yes"],
    ]
    sizes = {(row_index, 1): 11 for row_index in range(len(rows))}
    sizes[(1, 1)] = 20

    tasks = _table_tasks(
        _FakePage(sizes),
        _FakeTable(len(rows), len(rows[0])),
        rows,
        "General",
        1,
    )

    assert [task["title"] for task in tasks] == [
        "Majority Element-I",
        "Leaders in an Array",
        "Next Permutation",
    ]
    assert {task["timeframe"] for task in tasks} == {"Arrays Medium"}
    assert [(block["type"], block["data"]["label"]) for block in tasks[-1]["blocks"]] == [
        ("counter", "Revision"),
        ("bookmark", "Revisit"),
    ]


def test_page_split_rotated_group_fragments_are_reassembled_conservatively():
    from pdf_importer import _TableTaskContext, _table_tasks

    headers = ["Topic", "Problem Name", "Completed", "Revision Count", "Revisit"]
    context = _TableTaskContext()
    first_rows = [
        headers,
        ["dow", "Theory", "", "", ""],
        [None, "Maximum Points You Can Obtain from Cards", "", "", ""],
    ]
    first = _table_tasks(
        _FakePage({(1, 1): 11, (2, 1): 11}),
        _FakeTable(len(first_rows), len(headers)),
        first_rows,
        "General",
        3,
        context,
    )
    assert {task["timeframe"] for task in first} == {"dow"}

    # The inherited header is synthetic, so the physical table has two rows.
    second_rows = [
        headers,
        ["Sliding Win", "Longest Substring Without Repeating Characters", "", "", ""],
        [None, "Fruit Into Baskets", "", "", ""],
    ]
    second = _table_tasks(
        _FakePage({(0, 1): 11, (1, 1): 11}),
        _FakeTable(2, len(headers)),
        second_rows,
        "General",
        4,
        context,
    )

    assert {task["timeframe"] for task in second} == {"Sliding Window"}
    assert context.renamed_group_from == "dow"
    assert context.renamed_group_to == "Sliding Window"


def test_json_roadmap_reimport_preserves_task_metadata_and_does_not_invent_empty_tasks():
    from roadmap_parser import parse_tasks

    tasks = parse_tasks(
        """{
            "tasks": [{
                "title": "Ship the image",
                "timeframe": "Docker",
                "is_done": "false",
                "granularity": "module",
                "properties": {"Priority": "High"},
                "blocks": [{"type": "note", "data": {"text": "Use CI"}, "position": 4}]
            }]
        }"""
    )

    assert tasks == [
        {
            "title": "Ship the image",
            "timeframe": "Docker",
            "is_done": False,
            "granularity": "module",
            "properties": {"Priority": "High"},
            "blocks": [{"type": "note", "data": {"text": "Use CI"}, "position": 4}],
        }
    ]
    assert parse_tasks('{"tasks": []}') == []


def test_text_parser_supports_common_checkbox_glyphs_and_ignores_fenced_code():
    from roadmap_parser import parse_tasks

    tasks = parse_tasks(
        """Docker setup
        ☑ Install Docker Desktop
        ☐ Build an image

        ```bash
        docker run --rm app
        ```
        [v] Push the image
        """
    )

    assert [task["title"] for task in tasks] == [
        "Install Docker Desktop",
        "Build an image",
        "Push the image",
    ]
    assert [task["is_done"] for task in tasks] == [True, False, True]


def test_local_tuf_checklist_imports_every_task_row_without_header_noise():
    from pdf_importer import parse_pdf_document

    sample = Path(r"D:\Download\DSA 400 Days Challenge.pdf")
    if not sample.exists():
        pytest.skip("Local TUF+ checklist fixture is unavailable")

    result = parse_pdf_document(sample.read_bytes())
    titles = [task["title"] for task in result.tasks]
    task_by_title = {task["title"]: task for task in result.tasks}

    assert len(result.tasks) == 328
    assert "Problem Name" not in titles
    assert task_by_title["Theory"]["timeframe"] == "Sliding Window"
    assert task_by_title["Level Order Traversal"]["timeframe"] == "Binary Trees Theory"
    assert task_by_title["Distinct subsequences"]["timeframe"] == "DP on Strings"
    assert task_by_title["Rabin Karp Algorithm"]["timeframe"] == "Advanced Problems (Less asked)"
