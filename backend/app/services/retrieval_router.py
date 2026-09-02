"""检索路由：根据问题类型选择检索策略，合并排序，证据保护。"""

from .question_classifier import classify_question
from .timeline_service import query_timeline
from .keyword_service import keyword_search, extract_keywords
from .vector_service import retrieve_chunks
from .entity_query_router import detect_entities, route_entity_query
from .world_service import detect_worlds


def _merge_and_rank(
    vector_chunks: list[dict],
    keyword_chunks: list[dict],
    timeline_events: list[dict],
    query_type: str,
) -> list[dict]:
    seen = {}
    all_items = []

    for chunk in vector_chunks:
        cid = chunk["chunk_id"]
        if cid not in seen:
            seen[cid] = chunk
            chunk["_semantic_score"] = chunk.get("score", 0)
            chunk["_keyword_score"] = 0
            chunk["_event_type_score"] = 0
            all_items.append(chunk)

    for chunk in keyword_chunks:
        cid = chunk["chunk_id"]
        if cid in seen:
            seen[cid]["_keyword_score"] = chunk.get("score", 0)
        else:
            chunk["_semantic_score"] = 0
            chunk["_keyword_score"] = chunk.get("score", 0)
            chunk["_event_type_score"] = 0
            seen[cid] = chunk
            all_items.append(chunk)

    for evt in timeline_events:
        cid = evt.get("chunk_id")
        if not cid:
            continue
        if cid in seen:
            seen[cid]["_event_type_score"] = evt.get("confidence", 0.7)
            if "event_type" not in seen[cid]:
                seen[cid]["event_type"] = evt["event_type"]
        else:
            all_items.append({
                "chunk_id": cid,
                "chapter_no": evt["chapter_no"],
                "chapter_title": evt.get("chapter_title", ""),
                "text": evt.get("evidence", ""),
                "score": 0,
                "source": "timeline",
                "_semantic_score": 0,
                "_keyword_score": 0,
                "_event_type_score": evt.get("confidence", 0.7),
                "event_type": evt["event_type"],
            })
            seen[cid] = all_items[-1]

    # Compute composite score
    max_chapter = max((c.get("chapter_no", 1) for c in all_items), default=1) or 1

    for item in all_items:
        sem = item.get("_semantic_score", 0)
        kw = item.get("_keyword_score", 0)
        evt = item.get("_event_type_score", 0)
        ch = item.get("chapter_no", 1)
        early = 1.0 - (ch / max_chapter) if max_chapter > 0 else 0

        if query_type == "sequence_first":
            item["_composite"] = sem * 0.25 + kw * 0.20 + evt * 0.30 + early * 0.25
        elif query_type in ("sequence_order", "timeline_summary"):
            item["_composite"] = sem * 0.20 + kw * 0.15 + evt * 0.30 + early * 0.35
        else:
            item["_composite"] = sem * 0.40 + kw * 0.30 + evt * 0.20 + early * 0.10

    all_items.sort(key=lambda x: -x["_composite"])
    return all_items


def guard_evidence(query_analysis: dict, merged_chunks: list[dict], timeline_events: list[dict]) -> dict:
    warnings = []
    insufficient = False
    query_type = query_analysis["query_type"]

    if query_type == "sequence_first":
        if not timeline_events:
            insufficient = True
            warnings.append("未找到时间线事件证据，无法确认顺序。")

        if timeline_events:
            early_events = [e for e in timeline_events if e["chapter_no"] <= 100]
            if not early_events:
                warnings.append("所有时间线候选均来自后期章节(>100章)，可能无法确认'第一个'。")

        if not timeline_events and merged_chunks:
            late_chunks = [c for c in merged_chunks if c.get("chapter_no", 0) > 500]
            if late_chunks and len(late_chunks) == len(merged_chunks):
                warnings.append("所有召回片段均来自后期章节(>500章)，不建议据此回答'第一个'。")

    if query_type in _ENTITY_QUERY_TYPES:
        if not merged_chunks:
            insufficient = True
            warnings.append("未在实体库中找到相关实体，建议构建/更新实体索引。")

        # Check for low-confidence relations
        low_conf = [c for c in merged_chunks if c.get("source") == "entity_relation" and c.get("score", 0) < 0.6]
        if low_conf:
            warnings.append("部分关系为低置信候选，仅供参考。")

    return {
        "insufficient_order_evidence": insufficient,
        "warnings": warnings,
    }


_ENTITY_QUERY_TYPES = {
    "entity_first_seen", "entity_timeline", "entity_profile",
    "entity_relation", "entity_mentions", "world_entity_timeline",
}


def retrieve_evidence(project_id: str, question: str, top_k: int | None = None) -> dict:
    if top_k is None:
        top_k = 8

    analysis = classify_question(question)
    query_type = analysis["query_type"]
    event_hints = analysis["event_hints"]
    entities = analysis["entities"]
    matched_worlds = detect_worlds(project_id, question)
    world_ids = {world["world_id"] for world in matched_worlds}

    vector_chunks = []
    keyword_chunks = []
    timeline_events = []
    entity_mentions = []
    entity_timeline = []
    entity_relations = []

    route_parts = []

    # Entity query routing
    protected_answer = None
    evidence_scores = []

    if query_type in _ENTITY_QUERY_TYPES:
        entity_result = route_entity_query(project_id, question, analysis, world_ids or None)
        entity_chunks = entity_result["entity_chunks"]
        entity_mentions = entity_result["entity_mentions"]
        entity_timeline = entity_result["entity_timeline"]
        entity_relations = entity_result["entity_relations"]
        protected_answer = entity_result.get("protected_answer")
        evidence_scores = entity_result.get("evidence_scores", [])
        route_parts.append(entity_result["route"])

        if world_ids:
            route_parts.append("world_filter")

        if query_type == "entity_first_seen":
            # P0: Protected first_seen - entity chunks are primary, vector is supplemental only
            entity_chunks.sort(key=lambda c: (-c.get("final_score", 0), c["chapter_no"]))
            merged = list(entity_chunks)
            # Vector only as supplemental context, not as first_seen candidates
            supplemental_vector = retrieve_chunks(project_id, question, 3, world_ids or None)
            for vc in supplemental_vector:
                vc["source"] = "vector_supplemental"
                vc["protected"] = False
            merged.extend(supplemental_vector)
            route_parts.append("vector_supplemental")
        elif query_type in {"entity_timeline", "world_entity_timeline"}:
            # Entity timeline scored by entity timeline formula, sorted by chapter
            entity_chunks.sort(key=lambda c: (c["chapter_no"], -c.get("final_score", 0)))
            if query_type == "world_entity_timeline":
                # Preserve room for semantic evidence from the same world;
                # otherwise the first 20 rule events consume every Top K slot.
                entity_limit = max(1, top_k - 3)
                merged = list(entity_chunks[:entity_limit])
            else:
                merged = list(entity_chunks)
            # Vector only supplements the already world-filtered timeline.
            supplemental_vector = retrieve_chunks(project_id, question, 3, world_ids or None)
            for vc in supplemental_vector:
                vc["source"] = "vector_supplemental"
                vc["protected"] = False
            merged.extend(supplemental_vector)
            route_parts.append("vector_supplemental")
        elif query_type == "entity_relation":
            # Seed 关系库只覆盖已入库实体。问「杨间和秦老」时若秦老不在库中，
            # 杨间与其他种子实体的共现关系会占满 Top K，真正写「秦老」的向量/关键词
            # 证据进不了上下文。因此：关系证据限量，并强制混入关键词+向量。
            entity_chunks.sort(
                key=lambda c: (0 if c.get("protected") else 1, -c.get("final_score", 0))
            )
            keywords = extract_keywords(question)
            if keywords:
                keyword_chunks = keyword_search(project_id, keywords, limit=top_k)
            vector_chunks = retrieve_chunks(project_id, question, top_k, world_ids or None)
            hybrid = _merge_and_rank(vector_chunks, keyword_chunks, [], "normal_fact")
            entity_limit = min(len(entity_chunks), max(1, top_k // 2))
            if not entity_chunks:
                entity_limit = 0
            # 库中只命中一方时，关系边几乎全是噪声，进一步压缩名额
            matched_names = {ent.get("name", "") for ent in detect_entities(project_id, question)}
            asked_names = {kw for kw in keywords if len(kw) >= 2}
            if asked_names and not asked_names.issubset(matched_names):
                entity_limit = min(entity_limit, 2)
            merged = list(entity_chunks[:entity_limit])
            seen_ids = {c.get("chunk_id") for c in merged}
            for chunk in hybrid:
                if chunk.get("chunk_id") in seen_ids:
                    continue
                merged.append(chunk)
                seen_ids.add(chunk.get("chunk_id"))
                if len(merged) >= top_k:
                    break
            route_parts.extend(["keyword", "vector"])
        else:
            # entity_mentions, entity_profile: entity primary + vector supplemental
            merged = list(entity_chunks)
            supplemental_vector = retrieve_chunks(project_id, question, 3, world_ids or None)
            for vc in supplemental_vector:
                vc["source"] = "vector_supplemental"
                vc["protected"] = False
            merged.extend(supplemental_vector)
            route_parts.append("vector_supplemental")

        # Also append timeline events from entity timeline
        for evt in entity_timeline:
            timeline_events.append(evt)
    elif query_type == "normal_fact":
        vector_chunks = retrieve_chunks(project_id, question, top_k, world_ids or None)
        route_parts.extend(["vector", "world_filter"] if world_ids else ["vector"])
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)
    elif query_type == "sequence_first":
        timeline_events = query_timeline(project_id, event_hints, entities, query_type, limit=10)
        keywords = extract_keywords(question)
        if event_hints:
            keywords.extend(event_hints)
        if keywords:
            keyword_chunks = keyword_search(project_id, keywords, limit=top_k)
        vector_chunks = retrieve_chunks(project_id, question, top_k)
        route_parts.extend(["timeline", "keyword", "vector"])
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)
    elif query_type == "sequence_order":
        timeline_events = query_timeline(project_id, event_hints, entities, query_type, limit=20)
        keywords = extract_keywords(question)
        if event_hints:
            keywords.extend(event_hints)
        if keywords:
            keyword_chunks = keyword_search(project_id, keywords, limit=top_k)
        route_parts.extend(["timeline", "keyword"])
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)
    elif query_type == "timeline_summary":
        timeline_events = query_timeline(project_id, event_hints, entities, query_type, limit=30)
        route_parts.append("timeline")
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)
    elif query_type == "chapter_lookup":
        keywords = extract_keywords(question)
        if event_hints:
            keywords.extend(event_hints)
        if keywords:
            keyword_chunks = keyword_search(project_id, keywords, limit=top_k)
        vector_chunks = retrieve_chunks(project_id, question, top_k, world_ids or None)
        route_parts.extend(["keyword", "vector", "world_filter"] if world_ids else ["keyword", "vector"])
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)
    else:
        vector_chunks = retrieve_chunks(project_id, question, top_k)
        route_parts.append("vector")
        merged = _merge_and_rank(vector_chunks, keyword_chunks, timeline_events, query_type)

    merged = merged[:top_k]

    guard = guard_evidence(analysis, merged, timeline_events)

    route = "_plus_".join(route_parts) if route_parts else "none"
    debug = {
        "route": route,
        "vector_count": len(vector_chunks),
        "timeline_count": len(timeline_events),
        "keyword_count": len(keyword_chunks),
        "entity_mention_count": len(entity_mentions),
        "entity_timeline_count": len(entity_timeline),
        "entity_relation_count": len(entity_relations),
        "world_filter_count": len(matched_worlds),
        "matched_worlds": [
            {"world_id": world["world_id"], "name": world["name"]}
            for world in matched_worlds
        ],
        "warnings": guard.get("warnings", []),
    }

    return {
        "query_analysis": analysis,
        "chunks": merged,
        "timeline_events": timeline_events,
        "entity_mentions": entity_mentions,
        "entity_timeline": entity_timeline,
        "entity_relations": entity_relations,
        "protected_answer": protected_answer,
        "evidence_scores": evidence_scores,
        "retrieval_debug": debug,
        "guard": guard,
    }
