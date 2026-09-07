"""时间线事件查询服务：通用事件类型 + follows/因果链展开。"""

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


def expand_causal_neighbors(
    project_id: str,
    seed_events: list[dict],
    relations: list[str] | None = None,
    depth: int = 1,
) -> list[dict]:
    """沿 causes/enables/blocks 展开邻居（默认出入边各 depth 层）。"""
    if not seed_events or depth <= 0:
        return seed_events

    allow = set(relations or ["causes", "enables", "blocks"])
    events = load_timeline_events(project_id)
    by_id = {e["event_id"]: e for e in events}
    index = load_timeline_index(project_id)
    cout = index.get("causal_out") or {}
    cin = index.get("causal_in") or {}

    if not cout and not cin:
        for edge in load_timeline_edges(project_id):
            rel = edge.get("relation")
            if rel not in allow:
                continue
            cout.setdefault(edge["from_event_id"], []).append({
                "relation": rel,
                "other_event_id": edge["to_event_id"],
            })
            cin.setdefault(edge["to_event_id"], []).append({
                "relation": rel,
                "other_event_id": edge["from_event_id"],
            })

    ordered_ids: list[str] = []
    seen: set[str] = set()

    def add_id(eid: str) -> None:
        if eid in by_id and eid not in seen:
            seen.add(eid)
            ordered_ids.append(eid)

    frontier = [e["event_id"] for e in seed_events]
    for eid in frontier:
        add_id(eid)

    for _ in range(depth):
        nxt_frontier: list[str] = []
        for eid in frontier:
            for item in cout.get(eid, []):
                if item.get("relation") in allow:
                    oid = item.get("other_event_id")
                    if oid and oid not in seen:
                        add_id(oid)
                        nxt_frontier.append(oid)
            for item in cin.get(eid, []):
                if item.get("relation") in allow:
                    oid = item.get("other_event_id")
                    if oid and oid not in seen:
                        add_id(oid)
                        nxt_frontier.append(oid)
        frontier = nxt_frontier
        if not frontier:
            break

    return [by_id[eid] for eid in ordered_ids]


def get_causal_edges_for_events(
    project_id: str,
    event_ids: list[str],
    min_confidence: float = 0.68,
) -> list[dict]:
    idset = set(event_ids)
    edges = [
        e for e in load_timeline_edges(project_id)
        if e.get("relation") in {"causes", "enables", "blocks"}
        and (e.get("from_event_id") in idset or e.get("to_event_id") in idset)
        and float(e.get("confidence") or 0) >= min_confidence
    ]
    edges.sort(key=lambda e: (-float(e.get("confidence") or 0), e.get("from_chapter_no") or 0))
    return edges


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
    if query_type == "sequence_first":
        seeds = filtered[:seed_limit]
    else:
        # 全文覆盖：按章节带轮转取种子，避免因果/脉络题总困在前几十章
        seeds = _pick_seeds_across_chapters(filtered, seed_limit)

    if chain_radius > 0 and seeds:
        chained = expand_follows_chain(project_id, seeds, radius=chain_radius)
        # 时间线/顺序类问题再叠一层因果邻居，便于回答「为什么/怎么发展到」
        if query_type in {"timeline_summary", "sequence_order", "sequence_first", "causal_why"}:
            depth = 2 if query_type == "causal_why" else 1
            chained = expand_causal_neighbors(project_id, chained, depth=depth)
        chained = sorted(chained, key=lambda e: (e["chapter_no"], e.get("chunk_id", ""), e["event_id"]))
        return chained[:limit]

    return seeds[:limit]


def _pick_seeds_across_chapters(events: list[dict], limit: int, band_size: int = 100) -> list[dict]:
    if len(events) <= limit:
        return list(events)
    buckets: dict[int, list[dict]] = {}
    for evt in events:
        band = int(evt.get("chapter_no", 1) or 1) // band_size
        buckets.setdefault(band, []).append(evt)
    # 每带内保持章节升序；轮转各带，兼顾全书
    for band in buckets:
        buckets[band].sort(key=lambda e: (e["chapter_no"], e.get("chunk_id", ""), e["event_id"]))
    bands = sorted(buckets.keys())
    picked: list[dict] = []
    seen: set[str] = set()
    while len(picked) < limit:
        progressed = False
        for band in bands:
            if not buckets.get(band):
                continue
            evt = buckets[band].pop(0)
            eid = evt.get("event_id")
            if eid in seen:
                continue
            seen.add(eid)
            picked.append(evt)
            progressed = True
            if len(picked) >= limit:
                break
        if not progressed:
            break
    return picked
