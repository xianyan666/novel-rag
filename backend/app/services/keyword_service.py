"""关键词检索服务：子串匹配 chunks.jsonl。"""

import json
import re
from pathlib import Path

from ..config import data_dir

_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "被",
    "从", "把", "还", "什么", "吗", "呢", "吧", "啊", "呀", "哦",
    "什么", "怎么", "如何", "哪个", "哪些", "为什么", "哪", "几",
    "能", "可以", "可", "可能", "该", "应该", "第", "章", "中", "里",
    "里", "与", "及", "或", "但", "而", "对", "为", "以", "于",
}

_chunks_cache: dict[str, tuple[float, list[dict]]] = {}


def _load_chunks(project_id: str) -> list[dict]:
    chunks_path = data_dir(project_id) / "chunks.jsonl"
    if not chunks_path.exists():
        return []

    mtime = chunks_path.stat().st_mtime
    cached = _chunks_cache.get(project_id)
    if cached and cached[0] == mtime:
        return cached[1]

    chunks = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    _chunks_cache[project_id] = (mtime, chunks)
    return chunks


def _ngram_fallback(question: str) -> list[str]:
    """无 jieba 时的退化方案：CJK 连续段 + 2/3-gram 切分。"""
    words: list[str] = []
    for run in re.findall(r"[一-鿿]+", question):
        if len(run) >= 2:
            words.append(run)
        for n in (3, 2):
            if len(run) >= n:
                words.extend(run[i:i + n] for i in range(len(run) - n + 1))
    return words


def extract_keywords(question: str) -> list[str]:
    """抽取中文关键词。优先 jieba 分词，失败时退回 n-gram。"""
    try:
        import jieba  # type: ignore
        words = [w.strip() for w in jieba.cut(question) if len(w.strip()) >= 2]
    except Exception:
        words = _ngram_fallback(question)

    keywords: list[str] = []
    seen: set[str] = set()
    for w in words:
        if w not in _STOP_WORDS and w not in seen:
            seen.add(w)
            keywords.append(w)
    return keywords


def keyword_search(
    project_id: str,
    keywords: list[str],
    limit: int = 20,
) -> list[dict]:
    if not keywords:
        return []

    chunks = _load_chunks(project_id)
    results = []

    for chunk in chunks:
        text = chunk["text"]
        hit_count = 0
        for kw in keywords:
            if kw in text:
                hit_count += 1

        if hit_count > 0:
            score = hit_count / len(keywords)
            results.append({
                "chunk_id": chunk["chunk_id"],
                "chapter_no": chunk["chapter_no"],
                "chapter_title": chunk.get("chapter_title", ""),
                "text": text,
                "score": score,
                "source": "keyword",
                "hit_count": hit_count,
            })

    results.sort(key=lambda r: (-r["hit_count"], r["chapter_no"]))
    return results[:limit]
