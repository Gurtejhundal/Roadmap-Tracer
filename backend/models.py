from pydantic import BaseModel
from typing import List, Optional

class RoadmapCreate(BaseModel):
    name: str
    text: str

class RoadmapUpdate(BaseModel):
    text: str

class RoadmapResponse(BaseModel):
    id: int
    name: str
    created_at: str
    raw_text: Optional[str] = None
    total_tasks: int = 0
    completed_tasks: int = 0

class TaskUpdate(BaseModel):
    is_done: bool

class TaskCreate(BaseModel):
    roadmap_id: int
    timeframe_label: str
    title: str

class TaskTitleUpdate(BaseModel):
    title: str

class RoadmapNameUpdate(BaseModel):
    name: str

class TimeframeDateUpdate(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class TaskImport(BaseModel):
    title: str
    timeframe: str
    is_done: bool = False

class RoadmapImport(BaseModel):
    name: str
    tasks: List[TaskImport]
