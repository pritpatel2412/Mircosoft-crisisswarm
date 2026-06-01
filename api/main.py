from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os
import sys

# Add root folder to sys.path to resolve core imports
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.scenario import load_demo_scenario
from core.swarm import run_swarm, finalize_mission, run_aftershock_rerun
from core.arena import run_arena

app = FastAPI(
    title="CrisisSwarm API",
    description="Emergency Multi-Agent Logistics Swarm API Core",
    version="1.0.0"
)

# Enable CORS for local Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SwarmRequest(BaseModel):
    scenario_text: str
    strategy: Optional[str] = "default"
    conflict_demo: Optional[bool] = False

class FinalizeRequest(BaseModel):
    pending: Dict[str, Any]
    decision: str
    officer: Optional[str] = "Incident Commander"
    notes: Optional[str] = ""

class AftershockRequest(BaseModel):
    pending: Dict[str, Any]

class ArenaRequest(BaseModel):
    scenario_text: str
    inject_aftershock: Optional[bool] = True

@app.get("/api/scenarios/demo")
def get_demo_scenario():
    return {"scenario_text": load_demo_scenario()}

@app.post("/api/run-swarm")
def api_run_swarm(req: SwarmRequest):
    text = req.scenario_text
    if req.conflict_demo:
        text = f"{text}\n\nFleet status: only 5 ambulances available in Mumbai. Do not over-allocate."
    
    res = run_swarm(text, strategy=req.strategy, await_human_approval=True)
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.post("/api/finalize-mission")
def api_finalize_mission(req: FinalizeRequest):
    res = finalize_mission(
        pending=req.pending,
        decision=req.decision,
        officer=req.officer,
        notes=req.notes
    )
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.post("/api/aftershock")
def api_aftershock(req: AftershockRequest):
    res = run_aftershock_rerun(req.pending)
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.post("/api/arena")
def api_run_arena(req: ArenaRequest):
    res = run_arena(
        scenario_text=req.scenario_text,
        inject_aftershock=req.inject_aftershock,
        aftershock_round=True
    )
    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])
    return res

# Serve React static built files if they exist in production
frontend_dist = os.path.join(ROOT_DIR, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
