from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="public") # New: Link to Clerk User ID
    name = Column(String, index=True)
    raw_text = Column(String)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

    timeframes = relationship("Timeframe", back_populates="roadmap", cascade="all, delete-orphan")

class Timeframe(Base):
    __tablename__ = "timeframes"

    id = Column(Integer, primary_key=True, index=True)
    roadmap_id = Column(Integer, ForeignKey("roadmaps.id"))
    label = Column(String)
    granularity = Column(String)
    # parent_id = Column(Integer, ForeignKey("timeframes.id"), nullable=True) # Not strictly used yet but kept for schema compatibility
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)

    roadmap = relationship("Roadmap", back_populates="timeframes")
    tasks = relationship("Task", back_populates="timeframe", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    timeframe_id = Column(Integer, ForeignKey("timeframes.id"))
    title = Column(String)
    details = Column(String, nullable=True)
    is_done = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

    timeframe = relationship("Timeframe", back_populates="tasks")

# Removed ActivityLog as streak system was deleted
