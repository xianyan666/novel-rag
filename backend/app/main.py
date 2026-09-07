"""FastAPI 后端主入口。"""

import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    ProjectInfo, IngestReport, QueryRequest, QueryResponse,
    Citation, RetrievedChunk, QueryAnalysis, TimelineEventResponse, RetrievalDebug,
    EntityInfo, EntityMentionResponse, EntityTimelineEventResponse,
    EntityRelationResponse, EntityAnalysis,
)
from .services import project_service, ingest_service, index_service, query_service
from .services import timeline_build_service, timeline_service
from .services import entity_build_service, entity_service
from .services import world_build_service, world_service

app = FastAPI(title="小说 RAG 知识库", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/projects")
def list_projects():
    try:
        return project_service.list_projects()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return p


@app.post("/api/projects/{project_id}/scan")
def scan_project(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    from .config import ROOT
    source_dir = ROOT / p["source_dir"]
    if not source_dir.exists():
        raise HTTPException(status_code=400, detail=f"Source directory not found: {p['source_dir']}")

    txt_files = list(source_dir.glob("*.txt"))
    return {
        "project_id": project_id,
        "source_dir": str(source_dir),
        "txt_files": [f.name for f in txt_files],
        "total_size_mb": round(sum(f.stat().st_size for f in txt_files) / 1024 / 1024, 2),
    }


@app.post("/api/projects/{project_id}/ingest")
def ingest_project(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        result = ingest_service.run_ingest(project_id)
        # Reload report
        from .config import data_dir
        import json
        report_path = data_dir(project_id) / "ingest_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
        else:
            report = {}
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


@app.post("/api/projects/{project_id}/index")
def build_index(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        result = index_service.build_index(project_id)
        return {"status": "ok", "output": result["stdout"]}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Index build failed: {str(e)}")


@app.post("/api/projects/{project_id}/query")
def query_project(project_id: str, req: QueryRequest):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = query_service.query(project_id, req.question, req.top_k)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.post("/api/projects/{project_id}/timeline/build")
def build_timeline(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        result = timeline_build_service.build_timeline(project_id)
        return {"status": "ok", "output": result["stdout"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Timeline build failed: {str(e)}")


@app.get("/api/projects/{project_id}/timeline/events")
def get_timeline_events(project_id: str, event_type: str | None = None, subject: str | None = None):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    events = timeline_service.load_timeline_events(project_id)
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]
    if subject:
        events = [e for e in events if subject in e.get("subjects", [])]
    return {"project_id": project_id, "events": events, "count": len(events)}


@app.get("/api/projects/{project_id}/timeline/edges")
def get_timeline_edges(project_id: str, relation: str | None = "follows"):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    edges = timeline_service.load_timeline_edges(project_id)
    if relation:
        edges = [e for e in edges if e.get("relation") == relation]
    return {"project_id": project_id, "edges": edges, "count": len(edges)}


# ---------------------------------------------------------------------------
# World index APIs
# ---------------------------------------------------------------------------

@app.post("/api/projects/{project_id}/worlds/build")
def build_world_index(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    try:
        result = world_build_service.build_world_index(project_id)
        return {"status": "ok", "output": result["stdout"]}
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"World index build failed: {str(e)}")


@app.get("/api/projects/{project_id}/worlds")
def list_worlds(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    worlds = world_service.list_worlds(project_id)
    return {"project_id": project_id, "worlds": worlds, "count": len(worlds)}


@app.get("/api/projects/{project_id}/worlds/chapter/{chapter_no}")
def get_chapter_world(project_id: str, chapter_no: int):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    world = world_service.get_chapter_world(project_id, chapter_no)
    if not world:
        raise HTTPException(status_code=404, detail=f"No world mapping for chapter {chapter_no}")
    return {"project_id": project_id, "chapter_no": chapter_no, "world": world}


@app.get("/api/projects/{project_id}/worlds/{world_id}")
def get_world(project_id: str, world_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    world = world_service.get_world(project_id, world_id)
    if not world:
        raise HTTPException(status_code=404, detail=f"World '{world_id}' not found")
    return world


# ---------------------------------------------------------------------------
# Entity API
# ---------------------------------------------------------------------------

@app.post("/api/projects/{project_id}/entities/build")
def build_entities(project_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    try:
        result = entity_build_service.build_entities(project_id)
        return {"status": "ok", "output": result["stdout"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Entity build failed: {str(e)}")


@app.get("/api/projects/{project_id}/entities")
def list_entities(project_id: str, entity_type: str | None = None):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    entities = entity_service.load_entities(project_id)
    if entity_type:
        entities = [e for e in entities if e["type"] == entity_type]
    return {"project_id": project_id, "entities": entities, "count": len(entities)}


@app.get("/api/projects/{project_id}/entities/search")
def search_entities(project_id: str, q: str = ""):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    results = entity_service.search_entities(project_id, q)
    return {"project_id": project_id, "query": q, "entities": results, "count": len(results)}


@app.get("/api/projects/{project_id}/entities/{entity_id}")
def get_entity(project_id: str, entity_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    ent = entity_service.get_entity(project_id, entity_id)
    if not ent:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return ent


@app.get("/api/projects/{project_id}/entities/{entity_id}/mentions")
def get_entity_mentions(project_id: str, entity_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    mentions = entity_service.get_entity_mentions(project_id, entity_id)
    return {"project_id": project_id, "entity_id": entity_id, "mentions": mentions, "count": len(mentions)}


@app.get("/api/projects/{project_id}/entities/{entity_id}/timeline")
def get_entity_timeline(project_id: str, entity_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    timeline = entity_service.get_entity_timeline(project_id, entity_id)
    return {"project_id": project_id, "entity_id": entity_id, "timeline": timeline, "count": len(timeline)}


@app.get("/api/projects/{project_id}/entities/{entity_id}/relations")
def get_entity_relations(project_id: str, entity_id: str):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    relations = entity_service.get_entity_relations(project_id, entity_id)
    return {"project_id": project_id, "entity_id": entity_id, "relations": relations, "count": len(relations)}


@app.get("/api/projects/{project_id}/relations")
def query_relations(project_id: str, source: str | None = None, target: str | None = None):
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    relations = entity_service.query_relations(project_id, source, target)
    return {"project_id": project_id, "relations": relations, "count": len(relations)}


@app.get("/api/projects/{project_id}/history")
def get_query_history(project_id: str, limit: int = 50):
    """读取本地问答历史记录（最新的在前）。"""
    p = project_service.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    import json
    from .config import data_dir
    path = data_dir(project_id) / "query_history.jsonl"
    records = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    records.reverse()
    limit = max(1, min(limit, 500))
    return {"project_id": project_id, "history": records[:limit], "count": len(records[:limit])}
