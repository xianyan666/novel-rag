"""从 chunks.jsonl 规则抽取通用叙事事件，并生成 follows 边。

v2.1：收紧规则，降低鬼眼/同章/论坛噪声。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import data_dir

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

# 更严的模式：避免单字/高频名词裸匹配
EVENT_PATTERNS: dict[str, list[str]] = {
    "encounter": [
        "遇到了鬼", "遇见了鬼", "撞见了鬼", "发现了鬼", "出现了鬼",
        "鬼出现了", "鬼突然出现", "厉鬼出现", "眼前出现一只",
        "遇到了", "遇见了", "撞见",
    ],
    "conflict": [
        "对峙", "交手", "厮杀", "搏斗", "打斗", "开战",
        "出手攻击", "发起攻击", "互相厮杀", "战斗开始",
        "和厉鬼交手", "与鬼搏斗",
    ],
    "rule_reveal": [
        "规则是", "鬼域规则", "存在一条规则", "这条规则",
        "一旦违反", "违反规则", "必须遵守", "不能做的事",
        "杀人规则", "鬼的规则",
    ],
    "ability_change": [
        # 不再用裸「鬼眼」——必须是变化/掌控类短语
        "能力觉醒", "能力提升", "能力变化", "能力失控",
        "获得能力", "觉醒了", "掌控了", "强化了",
        "鬼眼睁开", "鬼眼复苏", "鬼眼觉醒", "掌控鬼眼",
        "使用鬼眼", "催动鬼眼", "鬼眼之力",
        "驭鬼成功", "成为驭鬼者",
    ],
    "death_or_seal": [
        "被杀死", "已经死亡", "死去了", "被封印", "封印住",
        "镇压住", "彻底消失", "灭杀", "粉身碎骨",
        "死于厉鬼", "被鬼杀死", "厉鬼复苏而死",
    ],
    "alliance_or_break": [
        "达成合作", "一起联手", "结盟", "一起行动",
        "决裂", "背叛了", "交易达成", "谈妥了", "反目",
        "联手合作", "联手抓鬼",
    ],
    "clue": [
        "发现线索", "找到线索", "得知真相", "原来如此",
        "真相是", "这就对了", "查出了",
    ],
    "state_change": [
        "进入鬼域", "离开鬼域", "陷入昏迷", "苏醒过来",
        "失去意识", "恢复意识", "失控了",
        "进入衍生世界", "回归乐园", "返回轮回乐园",
        "传送开始", "世界结算",
    ],
}

# 证据窗口命中这些，整条丢弃（论坛/转述噪声）
NOISE_EVIDENCE_MARKERS = [
    "帖子", "回帖", "楼主", "论坛", "点击进入", "更多精彩小说",
    "名侦探动画", "报了警", "向警方",
]

# 同章每种类型最多保留几条（按首次出现）
MAX_PER_CHAPTER_TYPE = 1


def _load_character_names(project_id: str) -> list[str]:
    """只取人物/厉鬼角色，排除 item/concept（鬼眼、鬼域）。"""
    names: list[str] = []
    seed_path = ROOT / "config" / "entities.seed.json"
    if seed_path.exists():
        try:
            for item in json.loads(seed_path.read_text(encoding="utf-8")):
                et = item.get("type", "")
                if et not in {"character"}:
                    continue
                names.append(item.get("name", ""))
                names.extend(item.get("aliases", []))
        except Exception:
            pass
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


def _is_noisy_evidence(evidence: str) -> bool:
    return any(m in evidence for m in NOISE_EVIDENCE_MARKERS)


def _summarize(event_type: str, keyword: str, evidence: str) -> str:
    label = EVENT_TYPE_LABELS.get(event_type, event_type)
    snippet = re.sub(r"\s+", " ", evidence).strip()
    # 尽量从关键词附近起摘要
    idx = snippet.find(keyword)
    if idx > 0:
        snippet = snippet[max(0, idx - 8):]
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


def _dedupe_events(events: list[dict]) -> list[dict]:
    """同章同类型只留第一条；同章同 pattern 也去重。"""
    kept: list[dict] = []
    chapter_type_count: dict[tuple[int, str], int] = {}
    chapter_pattern: set[tuple[int, str, str]] = set()
    for evt in events:
        ch = evt["chapter_no"]
        et = evt["event_type"]
        pat = evt.get("matched_pattern") or ""
        key_ct = (ch, et)
        key_cp = (ch, et, pat)
        if chapter_type_count.get(key_ct, 0) >= MAX_PER_CHAPTER_TYPE:
            continue
        if key_cp in chapter_pattern:
            continue
        chapter_type_count[key_ct] = chapter_type_count.get(key_ct, 0) + 1
        chapter_pattern.add(key_cp)
        kept.append(evt)
    return kept


def _build_follows_edges(events: list[dict], project_id: str) -> list[dict]:
    edges: list[dict] = []
    for i in range(len(events) - 1):
        a = events[i]
        b = events[i + 1]
        # 跨章过远的相邻事件降低置信度，但仍标 follows（非因果）
        gap = abs(int(b["chapter_no"]) - int(a["chapter_no"]))
        conf = 0.6 if gap <= 1 else (0.45 if gap <= 5 else 0.3)
        edges.append({
            "edge_id": f"{project_id}_edge_{i+1:06d}",
            "project_id": project_id,
            "from_event_id": a["event_id"],
            "to_event_id": b["event_id"],
            "relation": "follows",
            "from_chapter_no": a["chapter_no"],
            "to_chapter_no": b["chapter_no"],
            "evidence": f"叙事顺序：第{a['chapter_no']}章 → 第{b['chapter_no']}章",
            "confidence": conf,
            "extract_method": "order",
        })
    return edges


def build_timeline(project_id: str) -> dict:
    dd = data_dir(project_id)
    chunks_path = dd / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {chunks_path}")

    names = _load_character_names(project_id)
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
                    evidence = extract_evidence(text, pat)
                    if _is_noisy_evidence(evidence):
                        continue
                    # 「遇到了/遇见了」过宽：要求附近像遭遇（鬼/人/厉）
                    if pat in {"遇到了", "遇见了", "撞见"}:
                        window = evidence
                        if not any(x in window for x in ("鬼", "厉", "老人", "人影", "尸体")):
                            continue
                    seen.add(dedup_key)
                    subjects = _extract_subjects(text, names)
                    events.append({
                        "event_id": f"{project_id}_evt_{len(events)+1:06d}",
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
                        "confidence": 0.75,
                        "extract_method": "rule_v2.1",
                    })
                    break

    events.sort(key=lambda e: (e["chapter_no"], e["chunk_id"], e["event_id"]))
    events = _dedupe_events(events)
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
        "extract_version": "rule_v2.1",
        "edge_relation_default": "follows",
        "event_types": sorted(EVENT_TYPE_LABELS.keys()),
        "by_event_type": by_event_type,
        "by_subject": by_subject,
        "by_chapter": by_chapter,
        "follows_next": follows_next,
        "follows_prev": follows_prev,
        "event_count": len(events),
        "edge_count": len(edges),
        "tighten_notes": [
            "no bare 鬼眼 for ability_change",
            "subjects = character seeds only",
            "max 1 event per chapter+type",
            "drop forum/noise evidence markers",
        ],
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
        description="Build tightened literary timeline events + follows edges"
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
