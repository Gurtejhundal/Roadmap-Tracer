from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models_db as models
from datetime import datetime
from typing import List, Dict, Any, Optional

# Initialize DB (Create tables)
def init_db():
    models.Base.metadata.create_all(bind=engine)

def get_db_session():
    return SessionLocal()

# --- Roadmaps ---

def get_roadmaps(user_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        roadmaps = db.query(models.Roadmap).filter(models.Roadmap.user_id == user_id).order_by(models.Roadmap.created_at.desc()).all()
        # Convert to dict for compatibility
        return [{"id": r.id, "name": r.name, "created_at": r.created_at, "raw_text": r.raw_text} for r in roadmaps]
    finally:
        db.close()

def get_roadmap(roadmap_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if r:
            return {"id": r.id, "name": r.name, "created_at": r.created_at, "raw_text": r.raw_text}
        return None
    finally:
        db.close()

def save_roadmap(name: str, raw_text: str, user_id: str) -> int:
    db = SessionLocal()
    try:
        new_roadmap = models.Roadmap(name=name, raw_text=raw_text, user_id=user_id)
        db.add(new_roadmap)
        db.commit()
        db.refresh(new_roadmap)
        return new_roadmap.id
    finally:
        db.close()

def delete_roadmap(roadmap_id: int):
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if r:
            db.delete(r)
            db.commit()
    finally:
        db.close()

def rename_roadmap(roadmap_id: int, new_name: str):
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if r:
            r.name = new_name
            db.commit()
    finally:
        db.close()

# --- Content Updates & Parsing ---

def update_roadmap_content(roadmap_id: int, new_text: str, parser_func):
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if not r:
            return False
            
        # 1. Update text
        r.raw_text = new_text
        
        # 2. Clear existing structure (Cascade delete handles tasks/timeframes via relationships)
        # Actually standard SQLAlchemy cascade might need explicit deletion if not perfectly configured,
        # but let's do it explicitly to be safe.
        db.query(models.Task).filter(models.Task.timeframe_id.in_(
            db.query(models.Timeframe.id).filter(models.Timeframe.roadmap_id == roadmap_id)
        )).delete(synchronize_session=False)
        
        db.query(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id).delete(synchronize_session=False)
        
        # 3. Re-parse and Insert
        parsed_data = parser_func(new_text)
        tf_map = {} # label -> timeframe_obj
        
        for item in parsed_data:
            if item['type'] == 'task':
                tf_label = item['timeframe_label']
                
                if tf_label not in tf_map:
                    new_tf = models.Timeframe(roadmap_id=roadmap_id, label=tf_label, granularity=item['granularity'])
                    db.add(new_tf)
                    db.flush() # Get ID
                    tf_map[tf_label] = new_tf
                
                tf_obj = tf_map[tf_label]
                new_task = models.Task(timeframe_id=tf_obj.id, title=item['title'])
                db.add(new_task)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error updating roadmap: {e}")
        return False
    finally:
        db.close()

def update_roadmap_smart(roadmap_id: int, name: str, tasks: List[Dict[str, Any]]) -> bool:
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if not r:
            return False
            
        r.name = name
        
        # Clear existing
        db.query(models.Task).filter(models.Task.timeframe_id.in_(
            db.query(models.Timeframe.id).filter(models.Timeframe.roadmap_id == roadmap_id)
        )).delete(synchronize_session=False)
        
        db.query(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id).delete(synchronize_session=False)
        
        # Insert New
        tf_map = {}
        
        for task in tasks:
            tf_label = task.get('timeframe', 'General')
            title = task['title']
            is_done = task.get('is_done', False)
            
            if tf_label not in tf_map:
                new_tf = models.Timeframe(roadmap_id=roadmap_id, label=tf_label, granularity="smart_update")
                db.add(new_tf)
                db.flush()
                tf_map[tf_label] = new_tf
            
            tf_obj = tf_map[tf_label]
            new_task = models.Task(timeframe_id=tf_obj.id, title=title, is_done=is_done)
            db.add(new_task)
            
        db.commit()
        return True
    finally:
        db.close()

def save_imported_roadmap(name: str, tasks: List[Dict[str, Any]], user_id: str) -> int:
    db = SessionLocal()
    try:
        new_roadmap = models.Roadmap(name=name, raw_text="", user_id=user_id)
        db.add(new_roadmap)
        db.commit()
        db.refresh(new_roadmap)
        
        tf_map = {}
        
        for task in tasks:
            tf_label = task.get('timeframe', 'General')
            title = task['title']
            is_done = task.get('is_done', False)
            
            if tf_label not in tf_map:
                new_tf = models.Timeframe(roadmap_id=new_roadmap.id, label=tf_label, granularity="import")
                db.add(new_tf)
                db.flush()
                tf_map[tf_label] = new_tf
                
            tf_obj = tf_map[tf_label]
            new_task = models.Task(timeframe_id=tf_obj.id, title=title, is_done=is_done)
            db.add(new_task)
            
        db.commit()
        return new_roadmap.id
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

# --- Tasks & Timeframes ---

def get_tasks(roadmap_id: int, timeframe_id: Optional[int] = None) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(models.Task).join(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id)
        
        if timeframe_id:
            query = query.filter(models.Task.timeframe_id == timeframe_id)
            
        tasks = query.all()
        
        # Format for frontend
        res = []
        for t in tasks:
            res.append({
                "id": t.id,
                "title": t.title,
                "is_done": t.is_done,
                "timeframe_id": t.timeframe_id,
                "timeframe_label": t.timeframe.label, # Joined load
                "created_at": t.created_at
            })
        return res
    finally:
        db.close()

def update_task_status(task_id: int, is_done: bool):
    db = SessionLocal()
    try:
        t = db.query(models.Task).filter(models.Task.id == task_id).first()
        if t:
            t.is_done = is_done
            db.commit()
    finally:
        db.close()

def get_timeframes(roadmap_id: int) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        tfs = db.query(models.Timeframe).filter(models.Timeframe.roadmap_id == roadmap_id).all()
        return [{"id": t.id, "label": t.label, "start_date": t.start_date, "end_date": t.end_date} for t in tfs]
    finally:
        db.close()

def update_timeframe_dates(timeframe_id: int, start_date: Optional[str], end_date: Optional[str]):
    db = SessionLocal()
    try:
        tf = db.query(models.Timeframe).filter(models.Timeframe.id == timeframe_id).first()
        if tf:
            tf.start_date = start_date
            tf.end_date = end_date
            db.commit()
    finally:
        db.close()

def export_roadmap_data(roadmap_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        r = db.query(models.Roadmap).filter(models.Roadmap.id == roadmap_id).first()
        if not r:
            return None
            
        tfs = r.timeframes # Access via relationship
        export_tasks = []
        
        for tf in tfs:
            for t in tf.tasks:
                export_tasks.append({
                    "title": t.title,
                    "timeframe": tf.label,
                    "is_done": t.is_done
                })
                
        return {
            "name": r.name,
            "tasks": export_tasks
        }
    finally:
        db.close()
