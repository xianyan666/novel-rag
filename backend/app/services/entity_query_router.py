"""实体查询路由：检测问题中的实体并路由到实体检索。"""

from .entity_service import (
    load_entities,
    search_entities,
    get_entity_mentions,
    get_entity_timeline,
    get_entity_relations,
)
from .world_service import get_chapter_world


def _score_mention(mention: dict, max_chapter: int) -> dict:
    """Score an entity mention for first_seen queries."""
    ch = mention.get("chapter_no", 1)
    # order_score: earlier chapter = higher score
    order_score = 1.0 - (ch / max_chapter) if max_chapter > 0 else 0
    # keyword_score: check if evidence contains first-seen keywords
    evidence = mention.get("evidence", "")
    first_seen_keywords = ["获得", "拿到", "装备", "第一次", "首次", "登场", "出现", "入手"]
    keyword_score = 0.8 if any(kw in evidence for kw in first_seen_keywords) else 0.3
    # confidence from mention
    confidence_score = mention.get("confidence", 0.9)
    # entity_score is always 1.0 for matched entities
    entity_score = 1.0
    # final_score: entity-first weighted formula
    final_score = (
        entity_score * 0.50
        + order_score * 0.35
        + keyword_score * 0.10
        + confidence_score * 0.02
    )
    # vector_score placeholder (0 for entity-only chunks)
    return {
        **mention,
        "entity_score": entity_score,
        "order_score": round(order_score, 3),
        "keyword_score": round(keyword_score, 3),
        "vector_score": 0.0,
        "confidence_score": round(confidence_score, 3),
        "final_score": round(final_score, 3),
        "protected": mention.get("mention_type", "") == "explicit",
        "source": "entity_mention",
    }


def _score_timeline_event(event: dict, max_chapter: int) -> dict:
    """Score an entity timeline event."""
    ch = event.get("chapter_no", 1)
    chapter_score = 1.0 - (ch / max_chapter) if max_chapter > 0 else 0
    confidence_score = event.get("confidence", 0.7)
    # entity_nearby_score: assume build_entities.py already filters by window
    entity_nearby_score = 0.8 if confidence_score >= 0.65 else 0.4
    event_word_score = 0.8  # matched by rules
    final_score = (
        entity_nearby_score * 0.35
        + event_word_score * 0.25
        + confidence_score * 0.20
        + chapter_score * 0.10
    )
    return {
        **event,
        "entity_nearby_score": round(entity_nearby_score, 3),
        "event_word_score": round(event_word_score, 3),
        "chapter_score": round(chapter_score, 3),
        "vector_score": 0.0,
        "confidence_score": round(confidence_score, 3),
        "final_score": round(final_score, 3),
        "source": "entity_timeline",
    }


def _score_relation(relation: dict, max_chapter: int) -> dict:
    """Score an entity relation."""
    ch = relation.get("chapter_no", 1)
    chapter_score = 1.0 - (ch / max_chapter) if max_chapter > 0 else 0
    confidence_score = relation.get("confidence", 0.5)
    rel_type = relation.get("relation_type", "")
    # related_to is low-confidence co-occurrence
    entity_pair_score = 0.9 if rel_type != "related_to" else 0.45
    relation_word_score = 0.8 if rel_type != "related_to" else 0.3
    final_score = (
        entity_pair_score * 0.35
        + relation_word_score * 0.25
        + confidence_score * 0.20
        + chapter_score * 0.10
    )
    return {
        **relation,
        "entity_pair_score": round(entity_pair_score, 3),
        "relation_word_score": round(relation_word_score, 3),
        "chapter_score": round(chapter_score, 3),
        "vector_score": 0.0,
        "confidence_score": round(confidence_score, 3),
        "final_score": round(final_score, 3),
        "protected": rel_type != "related_to",
        "source": "entity_relation",
    }


def detect_entities(project_id: str, question: str) -> list[dict]:
    # First try direct search
    entities = search_entities(project_id, question.strip())

    # If no results, scan all entities to see if any name/alias appears in the question
    if not entities:
        all_entities = load_entities(project_id)
        q = question.strip()
        for ent in all_entities:
            if ent["name"] in q:
                entities.append(ent)
            else:
                for alias in ent.get("aliases", []):
                    if alias in q:
                        entities.append(ent)
                        break

    # Deduplicate by entity_id
    seen = set()
    unique = []
    for ent in entities:
        if ent["entity_id"] not in seen:
            seen.add(ent["entity_id"])
            unique.append({
                "entity_id": ent["entity_id"],
                "name": ent["name"],
                "type": ent["type"],
                "confidence": 0.9,
            })
    return unique


def route_entity_query(
    project_id: str,
    question: str,
    query_analysis: dict,
    world_ids: set[str] | None = None,
) -> dict:
    query_type = query_analysis["query_type"]
    entities = query_analysis.get("entities", [])

    # Classifier entity extraction can lag behind the seed entity list. For
    # entity-classified questions, always fall back to the full question.
    matched = detect_entities(project_id, " ".join(entities)) if entities else []
    if not matched:
        matched = detect_entities(project_id, question)

    if not matched:
        return {
            "entity_chunks": [],
            "entity_mentions": [],
            "entity_timeline": [],
            "entity_relations": [],
            "protected_answer": None,
            "evidence_scores": [],
            "route": "entity_empty",
        }

    all_mentions = []
    all_timeline = []
    all_relations = []

    for m in matched:
        eid = m["entity_id"]
        mentions = get_entity_mentions(project_id, eid)
        timeline = get_entity_timeline(project_id, eid)
        relations = get_entity_relations(project_id, eid)
        all_mentions.extend(mentions)
        all_timeline.extend(timeline)
        all_relations.extend(relations)

    if world_ids:
        def belongs_to_selected_world(record: dict) -> bool:
            world = get_chapter_world(project_id, record.get("chapter_no", 0))
            return bool(world and world["world_id"] in world_ids)

        all_mentions = [mention for mention in all_mentions if belongs_to_selected_world(mention)]
        all_timeline = [event for event in all_timeline if belongs_to_selected_world(event)]
        all_relations = [relation for relation in all_relations if belongs_to_selected_world(relation)]

    # Sort by chapter
    all_mentions.sort(key=lambda m: m["chapter_no"])
    all_timeline.sort(key=lambda e: e["chapter_no"])
    all_relations.sort(key=lambda r: r["chapter_no"])

    max_chapter = max(
        (m.get("chapter_no", 1) for m in all_mentions), default=1
    ) or 1

    # Route based on query type
    entity_chunks = []
    protected_answer = None
    evidence_scores = []

    if query_type == "entity_first_seen":
        # Score all mentions and select protected earliest
        scored_mentions = [_score_mention(m, max_chapter) for m in all_mentions]
        # Sort: explicit mentions first, then by chapter ascending
        scored_mentions.sort(
            key=lambda m: (0 if m["protected"] else 1, m["chapter_no"])
        )
        if scored_mentions:
            earliest = scored_mentions[0]
            entity_chunks.append({
                "chunk_id": earliest["chunk_id"],
                "chapter_no": earliest["chapter_no"],
                "chapter_title": earliest["chapter_title"],
                "text": earliest.get("evidence", ""),
                "source": "entity_mention",
                "score": earliest["final_score"],
                "entity_score": earliest["entity_score"],
                "order_score": earliest["order_score"],
                "keyword_score": earliest["keyword_score"],
                "vector_score": 0.0,
                "confidence_score": earliest["confidence_score"],
                "final_score": earliest["final_score"],
                "protected": True,
            })
            evidence_scores.append({
                "chunk_id": earliest["chunk_id"],
                "source": "entity_mention",
                "entity_score": earliest["entity_score"],
                "order_score": earliest["order_score"],
                "keyword_score": earliest["keyword_score"],
                "vector_score": 0.0,
                "confidence_score": earliest["confidence_score"],
                "final_score": earliest["final_score"],
                "protected": True,
            })
            # Build protected answer
            entity_name = matched[0]["name"] if matched else "未知实体"
            protected_answer = {
                "type": "entity_first_seen",
                "entity_id": earliest.get("entity_id", ""),
                "entity_name": entity_name,
                "chapter_no": earliest["chapter_no"],
                "chapter_title": earliest["chapter_title"],
                "chunk_id": earliest["chunk_id"],
                "source": "entity_mention",
                "final_score": earliest["final_score"],
            }

    elif query_type in {"entity_timeline", "world_entity_timeline"}:
        scored_events = [_score_timeline_event(e, max_chapter) for e in all_timeline]
        # Filter low confidence
        scored_events = [e for e in scored_events if e["confidence_score"] >= 0.65]
        # Dedup by (entity_id, chapter_no, event_type)
        seen_keys = set()
        deduped = []
        for evt in scored_events:
            key = (evt.get("entity_id", ""), evt["chapter_no"], evt["event_type"])
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(evt)
        # Sort by chapter asc, then final_score desc
        deduped.sort(key=lambda e: (e["chapter_no"], -e["final_score"]))
        for evt in deduped[:20]:
            entity_chunks.append({
                "chunk_id": evt["chunk_id"],
                "chapter_no": evt["chapter_no"],
                "chapter_title": evt.get("chapter_title", ""),
                "text": evt.get("evidence", evt.get("summary", "")),
                "source": "entity_timeline",
                "score": evt["final_score"],
                "event_type": evt["event_type"],
                "final_score": evt["final_score"],
                "protected": False,
            })
            evidence_scores.append({
                "chunk_id": evt["chunk_id"],
                "source": "entity_timeline",
                "final_score": evt["final_score"],
                "confidence_score": evt["confidence_score"],
                "protected": False,
            })

    elif query_type == "entity_relation":
        scored_rels = [_score_relation(r, max_chapter) for r in all_relations]
        # Sort: protected (non-related_to) first, then by final_score desc
        scored_rels.sort(
            key=lambda r: (0 if r["protected"] else 1, -r["final_score"])
        )
        for rel in scored_rels[:15]:
            entity_chunks.append({
                "chunk_id": rel["chunk_id"],
                "chapter_no": rel["chapter_no"],
                "chapter_title": rel.get("chapter_title", ""),
                "text": rel.get("evidence", ""),
                "source": "entity_relation",
                "score": rel["final_score"],
                "relation_type": rel["relation_type"],
                "final_score": rel["final_score"],
                "protected": rel["protected"],
            })
            evidence_scores.append({
                "chunk_id": rel["chunk_id"],
                "source": "entity_relation",
                "relation_type": rel["relation_type"],
                "final_score": rel["final_score"],
                "confidence_score": rel["confidence_score"],
                "protected": rel["protected"],
            })

    elif query_type == "entity_mentions":
        scored_mentions = [_score_mention(m, max_chapter) for m in all_mentions]
        scored_mentions.sort(key=lambda m: m["chapter_no"])
        for m in scored_mentions[:20]:
            entity_chunks.append({
                "chunk_id": m["chunk_id"],
                "chapter_no": m["chapter_no"],
                "chapter_title": m.get("chapter_title", ""),
                "text": m.get("evidence", ""),
                "source": "entity_mention",
                "score": m["final_score"],
                "final_score": m["final_score"],
                "protected": m["protected"],
            })
            evidence_scores.append({
                "chunk_id": m["chunk_id"],
                "source": "entity_mention",
                "final_score": m["final_score"],
                "confidence_score": m["confidence_score"],
                "protected": m["protected"],
            })

    elif query_type == "entity_profile":
        if all_mentions:
            scored_mentions = [_score_mention(m, max_chapter) for m in all_mentions]
            earliest = min(scored_mentions, key=lambda m: m["chapter_no"])
            entity_chunks.append({
                "chunk_id": earliest["chunk_id"],
                "chapter_no": earliest["chapter_no"],
                "chapter_title": earliest.get("chapter_title", ""),
                "text": earliest.get("evidence", ""),
                "source": "entity_mention",
                "score": earliest["final_score"],
                "final_score": earliest["final_score"],
                "protected": True,
            })
        scored_events = [_score_timeline_event(e, max_chapter) for e in all_timeline]
        scored_events = [e for e in scored_events if e["confidence_score"] >= 0.65]
        scored_events.sort(key=lambda e: (e["chapter_no"], -e["final_score"]))
        for evt in scored_events[:10]:
            entity_chunks.append({
                "chunk_id": evt["chunk_id"],
                "chapter_no": evt["chapter_no"],
                "chapter_title": evt.get("chapter_title", ""),
                "text": evt.get("evidence", evt.get("summary", "")),
                "source": "entity_timeline",
                "score": evt["final_score"],
                "event_type": evt["event_type"],
                "final_score": evt["final_score"],
                "protected": False,
            })

    return {
        "entity_chunks": entity_chunks,
        "entity_mentions": all_mentions[:20],
        "entity_timeline": all_timeline[:20],
        "entity_relations": all_relations[:15],
        "protected_answer": protected_answer,
        "evidence_scores": evidence_scores,
        "route": f"entity_{query_type}",
    }
