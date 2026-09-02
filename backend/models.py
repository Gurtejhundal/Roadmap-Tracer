from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


MAX_ROADMAP_NAME_LENGTH = 200
MAX_ROADMAP_TEXT_LENGTH = 8 * 1024 * 1024
MAX_TASK_TITLE_LENGTH = 4000
MAX_TIMEFRAME_LABEL_LENGTH = 500


class RoadmapCreate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_ROADMAP_NAME_LENGTH)
    text: str = Field(min_length=1, max_length=MAX_ROADMAP_TEXT_LENGTH)

class RoadmapUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ROADMAP_TEXT_LENGTH)

class RoadmapSummary(BaseModel):
    id: int
    name: str
    created_at: str
    total_tasks: int = 0
    completed_tasks: int = 0


class RoadmapResponse(RoadmapSummary):
    raw_text: Optional[str] = None

class TaskUpdate(BaseModel):
    is_done: bool

class TaskCreate(BaseModel):
    roadmap_id: int
    timeframe_id: Optional[int] = Field(default=None, ge=1)
    timeframe_label: Optional[str] = Field(default=None, max_length=MAX_TIMEFRAME_LABEL_LENGTH)
    title: str = Field(min_length=1, max_length=MAX_TASK_TITLE_LENGTH)

class TaskTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TASK_TITLE_LENGTH)

class TaskPropertiesUpdate(BaseModel):
    properties: Dict[str, Any]


class TaskBlockCreate(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    data: Dict[str, Any] = Field(default_factory=dict)
    position: Optional[int] = Field(default=None, ge=0)


class TaskBlockBulkCreate(BaseModel):
    task_ids: List[int] = Field(min_length=1, max_length=5000)
    type: str = Field(min_length=1, max_length=40)
    data: Dict[str, Any] = Field(default_factory=dict)


class TaskBlockUpdate(BaseModel):
    type: Optional[str] = Field(default=None, min_length=1, max_length=40)
    data: Optional[Dict[str, Any]] = None
    position: Optional[int] = Field(default=None, ge=0)

class RoadmapNameUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_ROADMAP_NAME_LENGTH)

class TimeframeDateUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class TaskImport(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TASK_TITLE_LENGTH)
    timeframe: str = Field(max_length=MAX_TIMEFRAME_LABEL_LENGTH)
    timeframe_id: Optional[int] = Field(default=None, ge=1)
    is_done: bool = False
    granularity: Optional[str] = Field(default=None, max_length=40)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    blocks: List[TaskBlockCreate] = Field(default_factory=list)

class RoadmapImport(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_ROADMAP_NAME_LENGTH)
    tasks: List[TaskImport] = Field(max_length=10_000)
