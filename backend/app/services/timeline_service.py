"""时间线事件查询服务：通用事件类型 + follows 链展开。"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import data_dir

_events_cache: dict[str, tuple[float, list[dict]]] = {}
_edges_cache: dict[str, tuple[float, list[dict]]] = {}
_index_cache: dict[str, tuple[float, dict]] = {}


def load_timeline_events(project_id: str) -> list[dict]:
    events_path = data_dir(project_id) / "timeline_events.jsonl"
    if not events_path.exists():
        return []

    mtime = events_path.stat().st_mtime
    cached = _events_cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    events = []
    with open(events_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    _events_cache[project_id] = (mtime, events)
    return events


def load_timeline_edges(project_id: str) -> list[dict]:
    edges_path = data_dir(project_id) / "timeline_edges.jsonl"
    if not edges_path.exists():
        return []

    mtime = edges_path.stat().st_mtime
    cached = _edges_cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    edges = []
    with open(edges_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                edges.append(json.loads(line))

    _edges_cache[project_id] = (mtime, edges)
    return edges


def load_timeline_index(project_id: str) -> dict:
    index_path = data_dir(project_id) / "timeline_index.json"
    if not index_path.exists():
        return {}

    mtime = index_path.stat().st_mtime
    cached = _index_cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    index = json.loads(index_path.read_text(encoding="utf-8"))
    _index_cache[project_id] = (mtime, index)
    return index


# 中文提示 / 旧乐园提示 → 通用 event_type
_HINT_TO_TYPES = {
    "遭遇": ["encounter"],
    "冲突": ["conflict"],
    "规则": ["rule_reveal"],
    "能力": ["ability_change"],
    "死亡": ["death_or_seal"],
    "封印": ["death_or_seal"],
    "结盟": ["alliance_or_break"],
    "决裂": ["alliance_or_break"],
    "线索": ["clue"],
    "状态": ["state_change"],
    "角色相遇": ["encounter"],
    "技能获得": ["ability_change"],
    "装备获得": ["state_change", "clue"],
    "获得": ["ability_change", "clue", "state_change"],
    # 旧提示别名（兼容已有分类器输出）
    "进入世界": ["state_change", "encounter"],
    "回归乐园": ["state_change"],
    "任务": ["state_change", "clue"],
}

# 也可直接传英文 event_type
_VALID_TYPES = {
    "encounter",
    "conflict",
    "rule_reveal",
    "ability_change",
    "death_or_seal",
    "alliance_or_break",
    "clue",
    "state_change",
    "other",
}


def _resolve_types(event_hints: list[str] | None) -> set[str]:
    target: set[str] = set()
    if not event_hints:
        return target
    for hint in event_hints:
        if hint in _VALID_TYPES:
            target.add(hint)
            continue
        types = _HINT_TO_TYPES.get(hint, [])
        target.update(types)
    return target


def expand_follows_chain(
    project_id: str,
    seed_events: list[dict],
    radius: int = 1,
) -> list[dict]:
    """围绕命中事件，沿 follows 边前后各展开 radius 步。"""
    if not seed_events or radius <= 0:
        return seed_events

    events = load_timeline_events(project_id)
    by_id = {e["event_id"]: e for e in events}
    index = load_timeline_index(project_id)
    nxt = index.get("follows_next") or {}
    prv = index.get("follows_prev") or {}

    # 若索引缺失，从 edges 重建
    if not nxt and not prv:
        for edge in load_timeline_edges(project_id):
            if edge.get("relation") != "follows":
                continue
            nxt[edge["from_event_id"]] = edge["to_event_id"]
            prv[edge["to_event_id"]] = edge["from_event_id"]

    ordered_ids: list[str] = []
    seen: set[str] = set()

    def add_id(eid: str) -> None:
        if eid in by_id and eid not in seen:
            seen.add(eid)
            ordered_ids.append(eid)

    for seed in seed_events:
        sid = seed["event_id"]
        # 向前
        walk = sid
        prev_chain: list[str] = []
        for _ in range(radius):
            walk = prv.get(walk)
            if not walk:
                break
            prev_chain.append(walk)
        for eid in reversed(prev_chain):
            add_id(eid)

        add_id(sid)

        # 向后
        walk = sid
        for _ in range(radius):
            walk = nxt.get(walk)
            if not walk:
                break
            add_id(walk)

    return [by_id[eid] for eid in ordered_ids]


def query_timeline(
    project_id: str,
    event_hints: list[str] | None = None,
    entities: list[str] | None = None,
    query_type: str = "normal_fact",
    limit: int = 10,
    chain_radius: int = 1,
) -> list[dict]:
    events = load_timeline_events(project_id)
    if not events:
        return []

    target_types = _resolve_types(event_hints)

    filtered = events
    if target_types:
        typed = [e for e in events if e["event_type"] in target_types]
        if typed:
            filtered = typed

    if entities:
        entity_filtered = [
            e for e in filtered
            if any(
                s in e.get("subjects", []) or s in (e.get("event_summary") or "") or s in (e.get("evidence") or "")
                for s in entities
            )
        ]
        if entity_filtered:
            filtered = entity_filtered

    filtered = sorted(filtered, key=lambda e: (e["chapter_no"], e.get("chunk_id", ""), e["event_id"]))

    # 时间线类问题多取一些种子，再展开链
    seed_limit = limit if query_type in {"timeline_summary", "sequence_order"} else max(3, min(limit, 8))
    seeds = filtered[:seed_limit]

    if chain_radius > 0 and seeds:
        chained = expand_follows_chain(project_id, seeds, radius=chain_radius)
        # 保持章节序，截断
        chained = sorted(chained, key=lambda e: (e["chapter_no"], e.get("chunk_id", ""), e["event_id"]))
        return chained[:limit]

    return seeds[:limit]
