"""World index loading, lookup, and query matching."""

import json
from pathlib import Path

from ..config import data_dir

_cache: dict[str, tuple[float, dict]] = {}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_all(project_id: str) -> dict:
    dd = data_dir(project_id)
    index_path = dd / "world_index.json"
    if not index_path.exists():
        return {"worlds": [], "chapter_map": [], "index": {}}

    mtime = index_path.stat().st_mtime
    cached = _cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    data = {
        "worlds": _load_jsonl(dd / "worlds.jsonl"),
        "chapter_map": _load_jsonl(dd / "chapter_world_map.jsonl"),
        "index": json.loads(index_path.read_text(encoding="utf-8")),
    }
    _cache[project_id] = (mtime, data)
    return data


def list_worlds(project_id: str) -> list[dict]:
    return _load_all(project_id)["worlds"]


def get_world(project_id: str, world_id: str) -> dict | None:
    return next((world for world in list_worlds(project_id) if world["world_id"] == world_id), None)


def get_chapter_world(project_id: str, chapter_no: int) -> dict | None:
    data = _load_all(project_id)
    chapter_to_world = data["index"].get("chapter_to_world", {})
    world_id = chapter_to_world.get(str(chapter_no))
    if not world_id:
        return None
    if world_id == "outside_world":
        return {"world_id": world_id, "world_name": "乐园/现实过渡", "confidence": 0.50}
    world = get_world(project_id, world_id)
    if not world:
        return None
    return {"world_id": world_id, "world_name": world["name"], "confidence": world["confidence"]}


def detect_worlds(project_id: str, question: str) -> list[dict]:
    query = question.strip().casefold()
    matched = []
    for world in list_worlds(project_id):
        name = world["name"]
        if name.startswith("未命名"):
            continue
        names = [name, *world.get("aliases", [])]
        if any(candidate and candidate.casefold() in query for candidate in names):
            matched.append(world)
    return matched
