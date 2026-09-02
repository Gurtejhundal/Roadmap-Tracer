import pytest


@pytest.fixture
def repeated_header_table_pages():
    return [
        {
            "page_number": 1,
            "section_label": "400-Day DSA Roadmap",
            "rows": [["Day", "Problem"], ["1", "Print Hello, DSA!"]],
        },
        {
            "page_number": 2,
            "section_label": "General",
            "rows": [["Day", "Problem"], ["37", "Check whether a list is sorted"]],
        },
        {
            "page_number": 3,
            "section_label": "400-Day DSA Roadmap",
            "rows": [["Day", "Problem"], ["76", "Toggle character case"]],
        },
    ]


def test_repeated_matching_headers_inherit_the_adjacent_table_section(
    repeated_header_table_pages,
):
    from pdf_importer import _resolve_table_rows, _table_tasks

    class FakePage:
        def crop(self, _bbox):
            return type("Crop", (), {"chars": []})()

    class FakeTable:
        bbox = (0, 20, 500, 200)

        def __init__(self, row_count):
            self.rows = [object()] * row_count

    previous = None
    tasks = []
    for page in repeated_header_table_pages:
        rows, previous, section = _resolve_table_rows(
            page["rows"],
            previous,
            document_title="400-Day DSA Roadmap",
            section_label=page["section_label"],
            page_number=page["page_number"],
            allow_continuation=True,
        )
        assert previous is not None
        assert section == "400-Day DSA Roadmap"
        assert previous.section_label == "400-Day DSA Roadmap"
        tasks.extend(
            _table_tasks(
                FakePage(),
                FakeTable(len(rows)),
                rows,
                section,
                page["page_number"],
            )
        )

    assert [task["title"] for task in tasks] == [
        "Day 1: Print Hello, DSA!",
        "Day 37: Check whether a list is sorted",
        "Day 76: Toggle character case",
    ]
    assert {task["timeframe"] for task in tasks} == {"400-Day DSA Roadmap"}


def test_repeated_header_does_not_override_a_new_specific_section():
    from pdf_importer import _resolve_table_rows

    _, first_schema, _ = _resolve_table_rows(
        [["Day", "Problem"], ["1", "First task"]],
        None,
        document_title="DSA Roadmap",
        section_label="Foundation",
        page_number=1,
        allow_continuation=True,
    )
    assert first_schema is not None

    _, next_schema, section = _resolve_table_rows(
        [["Day", "Problem"], ["20", "Advanced task"]],
        first_schema,
        document_title="DSA Roadmap",
        section_label="Advanced",
        page_number=2,
        allow_continuation=True,
    )

    assert next_schema is not None
    assert section == "Advanced"
    assert next_schema.section_label == "Advanced"
