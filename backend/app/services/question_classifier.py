"""问题分类器：规则识别问题类型、实体、事件提示。"""

import re

_SEQUENCE_FIRST_PATTERNS = [
    "第一个", "第一次", "首次", "最早", "初次", "起初", "开端", "最开始", "一开始", "首个",
]

_SEQUENCE_ORDER_PATTERNS = [
    "第几次", "第几个", "顺序", "先后", "依次", "分别在哪", "时间顺序", "发展过程",
]

_TIMELINE_SUMMARY_PATTERNS = [
    "时间线", "经历", "全过程", "发展脉络", "事件脉络", "按章节整理",
]

_CHAPTER_LOOKUP_PATTERNS = [
    "哪一章", "在哪章", "首次出现在哪", "出现章节", "登场章节",
]

_ENTITY_FIRST_SEEN_PATTERNS = [
    "第一次出现", "首次出现", "最早出现", "第一次登场", "首次登场",
    "第一次出现在", "首次出现在",
]

_ENTITY_TIMELINE_PATTERNS = [
    "后续变化", "发生了什么变化", "经历了什么", "成长", "升级", "强化",
    "发生了哪些变化", "哪些变化", "经历", "变化",
]

_WORLD_CONTEXT_PATTERNS = ["世界", "副本", "位面"]

_ENTITY_PROFILE_PATTERNS = [
    "档案", "介绍", "总结", "资料",
]

_ENTITY_RELATION_PATTERNS = [
    "关系", "交集", "互动", "和谁有关",
]

_ENTITY_MENTIONS_PATTERNS = [
    "出现在哪些章节", "相关章节",
    "相关的重要章节", "重要章节",
]

_EVENT_HINT_MAP = [
    # 通用叙事事件提示（与 timeline 通用 event_type 对齐）
    (["遇到", "遇见", "撞见", "碰见", "登场", "相遇"], "遭遇"),
    (["对峙", "交手", "厮杀", "搏斗", "打斗", "战斗", "攻击"], "冲突"),
    (["规则", "禁忌", "鬼域规则", "不能做"], "规则"),
    (["能力", "觉醒", "鬼眼", "掌控", "强化"], "能力"),
    (["死亡", "死去", "身亡", "灭杀"], "死亡"),
    (["封印", "镇压"], "封印"),
    (["结盟", "联手", "合作", "交易", "决裂", "背叛"], "结盟"),
    (["线索", "真相", "得知", "获悉", "查出"], "线索"),
    (["进入鬼域", "离开鬼域", "昏迷", "苏醒", "失控", "状态"], "状态"),
    # 旧乐园提示别名（仍可映射到通用类型）
    (["衍生世界", "世界难度", "世界之源", "传送"], "进入世界"),
    (["回归乐园", "回到乐园", "世界结算"], "回归乐园"),
    (["主线任务", "支线任务", "隐藏任务"], "任务"),
]

_ENTITIES = ["杨间", "周正", "曹延华", "林龙", "高志强", "李军"]

# Load seed entities at module level for classifier
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SEED_ENTITIES: list[str] = []
try:
    _seed_path = _ROOT / "config" / "entities.seed.json"
    if _seed_path.exists():
        _seeds = json.loads(_seed_path.read_text(encoding="utf-8"))
        for s in _seeds:
            _SEED_ENTITIES.append(s["name"])
            _SEED_ENTITIES.extend(s.get("aliases", []))
except Exception:
    pass


def _extract_event_hints(question: str) -> list[str]:
    hints = []
    for keywords, hint in _EVENT_HINT_MAP:
        for kw in keywords:
            if kw in question:
                if hint not in hints:
                    hints.append(hint)
                break
    return hints


def _extract_entities(question: str) -> list[str]:
    entities = []
    for e in [*_ENTITIES, *_SEED_ENTITIES]:
        if e in question and e not in entities:
            entities.append(e)
    return entities


def _has_entity_context(q: str) -> bool:
    """Check if the question mentions a known entity or entity-like noun."""
    # Check known entities
    for e in _ENTITIES:
        if e in q:
            return True
    # Check seed entities
    for e in _SEED_ENTITIES:
        if e in q:
            return True
    # Check common entity patterns (names with specific suffixes/patterns)
    entity_indicators = ["闪", "影", "刃", "剑", "刀", "甲", "戒", "环", "链"]
    for ind in entity_indicators:
        if ind in q and len(q) < 50:
            return True
    return False


def _has_world_context(q: str) -> bool:
    return any(pattern in q for pattern in _WORLD_CONTEXT_PATTERNS)


def classify_question(question: str) -> dict:
    q = question.strip()

    query_type = "normal_fact"
    time_constraint = None
    confidence = 0.5

    # Entity question types (checked first for priority)
    for pat in _ENTITY_FIRST_SEEN_PATTERNS:
        if pat in q and _has_entity_context(q):
            query_type = "entity_first_seen"
            time_constraint = "earliest"
            confidence = 0.92
            break

    if query_type == "normal_fact":
        for pat in _ENTITY_TIMELINE_PATTERNS:
            if pat in q and _has_entity_context(q) and _has_world_context(q):
                query_type = "world_entity_timeline"
                time_constraint = "ordered"
                confidence = 0.94
                break

    if query_type == "normal_fact":
        for pat in _ENTITY_TIMELINE_PATTERNS:
            if pat in q and _has_entity_context(q):
                query_type = "entity_timeline"
                time_constraint = "ordered"
                confidence = 0.90
                break

    if query_type == "normal_fact":
        for pat in _ENTITY_RELATION_PATTERNS:
            if pat in q and _has_entity_context(q):
                query_type = "entity_relation"
                confidence = 0.88
                break

    if query_type == "normal_fact":
        for pat in _ENTITY_MENTIONS_PATTERNS:
            if pat in q and _has_entity_context(q):
                query_type = "entity_mentions"
                confidence = 0.88
                break

    if query_type == "normal_fact":
        for pat in _ENTITY_PROFILE_PATTERNS:
            if pat in q and _has_entity_context(q):
                query_type = "entity_profile"
                confidence = 0.85
                break

    # Non-entity patterns (only if no entity type matched)
    if query_type == "normal_fact":
        for pat in _SEQUENCE_FIRST_PATTERNS:
            if pat in q:
                query_type = "sequence_first"
                time_constraint = "earliest"
                confidence = 0.9
                break

    if query_type == "normal_fact":
        for pat in _SEQUENCE_ORDER_PATTERNS:
            if pat in q:
                query_type = "sequence_order"
                confidence = 0.85
                break

    if query_type == "normal_fact":
        for pat in _TIMELINE_SUMMARY_PATTERNS:
            if pat in q:
                query_type = "timeline_summary"
                confidence = 0.85
                break

    if query_type == "normal_fact":
        for pat in _CHAPTER_LOOKUP_PATTERNS:
            if pat in q:
                query_type = "chapter_lookup"
                confidence = 0.85
                break

    entities = _extract_entities(q)
    event_hints = _extract_event_hints(q)

    if entities and confidence < 0.9:
        confidence = min(confidence + 0.05, 0.95)

    return {
        "query_type": query_type,
        "entities": entities,
        "event_hints": event_hints,
        "time_constraint": time_constraint,
        "confidence": confidence,
    }
