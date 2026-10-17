"""
FastAPI Backend Server for ChainSight Agent.
Endpoints:
- GET /health: Healthcheck and system status
- POST /api/analyze: Disruption event analysis and resolution report generation
- GET /api/network: Network graph topology and active nodes
- GET /api/shipments: All monitored shipments
- GET /api/memory: Prior incident history from SQLite store
- POST /api/mcp/tool: Direct MCP tool execution gateway
"""
import sys
import os
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import ChainSightAgent
from memory.store import IncidentMemoryStore
from schemas import ResolutionReport

app = FastAPI(
    title="ChainSight API Backend",
    description="REST API for ChainSight Autonomous Supply Chain Risk & Recovery System",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = ChainSightAgent(offline_mode=True)
memory_store = IncidentMemoryStore()


class AnalyzeRequest(BaseModel):
    input_text: str
    target_nodes: Optional[List[str]] = None
    simulate_notification: bool = True
    save_to_memory: bool = True
    test_weather_failure: bool = False


@app.get("/health")
def healthcheck():
    return {
        "status": "healthy",
        "service": "ChainSight Agent Backend",
        "nodes_loaded": len(agent.network.graph.nodes),
        "shipments_loaded": len(agent.network.shipments_df),
    }


@app.post("/api/analyze", response_model=Dict[str, Any])
def analyze_disruption(req: AnalyzeRequest):
    """Run full agent resolution pipeline on textual alert."""
    try:
        custom_agent = ChainSightAgent(
            offline_mode=True,
            test_weather_failure=req.test_weather_failure,
        )
        report = custom_agent.run(
            input_text=req.input_text,
            target_nodes=req.target_nodes,
            simulate_notification=req.simulate_notification,
            save_to_memory=req.save_to_memory,
        )
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze/multimodal")
async def analyze_multimodal_advisory(
    file: UploadFile = File(...),
    simulate_notification: bool = Form(True),
    save_to_memory: bool = Form(True),
):
    """Upload advisory document/image for multimodal extraction."""
    try:
        img_bytes = await file.read()
        report = agent.run(
            image_bytes=img_bytes,
            image_mime=file.content_type or "image/png",
            simulate_notification=simulate_notification,
            save_to_memory=save_to_memory,
        )
        return report.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/network")
def get_network_topology():
    """Retrieve supply chain nodes, edges, and mitigation catalogs."""
    return agent.network.raw_network_data


@app.get("/api/shipments")
def get_all_shipments():
    """Retrieve all monitored shipments."""
    return agent.network.shipments_df.to_dict(orient="records")


@app.get("/api/memory")
def get_incident_memory(limit: int = 20):
    """Retrieve incident memory records from SQLite."""
    with memory_store.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incident_memory ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
