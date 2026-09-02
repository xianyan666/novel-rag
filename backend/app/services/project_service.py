"""项目管理服务。"""

import json
from pathlib import Path

from ..config import load_projects, load_project, data_dir, index_dir, ROOT


def list_projects() -> list[dict]:
    projects = load_projects()
    result = []
    for p in projects:
        pid = p["project_id"]
        info = {
            "project_id": pid,
            "display_name": p["display_name"],
            "source_dir": p["source_dir"],
            "source_exists": (ROOT / p["source_dir"]).exists(),
            "has_chapters": (data_dir(pid) / "chapters.jsonl").exists(),
            "has_chunks": (data_dir(pid) / "chunks.jsonl").exists(),
            "has_index": index_dir(pid).exists(),
        }
        # Load report if exists
        report_path = data_dir(pid) / "ingest_report.json"
        if report_path.exists():
            info["report"] = json.loads(report_path.read_text(encoding="utf-8"))
        result.append(info)
    return result


def get_project(project_id: str) -> dict | None:
    p = load_project(project_id)
    if not p:
        return None
    return {
        "project_id": p["project_id"],
        "display_name": p["display_name"],
        "source_dir": p["source_dir"],
        "encoding": p["encoding"],
        "chapter_patterns": p["chapter_patterns"],
        "chunk_size": p.get("chunk_size", 1000),
        "chunk_overlap": p.get("chunk_overlap", 200),
    }
