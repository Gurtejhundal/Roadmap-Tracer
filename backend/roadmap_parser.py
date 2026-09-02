import json
import math
import re
from typing import Any, Dict, List, Optional


BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[\.)]\s+|\[[ xXvV\u2713\u2714]\]\s+|"
    r"[\u2610\u2611\u2612\u2022\u25e6\u2023\u2043\u2219\u2192]\s*)"
)
CHECKED_TASK_RE = re.compile(
    r"^\s*(?:\[[xXvV\u2713\u2714]\]|[\u2611\u2612])(?:\s+|$)"
)
FENCE_RE = re.compile(r"^\s*(?:`{3,}|~{3,})")

HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"(?:(?:phase|month|week|day|module|unit|section|part|step|sprint|milestone|quarter|q)\s*[\divx]*"
    r"|learning path|foundation|foundations|advanced|capstone|project|projects|assessment|review|final full mock"
    r"|core strategy|version\s*[\d.]+\s*upgrades|target profile by month\s*\d+|non-negotiable operating rules"
    r"|weekly time budget|milestone gates|roadmap overview|final checklist|final priority list"
    r"|final coding revision set|mock mcqs|coding question\s*\d*)\b"
    r"[\s:.-]*(.*)$",
    re.IGNORECASE,
)

GRANULARITY_RE = re.compile(
    r"\b(month|week|day|hour|phase|module|unit|section|part|step|sprint|milestone|quarter|q)\b",
    re.IGNORECASE,
)

DAY_RE = re.compile(r"^(day\s*\d+\b.*)$", re.IGNORECASE)
TIME_RANGE_RE = re.compile(
    r"^\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-\u2013\u2014]\s*"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\b.*)?$",
    re.IGNORECASE,
)
NOTE_SECTION_RE = re.compile(
    r"^(?:.+\s+revision notes?|.+\s+mcq points?|coding practice(?:\s+for .+)?|practice(?:\s+.+)?|"
    r"requirements|queries|cover these topics(?: properly)?|advantages|disadvantages|types|examples|commands|"
    r"uses|steps|features|important points|mock mcqs|what not to do|the exact codetantra method|"
    r"final checklist for 30/30|final priority list)$",
    re.IGNORECASE,
)
QUESTION_ANSWER_RE = re.compile(r"^(.+\?)\s+(.+)$")
NUMBERED_HEADING_RE = re.compile(r"^\d{1,2}\.\s+[A-Z][A-Za-z0-9 ,'+/&().:-]{3,}$")
PERCENT_RE = re.compile(r"^\d+\s*%")
SQL_STATEMENT_RE = re.compile(
    r"^(select|insert|update|delete|create|alter|drop|truncate|grant|revoke|commit|rollback|savepoint|explain)\b",
    re.IGNORECASE,
)
ACRONYM_RE = re.compile(r"^[A-Z0-9]{2,8}$")
PAGE_FOOTER_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Normalize common roadmap text artifacts without changing user wording."""
    if not text:
        return ""

    replacements = {
        "\r\n": "\n",
        "\r": "\n",
        "\u00a0": " ",
        "\ufeff": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.strip()


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^`{3,}.*$", "", line).strip()
    line = re.sub(r"^\|?[-:\s|]{3,}\|?$", "", line).strip()
    line = line.replace("\u2013", "-").replace("\u2014", "-")
    return line


def _is_heading(line: str, next_line: Optional[str] = None) -> bool:
    if not line:
        return False
    if NUMBERED_HEADING_RE.match(line):
        return True
    if BULLET_PREFIX_RE.match(line):
        return False
    if TIME_RANGE_RE.match(line):
        return True
    if PERCENT_RE.match(line) or SQL_STATEMENT_RE.match(line) or ACRONYM_RE.match(line):
        return False
    if NOTE_SECTION_RE.match(line):
        return True
    if line.endswith(":"):
        return True
    if re.match(r"^\s*#{1,6}\s+\S+", line):
        return True
    if HEADING_RE.match(line):
        return True
    if next_line and BULLET_PREFIX_RE.match(next_line) and len(line) <= 100:
        return True

    return False


def _clean_heading(line: str) -> str:
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
    cleaned = cleaned.rstrip(":").strip()
    return cleaned or "General"


def _granularity(label: str) -> str:
    match = GRANULARITY_RE.search(label or "")
    if not match:
        return "section"
    value = match.group(1).lower()
    return "quarter" if value == "q" else value


def _clean_task(line: str) -> str:
    cleaned = BULLET_PREFIX_RE.sub("", line).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _prepare_lines(text: str) -> List[str]:
    lines: List[str] = []
    inside_fence = False
    for raw_line in text.split("\n"):
        if FENCE_RE.match(raw_line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        cleaned = _clean_line(raw_line)
        if cleaned:
            lines.append(cleaned)
    if not lines:
        return []

    document_title = lines[0]
    prepared = []
    for index, line in enumerate(lines):
        if PAGE_FOOTER_RE.match(line):
            continue
        if index > 0 and line == document_title:
            continue
        prepared.append(line)
    return prepared


def _looks_like_task(line: str, has_context: bool) -> bool:
    if BULLET_PREFIX_RE.match(line):
        return True
    if QUESTION_ANSWER_RE.match(line):
        return True
    if has_context and len(line) <= 180 and not line.endswith(":"):
        return True
    return False


def _compose_timeframe(day_label: str, heading: str) -> str:
    heading = _clean_heading(heading)
    if day_label and heading and not heading.lower().startswith(day_label.lower()):
        return f"{day_label} - {heading}"
    return heading or day_label or "General"


def _append_to_timeframe(base_label: str, heading: str) -> str:
    heading = _clean_heading(heading)
    if base_label and heading and heading.lower() not in base_label.lower():
        return f"{base_label} - {heading}"
    return heading or base_label or "General"


def _json_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "x",
        "done",
        "complete",
        "completed",
        "checked",
    }


def _json_blocks(value: Any) -> List[Dict[str, object]]:
    if not isinstance(value, list):
        return []
    blocks: List[Dict[str, object]] = []
    for index, block in enumerate(value):
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        data = block.get("data")
        if not block_type or not isinstance(data, dict):
            continue
        position = block.get("position")
        blocks.append(
            {
                "type": block_type,
                "data": data,
                "position": position if isinstance(position, int) and position >= 0 else index,
            }
        )
    return blocks


DOCUMENT_ELEMENT_TYPES = {"heading", "paragraph", "list", "callout", "code", "table"}
_INVALID_DISPLAY_VALUE = object()


def _display_value(value: Any):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(value)
    return _INVALID_DISPLAY_VALUE


def _bounded_integer(value: Any, minimum: int, maximum: int) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return max(minimum, min(maximum, parsed))


def _document_context(element: Dict[str, Any]) -> Dict[str, object]:
    context: Dict[str, object] = {}
    page = _bounded_integer(element.get("page"), 0, 1_000_000)
    if page is not None:
        context["page"] = page

    section_path = element.get("section_path")
    if isinstance(section_path, list):
        safe_path = []
        for value in section_path:
            display = _display_value(value)
            if display is not _INVALID_DISPLAY_VALUE and display:
                safe_path.append(display)
        context["section_path"] = safe_path
    return context


def _sanitize_document_element(element: Dict[str, Any]) -> Optional[Dict[str, object]]:
    raw_type = element.get("type")
    element_type = raw_type if isinstance(raw_type, str) and raw_type in DOCUMENT_ELEMENT_TYPES else "paragraph"
    sanitized: Dict[str, object] = {"type": element_type, **_document_context(element)}

    if element_type in {"heading", "paragraph", "code"}:
        text = _display_value(element.get("text"))
        if text is _INVALID_DISPLAY_VALUE or not text:
            return None
        sanitized["text"] = text
        if element_type == "heading":
            sanitized["level"] = _bounded_integer(element.get("level"), 1, 6) or 3
        return sanitized

    if element_type == "callout":
        title = _display_value(element.get("title"))
        text = _display_value(element.get("text"))
        if title is not _INVALID_DISPLAY_VALUE and title:
            sanitized["title"] = title
        if text is not _INVALID_DISPLAY_VALUE and text:
            sanitized["text"] = text
        return sanitized if "title" in sanitized or "text" in sanitized else None

    if element_type == "list":
        raw_items = element.get("items")
        if not isinstance(raw_items, list):
            return None
        items = []
        for value in raw_items:
            display = _display_value(value)
            if display is not _INVALID_DISPLAY_VALUE and display:
                items.append(display)
        if not items:
            return None
        sanitized["items"] = items
        return sanitized

    raw_columns = element.get("columns")
    if raw_columns is None:
        raw_columns = element.get("headers")
    columns = []
    if isinstance(raw_columns, list):
        for value in raw_columns:
            display = _display_value(value)
            columns.append("" if display is _INVALID_DISPLAY_VALUE else display)

    rows = []
    raw_rows = element.get("rows")
    if isinstance(raw_rows, list):
        for raw_row in raw_rows:
            values = raw_row if isinstance(raw_row, list) else [raw_row]
            row = []
            for value in values:
                display = _display_value(value)
                row.append("" if display is _INVALID_DISPLAY_VALUE else display)
            if any(row):
                rows.append(row)
    if not columns and not rows:
        return None
    sanitized["columns"] = columns
    sanitized["rows"] = rows
    return sanitized


def sanitize_document_elements(elements: Any) -> List[Dict[str, object]]:
    if not isinstance(elements, list):
        return []
    sanitized = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        safe_element = _sanitize_document_element(element)
        if safe_element is not None:
            sanitized.append(safe_element)
    return sanitized


def _json_document_elements(payload: Any) -> List[Dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    return sanitize_document_elements(payload.get("document"))


def parse_json_roadmap(text: str) -> Optional[Dict[str, List[Dict[str, object]]]]:
    """Parse Traqo's JSON interchange format without losing roadmap metadata."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(raw_tasks, list):
        raw_tasks = []

    tasks = []
    for item in raw_tasks:
        if isinstance(item, str):
            title = item.strip()
            timeframe = "General"
            is_done = False
            granularity = "section"
            properties: Dict[str, Any] = {}
            blocks: List[Dict[str, object]] = []
        elif isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            timeframe = str(item.get("timeframe") or item.get("timeframe_label") or "General").strip()
            is_done = _json_boolean(item.get("is_done", False))
            granularity = str(item.get("granularity") or _granularity(timeframe)).strip() or "section"
            properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            blocks = _json_blocks(item.get("blocks"))
        else:
            continue

        if title:
            parsed_task: Dict[str, object] = {
                "title": title,
                "timeframe": timeframe or "General",
                "is_done": is_done,
                "granularity": granularity,
                "properties": properties,
                "blocks": blocks,
            }
            for date_field in ("start_date", "end_date"):
                if isinstance(item, dict) and date_field in item:
                    value = item.get(date_field)
                    parsed_task[date_field] = None if value is None else str(value).strip()
            timeframe_id = item.get("timeframe_id") if isinstance(item, dict) else None
            if isinstance(timeframe_id, int) and not isinstance(timeframe_id, bool) and timeframe_id > 0:
                parsed_task["timeframe_id"] = timeframe_id
            tasks.append(parsed_task)

    return {
        "tasks": tasks,
        "document": _json_document_elements(payload),
    }


def _parse_json_tasks(text: str) -> Optional[List[Dict[str, object]]]:
    roadmap = parse_json_roadmap(text)
    return None if roadmap is None else roadmap["tasks"]


def parse_tasks(text: str) -> List[Dict[str, object]]:
    """Parse pasted or extracted roadmap text into timeframe-scoped tasks."""
    text = normalize_text(text)
    if not text:
        return []

    json_tasks = _parse_json_tasks(text)
    if json_tasks is not None:
        return json_tasks

    tasks: List[Dict[str, object]] = []
    current_timeframe = "General"
    base_timeframe = "General"
    current_day = ""
    pending_time = ""
    cleaned_lines = _prepare_lines(text)

    for index, line in enumerate(cleaned_lines):
        next_line = cleaned_lines[index + 1] if index + 1 < len(cleaned_lines) else None

        if index == 0 and current_timeframe == "General" and not _looks_like_task(line, False):
            current_timeframe = _clean_heading(line)
            base_timeframe = current_timeframe
            continue

        if _is_heading(line, next_line):
            heading = _clean_heading(line)

            if DAY_RE.match(heading):
                current_day = heading
                pending_time = ""
                current_timeframe = heading
                base_timeframe = heading
                continue

            if TIME_RANGE_RE.match(heading):
                pending_time = heading
                current_timeframe = _compose_timeframe(current_day, pending_time)
                base_timeframe = current_timeframe
                continue

            if pending_time:
                current_timeframe = _compose_timeframe(current_day, f"{pending_time} - {heading}")
                base_timeframe = current_timeframe
                pending_time = ""
            elif NOTE_SECTION_RE.match(heading) and base_timeframe != "General":
                current_timeframe = _append_to_timeframe(base_timeframe, heading)
            else:
                current_timeframe = _compose_timeframe(current_day, heading)
                base_timeframe = current_timeframe
            continue

        if _looks_like_task(line, current_timeframe != "General"):
            title = _clean_task(line)
            if title:
                tasks.append(
                    {
                        "title": title,
                        "timeframe": current_timeframe,
                        "is_done": CHECKED_TASK_RE.match(line) is not None,
                        "granularity": _granularity(current_timeframe),
                    }
                )

    if not tasks:
        sentences = [
            chunk.strip(" -")
            for chunk in re.split(r"(?:\n+|(?<=[.!?])\s+)", text)
            if chunk.strip(" -")
        ]
        tasks = [
            {
                "title": sentence,
                "timeframe": "General",
                "is_done": False,
                "granularity": "section",
            }
            for sentence in sentences
        ]

    return tasks


def parse_roadmap(text: str) -> List[Dict[str, object]]:
    """Compatibility shape used by the database writer."""
    parsed = []
    for task in parse_tasks(text):
        timeframe = task["timeframe"]
        parsed.append(
            {
                "type": "task",
                "title": task["title"],
                "timeframe_label": timeframe,
                "granularity": task.get("granularity") or _granularity(str(timeframe)),
                "is_done": bool(task.get("is_done", False)),
                **(
                    {"timeframe_id": task["timeframe_id"]}
                    if task.get("timeframe_id") is not None
                    else {}
                ),
            }
        )
    return parsed
