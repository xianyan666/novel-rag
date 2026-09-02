"""从 chunks.jsonl + seeds 规则抽取实体、提及、时间线和关系。"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import data_dir

# ---------------------------------------------------------------------------
# Entity timeline event word patterns
# ---------------------------------------------------------------------------

ITEM_EVENT_WORDS = {
    "item_obtained": ["获得", "拿到", "入手", "得到"],
    "item_upgrade": ["强化", "升级", "品质提升", "晋升"],
    "item_repair": ["修复", "重铸"],
    "item_evolution": ["吞噬", "融合", "进化"],
    "status_changed": ["破损", "损毁"],
}

SKILL_EVENT_WORDS = {
    "skill_obtained": ["获得", "掌握"],
    "skill_upgrade": ["提升", "升级"],
    "skill_awakened": ["觉醒", "激活", "突破"],
}

CHARACTER_EVENT_WORDS = {
    "character_intro": ["登场", "出现"],
    "character_interaction": ["合作", "交易", "交手", "追杀", "谈判", "遇到"],
    "faction_joined": ["加入"],
    "faction_left": ["背叛", "离开"],
    "relation_changed": ["背叛", "离开"],
}

# ---------------------------------------------------------------------------
# Relation extraction word patterns
# ---------------------------------------------------------------------------

RELATION_WORDS = {
    "owns": ["持有", "拿着", "装备", "佩戴"],
    "uses": ["使用", "施展"],
    "upgrades": ["强化", "升级", "修复"],
    "member_of": ["加入", "成员"],
    "ally_of": ["合作", "盟友", "队友"],
    "enemy_of": ["敌人", "追杀", "交手"],
    "meets": ["遇到", "见到"],
    "interacts_with": ["交易", "谈判", "委托"],
    "located_in": ["位于", "来自"],
}


def stable_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


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


def load_seeds(project_id: str) -> list[dict]:
    seed_path = ROOT / "config" / "entities.seed.json"
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")
    return json.loads(seed_path.read_text(encoding="utf-8"))


def build_entity_id(project_id: str, entity_type: str, name: str) -> str:
    slug = stable_hash(name)
    return f"{project_id}_{entity_type}_{slug}"


def match_entity_in_text(text: str, name: str, aliases: list[str]) -> str | None:
    if name in text:
        return name
    for alias in aliases:
        if alias in text:
            return alias
    return None


def entity_windows(text: str, name: str, aliases: list[str], window: int = 120) -> list[str]:
    """Extract text windows around each occurrence of entity name or aliases."""
    windows = []
    all_names = [name] + aliases
    for alias in all_names:
        start = 0
        while True:
            pos = text.find(alias, start)
            if pos < 0:
                break
            w_start = max(0, pos - window)
            w_end = min(len(text), pos + len(alias) + window)
            windows.append(text[w_start:w_end])
            start = pos + len(alias)
    return windows


def detect_timeline_event(text: str, entity_type: str, name: str = "", aliases: list[str] | None = None) -> tuple[str, float] | None:
    if entity_type == "item":
        word_map = ITEM_EVENT_WORDS
    elif entity_type == "skill":
        word_map = SKILL_EVENT_WORDS
    elif entity_type == "character":
        word_map = CHARACTER_EVENT_WORDS
    else:
        return None

    # v0.3.1: Use nearby window matching when name/aliases provided
    if name and aliases is not None:
        windows = entity_windows(text, name, aliases, window=120)
        if not windows:
            return None
        for event_type, words in word_map.items():
            for w in words:
                for win in windows:
                    if w in win:
                        return event_type, 0.75
        return None

    # Fallback: chunk-level matching (legacy)
    for event_type, words in word_map.items():
        for w in words:
            if w in text:
                return event_type, 0.75
    return None


def detect_relation(text: str) -> tuple[str, float] | None:
    for rel_type, words in RELATION_WORDS.items():
        for w in words:
            if w in text:
                return rel_type, 0.70
    return None


def build_entities(project_id: str) -> dict:
    dd = data_dir(project_id)
    chunks_path = dd / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {chunks_path}")

    seeds = load_seeds(project_id)

    # Build seed lookup: name -> seed info
    seed_lookup: dict[str, dict] = {}
    for seed in seeds:
        entity_id = build_entity_id(project_id, seed["type"], seed["name"])
        seed_lookup[seed["name"]] = {
            "entity_id": entity_id,
            "name": seed["name"],
            "type": seed["type"],
            "subtype": seed.get("subtype", ""),
            "aliases": seed.get("aliases", []),
        }
        for alias in seed.get("aliases", []):
            seed_lookup[alias] = seed_lookup[seed["name"]]

    # Phase 1: Scan chunks for mentions
    mentions: list[dict] = []
    mention_dedup: set[tuple[str, str]] = set()  # (chunk_id, entity_id)

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            chapter_no = chunk["chapter_no"]
            chapter_title = chunk.get("chapter_title", "")

            for name_key, info in seed_lookup.items():
                matched = match_entity_in_text(text, info["name"], info["aliases"])
                if not matched:
                    continue

                dedup_key = (chunk_id, info["entity_id"])
                if dedup_key in mention_dedup:
                    continue
                mention_dedup.add(dedup_key)

                mention_id = f"{project_id}_m_{len(mentions)+1:06d}"
                mentions.append({
                    "mention_id": mention_id,
                    "entity_id": info["entity_id"],
                    "project_id": project_id,
                    "name": info["name"],
                    "matched_alias": matched,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "chunk_id": chunk_id,
                    "mention_type": "explicit",
                    "evidence": extract_evidence(text, matched),
                    "confidence": 0.95,
                })

    mentions.sort(key=lambda m: (m["chapter_no"], m["chunk_id"]))

    # Phase 2: Build entities from mentions
    entity_map: dict[str, dict] = {}
    for m in mentions:
        eid = m["entity_id"]
        if eid not in entity_map:
            info = None
            for seed in seeds:
                sid = build_entity_id(project_id, seed["type"], seed["name"])
                if sid == eid:
                    info = seed
                    break
            entity_map[eid] = {
                "entity_id": eid,
                "project_id": project_id,
                "name": m["name"],
                "type": info["type"] if info else "unknown",
                "subtype": info.get("subtype", "") if info else "",
                "aliases": info.get("aliases", []) if info else [],
                "first_seen_chapter": m["chapter_no"],
                "first_seen_title": m["chapter_title"],
                "first_seen_chunk_id": m["chunk_id"],
                "description": "",
                "confidence": 0.92,
                "status": "candidate",
                "extract_method": "seed+rule",
            }
        else:
            if m["chapter_no"] < entity_map[eid]["first_seen_chapter"]:
                entity_map[eid]["first_seen_chapter"] = m["chapter_no"]
                entity_map[eid]["first_seen_title"] = m["chapter_title"]
                entity_map[eid]["first_seen_chunk_id"] = m["chunk_id"]

    entities = list(entity_map.values())
    entities.sort(key=lambda e: e["entity_id"])

    # Build chunk -> entity map for timeline and relations
    chunk_entities: dict[str, list[dict]] = {}
    for m in mentions:
        chunk_entities.setdefault(m["chunk_id"], []).append(m)

    # Phase 3: Build entity timeline
    timeline_events: list[dict] = []
    timeline_dedup: set[tuple[str, str]] = set()  # (entity_id, chunk_id)
    # v0.3.1: Also dedup by (entity_id, chapter_no, event_type) for chapter-level dedup
    chapter_event_dedup: dict[tuple[str, int, str], dict] = {}  # key -> best event

    # Add first_seen for every entity
    for ent in entities:
        evt_id = f"{project_id}_et_{len(timeline_events)+1:06d}"
        timeline_events.append({
            "entity_event_id": evt_id,
            "entity_id": ent["entity_id"],
            "project_id": project_id,
            "entity_name": ent["name"],
            "event_type": "first_seen",
            "chapter_no": ent["first_seen_chapter"],
            "chapter_title": ent["first_seen_title"],
            "chunk_id": ent["first_seen_chunk_id"],
            "summary": f"{ent['name']}首次出现。",
            "evidence": "",
            "related_entities": [],
            "confidence": 0.90,
            "extract_method": "rule",
        })

    # Scan mentions for timeline events
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            chapter_no = chunk["chapter_no"]
            chapter_title = chunk.get("chapter_title", "")

            if chunk_id not in chunk_entities:
                continue

            for m in chunk_entities[chunk_id]:
                eid = m["entity_id"]
                dedup_key = (eid, chunk_id)
                if dedup_key in timeline_dedup:
                    continue

                ent_info = entity_map.get(eid, {})
                ent_type = ent_info.get("type", "unknown")
                ent_name = ent_info.get("name", "")
                ent_aliases = ent_info.get("aliases", [])
                # v0.3.1: Use nearby window matching
                result = detect_timeline_event(text, ent_type, ent_name, ent_aliases)
                if not result:
                    continue

                event_type, confidence = result
                timeline_dedup.add(dedup_key)

                # v0.3.1: Chapter-level dedup - keep only highest confidence per (entity_id, chapter_no, event_type)
                dedup_chapter_key = (eid, chapter_no, event_type)
                if dedup_chapter_key in chapter_event_dedup:
                    existing = chapter_event_dedup[dedup_chapter_key]
                    if confidence <= existing["confidence"]:
                        continue
                    # Replace with higher confidence event
                    # Remove old event from timeline_events
                    timeline_events = [e for e in timeline_events if e["entity_event_id"] != existing["entity_event_id"]]

                # Find related entities in same chunk
                related = [
                    om["name"] for om in chunk_entities[chunk_id]
                    if om["entity_id"] != eid
                ]

                evt_id = f"{project_id}_et_{len(timeline_events)+1:06d}"
                new_event = {
                    "entity_event_id": evt_id,
                    "entity_id": eid,
                    "project_id": project_id,
                    "entity_name": m["name"],
                    "event_type": event_type,
                    "chapter_no": chapter_no,
                    "chapter_title": chapter_title,
                    "chunk_id": chunk_id,
                    "summary": f"检测到{event_type}事件。",
                    "evidence": extract_evidence(text, m["matched_alias"]),
                    "related_entities": related,
                    "confidence": confidence,
                    "extract_method": "rule",
                }
                timeline_events.append(new_event)
                chapter_event_dedup[dedup_chapter_key] = new_event

    timeline_events.sort(key=lambda e: (e["chapter_no"], e["entity_event_id"]))

    # Phase 4: Build relations
    relations: list[dict] = []
    relation_dedup: set[tuple[str, str, str]] = set()  # (source_id, target_id, chunk_id)

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            chunk_id = chunk["chunk_id"]
            text = chunk["text"]
            chapter_no = chunk["chapter_no"]
            chapter_title = chunk.get("chapter_title", "")

            if chunk_id not in chunk_entities:
                continue

            ent_in_chunk = chunk_entities[chunk_id]
            if len(ent_in_chunk) < 2:
                continue

            # Detect relation words
            rel_result = detect_relation(text)
            if rel_result:
                rel_type, confidence = rel_result
            else:
                rel_type, confidence = "related_to", 0.40

            # Generate pairwise relations
            for i, m1 in enumerate(ent_in_chunk):
                for m2 in ent_in_chunk[i+1:]:
                    dedup_key = (m1["entity_id"], m2["entity_id"], chunk_id)
                    if dedup_key in relation_dedup:
                        continue
                    relation_dedup.add(dedup_key)

                    rel_id = f"{project_id}_rel_{len(relations)+1:06d}"
                    relations.append({
                        "relation_id": rel_id,
                        "project_id": project_id,
                        "source_entity_id": m1["entity_id"],
                        "source_name": m1["name"],
                        "target_entity_id": m2["entity_id"],
                        "target_name": m2["name"],
                        "relation_type": rel_type,
                        "chapter_no": chapter_no,
                        "chapter_title": chapter_title,
                        "chunk_id": chunk_id,
                        "evidence": extract_evidence(text, m1["matched_alias"]),
                        "confidence": confidence,
                        "status": "candidate" if confidence < 0.6 else "active",
                    })

    relations.sort(key=lambda r: (r["chapter_no"], r["relation_id"]))

    # Phase 5: Write outputs
    entities_path = dd / "entities.jsonl"
    with open(entities_path, "w", encoding="utf-8") as f:
        for ent in entities:
            f.write(json.dumps(ent, ensure_ascii=False) + "\n")

    mentions_path = dd / "entity_mentions.jsonl"
    with open(mentions_path, "w", encoding="utf-8") as f:
        for m in mentions:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    timeline_path = dd / "entity_timeline.jsonl"
    with open(timeline_path, "w", encoding="utf-8") as f:
        for evt in timeline_events:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    relations_path = dd / "entity_relations.jsonl"
    with open(relations_path, "w", encoding="utf-8") as f:
        for rel in relations:
            f.write(json.dumps(rel, ensure_ascii=False) + "\n")

    # Phase 6: Build entity index
    by_name = {}
    by_alias = {}
    by_type = {}
    mentions_by_entity = {}
    timeline_by_entity = {}
    relations_by_entity = {}

    for ent in entities:
        eid = ent["entity_id"]
        by_name[ent["name"]] = eid
        for alias in ent.get("aliases", []):
            by_alias[alias] = eid
        by_type.setdefault(ent["type"], []).append(eid)

    for m in mentions:
        mentions_by_entity.setdefault(m["entity_id"], []).append(m["mention_id"])

    for evt in timeline_events:
        timeline_by_entity.setdefault(evt["entity_id"], []).append(evt["entity_event_id"])

    for rel in relations:
        relations_by_entity.setdefault(rel["source_entity_id"], []).append(rel["relation_id"])
        relations_by_entity.setdefault(rel["target_entity_id"], []).append(rel["relation_id"])

    index = {
        "project_id": project_id,
        "by_name": by_name,
        "by_alias": by_alias,
        "by_type": by_type,
        "mentions_by_entity": mentions_by_entity,
        "timeline_by_entity": timeline_by_entity,
        "relations_by_entity": relations_by_entity,
    }
    index_path = dd / "entity_index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "entity_count": len(entities),
        "mention_count": len(mentions),
        "timeline_event_count": len(timeline_events),
        "relation_count": len(relations),
    }


def main():
    parser = argparse.ArgumentParser(description="Build entity index")
    parser.add_argument("--project", required=True, help="Project ID")
    args = parser.parse_args()

    result = build_entities(args.project)
    print(f"Entities built:")
    print(f"  Entities:        {result['entity_count']}")
    print(f"  Mentions:        {result['mention_count']}")
    print(f"  Timeline events: {result['timeline_event_count']}")
    print(f"  Relations:       {result['relation_count']}")


if __name__ == "__main__":
    main()
