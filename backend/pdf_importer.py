"""Layout-aware PDF roadmap importer.

The importer intentionally separates document semantics from task extraction:
tables with a recognizable task column become tasks, while headings, prose,
lists, callouts, code, and all tables are retained in a structured outline.
This avoids turning every PDF sentence or every table cell into a checkbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
import re
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


MAX_CELL_LENGTH = 12_000
MAX_PDF_PAGES = 250
MAX_PDF_TEXT_LINES = 50_000
MAX_PDF_TABLE_ROWS = 25_000
MAX_PDF_TASKS = 5_000
MAX_OUTLINE_ELEMENTS = 10_000

_BULLET_RE = re.compile(r"^\s*[\u2022\uf0b7\u25e6\u25aa\u25cf\-]\s*")
_CHECKBOX_ITEM_RE = re.compile(
    r"^\s*(?:[\u2022\uf0b7\u25e6\u25aa\u25cf\-]\s*)?"
    r"(?:\[(?P<bracket>[^\]])\]|(?P<glyph>[\u2610\u2611\u2612]))\s*(?P<title>.+?)\s*$"
)
_NUMBERED_ITEM_RE = re.compile(r"^\s*(?P<number>\d{1,3})[.)]\s+(?P<title>.+?)\s*$")
_STAGE_HEADING_RE = re.compile(
    r"^(?:"
    r"weeks?\s+\d|phases?\s+\w|stages?\s+\w|levels?\s+\w|sprints?\s+\w|"
    r"nodes?\s+[a-z0-9]|days?\s+\d|months?\s+\d|quarters?\s+\w|"
    r"t\s*[-+]\s*\d|parallel\s+tracks?\b|tracks?\s+[a-z0-9]|"
    r"recurring\s+(?:habits?|tasks?|work)\b"
    r")",
    re.IGNORECASE,
)
_NON_TASK_CONTAINER_RE = re.compile(
    r"^(?:priorit(?:y|ies)(?:\s+order)?|prerequisite\s+chain|deferred\s+items?|"
    r"resources?|references?|further\s+reading|reading\s+list|useful\s+links?|"
    r"what\s+(?:you|learners?)\s+(?:should|will)\s+know|do\s+not\b|don['\u2019]t\b|"
    r"out\s+of\s+scope|readme\b|templates?\b|success\s+criteria?)\b",
    re.IGNORECASE,
)
_NON_TASK_DOCUMENT_RE = re.compile(
    r"\b(?:test\s+suite|coverage\s+summary|appendix|reference\s+(?:guide|sheet)|"
    r"sample\s+(?:set|collection)|catalog|index)\b",
    re.IGNORECASE,
)
_ORDER_CONTAINER_RE = re.compile(r"\b(?:order|sequence|pipeline|path)\b", re.IGNORECASE)
_OUTCOME_CONTAINER_RE = re.compile(
    r"^(?:final\s+(?:target|goal|outcome|result)|end\s+(?:goal|state))\b",
    re.IGNORECASE,
)
_TRACKABLE_LABEL_RE = re.compile(
    r"^(?P<label>weekly\s+outcome|milestone|deliverable|capstone|final\s+(?:artifact|deliverable|output)|exit\s+criterion)"
    r"\s*:\s*(?P<title>.+?)\s*$",
    re.IGNORECASE,
)
_ARROW_SPLIT_RE = re.compile(r"\s*(?:->|\u2192|\u21d2)\s*")
_STAGE_METADATA_RE = re.compile(
    r"^(?P<label>requires?|unlocks?|prerequisites?|entry\s+gate)\s*:\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_SCHEDULE_METADATA_RE = re.compile(
    r"^(?P<label>weeks?|days?|months?|quarters?)\s+(?P<value>.+)$",
    re.IGNORECASE,
)
_DOCUMENT_METADATA_RE = re.compile(r"\b(?:structure|duration|goal)\s*:", re.IGNORECASE)
_REFERENCE_PAGE_RE = re.compile(
    r"\b(?:not part of (?:any|the) roadmap|appendix only|reference only)\b",
    re.IGNORECASE,
)
_HEADER_NORMALIZE_RE = re.compile(r"[^a-z0-9+#]+")
_SPACE_RE = re.compile(r"\s+")
_PLAIN_WORD_RE = re.compile(r"^[A-Za-z]+$")
_LOWERCASE_SUFFIX_FRAGMENTS = {
    "ed",
    "er",
    "ers",
    "es",
    "ing",
    "ion",
    "ions",
    "ity",
    "ly",
    "ment",
    "ness",
    "on",
}
_COMPLETE_WORD_SUFFIXES = (
    "ability",
    "ibility",
    "ment",
    "ness",
    "sion",
    "tion",
    "ing",
    "ity",
    "ous",
    "ive",
)

_TASK_HEADER_SCORES = {
    "problem name": 120,
    "task name": 120,
    "checklist item": 115,
    "action item": 115,
    "problem": 110,
    "task": 110,
    "action": 105,
    "to do": 105,
    "todo": 105,
    "title": 100,
    "step": 95,
    "concept": 90,
    "focus": 90,
    "habit": 95,
    "activity": 95,
    "objective": 95,
    "learning objective": 95,
    "deliverable": 90,
    "milestone": 90,
    "item": 85,
    "topic": 70,
    "what to do": 60,
}
_GROUP_HEADERS = {"area", "category", "group", "module", "section", "stage", "phase", "topic"}
_SEQUENCE_HEADERS = {
    "#",
    "day",
    "week",
    "month",
    "number",
    "no",
    "step no",
    "step number",
    "step",
    "window",
    "period",
    "timeline",
    "range",
}
_STATUS_HEADERS = {"complete", "completed", "done", "finished", "status"}
_REVISION_HEADERS = {"revision", "revision count", "revisions"}
_REVISIT_HEADERS = {"bookmark", "revisit", "visit again"}
_BOOKMARK_HEADERS = {"link", "resource", "source", "url"}
_PRIMARY_ENTITY_HEADERS = {"stage", "phase", "level", "module", "milestone"}
_DETAIL_HEADERS = {
    "cadence",
    "duration",
    "evidence",
    "focus",
    "goal",
    "learn",
    "objective",
    "output",
    "practice",
    "proof",
    "proof of skill",
    "required output",
}
_REFERENCE_CONTEXT_RE = re.compile(
    r"\b(?:for every|how to|instructions?|protocol|reference|template|workflow)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PdfImportResult:
    text: str
    tasks: List[Dict[str, Any]]
    outline: List[Dict[str, Any]]
    page_count: int


@dataclass
class _ListTaskContext:
    document_title: str = ""
    document_confirmed: bool = False
    stage: str = ""
    subsection: str = ""
    pending_outcome: bool = False
    stage_metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _TableSchema:
    headers: Tuple[str, ...]
    document_title: str
    section_label: str
    page_number: int


@dataclass
class _TableTaskContext:
    """Carry a merged table's active group across adjacent PDF pages."""

    current_group: str = ""
    page_number: int = 0
    renamed_group_from: str = ""
    renamed_group_to: str = ""


def _enforce_pdf_limit(label: str, count: int, limit: int) -> None:
    if count > limit:
        raise ValueError(
            f"PDF exceeds the supported {label} limit of {limit:,}. "
            "Split it into smaller documents and import them separately."
        )


def _clean_text(value: Any) -> str:
    text = str(value or "").replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
    return _SPACE_RE.sub(" ", text).strip()[:MAX_CELL_LENGTH]


def _is_unhyphenated_word_split(previous: str, continuation: str) -> bool:
    """Recognize a word forced across cell lines without joining normal prose.

    PDF table extractors retain visual line wraps. Most of those wraps represent
    real word boundaries and must remain available to the document renderer.
    This deliberately narrow heuristic only rejoins a long, unfinished single
    token followed by a short grammatical suffix (for example ``FOUNDATI`` +
    ``ON``). It does not join ordinary pairs such as ``HASH`` + ``MAP``.
    """
    if not (_PLAIN_WORD_RE.fullmatch(previous) and _PLAIN_WORD_RE.fullmatch(continuation)):
        return False
    if len(previous) < 6 or not 2 <= len(continuation) <= 5:
        return False

    previous_lower = previous.lower()
    continuation_lower = continuation.lower()
    if continuation_lower not in _LOWERCASE_SUFFIX_FRAGMENTS:
        return False
    if previous_lower.endswith(_COMPLETE_WORD_SUFFIXES):
        return False

    both_upper = previous.isupper() and continuation.isupper()
    lower_or_title_fragment = (
        (previous.islower() or (previous[:1].isupper() and previous[1:].islower()))
        and continuation.islower()
    )
    return both_upper or lower_or_title_fragment


def _repair_cell_line_breaks(lines: Sequence[str]) -> List[str]:
    """Repair lexical line breaks while preserving meaningful cell newlines."""
    repaired: List[str] = []
    for line in lines:
        if not repaired:
            repaired.append(line)
            continue

        previous = repaired[-1]
        # A hyphen directly attached to a word is lexical. A spaced dash such as
        # ``topic -`` remains a structural separator and is not collapsed.
        if re.search(r"[A-Za-z0-9]-$", previous) and re.match(r"^[a-z]", line):
            repaired[-1] = previous + line
        elif _is_unhyphenated_word_split(previous, line):
            repaired[-1] = previous + line
        else:
            repaired.append(line)
    return repaired


def _clean_multiline(value: Any) -> str:
    lines = [_clean_text(line) for line in str(value or "").splitlines()]
    nonempty_lines = [line for line in lines if line]
    return "\n".join(_repair_cell_line_breaks(nonempty_lines))[:MAX_CELL_LENGTH]


def _normalize_header(value: Any) -> str:
    normalized = _HEADER_NORMALIZE_RE.sub(" ", _clean_text(value).lower()).strip()
    return _SPACE_RE.sub(" ", normalized)


def _margin_signature(value: Any) -> str:
    text = _clean_text(value).lower()
    if re.fullmatch(r"\d{1,4}", text):
        return "page number"
    text = re.sub(r"\bpage\s+\d+(?:\s+of\s+\d+)?\b", "page number", text)
    text = re.sub(r"\b\d+\s*(?:/|of)\s*\d+\b", "page number", text)
    return _normalize_header(text)


def _is_truthy(value: Any) -> bool:
    return _normalize_header(value) in {"1", "true", "yes", "y", "x", "done", "complete", "completed", "checked"}


def _positive_integer(value: Any) -> Optional[int]:
    text = _clean_text(value)
    if not text:
        return None
    match = re.fullmatch(r"\+?\d+", text)
    if not match:
        return None
    number = int(text)
    return number if number > 0 else None


def _parse_checkbox(value: Any) -> Tuple[bool, bool, str]:
    """Return ``(recognized, checked, trailing_label)`` for checkbox text."""
    text = str(value or "").strip()
    match = _CHECKBOX_ITEM_RE.fullmatch(text)
    if match is None:
        return False, _is_truthy(text), ""

    marker = (match.group("bracket") or match.group("glyph") or "").strip().lower()
    checked = marker in {"x", "v", "\u2713", "\u2714", "\u2611"}
    return True, checked, _clean_text(match.group("title"))


def _parse_list_item(value: Any) -> Optional[Tuple[str, bool, str]]:
    """Recognize bullets, checkboxes, and numbered actions without guessing prose."""
    text = str(value or "").strip()
    checkbox, checked, checkbox_title = _parse_checkbox(text)
    if checkbox:
        return checkbox_title, checked, "checkbox"

    numbered = _NUMBERED_ITEM_RE.fullmatch(text)
    if numbered:
        return _clean_text(numbered.group("title")), False, "numbered"

    if _BULLET_RE.match(text):
        title = _clean_text(_BULLET_RE.sub("", text, count=1))
        if title:
            return title, False, "bullet"
    return None


def _header_score(value: Any) -> int:
    normalized = _normalize_header(value)
    if normalized in _TASK_HEADER_SCORES:
        return _TASK_HEADER_SCORES[normalized]
    if "problem" in normalized and "practice" not in normalized:
        return 100
    if normalized.endswith(" task") or normalized.startswith("task "):
        return 100
    return 0


def _fallback_task_index(headers: Sequence[str]) -> Optional[int]:
    normalized = [_normalize_header(header) for header in headers]
    detail_count = sum(header in _DETAIL_HEADERS for header in normalized)
    if detail_count == 0:
        return None
    for index, header in enumerate(normalized):
        if header in _PRIMARY_ENTITY_HEADERS:
            return index
    return None


def _candidate_task_index(headers: Sequence[str]) -> Tuple[Optional[int], int]:
    normalized = [_normalize_header(header) for header in headers]
    if "description" in normalized and any(header in _SEQUENCE_HEADERS for header in normalized):
        return normalized.index("description"), 105
    task_scores = [_header_score(header) for header in headers]
    task_score = max(task_scores, default=0)
    if task_score > 0:
        return task_scores.index(task_score), task_score
    fallback = _fallback_task_index(headers)
    return (fallback, 80 if fallback is not None else 0)


def _find_header_index(headers: Sequence[str], accepted: Iterable[str]) -> Optional[int]:
    accepted_set = set(accepted)
    for index, header in enumerate(headers):
        if _normalize_header(header) in accepted_set:
            return index
    return None


def _detect_header_row(rows: Sequence[Sequence[Any]]) -> Optional[Tuple[int, List[str], int]]:
    best: Optional[Tuple[int, List[str], int, int]] = None
    for row_index, row in enumerate(rows[:4]):
        headers = [_clean_text(cell) or f"Column {index + 1}" for index, cell in enumerate(row)]
        task_index, task_score = _candidate_task_index(headers)
        if task_index is None or task_score <= 0:
            continue
        if row_index > 0:
            preceding_rows = rows[:row_index]
            has_dense_prelude = any(
                sum(bool(_clean_text(cell)) for cell in preceding_row) > 1
                for preceding_row in preceding_rows
            )
            if has_dense_prelude:
                continue
        semantic_columns = sum(
            1
            for header in headers
            if _normalize_header(header)
            in (
                _GROUP_HEADERS
                | _SEQUENCE_HEADERS
                | _STATUS_HEADERS
                | _REVISION_HEADERS
                | _REVISIT_HEADERS
                | _DETAIL_HEADERS
            )
            or _header_score(header) > 0
        )
        if row_index > 0 and semantic_columns < 2:
            continue
        candidate = (row_index, headers, task_index, task_score + semantic_columns * 5)
        if best is None or candidate[3] > best[3]:
            best = candidate
    if best is None:
        return None
    return best[0], best[1], best[2]


def _resolve_table_rows(
    rows: Sequence[Sequence[Any]],
    previous: Optional[_TableSchema],
    *,
    document_title: str,
    section_label: str,
    page_number: int,
    allow_continuation: bool,
) -> Tuple[List[Sequence[Any]], Optional[_TableSchema], str]:
    """Resolve an explicit or conservatively inherited semantic table header."""
    materialized = [list(row) for row in rows]
    detected = _detect_header_row(materialized)
    if detected is not None:
        _, headers, _ = detected
        cleaned_document_title = _clean_text(document_title)
        effective_section = _clean_text(section_label) or "General"
        current_section = _normalize_header(effective_section)
        document_section = _normalize_header(cleaned_document_title)
        matching_previous_schema = bool(
            allow_continuation
            and previous
            and page_number == previous.page_number + 1
            and _normalize_header(cleaned_document_title)
            == _normalize_header(previous.document_title)
            and tuple(_normalize_header(value) for value in headers)
            == tuple(_normalize_header(value) for value in previous.headers)
        )
        if matching_previous_schema and current_section in {"", "general", document_section}:
            effective_section = previous.section_label
        schema = _TableSchema(
            headers=tuple(headers),
            document_title=cleaned_document_title,
            section_label=effective_section,
            page_number=page_number,
        )
        return materialized, schema, effective_section

    if not (allow_continuation and previous and page_number == previous.page_number + 1):
        return materialized, None, section_label
    if _normalize_header(document_title) != _normalize_header(previous.document_title):
        return materialized, None, section_label
    if not materialized or any(len(row) != len(previous.headers) for row in materialized):
        return materialized, None, section_label

    current_section = _normalize_header(section_label)
    previous_section = _normalize_header(previous.section_label)
    document_section = _normalize_header(document_title)
    if current_section not in {"", "general", previous_section, document_section}:
        return materialized, None, section_label

    effective_section = (
        previous.section_label
        if current_section in {"", "general", document_section}
        else section_label
    )
    continued_rows: List[Sequence[Any]] = [list(previous.headers), *materialized]
    schema = _TableSchema(
        headers=previous.headers,
        document_title=previous.document_title,
        section_label=effective_section,
        page_number=page_number,
    )
    return continued_rows, schema, effective_section


def _is_instruction_reference_table(headers: Sequence[str], task_index: int, section_label: str) -> bool:
    normalized_headers = {_normalize_header(header) for header in headers}
    task_header = _normalize_header(headers[task_index])
    return (
        task_header == "step"
        and "what to do" in normalized_headers
        and _REFERENCE_CONTEXT_RE.search(section_label or "") is not None
    )


def _line_metadata(page: Any) -> List[Dict[str, Any]]:
    try:
        raw_lines = page.extract_text_lines(layout=False, return_chars=True) or []
    except (AttributeError, TypeError):
        raw_lines = []

    lines: List[Dict[str, Any]] = []
    for raw in raw_lines:
        text = _clean_text(raw.get("text"))
        if not text:
            continue
        chars = raw.get("chars") or []
        sizes = [float(char.get("size") or 0) for char in chars]
        fonts = [str(char.get("fontname") or "").lower() for char in chars]
        lines.append(
            {
                "text": text,
                "x0": float(raw.get("x0") or 0),
                "top": float(raw.get("top") or 0),
                "bottom": float(raw.get("bottom") or raw.get("top") or 0),
                "size": max(sizes, default=0),
                "bold": any("bold" in font for font in fonts),
                "mono": any(token in font for font in fonts for token in ("mono", "courier", "consolas")),
            }
        )
    return lines


def _inside_bbox(line: Dict[str, Any], bbox: Sequence[float]) -> bool:
    midpoint = (line["top"] + line["bottom"]) / 2
    return float(bbox[1]) - 1 <= midpoint <= float(bbox[3]) + 1


def _recurring_margin_lines(page_lines: Sequence[Sequence[Dict[str, Any]]], page_heights: Sequence[float]) -> set[str]:
    occurrences: Dict[str, set[int]] = {}
    page_count = max(1, len(page_lines))
    for page_index, lines in enumerate(page_lines):
        height = page_heights[page_index]
        for line in lines:
            if line["top"] > 65 and line["bottom"] < height - 55:
                continue
            normalized = _margin_signature(line["text"])
            if len(normalized) < 4:
                continue
            occurrences.setdefault(normalized, set()).add(page_index)
    minimum_pages = 2 if page_count <= 3 else max(2, (page_count + 1) // 2)
    return {text for text, pages in occurrences.items() if len(pages) >= minimum_pages}


def _heading_level(size: float) -> int:
    if size >= 24:
        return 1
    if size >= 17:
        return 2
    if size >= 12:
        return 3
    return 4


def _is_heading(line: Dict[str, Any], body_size: float) -> bool:
    text = line["text"]
    if len(text) > 150:
        return False
    if line["size"] >= max(12, body_size * 1.35):
        return True
    return bool(line["bold"] and line["size"] >= max(10, body_size * 1.18))


def _nearest_heading(
    lines: Sequence[Dict[str, Any]],
    table_top: float,
    body_size: float,
    recurring: set[str],
) -> str:
    candidates = [
        line
        for line in lines
        if line["bottom"] <= table_top
        and _margin_signature(line["text"]) not in recurring
        and _is_heading(line, body_size)
    ]
    return candidates[-1]["text"] if candidates else "General"


def _normalize_rotated_label(page: Any, cell_bbox: Any, value: Any) -> str:
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return ""
    rotated = False
    if cell_bbox:
        try:
            chars = page.crop(cell_bbox).chars
            rotated = bool(chars) and sum(bool(char.get("upright", True)) for char in chars) < len(chars) / 2
        except Exception:
            rotated = False
    if not rotated:
        return _clean_text(" ".join(lines))
    restored = " ".join(line[::-1].strip() for line in reversed(lines))
    restored = re.sub(r"^DP (.+) on$", r"DP on \1", restored, flags=re.IGNORECASE)
    restored = re.sub(r"^DP on (.+) Sub-$", r"DP on Sub-\1", restored, flags=re.IGNORECASE)
    if restored.lower() == "s asked) advance problems(les":
        restored = "Advanced Problems (Less asked)"
    return _clean_text(restored)


def _table_cell_font_size(page: Any, table: Any, row_index: int, column_index: int) -> float:
    """Return the largest font in a physical table cell when layout data exists."""
    try:
        cell_bbox = table.rows[row_index].cells[column_index]
        if not cell_bbox:
            return 0.0
        words = page.crop(cell_bbox).extract_words(extra_attrs=["size"]) or []
        return max((float(word.get("size") or 0) for word in words), default=0.0)
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0.0


def _is_repeated_table_header(values: Sequence[str], headers: Sequence[str], task_index: int) -> bool:
    """Recognize headers repeated in the middle of a long, page-split table."""
    if task_index >= len(values) or task_index >= len(headers):
        return False
    if _normalize_header(values[task_index]) != _normalize_header(headers[task_index]):
        return False

    matching_cells = sum(
        1
        for index, value in enumerate(values)
        if index < len(headers)
        and _normalize_header(value)
        and _normalize_header(value) == _normalize_header(headers[index])
    )
    return matching_cells >= 2


def _is_visual_group_heading(title: str, font_size: float, body_font_size: float) -> bool:
    """Distinguish a styled section row from an ordinary task-only row."""
    if font_size > 0:
        minimum = max(12.0, body_font_size * 1.25 if body_font_size > 0 else 12.0)
        return font_size >= minimum
    return _STAGE_HEADING_RE.match(title) is not None


def _merge_group_label(previous: str, candidate: str, *, page_continuation: bool) -> str:
    """Prefer complete labels and repair rotated labels split at a page boundary."""
    previous = _clean_text(previous)
    candidate = _clean_text(candidate)
    if not previous:
        return candidate
    if not candidate:
        return previous

    previous_key = _normalize_header(previous)
    candidate_key = _normalize_header(candidate)
    if previous_key == candidate_key:
        return previous if len(previous) >= len(candidate) else candidate
    if previous_key.endswith(candidate_key) or previous_key.startswith(candidate_key):
        return previous
    if candidate_key.endswith(previous_key) or candidate_key.startswith(previous_key):
        return candidate

    # Vertical text is sometimes divided by the physical page boundary. The
    # bottom fragment starts with a lowercase continuation ("dow", "s", or
    # "n Strings") and the next page contains its prefix ("Sliding Win",
    # "FAQ", or "DP o"). Joining only at an adjacent-page boundary keeps this
    # conservative for legitimate short group names.
    if page_continuation and previous[:1].islower():
        return _clean_text(f"{candidate}{previous}")
    return candidate


def _block(block_type: str, data: Dict[str, Any], position: int) -> Dict[str, Any]:
    return {"type": block_type, "data": data, "position": position}


def _sequence_title(header: str, value: str, title: str) -> str:
    normalized = _normalize_header(header)
    if not value:
        return title
    if normalized == "day":
        return f"Day {value}: {title}"
    if normalized == "week":
        return f"Week {value}: {title}"
    if normalized == "month":
        return f"Month {value}: {title}"
    if normalized in {"window", "period", "timeline", "range"}:
        return f"{value}: {title}"
    return f"{value}. {title}"


def _status_sequence_title(value: str, title: str) -> str:
    match = re.fullmatch(
        r"(day|week|month|sprint|phase|stage|step)\s+(.+)",
        _clean_text(value),
        flags=re.IGNORECASE,
    )
    if match is not None:
        return _sequence_title(match.group(1), match.group(2), title)
    if re.fullmatch(r"\d{1,4}", _clean_text(value)):
        return f"{_clean_text(value)}. {title}"
    return title


def _table_tasks(
    page: Any,
    table: Any,
    rows: Sequence[Sequence[Any]],
    section_label: str,
    page_number: int,
    task_context: Optional[_TableTaskContext] = None,
) -> List[Dict[str, Any]]:
    detected = _detect_header_row(rows)
    if detected is None:
        return []

    header_row, headers, task_index = detected
    sequence_index = _find_header_index(headers, _SEQUENCE_HEADERS)
    if sequence_index == task_index:
        sequence_index = None
    status_index = _find_header_index(headers, _STATUS_HEADERS)
    group_index = _find_header_index(headers, _GROUP_HEADERS)
    if group_index == task_index:
        group_index = None

    if _is_instruction_reference_table(headers, task_index, section_label):
        return []

    normalized_task_header = _normalize_header(headers[task_index])
    if normalized_task_header == "habit":
        task_kind = "recurring_habit"
    elif normalized_task_header in _PRIMARY_ENTITY_HEADERS:
        task_kind = "stage"
    elif status_index is not None:
        task_kind = "checklist"
    else:
        task_kind = "task"

    continued_from_previous_page = bool(
        task_context is not None and task_context.page_number == page_number - 1
    )
    if task_context is not None:
        task_context.renamed_group_from = ""
        task_context.renamed_group_to = ""
    current_group = (
        task_context.current_group
        if task_context is not None and task_context.current_group
        else section_label or "General"
    )
    tasks: List[Dict[str, Any]] = []
    try:
        physical_row_count = len(table.rows)
    except (AttributeError, TypeError):
        physical_row_count = len(rows)
    synthetic_header = physical_row_count == len(rows) - 1

    task_font_sizes: List[float] = []
    for row_index in range(header_row + 1, len(rows)):
        physical_row_index = row_index - 1 if synthetic_header else row_index
        size = _table_cell_font_size(page, table, physical_row_index, task_index)
        if size > 0:
            task_font_sizes.append(size)
    body_font_size = median(task_font_sizes) if task_font_sizes else 0.0
    first_group_on_page = True

    for row_index in range(header_row + 1, len(rows)):
        physical_row_index = row_index - 1 if synthetic_header else row_index
        row = list(rows[row_index])
        while len(row) < len(headers):
            row.append("")
        values = [_clean_multiline(value) for value in row]
        title = _clean_text(values[task_index] if task_index < len(values) else "")
        if not title:
            continue

        if _is_repeated_table_header(values, headers, task_index):
            continue

        nonempty_indexes = [index for index, value in enumerate(values) if _clean_text(value)]
        if (
            len(headers) > 1
            and len(nonempty_indexes) == 1
            and nonempty_indexes[0] == task_index
            and len(title) <= 140
            and _is_visual_group_heading(
                title,
                _table_cell_font_size(page, table, physical_row_index, task_index),
                body_font_size,
            )
        ):
            current_group = title
            first_group_on_page = False
            continue

        if group_index is not None and group_index < len(values):
            group_cell = None
            try:
                group_cell = table.rows[physical_row_index].cells[group_index]
            except (AttributeError, IndexError):
                group_cell = None
            group = _normalize_rotated_label(page, group_cell, row[group_index])
            if group and _normalize_header(group) not in _GROUP_HEADERS:
                previous_group = current_group
                current_group = _merge_group_label(
                    previous_group,
                    group,
                    page_continuation=continued_from_previous_page and first_group_on_page,
                )
                if (
                    task_context is not None
                    and continued_from_previous_page
                    and first_group_on_page
                    and _normalize_header(current_group) != _normalize_header(previous_group)
                    and previous_group[:1].islower()
                ):
                    task_context.renamed_group_from = previous_group
                    task_context.renamed_group_to = current_group
                first_group_on_page = False

        sequence = _clean_text(values[sequence_index]) if sequence_index is not None else ""
        if sequence_index is not None:
            title = _sequence_title(headers[sequence_index], sequence, title)

        completed = False
        if status_index is not None:
            checkbox, checkbox_done, status_detail = _parse_checkbox(values[status_index])
            completed = checkbox_done if checkbox else _is_truthy(values[status_index])
            if checkbox and sequence_index is None and status_detail:
                title = _status_sequence_title(status_detail, title)

        blocks: List[Dict[str, Any]] = []
        reserved = {task_index, sequence_index, group_index, status_index}
        for column_index, value in enumerate(values):
            if column_index in reserved or not _clean_text(value):
                continue
            label = headers[column_index] if column_index < len(headers) else f"Column {column_index + 1}"
            normalized_label = _normalize_header(label)
            if normalized_label in _REVISION_HEADERS:
                revision_count = _positive_integer(value)
                if revision_count is not None:
                    blocks.append(
                        _block(
                            "counter",
                            {"label": "Revision", "value": revision_count, "step": 1},
                            len(blocks),
                        )
                    )
                continue
            if normalized_label in _REVISIT_HEADERS:
                if _is_truthy(value):
                    blocks.append(
                        _block(
                            "bookmark",
                            {"label": "Revisit", "bookmarked": True},
                            len(blocks),
                        )
                    )
                continue
            if normalized_label in _BOOKMARK_HEADERS and re.match(r"^https?://", _clean_text(value), re.IGNORECASE):
                blocks.append(
                    _block(
                        "bookmark",
                        {"label": label, "url": _clean_text(value), "bookmarked": True},
                        len(blocks),
                    )
                )
                continue
            blocks.append(
                _block(
                    "note",
                    {"label": label, "text": _clean_multiline(value)},
                    len(blocks),
                )
            )

        tasks.append(
            {
                "title": title,
                "timeframe": current_group or "General",
                "is_done": completed,
                "granularity": "section",
                "properties": (
                    {"Type": _kind_label(task_kind)}
                    if task_kind != "task" or normalized_task_header != "concept"
                    else {}
                ),
                "blocks": blocks,
                "source": {
                    "page": page_number,
                    "top": float(table.bbox[1]) + physical_row_index / 1000,
                    "table": True,
                    "row": physical_row_index + 1,
                    "kind": task_kind,
                },
            }
        )

    if task_context is not None:
        task_context.current_group = current_group
        task_context.page_number = page_number
    return tasks


def _table_outline_elements(rows: Sequence[Sequence[Any]], page_number: int, top: float) -> List[Dict[str, Any]]:
    cleaned_rows = [[_clean_multiline(cell) for cell in row] for row in rows]
    cleaned_rows = [row for row in cleaned_rows if any(_clean_text(cell) for cell in row)]
    if not cleaned_rows:
        return []

    detected = _detect_header_row(cleaned_rows)
    if detected is not None:
        header_row, headers, _ = detected
        return [
            {
                "type": "table",
                "page": page_number,
                "top": top,
                "columns": headers,
                "rows": [row for row in cleaned_rows[header_row + 1 :]],
            }
        ]

    elements: List[Dict[str, Any]] = []
    for offset, row in enumerate(cleaned_rows):
        cells = [cell for cell in row if _clean_text(cell)]
        if len(cells) == 1 and "\n" in cells[0]:
            lines = cells[0].splitlines()
            first = lines[0].strip()
            code_like = bool(re.match(r"^(?:for |while |if |def |class |[A-Za-z_]\w*\s*=)", first))
            if code_like:
                elements.append(
                    {"type": "code", "page": page_number, "top": top + offset / 1000, "text": cells[0]}
                )
            else:
                elements.append(
                    {
                        "type": "callout",
                        "page": page_number,
                        "top": top + offset / 1000,
                        "title": first,
                        "text": "\n".join(lines[1:]).strip(),
                    }
                )
        else:
            elements.append(
                {
                    "type": "table",
                    "page": page_number,
                    "top": top + offset / 1000,
                    "columns": [],
                    "rows": [row],
                }
            )
    return elements


def _is_document_heading(line: Dict[str, Any]) -> bool:
    text = line["text"]
    if _STAGE_HEADING_RE.match(text):
        return False
    if line["size"] < 17 or line["top"] > 125:
        return False
    return bool(
        re.match(r"^\s*\d{1,3}[.)]\s+\S", text)
        or "roadmap" in _normalize_header(text)
        or line["size"] >= 19
    )


def _looks_like_task_document(title: str) -> bool:
    return bool(_clean_text(title) and _NON_TASK_DOCUMENT_RE.search(title) is None)


def _is_major_heading(line: Dict[str, Any], body_size: float) -> bool:
    if len(line["text"]) > 150:
        return False
    minimum = max(11.5, body_size * 1.12)
    return line["size"] >= minimum and (line["bold"] or line["size"] >= 14)


def _is_subheading(line: Dict[str, Any], body_size: float) -> bool:
    return bool(
        line["bold"]
        and line["size"] >= max(8, body_size * 0.82)
        and len(line["text"]) <= 90
    )


def _is_reference_page(lines: Sequence[Dict[str, Any]]) -> bool:
    text = " ".join(line["text"] for line in lines[:12])
    return _REFERENCE_PAGE_RE.search(text) is not None


def _semantic_task_kind(subsection: str, marker: str) -> str:
    normalized = _normalize_header(subsection)
    if "kpi" in normalized:
        return "kpi"
    if "evidence" in normalized or "proof" in normalized:
        return "evidence"
    if "practice" in normalized or "problem" in normalized:
        return "practice"
    if any(token in normalized for token in ("learn", "concept", "scope", "topic")):
        return "learning"
    return "checklist" if marker == "checkbox" else "task"


def _trackable_label_kind(label: str) -> str:
    normalized = _normalize_header(label)
    if "outcome" in normalized:
        return "outcome"
    if "capstone" in normalized:
        return "project"
    if "deliverable" in normalized or "artifact" in normalized or "output" in normalized:
        return "deliverable"
    return "milestone"


def _kind_label(kind: str) -> str:
    return {
        "kpi": "KPI",
        "project": "Project",
    }.get(kind, kind.replace("_", " ").title())


def _stage_metadata(value: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for segment in re.split(r"\s*\|\s*", value):
        match = _STAGE_METADATA_RE.fullmatch(segment.strip())
        if match is not None:
            label = _clean_text(match.group("label")).title()
            if label.lower().startswith("require"):
                label = "Requires"
            elif label.lower().startswith("prerequisite"):
                label = "Prerequisite"
            elif label.lower().startswith("unlock"):
                label = "Unlocks"
            elif label.lower().startswith("entry"):
                label = "Entry gate"
            metadata[label] = _clean_text(match.group("value"))
            continue

        schedule = _SCHEDULE_METADATA_RE.fullmatch(segment.strip())
        if schedule is not None:
            metadata["Schedule"] = _clean_text(segment)
    return metadata


def _page_list_tasks(
    lines: Sequence[Dict[str, Any]],
    table_bboxes: Sequence[Sequence[float]],
    page_number: int,
    body_size: float,
    recurring: set[str],
    context: _ListTaskContext,
) -> List[Dict[str, Any]]:
    """Extract explicit list actions while carrying stage context across pages."""
    if _is_reference_page(lines):
        context.stage = ""
        context.subsection = ""
        context.pending_outcome = False
        context.stage_metadata = {}
        return []

    tasks: List[Dict[str, Any]] = []
    last_task: Optional[Dict[str, Any]] = None
    last_x0 = 0.0
    last_bottom = 0.0
    aligned_continuation = False

    def add_task(
        title: str,
        line: Dict[str, Any],
        *,
        kind: str,
        marker: str,
        is_done: bool = False,
        order: Optional[int] = None,
        include_subsection: bool = True,
    ) -> Dict[str, Any]:
        properties: Dict[str, Any] = {"Type": _kind_label(kind)}
        properties.update(context.stage_metadata)
        if include_subsection and context.subsection:
            properties["Section"] = context.subsection
        if order is not None:
            properties["Order"] = order
        if kind == "milestone" and _normalize_header(title).startswith("exit criterion"):
            _, _, criterion = title.partition(":")
            if criterion.strip():
                properties["Exit criterion"] = _clean_text(criterion)
        task = {
            "title": _clean_text(title),
            "timeframe": context.stage,
            "is_done": is_done,
            "granularity": "section",
            "properties": properties,
            "blocks": [],
            "source": {
                "page": page_number,
                "top": line["top"] + (order or 0) / 1000,
                "table": False,
                "marker": marker,
                "kind": kind,
                "document": context.document_title,
            },
        }
        tasks.append(task)
        return task

    for line in lines:
        text = line["text"]
        if _margin_signature(text) in recurring:
            continue
        if any(_inside_bbox(line, bbox) for bbox in table_bboxes):
            continue

        if _is_document_heading(line):
            context.document_title = text
            context.document_confirmed = _looks_like_task_document(text)
            context.stage = ""
            context.subsection = ""
            context.pending_outcome = False
            context.stage_metadata = {}
            last_task = None
            continue

        metadata_labels = _DOCUMENT_METADATA_RE.findall(text)
        if len(metadata_labels) >= 2:
            context.document_confirmed = True

        if _is_major_heading(line, body_size):
            if _NON_TASK_CONTAINER_RE.match(text):
                context.stage = ""
            elif _STAGE_HEADING_RE.match(text) or context.document_confirmed:
                context.stage = text
            else:
                context.stage = ""
            context.subsection = ""
            context.pending_outcome = bool(context.stage and _OUTCOME_CONTAINER_RE.match(text))
            context.stage_metadata = {}
            last_task = None
            continue


        if _NON_TASK_CONTAINER_RE.match(text) and _is_subheading(line, body_size):
            context.stage = ""
            context.subsection = ""
            context.pending_outcome = False
            context.stage_metadata = {}
            last_task = None
            continue

        if context.stage and _is_subheading(line, body_size):
            context.subsection = text
            context.pending_outcome = False
            last_task = None
            continue

        metadata = _stage_metadata(text) if context.stage else {}
        if metadata:
            context.stage_metadata.update(metadata)
            last_task = None
            continue

        labeled = _TRACKABLE_LABEL_RE.match(text)
        if labeled is not None and context.stage:
            kind = _trackable_label_kind(labeled.group("label"))
            last_task = add_task(
                labeled.group("title"),
                line,
                kind=kind,
                marker="labeled",
                include_subsection=False,
            )
            last_x0 = line.get("x0", 0.0)
            last_bottom = line["bottom"]
            aligned_continuation = True
            context.pending_outcome = False
            continue

        if context.pending_outcome and context.stage and _parse_list_item(text) is None:
            last_task = add_task(
                text,
                line,
                kind="milestone",
                marker="outcome",
                include_subsection=False,
            )
            last_x0 = line.get("x0", 0.0)
            last_bottom = line["bottom"]
            aligned_continuation = True
            context.pending_outcome = False
            continue

        parsed = _parse_list_item(text)
        if parsed is not None and context.stage:
            title, is_done, marker = parsed
            kind = _semantic_task_kind(context.subsection, marker)
            ordered_titles = [title]
            if _ORDER_CONTAINER_RE.search(context.stage):
                split_titles = [part for part in _ARROW_SPLIT_RE.split(title) if _clean_text(part)]
                if len(split_titles) > 1:
                    ordered_titles = split_titles
                    kind = "ordered_task"
            for order, ordered_title in enumerate(ordered_titles, start=1):
                last_task = add_task(
                    ordered_title,
                    line,
                    kind=kind,
                    marker=marker,
                    is_done=is_done,
                    order=order if len(ordered_titles) > 1 else None,
                )
            last_x0 = line.get("x0", 0.0)
            last_bottom = line["bottom"]
            aligned_continuation = False
            continue

        continuation = bool(
            last_task is not None
            and line.get("x0", 0.0) >= last_x0 + (-1 if aligned_continuation else 4)
            and line["top"] - last_bottom <= max(8, body_size * 1.15)
            and text[:1].islower()
            and re.match(r"^[A-Za-z][A-Za-z /+-]{1,35}:", text) is None
        )
        if continuation:
            last_task["title"] = _clean_text(f'{last_task["title"]} {text}')
            last_bottom = line["bottom"]
        else:
            last_task = None

    return tasks


def _add_multi_document_context(tasks: List[Dict[str, Any]]) -> None:
    document_titles = {
        _clean_text(task.get("source", {}).get("document"))
        for task in tasks
        if _clean_text(task.get("source", {}).get("document"))
    }
    if len(document_titles) <= 1:
        return
    for task in tasks:
        document_title = _clean_text(task.get("source", {}).get("document"))
        if document_title:
            task.setdefault("properties", {})["Roadmap"] = document_title


def _page_text_elements(
    lines: Sequence[Dict[str, Any]],
    table_bboxes: Sequence[Sequence[float]],
    page_number: int,
    body_size: float,
    recurring: set[str],
) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []
    paragraph_lines: List[str] = []
    paragraph_top = 0.0
    list_items: List[str] = []
    list_top = 0.0

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            elements.append(
                {
                    "type": "paragraph",
                    "page": page_number,
                    "top": paragraph_top,
                    "text": " ".join(paragraph_lines),
                }
            )
            paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            elements.append(
                {"type": "list", "page": page_number, "top": list_top, "items": list_items}
            )
            list_items = []

    previous_bottom: Optional[float] = None
    for line in lines:
        if _margin_signature(line["text"]) in recurring:
            continue
        if any(_inside_bbox(line, bbox) for bbox in table_bboxes):
            continue
        text = line["text"]
        if _is_heading(line, body_size):
            flush_paragraph()
            flush_list()
            elements.append(
                {
                    "type": "heading",
                    "page": page_number,
                    "top": line["top"],
                    "level": _heading_level(line["size"]),
                    "text": text,
                }
            )
        elif _BULLET_RE.match(text):
            flush_paragraph()
            if not list_items:
                list_top = line["top"]
            item = _BULLET_RE.sub("", text).strip()
            if item:
                list_items.append(item)
        else:
            flush_list()
            gap = line["top"] - previous_bottom if previous_bottom is not None else 0
            if paragraph_lines and gap > max(8, body_size * 1.1):
                flush_paragraph()
            if not paragraph_lines:
                paragraph_top = line["top"]
            paragraph_lines.append(text)
        previous_bottom = line["bottom"]
    flush_paragraph()
    flush_list()
    return elements


def _add_section_paths(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _enforce_pdf_limit("document outline element", len(elements), MAX_OUTLINE_ELEMENTS)
    stack: List[Tuple[int, str]] = []
    result: List[Dict[str, Any]] = []
    for element in sorted(elements, key=lambda item: (int(item.get("page", 0)), float(item.get("top", 0)))):
        element = dict(element)
        if element["type"] == "heading":
            level = int(element.get("level", 4))
            stack = [(existing_level, title) for existing_level, title in stack if existing_level < level]
            stack.append((level, element["text"]))
            element["section_path"] = [title for _, title in stack[:-1]]
        else:
            element["section_path"] = [title for _, title in stack]
        element.pop("top", None)
        result.append(element)
    return result


def parse_pdf_document(content: bytes) -> PdfImportResult:
    """Parse a text PDF into tasks plus a loss-minimized document outline."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for layout-aware PDF import") from exc

    try:
        document = pdfplumber.open(BytesIO(content))
    except Exception as exc:
        raise ValueError("Could not open this PDF") from exc

    with document:
        pages = list(document.pages)
        _enforce_pdf_limit("page count", len(pages), MAX_PDF_PAGES)

        page_lines: List[List[Dict[str, Any]]] = []
        page_heights: List[float] = []
        text_line_count = 0
        for page in pages:
            lines = _line_metadata(page)
            text_line_count += len(lines)
            _enforce_pdf_limit("extracted text line", text_line_count, MAX_PDF_TEXT_LINES)
            page_lines.append(lines)
            page_heights.append(float(page.height))

        recurring = _recurring_margin_lines(page_lines, page_heights)
        tasks: List[Dict[str, Any]] = []
        outline_elements: List[Dict[str, Any]] = []
        page_texts: List[str] = []
        list_context = _ListTaskContext()
        table_row_count = 0
        table_schema: Optional[_TableSchema] = None
        table_task_context = _TableTaskContext()

        for page_number, (page, lines) in enumerate(zip(pages, page_lines), start=1):
            clean_page_text = "\n".join(
                line["text"]
                for line in lines
                if _margin_signature(line["text"]) not in recurring
            )
            if clean_page_text.strip():
                page_texts.append(clean_page_text.strip())

            sizes = [line["size"] for line in lines if line["size"] > 0]
            body_size = median(sizes) if sizes else 10.0
            tables = page.find_tables() or []
            bboxes = [table.bbox for table in tables]
            outline_elements.extend(_page_text_elements(lines, bboxes, page_number, body_size, recurring))
            _enforce_pdf_limit(
                "document outline element",
                len(outline_elements),
                MAX_OUTLINE_ELEMENTS,
            )
            previous_document_title = list_context.document_title
            tasks.extend(
                _page_list_tasks(
                    lines,
                    bboxes,
                    page_number,
                    body_size,
                    recurring,
                    list_context,
                )
            )
            _enforce_pdf_limit("semantic task", len(tasks), MAX_PDF_TASKS)

            reference_page = _is_reference_page(lines)
            page_document_heading = next(
                (line["text"] for line in lines if _is_document_heading(line)),
                "",
            )
            document_changed = bool(
                page_document_heading
                and _normalize_header(previous_document_title)
                != _normalize_header(list_context.document_title)
            )
            if reference_page or document_changed:
                table_schema = None
                table_task_context = _TableTaskContext()

            for table in tables:
                rows = table.extract() or []
                if not rows:
                    table_schema = None
                    table_task_context = _TableTaskContext()
                    continue
                table_row_count += len(rows)
                _enforce_pdf_limit("table row", table_row_count, MAX_PDF_TABLE_ROWS)
                section = _nearest_heading(lines, float(table.bbox[1]), body_size, recurring)
                if reference_page:
                    effective_rows = [list(row) for row in rows]
                    effective_section = section
                    table_schema = None
                    table_task_context = _TableTaskContext()
                else:
                    previous_schema = table_schema
                    effective_rows, table_schema, effective_section = _resolve_table_rows(
                        rows,
                        table_schema,
                        document_title=list_context.document_title,
                        section_label=section,
                        page_number=page_number,
                        allow_continuation=not document_changed,
                    )
                    compatible_continuation = bool(
                        previous_schema is not None
                        and table_schema is not None
                        and page_number == previous_schema.page_number + 1
                        and tuple(_normalize_header(value) for value in table_schema.headers)
                        == tuple(_normalize_header(value) for value in previous_schema.headers)
                        and _normalize_header(table_schema.document_title)
                        == _normalize_header(previous_schema.document_title)
                        and _normalize_header(effective_section)
                        == _normalize_header(previous_schema.section_label)
                    )
                    if not compatible_continuation:
                        table_task_context = _TableTaskContext()
                if not reference_page:
                    table_tasks = _table_tasks(
                        page,
                        table,
                        effective_rows,
                        effective_section,
                        page_number,
                        table_task_context,
                    )
                    if table_task_context.renamed_group_from and table_task_context.renamed_group_to:
                        for existing_task in reversed(tasks):
                            source = existing_task.get("source", {})
                            source_page = int(source.get("page", 0))
                            if source_page < page_number - 1:
                                break
                            if (
                                source_page == page_number - 1
                                and source.get("table") is True
                                and _normalize_header(existing_task.get("timeframe"))
                                == _normalize_header(table_task_context.renamed_group_from)
                            ):
                                existing_task["timeframe"] = table_task_context.renamed_group_to
                    for task in table_tasks:
                        task.setdefault("source", {})["document"] = list_context.document_title
                    tasks.extend(table_tasks)
                    _enforce_pdf_limit("semantic task", len(tasks), MAX_PDF_TASKS)
                outline_elements.extend(
                    _table_outline_elements(effective_rows, page_number, float(table.bbox[1]))
                )
                _enforce_pdf_limit(
                    "document outline element",
                    len(outline_elements),
                    MAX_OUTLINE_ELEMENTS,
                )

        text = "\n\n".join(page_texts).strip()
        tasks.sort(
            key=lambda task: (
                int(task.get("source", {}).get("page", 0)),
                float(task.get("source", {}).get("top", 0)),
                int(task.get("source", {}).get("row", 0)),
            )
        )
        _add_multi_document_context(tasks)
        return PdfImportResult(
            text=text,
            tasks=tasks,
            outline=_add_section_paths(outline_elements),
            page_count=len(pages),
        )
