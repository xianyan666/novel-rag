"""查询服务：检索路由 + LLM 生成。"""

import json
import os
from datetime import datetime

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

from ..config import load_runtime, load_project, data_dir
from .retrieval_router import retrieve_evidence, _ENTITY_QUERY_TYPES
from .model_client import generate_text

SYSTEM_PROMPT = """你是小说原文考据助手。只能根据提供的原文片段回答。
如果片段不足以回答，必须说"当前证据不足"。
不要编造章节、人物关系、设定或剧情。
不要输出大段原文。
回答后列出引用章节。

如果用户询问"第一个、第一次、首次、最早、最开始"等顺序问题，你必须优先依据章节号最早且事件类型匹配的证据回答。
如果证据主要来自后期章节，不能断言它就是第一个。
如果没有足够证据确认顺序，回答"当前证据不足以确认第一个/首次"，并列出已找到的候选章节。
回答必须说明依据的章节号和证据类型。

如果出现实体相关证据（实体提及、实体时间线、实体关系），你必须：
1. 首次出现问题以最早提及章节为依据。
2. 后续变化问题按章节升序输出。
3. 关系问题列出关系类型和证据章节。
4. 低置信候选关系标注为"候选"。"""


def _render_protected_answer(pa: dict) -> str:
    """Render a protected answer as a fallback when LLM output conflicts."""
    entity_name = pa.get("entity_name", "未知实体")
    ch_no = pa.get("chapter_no", 0)
    ch_title = pa.get("chapter_title", "")
    pa_type = pa.get("type", "")
    if pa_type == "entity_first_seen":
        return f"根据实体索引，{entity_name}首次明确出现于第{ch_no}章《{ch_title}》。\n依据：实体提及记录 {pa.get('chunk_id', '')}"
    return f"根据实体索引，{entity_name}的相关信息来自第{ch_no}章《{ch_title}》。"


def generate_answer(
    question: str,
    chunks: list[dict],
    query_analysis: dict | None = None,
    timeline_events: list[dict] | None = None,
    guard: dict | None = None,
    entity_mentions: list[dict] | None = None,
    entity_timeline: list[dict] | None = None,
    entity_relations: list[dict] | None = None,
    protected_answer: dict | None = None,
) -> str:
    runtime = load_runtime()
    context_parts = []

    for c in chunks:
        source = c.get("source", "vector")
        ch_no = c["chapter_no"]
        ch_title = c["chapter_title"]
        label = f"第{ch_no}章 {ch_title}"

        if source == "entity_mention":
            context_parts.append(
                f"【实体提及 | {label} | confidence={c.get('score', 0):.2f}】\n{c['text']}"
            )
        elif source == "entity_timeline":
            context_parts.append(
                f"【实体时间线 | {c.get('event_type', '')} | {label} | confidence={c.get('score', 0):.2f}】\n{c['text']}"
            )
        elif source == "entity_relation":
            context_parts.append(
                f"【实体关系 | {c.get('relation_type', '')} | {label} | confidence={c.get('score', 0):.2f}】\n{c['text']}"
            )
        elif source == "timeline" and c.get("event_type"):
            context_parts.append(
                f"【时间线候选 | {c['event_type']} | {label}】\n{c['text']}"
            )
        elif source == "keyword":
            context_parts.append(
                f"【关键词召回 | {label}】\n{c['text']}"
            )
        else:
            score = c.get("score", 0)
            context_parts.append(
                f"【向量召回 | {label} | score={score:.2f}】\n{c['text']}"
            )

    context = "\n\n---\n\n".join(context_parts)

    extra_instructions = ""
    if guard and guard.get("warnings"):
        extra_instructions = "\n注意：" + "；".join(guard["warnings"])

    # Build structured conclusion block for protected answers
    protected_block = ""
    if protected_answer:
        pa_type = protected_answer.get("type", "")
        entity_name = protected_answer.get("entity_name", "")
        ch_no = protected_answer.get("chapter_no", 0)
        ch_title = protected_answer.get("chapter_title", "")
        if pa_type == "entity_first_seen":
            protected_block = f"""

【结构化结论】
实体：{entity_name}
问题类型：首次出现
受保护结论：{entity_name}首次出现于第{ch_no}章《{ch_title}》。
你必须以该结论为准，不能根据后期向量片段改写首次出现章节。"""

    prompt = f"""{SYSTEM_PROMPT}{extra_instructions}{protected_block}

原文片段：
{context}

用户问题：{question}

请基于以上原文片段回答："""

    answer = generate_text(prompt, runtime, timeout=120)

    # Post-processing: check if LLM answer conflicts with protected answer
    if protected_answer and protected_answer.get("type") == "entity_first_seen":
        protected_ch = str(protected_answer.get("chapter_no", ""))
        entity_name = protected_answer.get("entity_name", "")
        # If the protected chapter number is not in the answer, override
        if protected_ch and entity_name and protected_ch not in answer:
            answer = _render_protected_answer(protected_answer)

    return answer


def record_query(project_id: str, question: str, top_k: int, result: dict) -> None:
    """把每次网页问答追加写入本地 JSONL（data/<project_id>/query_history.jsonl）。"""
    try:
        path = data_dir(project_id) / "query_history.jsonl"
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "project_id": project_id,
            "question": question,
            "top_k": top_k,
            "query_type": (result.get("query_analysis") or {}).get("query_type"),
            "answer": result.get("answer"),
            "citations": result.get("citations", []),
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "retrieval_debug": result.get("retrieval_debug"),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # 记录失败不应影响正常问答流程
        pass


def query(project_id: str, question: str, top_k: int | None = None) -> dict:
    runtime = load_runtime()
    if top_k is None:
        top_k = runtime.get("top_k", 8)

    project = load_project(project_id)
    if not project:
        raise FileNotFoundError(f"Project '{project_id}' not found")

    evidence = retrieve_evidence(project_id, question, top_k)
    analysis = evidence["query_analysis"]
    chunks = evidence["chunks"]
    timeline_events = evidence["timeline_events"]
    debug = evidence["retrieval_debug"]
    guard = evidence["guard"]
    entity_mentions = evidence.get("entity_mentions", [])
    entity_timeline = evidence.get("entity_timeline", [])
    entity_relations = evidence.get("entity_relations", [])
    protected_answer = evidence.get("protected_answer")
    evidence_scores = evidence.get("evidence_scores", [])

    answer = generate_answer(
        question, chunks, analysis, timeline_events, guard,
        entity_mentions, entity_timeline, entity_relations,
        protected_answer,
    )

    seen = set()
    citations = []
    for c in chunks:
        key = (c["chapter_no"], c["chapter_title"])
        if key not in seen:
            seen.add(key)
            citations.append({
                "chapter_no": c["chapter_no"],
                "chapter_title": c["chapter_title"],
                "chunk_id": c["chunk_id"],
            })

    retrieved_chunks = []
    for c in chunks:
        preview = c["text"][:200].replace("\n", " ")
        retrieved_chunks.append({
            "chunk_id": c["chunk_id"],
            "chapter_no": c["chapter_no"],
            "chapter_title": c["chapter_title"],
            "text_preview": preview,
            "world_id": c.get("world_id"),
            "world_name": c.get("world_name"),
        })

    timeline_resp = []
    for evt in timeline_events:
        timeline_resp.append({
            "event_id": evt.get("event_id", ""),
            "event_type": evt.get("event_type", ""),
            "chapter_no": evt.get("chapter_no", 0),
            "chapter_title": evt.get("chapter_title", ""),
            "event_summary": evt.get("event_summary", ""),
            "evidence": evt.get("evidence", ""),
            "confidence": evt.get("confidence"),
        })

    # Entity analysis for response
    entity_analysis = None
    if analysis["query_type"] in _ENTITY_QUERY_TYPES:
        from .entity_query_router import detect_entities as detect_ent
        matched = detect_ent(project_id, question)
        entity_analysis = {
            "matched_entities": matched,
            "entity_query_type": analysis["query_type"],
        }

    entity_mentions_resp = []
    for m in entity_mentions:
        entity_mentions_resp.append({
            "mention_id": m.get("mention_id", ""),
            "entity_id": m.get("entity_id", ""),
            "name": m.get("name", ""),
            "chapter_no": m.get("chapter_no", 0),
            "chapter_title": m.get("chapter_title", ""),
            "chunk_id": m.get("chunk_id", ""),
            "evidence": m.get("evidence", ""),
            "confidence": m.get("confidence", 0),
        })

    entity_timeline_resp = []
    for evt in entity_timeline:
        entity_timeline_resp.append({
            "entity_event_id": evt.get("entity_event_id", ""),
            "entity_id": evt.get("entity_id", ""),
            "entity_name": evt.get("entity_name", ""),
            "event_type": evt.get("event_type", ""),
            "chapter_no": evt.get("chapter_no", 0),
            "chapter_title": evt.get("chapter_title", ""),
            "summary": evt.get("summary", ""),
            "evidence": evt.get("evidence", ""),
            "related_entities": evt.get("related_entities", []),
            "confidence": evt.get("confidence", 0),
        })

    entity_relations_resp = []
    for rel in entity_relations:
        entity_relations_resp.append({
            "relation_id": rel.get("relation_id", ""),
            "source_entity_id": rel.get("source_entity_id", ""),
            "source_name": rel.get("source_name", ""),
            "target_entity_id": rel.get("target_entity_id", ""),
            "target_name": rel.get("target_name", ""),
            "relation_type": rel.get("relation_type", ""),
            "chapter_no": rel.get("chapter_no", 0),
            "chapter_title": rel.get("chapter_title", ""),
            "evidence": rel.get("evidence", ""),
            "confidence": rel.get("confidence", 0),
            "status": rel.get("status", ""),
        })

    result = {
        "answer": answer,
        "citations": citations,
        "retrieved_chunks": retrieved_chunks,
        "query_analysis": analysis,
        "timeline_events": timeline_resp,
        "entity_analysis": entity_analysis,
        "entity_mentions": entity_mentions_resp,
        "entity_timeline": entity_timeline_resp,
        "entity_relations": entity_relations_resp,
        "protected_answer": protected_answer,
        "evidence_scores": evidence_scores,
        "retrieval_debug": debug,
    }

    record_query(project_id, question, top_k, result)
    return result
