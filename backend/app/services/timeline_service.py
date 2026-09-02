"""时间线事件查询服务。"""

import json
from pathlib import Path

from ..config import data_dir

_cache: dict[str, tuple[float, list[dict]]] = {}


def load_timeline_events(project_id: str) -> list[dict]:
    events_path = data_dir(project_id) / "timeline_events.jsonl"
    if not events_path.exists():
        return []

    mtime = events_path.stat().st_mtime
    cached = _cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    _cache[project_id] = (mtime, events)
    return events


_HINT_TO_TYPES = {
    "进入世界": ["world_entry"],
    "回归乐园": ["world_return"],
    "任务": ["task_start", "task_complete"],
    "获得": ["item_obtained", "skill_obtained"],
    "角色相遇": ["character_meet"],
    "技能获得": ["skill_obtained"],
    "装备获得": ["item_obtained"],
}


def query_timeline(
    project_id: str,
    event_hints: list[str] | None = None,
    entities: list[str] | None = None,
    query_type: str = "normal_fact",
    limit: int = 10,
) -> list[dict]:
    events = load_timeline_events(project_id)
    if not events:
        return []

    # Filter by event type from hints
    target_types = set()
    if event_hints:
        for hint in event_hints:
            types = _HINT_TO_TYPES.get(hint, [])
            target_types.update(types)

    filtered = events
    if target_types:
        filtered = [e for e in events if e["event_type"] in target_types]

    # Filter by entities
    if entities:
        entity_filtered = [
            e for e in filtered
            if any(s in e.get("subjects", []) for s in entities)
        ]
        if entity_filtered:
            filtered = entity_filtered

    # Sort based on query type
    if query_type == "sequence_first":
        filtered.sort(key=lambda e: e["chapter_no"])
    elif query_type == "timeline_summary":
        filtered.sort(key=lambda e: e["chapter_no"])
    else:
        filtered.sort(key=lambda e: e["chapter_no"])

    return filtered[:limit]
