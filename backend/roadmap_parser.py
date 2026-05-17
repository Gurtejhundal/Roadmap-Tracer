import json
import re
from typing import Dict, List, Optional


BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[\.)]\s+|\[[ xX]\]\s+|[\u2022\u25e6\u2023\u2043\u2219\u2192]\s*)"
)

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
    lines = [_clean_line(raw_line) for raw_line in text.split("\n")]
    lines = [line for line in lines if line]
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


def _parse_json_tasks(text: str) -> List[Dict[str, object]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    raw_tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    if not isinstance(raw_tasks, list):
        return []

    tasks = []
    for item in raw_tasks:
        if isinstance(item, str):
            title = item.strip()
            timeframe = "General"
            is_done = False
        elif isinstance(item, dict):
            title = str(item.get("title", "")).strip()
            timeframe = str(item.get("timeframe") or item.get("timeframe_label") or "General").strip()
            is_done = bool(item.get("is_done", False))
        else:
            continue

        if title:
            tasks.append(
                {
                    "title": title,
                    "timeframe": timeframe or "General",
                    "is_done": is_done,
                    "granularity": _granularity(timeframe),
                }
            )

    return tasks


def parse_tasks(text: str) -> List[Dict[str, object]]:
    """Parse pasted or extracted roadmap text into timeframe-scoped tasks."""
    text = normalize_text(text)
    if not text:
        return []

    json_tasks = _parse_json_tasks(text)
    if json_tasks:
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
                        "is_done": "[x]" in line.lower(),
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
            }
        )
    return parsed
