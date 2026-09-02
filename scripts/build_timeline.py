"""从 chunks.jsonl 规则抽取时间线事件。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import data_dir

EVENT_PATTERNS = {
    "world_entry": [
        "进入衍生世界", "进入世界", "新的衍生世界", "猎杀者即将进入",
        "传送开始", "传送中", "世界难度", "世界之源",
    ],
    "world_return": [
        "回归乐园", "返回轮回乐园", "回到轮回乐园", "世界结算",
        "开始结算", "任务完成", "传送回",
    ],
    "task_start": [
        "主线任务", "支线任务", "隐藏任务", "天赋觉醒任务",
        "任务简介", "任务难度", "任务奖励", "任务惩罚",
    ],
    "task_complete": [
        "任务完成", "主线任务已完成", "支线任务已完成", "结算奖励",
    ],
}


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


def build_timeline(project_id: str) -> dict:
    dd = data_dir(project_id)
    chunks_path = dd / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {chunks_path}")

    events = []
    seen = set()

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            chapter_no = chunk["chapter_no"]
            chapter_title = chunk.get("chapter_title", "")

            for event_type, patterns in EVENT_PATTERNS.items():
                for pat in patterns:
                    if pat in text:
                        dedup_key = (chunk_id, event_type)
                        if dedup_key in seen:
                            break
                        seen.add(dedup_key)

                        evt_id = f"{project_id}_evt_{len(events)+1:06d}"
                        events.append({
                            "event_id": evt_id,
                            "project_id": project_id,
                            "event_type": event_type,
                            "chapter_no": chapter_no,
                            "chapter_title": chapter_title,
                            "chunk_id": chunk_id,
                            "subjects": [],
                            "objects": [],
                            "world_name": None,
                            "event_summary": f"检测到{event_type}事件。",
                            "evidence": extract_evidence(text, pat),
                            "confidence": 0.7,
                            "extract_method": "rule",
                        })
                        break

    events.sort(key=lambda e: (e["chapter_no"], e["chunk_id"]))

    events_path = dd / "timeline_events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    by_event_type = {}
    by_subject = {}
    by_chapter = {}
    for evt in events:
        eid = evt["event_id"]
        et = evt["event_type"]
        ch = str(evt["chapter_no"])

        by_event_type.setdefault(et, []).append(eid)
        for s in evt.get("subjects", []):
            by_subject.setdefault(s, []).append(eid)
        by_chapter.setdefault(ch, []).append(eid)

    index = {
        "project_id": project_id,
        "by_event_type": by_event_type,
        "by_subject": by_subject,
        "by_chapter": by_chapter,
    }
    index_path = dd / "timeline_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "event_count": len(events),
        "events_path": str(events_path),
        "index_path": str(index_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Build timeline index")
    parser.add_argument("--project", required=True, help="Project ID")
    args = parser.parse_args()

    result = build_timeline(args.project)
    print(f"Timeline built: {result['event_count']} events")
    print(f"  Events: {result['events_path']}")
    print(f"  Index:  {result['index_path']}")


if __name__ == "__main__":
    main()
