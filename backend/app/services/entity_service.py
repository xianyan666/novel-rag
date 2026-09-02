"""实体服务：加载和查询实体、提及、时间线、关系。"""

import json
from pathlib import Path

from ..config import data_dir

_cache: dict[str, tuple[float, dict]] = {}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_all(project_id: str) -> dict:
    dd = data_dir(project_id)
    index_path = dd / "entity_index.json"
    if not index_path.exists():
        return {}

    mtime = index_path.stat().st_mtime
    cached = _cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    data = {
        "entities": _load_jsonl(dd / "entities.jsonl"),
        "mentions": _load_jsonl(dd / "entity_mentions.jsonl"),
        "timeline": _load_jsonl(dd / "entity_timeline.jsonl"),
        "relations": _load_jsonl(dd / "entity_relations.jsonl"),
        "index": _load_json(index_path),
    }
    _cache[project_id] = (mtime, data)
    return data


def load_entities(project_id: str) -> list[dict]:
    return _load_all(project_id).get("entities", [])


def load_entity_index(project_id: str) -> dict:
    return _load_all(project_id).get("index", {})


def search_entities(project_id: str, q: str) -> list[dict]:
    data = _load_all(project_id)
    entities = data.get("entities", [])
    index = data.get("index", {})

    results = []
    q_lower = q.strip()

    # Exact name match
    by_name = index.get("by_name", {})
    if q_lower in by_name:
        eid = by_name[q_lower]
        for ent in entities:
            if ent["entity_id"] == eid:
                results.append(ent)
                break

    # Alias match
    by_alias = index.get("by_alias", {})
    if q_lower in by_alias:
        eid = by_alias[q_lower]
        if not any(r["entity_id"] == eid for r in results):
            for ent in entities:
                if ent["entity_id"] == eid:
                    results.append(ent)
                    break

    # Substring fallback: check if entity name is in query, or query is in entity name
    if not results:
        for ent in entities:
            if ent["name"] in q_lower or q_lower in ent["name"] or any(a in q_lower or q_lower in a for a in ent.get("aliases", [])):
                results.append(ent)

    return results


def get_entity(project_id: str, entity_id: str) -> dict | None:
    entities = _load_all(project_id).get("entities", [])
    for ent in entities:
        if ent["entity_id"] == entity_id:
            return ent
    return None


def get_entity_mentions(project_id: str, entity_id: str) -> list[dict]:
    mentions = _load_all(project_id).get("mentions", [])
    return [m for m in mentions if m["entity_id"] == entity_id]


def get_entity_timeline(project_id: str, entity_id: str) -> list[dict]:
    timeline = _load_all(project_id).get("timeline", [])
    return [e for e in timeline if e["entity_id"] == entity_id]


def get_entity_relations(project_id: str, entity_id: str) -> list[dict]:
    relations = _load_all(project_id).get("relations", [])
    return [
        r for r in relations
        if r["source_entity_id"] == entity_id or r["target_entity_id"] == entity_id
    ]


def query_relations(project_id: str, source_name: str | None = None, target_name: str | None = None) -> list[dict]:
    data = _load_all(project_id)
    relations = data.get("relations", [])
    by_name = data.get("index", {}).get("by_name", {})

    results = relations
    if source_name:
        sid = by_name.get(source_name)
        if sid:
            results = [r for r in results if r["source_entity_id"] == sid]
    if target_name:
        tid = by_name.get(target_name)
        if tid:
            results = [r for r in results if r["target_entity_id"] == tid]

    return results
