"""从 chunks.jsonl 规则抽取通用叙事事件，并生成 follows 边。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import data_dir

# 通用文学/网文事件类型（不再绑定《轮回乐园》术语）
EVENT_TYPE_LABELS = {
    "encounter": "遭遇",
    "conflict": "冲突",
    "rule_reveal": "规则揭示",
    "ability_change": "能力变化",
    "death_or_seal": "死亡或封印",
    "alliance_or_break": "结盟或决裂",
    "clue": "线索",
    "state_change": "状态变化",
    "other": "其他",
}

# 模式按优先级排列；同一 chunk 每种类型最多一条
EVENT_PATTERNS: dict[str, list[str]] = {
    "encounter": [
        "遇到了", "遇见了", "撞见", "碰见", "发现了鬼", "出现了鬼",
        "鬼出现", "对面走来", "眼前出现", "突然出现",
    ],
    "conflict": [
        "对峙", "交手", "厮杀", "搏斗", "打斗", "开战", "出手攻击",
        "发起攻击", "互相厮杀", "杀气", "战斗开始",
    ],
    "rule_reveal": [
        "规则是", "鬼域规则", "禁忌", "一旦违反", "违反规则",
        "存在一条规则", "这条规则", "不能做的事", "必须遵守",
    ],
    "ability_change": [
        "能力觉醒", "鬼眼", "掌控了", "能力提升", "能力变化",
        "觉醒了", "获得能力", "强化了", "能力失控",
    ],
    "death_or_seal": [
        "被杀死", "已经死亡", "死去了", "身亡", "封印住", "被封印",
        "镇压住", "彻底消失", "灭杀", "粉身碎骨",
    ],
    "alliance_or_break": [
        "达成合作", "联手", "结盟", "一起行动", "决裂", "背叛了",
        "交易达成", "谈妥了", "反目",
    ],
    "clue": [
        "发现线索", "找到线索", "得知真相", "原来如此", "真相是",
        "获悉", "得到消息", "查出",
    ],
    "state_change": [
        "进入鬼域", "离开鬼域", "陷入昏迷", "苏醒过来", "失去意识",
        "恢复意识", "陷入恐慌", "失控了", "平静下来",
        # 兼容旧乐园类叙述，映射为状态变化而非独立类型
        "进入衍生世界", "进入世界", "回归乐园", "返回轮回乐园",
        "传送开始", "世界结算",
    ],
}


def _load_name_lexicon(project_id: str) -> list[str]:
    names: list[str] = []
    seed_path = ROOT / "config" / "entities.seed.json"
    if seed_path.exists():
        try:
            for item in json.loads(seed_path.read_text(encoding="utf-8")):
                names.append(item.get("name", ""))
                names.extend(item.get("aliases", []))
        except Exception:
            pass
    # 长名优先，减少短别名误伤
    names = [n for n in names if n]
    names.sort(key=len, reverse=True)
    return names


def extract_evidence(text: str, keyword: str, max_len: int = 300) -> str:
    idx = text.find(keyword)
    if idx < 0:
        return text[:max_len]
    start = max(0, idx - 50)
    end = min(len(text), idx + len(keyword) + 100)
    evidence = text[start:end].strip()
    if len(evidence) > max_len:
        evidence = evidence[:max_len]
    return evidence


def _summarize(event_type: str, keyword: str, evidence: str) -> str:
    label = EVENT_TYPE_LABELS.get(event_type, event_type)
    # 取证据首句式片段，去掉换行
    snippet = re.sub(r"\s+", " ", evidence).strip()
    if len(snippet) > 72:
        snippet = snippet[:72].rstrip() + "…"
    if not snippet:
        return f"{label}（关键词：{keyword}）"
    return f"{label}：{snippet}"


def _extract_subjects(text: str, names: list[str], limit: int = 4) -> list[str]:
    found: list[str] = []
    for name in names:
        if name and name in text and name not in found:
            found.append(name)
            if len(found) >= limit:
                break
    return found


def _build_follows_edges(events: list[dict], project_id: str) -> list[dict]:
    """按章节/chunk 顺序，将相邻事件连成 follows 边（暂不做因果断言）。"""
    edges: list[dict] = []
    for i in range(len(events) - 1):
        a = events[i]
        b = events[i + 1]
        edge_id = f"{project_id}_edge_{i+1:06d}"
        edges.append({
            "edge_id": edge_id,
            "project_id": project_id,
            "from_event_id": a["event_id"],
            "to_event_id": b["event_id"],
            "relation": "follows",
            "from_chapter_no": a["chapter_no"],
            "to_chapter_no": b["chapter_no"],
            "evidence": (
                f"叙事顺序：第{a['chapter_no']}章 → 第{b['chapter_no']}章"
            ),
            "confidence": 0.55,
            "extract_method": "order",
        })
    return edges


def build_timeline(project_id: str) -> dict:
    dd = data_dir(project_id)
    chunks_path = dd / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {chunks_path}")

    names = _load_name_lexicon(project_id)
    events: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            chapter_no = chunk["chapter_no"]
            chapter_title = chunk.get("chapter_title", "")

            for event_type, patterns in EVENT_PATTERNS.items():
                for pat in patterns:
                    if pat not in text:
                        continue
                    dedup_key = (chunk_id, event_type)
                    if dedup_key in seen:
                        break
                    seen.add(dedup_key)

                    evidence = extract_evidence(text, pat)
                    subjects = _extract_subjects(text, names)
                    evt_id = f"{project_id}_evt_{len(events)+1:06d}"
                    events.append({
                        "event_id": evt_id,
                        "project_id": project_id,
                        "event_type": event_type,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "chunk_id": chunk_id,
                        "subjects": subjects,
                        "objects": [],
                        "world_name": None,
                        "matched_pattern": pat,
                        "event_summary": _summarize(event_type, pat, evidence),
                        "evidence": evidence,
                        "confidence": 0.7,
                        "extract_method": "rule",
                    })
                    break

    events.sort(key=lambda e: (e["chapter_no"], e["chunk_id"], e["event_id"]))
    # 重新编号，保证顺序稳定
    for i, evt in enumerate(events, start=1):
        evt["event_id"] = f"{project_id}_evt_{i:06d}"

    edges = _build_follows_edges(events, project_id)

    events_path = dd / "timeline_events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    edges_path = dd / "timeline_edges.jsonl"
    with open(edges_path, "w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, ensure_ascii=False) + "\n")

    by_event_type: dict[str, list[str]] = {}
    by_subject: dict[str, list[str]] = {}
    by_chapter: dict[str, list[str]] = {}
    follows_next: dict[str, str] = {}
    follows_prev: dict[str, str] = {}

    for evt in events:
        eid = evt["event_id"]
        by_event_type.setdefault(evt["event_type"], []).append(eid)
        by_chapter.setdefault(str(evt["chapter_no"]), []).append(eid)
        for s in evt.get("subjects", []):
            by_subject.setdefault(s, []).append(eid)

    for edge in edges:
        if edge["relation"] != "follows":
            continue
        follows_next[edge["from_event_id"]] = edge["to_event_id"]
        follows_prev[edge["to_event_id"]] = edge["from_event_id"]

    index = {
        "project_id": project_id,
        "schema_version": 2,
        "edge_relation_default": "follows",
        "event_types": sorted(EVENT_TYPE_LABELS.keys()),
        "by_event_type": by_event_type,
        "by_subject": by_subject,
        "by_chapter": by_chapter,
        "follows_next": follows_next,
        "follows_prev": follows_prev,
        "event_count": len(events),
        "edge_count": len(edges),
    }
    index_path = dd / "timeline_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "event_count": len(events),
        "edge_count": len(edges),
        "events_path": str(events_path),
        "edges_path": str(edges_path),
        "index_path": str(index_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build generic literary timeline events + follows edges"
    )
    parser.add_argument("--project", required=True, help="Project ID")
    args = parser.parse_args()

    result = build_timeline(args.project)
    print(f"Timeline built: {result['event_count']} events, {result['edge_count']} follows edges")
    print(f"  Events: {result['events_path']}")
    print(f"  Edges:  {result['edges_path']}")
    print(f"  Index:  {result['index_path']}")


if __name__ == "__main__":
    main()
