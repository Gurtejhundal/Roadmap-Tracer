from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import db
import roadmap_parser as parser
from models import RoadmapCreate, RoadmapUpdate, RoadmapResponse, TaskUpdate, RoadmapNameUpdate, TimeframeDateUpdate, RoadmapImport


app = FastAPI(title="TRAQO API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Authentication Dependency ---
from fastapi import Header

# For now, we trust the frontend to send the user_id. 
# In production, we would verify the JWT token from Clerk here.
async def get_current_user(x_clerk_user_id: str = Header(None, alias="X-Clerk-User-Id")):
    if not x_clerk_user_id:
        # Fallback for now (or raise 401 if strict)
        return "public_user" 
    return x_clerk_user_id

@app.on_event("startup")
def startup_event():
    db.init_db()

@app.get("/")
def read_root():
    return {"message": "Welcome to TRAQO API"}

@app.post("/roadmaps", response_model=dict)
@app.post("/roadmaps", response_model=dict)
def create_roadmap(roadmap: RoadmapCreate, user_id: str = Depends(get_current_user)):
    # Check for duplicates (scoped to user?)
    try:
        existing = db.get_roadmaps(user_id)
        if any(r['name'].strip().lower() == roadmap.name.strip().lower() for r in existing):
            raise HTTPException(status_code=400, detail="Roadmap with this name already exists.")
        
        roadmap_id = db.save_roadmap(roadmap.name, roadmap.text, user_id)
        
        # Parse and save tasks
        parsed_items = parser.parse_roadmap(roadmap.text)
        
        success = db.update_roadmap_content(roadmap_id, roadmap.text, parser.parse_roadmap)
        if not success:
             raise HTTPException(status_code=500, detail="Failed to parse roadmap.")
             
        return {"id": roadmap_id, "message": "Roadmap created successfully"}
    except Exception as e:
        with open("backend_error.log", "a") as f:
            import traceback
            f.write(f"Error creating roadmap: {str(e)}\n")
            f.write(traceback.format_exc())
            f.write("\n")
        raise e

@app.post("/roadmaps/import", response_model=dict)
@app.post("/roadmaps/import", response_model=dict)
def import_roadmap(roadmap: RoadmapImport, user_id: str = Depends(get_current_user)):
    try:
        # Check for duplicates
        existing = db.get_roadmaps(user_id)
        if any(r['name'].strip().lower() == roadmap.name.strip().lower() for r in existing):
             # Append a number if duplicate? Or just allow it. The current DB allows it, UI logic checked it.
             # User might import "Python" twice. Let's allowing it for now or make name unique.
             # Original create_roadmap raises 400.
             pass 

        # Convert Pydantic models to dicts for DB function
        tasks_data = [t.dict() for t in roadmap.tasks]
        tasks_data = [t.dict() for t in roadmap.tasks]
        roadmap_id = db.save_imported_roadmap(roadmap.name, tasks_data, user_id)
        
        return {"id": roadmap_id, "message": "Roadmap imported successfully"}
    except Exception as e:
        print(f"Error importing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/roadmaps", response_model=List[RoadmapResponse])
@app.get("/roadmaps", response_model=List[RoadmapResponse])
def get_roadmaps(user_id: str = Depends(get_current_user)):
    return db.get_roadmaps(user_id)

@app.get("/roadmaps/{roadmap_id}", response_model=RoadmapResponse)
def get_roadmap(roadmap_id: int):
    roadmap = db.get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap

@app.get("/roadmaps/{roadmap_id}/export")
def export_roadmap(roadmap_id: int):
    data = db.export_roadmap_data(roadmap_id)
    if not data:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return data


@app.delete("/roadmaps/{roadmap_id}")
def delete_roadmap(roadmap_id: int):
    db.delete_roadmap(roadmap_id)
    return {"message": "Roadmap deleted"}

@app.put("/roadmaps/{roadmap_id}")
def update_roadmap(roadmap_id: int, roadmap: RoadmapUpdate):
    success = db.update_roadmap_content(roadmap_id, roadmap.text, parser.parse_roadmap)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update roadmap")
    return {"message": "Roadmap updated"}

@app.get("/roadmaps/{roadmap_id}/tasks")
def get_roadmap_tasks(roadmap_id: int):
    # Return tasks grouped by timeframe for easier frontend consumption
    tasks = db.get_tasks(roadmap_id)
    return tasks

@app.put("/tasks/{task_id}/status")
def update_task_status(task_id: int, status: TaskUpdate):
    db.update_task_status(task_id, status.is_done)
    return {"message": "Task status updated"}

@app.put("/roadmaps/{roadmap_id}/smart")
def update_roadmap_smart(roadmap_id: int, roadmap: RoadmapImport):
    # Reuse RoadmapImport model as it has {name, tasks}
    tasks_data = [t.dict() for t in roadmap.tasks]
    try:
        db.update_roadmap_smart(roadmap_id, roadmap.name, tasks_data)
        return {"message": "Roadmap updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/roadmaps/{roadmap_id}/smart")
def update_roadmap_smart(roadmap_id: int, roadmap: RoadmapImport):
    # Reuse RoadmapImport model as it has {name, tasks}
    tasks_data = [t.dict() for t in roadmap.tasks]
    try:
        db.update_roadmap_smart(roadmap_id, roadmap.name, tasks_data)
        return {"message": "Roadmap updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.put("/roadmaps/{roadmap_id}/name")
def rename_roadmap(roadmap_id: int, update: RoadmapNameUpdate):
    db.rename_roadmap(roadmap_id, update.name)
    return {"message": "Roadmap renamed"}

@app.get("/roadmaps/{roadmap_id}/timeframes")
def get_roadmap_timeframes(roadmap_id: int):
    return db.get_timeframes(roadmap_id)

@app.put("/timeframes/{timeframe_id}/dates")
def update_timeframe_dates(timeframe_id: int, update: TimeframeDateUpdate):
    db.update_timeframe_dates(timeframe_id, update.start_date, update.end_date)
    return {"message": "Timeframe dates updated"}
