"""Build conservative world/arc candidates from timeline boundary evidence."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import data_dir

MIN_ENTRY_GAP = 20
WORLD_SEED_PATH = ROOT / "config" / "worlds.seed.json"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_world_seeds() -> dict[str, dict]:
    if not WORLD_SEED_PATH.exists():
        return {}
    seeds = json.loads(WORLD_SEED_PATH.read_text(encoding="utf-8"))
    return {seed["name"].casefold(): seed for seed in seeds}


def strongest_entry_signal(event: dict) -> tuple[float, str] | None:
    evidence = event.get("evidence", "")
    # Generic prose such as "进入衍生世界后" occurs throughout an arc. A
    # boundary must look like an actual system notification, with the world
    # difficulty/source fields that accompany an entry.
    if "世界难度" in evidence and "世界之源" in evidence:
        if re.search(r"进入(?:衍生)?世界[；;：:]", evidence):
            return 0.98, "entry_system_prompt"
        if "【" in evidence and ("传送" in evidence or "衍生世界" in evidence):
            return 0.88, "entry_system_fields"
    return None


def is_return_event(event: dict) -> bool:
    evidence = event.get("evidence", "")
    return (
        "衍生世界：" in evidence
        and ("综合评价" in evidence or "结算" in evidence)
        and "【" in evidence
    )


def select_entry_events(events: list[dict]) -> list[tuple[dict, float, str]]:
    candidates = []
    for event in events:
        if event.get("event_type") != "world_entry":
            continue
        signal = strongest_entry_signal(event)
        if signal:
            confidence, matched_signal = signal
            candidates.append((event, confidence, matched_signal))

    candidates.sort(key=lambda item: (item[0]["chapter_no"], -item[1]))
    selected: list[tuple[dict, float, str]] = []
    for candidate in candidates:
        event = candidate[0]
        if selected and event["chapter_no"] - selected[-1][0]["chapter_no"] < MIN_ENTRY_GAP:
            if candidate[1] > selected[-1][1]:
                selected[-1] = candidate
            continue
        selected.append(candidate)
    return selected


def extract_world_name(evidence: str) -> str | None:
    patterns = [
        r"进入(?:衍生)?世界[；;：:]\s*[『「【\[]?([^』」】\]\n，。]{2,32})",
        r"衍生世界[；;：:]\s*[『「【\[]?([^』」】\]\n，。]{2,32})",
        r"世界名称[：:\s]*[『「【\[]?([^』」】\]\n，。]{2,32})",
    ]
    for pattern in patterns:
        match = re.search(pattern, evidence)
        if not match:
            continue
        name = match.group(1).strip(" ：:，。\"'")
        if name and not any(token in name for token in ("难度", "之源", "传送", "任务", "前", "后")):
            return name
    return None


def first_return_after(events: list[dict], start_chapter: int, next_entry_chapter: int) -> dict | None:
    for event in events:
        chapter_no = event.get("chapter_no", 0)
        if chapter_no < start_chapter:
            continue
        if chapter_no >= next_entry_chapter:
            return None
        if event.get("event_type") == "world_return" and is_return_event(event):
            return event
    return None


def build_world_index(project_id: str) -> dict:
    dd = data_dir(project_id)
    chapters = load_jsonl(dd / "chapters.jsonl")
    events = load_jsonl(dd / "timeline_events.jsonl")
    if not chapters:
        raise FileNotFoundError(f"chapters.jsonl not found at {dd}")
    if not events:
        raise FileNotFoundError(f"timeline_events.jsonl not found at {dd}. Build timeline first.")

    chapters_by_number = {}
    for chapter in chapters:
        chapters_by_number.setdefault(chapter["chapter_no"], chapter)
    chapters = sorted(chapters_by_number.values(), key=lambda chapter: chapter["chapter_no"])
    events.sort(key=lambda event: (event.get("chapter_no", 0), event.get("chunk_id", "")))
    first_chapter = chapters[0]["chapter_no"]
    last_chapter = chapters[-1]["chapter_no"]
    entries = select_entry_events(events)
    world_seeds = load_world_seeds()

    worlds: list[dict] = []
    ranges: list[dict] = []
    cursor = first_chapter
    world_sequence = 0
    for sequence, (entry, confidence, signal) in enumerate(entries, start=1):
        start_chapter = entry["chapter_no"]
        # A second entry inside an already closed candidate world is more
        # likely a timeline false positive than a new arc boundary.
        if start_chapter < cursor:
            continue
        world_sequence += 1
        if start_chapter > cursor:
            ranges.append({
                "world_id": "outside_world",
                "world_name": "乐园/现实过渡",
                "start_chapter": cursor,
                "end_chapter": start_chapter - 1,
                "confidence": 0.50,
            })

        next_entry = entries[sequence][0]["chapter_no"] if sequence < len(entries) else last_chapter + 1
        return_event = first_return_after(events, start_chapter, next_entry)
        end_chapter = (return_event or {}).get("chapter_no", next_entry - 1)
        end_chapter = min(end_chapter, last_chapter)
        name = extract_world_name(entry.get("evidence", ""))
        seed = world_seeds.get((name or "").casefold(), {})
        world_id = f"{project_id}_world_{world_sequence:03d}"
        world = {
            "world_id": world_id,
            "project_id": project_id,
            "name": name or f"未命名世界候选 {world_sequence}",
            "aliases": seed.get("aliases", []),
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            "entry_event_id": entry.get("event_id"),
            "exit_event_id": return_event.get("event_id") if return_event else None,
            "entry_evidence": entry.get("evidence", ""),
            "exit_evidence": return_event.get("evidence", "") if return_event else "",
            "boundary_signal": signal,
            "confidence": round(confidence if return_event else confidence * 0.85, 2),
            "status": "candidate",
            "extract_method": "timeline_rule",
        }
        worlds.append(world)
        ranges.append({
            "world_id": world_id,
            "world_name": world["name"],
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            "confidence": world["confidence"],
        })
        cursor = max(cursor, end_chapter + 1)

    if cursor <= last_chapter:
        ranges.append({
            "world_id": "outside_world",
            "world_name": "乐园/现实过渡",
            "start_chapter": cursor,
            "end_chapter": last_chapter,
            "confidence": 0.50,
        })

    chapter_map = []
    for chapter in chapters:
        chapter_no = chapter["chapter_no"]
        mapping = next(
            (item for item in ranges if item["start_chapter"] <= chapter_no <= item["end_chapter"]),
            {"world_id": "outside_world", "world_name": "乐园/现实过渡", "confidence": 0.50},
        )
        chapter_map.append({
            "project_id": project_id,
            "chapter_no": chapter_no,
            "world_id": mapping["world_id"],
            "world_name": mapping["world_name"],
            "confidence": mapping["confidence"],
        })

    worlds_path = dd / "worlds.jsonl"
    chapter_map_path = dd / "chapter_world_map.jsonl"
    with open(worlds_path, "w", encoding="utf-8") as f:
        for world in worlds:
            f.write(json.dumps(world, ensure_ascii=False) + "\n")
    with open(chapter_map_path, "w", encoding="utf-8") as f:
        for mapping in chapter_map:
            f.write(json.dumps(mapping, ensure_ascii=False) + "\n")

    index = {
        "project_id": project_id,
        "world_count": len(worlds),
        "candidate_count": sum(world["status"] == "candidate" for world in worlds),
        "by_id": {world["world_id"]: world for world in worlds},
        "by_name": {world["name"]: world["world_id"] for world in worlds if not world["name"].startswith("未命名")},
        "chapter_to_world": {str(item["chapter_no"]): item["world_id"] for item in chapter_map},
    }
    index_path = dd / "world_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "world_count": len(worlds),
        "candidate_count": index["candidate_count"],
        "mapped_chapter_count": len(chapter_map),
        "worlds_path": str(worlds_path),
        "chapter_map_path": str(chapter_map_path),
        "index_path": str(index_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build world/arc index")
    parser.add_argument("--project", required=True, help="Project ID")
    args = parser.parse_args()
    result = build_world_index(args.project)
    print(f"World index built: {result['world_count']} candidates")
    print(f"  Mapped chapters: {result['mapped_chapter_count']}")
    print(f"  Worlds: {result['worlds_path']}")
    print(f"  Map:    {result['chapter_map_path']}")


if __name__ == "__main__":
    main()
