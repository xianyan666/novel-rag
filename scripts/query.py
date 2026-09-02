"""命令行查询验证：检索相关 chunks，调用 Ollama LLM 回答。"""

import argparse
import json
import os
import sys
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

from backend.app.config import load_runtime
from backend.app.services.model_client import generate_text, get_embedding

CONFIG_PATH = ROOT / "config" / "projects.json"
RUNTIME_PATH = ROOT / "config" / "runtime.json"

SYSTEM_PROMPT = """你是小说原文考据助手。只能根据提供的原文片段回答。
如果片段不足以回答，必须说"当前证据不足"。
不要编造章节、人物关系、设定或剧情。
不要输出大段原文。
回答后列出引用章节。"""


def load_config(project_id: str) -> tuple[dict, dict]:
    projects = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    project = None
    for p in projects:
        if p["project_id"] == project_id:
            project = p
            break
    if not project:
        raise ValueError(f"Project '{project_id}' not found")
    runtime = load_runtime()
    return project, runtime


def query_llm(question: str, context_chunks: list[dict], runtime: dict) -> str:
    context_parts = []
    for c in context_chunks:
        context_parts.append(
            f"【第{c['chapter_no']}章 {c['chapter_title']}】\n{c['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

原文片段：
{context}

用户问题：{question}

请基于以上原文片段回答："""

    return generate_text(prompt, runtime, timeout=120)


def query(project_id: str, question: str, top_k: int | None = None) -> None:
    project, runtime = load_config(project_id)

    if top_k is None:
        top_k = runtime.get("top_k", 8)

    # Check index exists (use index_base_dir if configured, to avoid Unicode path issues)
    base = runtime.get("index_base_dir")
    if base:
        index_dir = Path(base) / project_id
    else:
        index_dir = ROOT / "index" / project_id
    index_path = index_dir / "index.faiss"
    if not index_path.exists():
        print(f"ERROR: Index not found at {index_dir}. Run build_index.py first.")
        sys.exit(1)

    # Load FAISS index
    index = faiss.read_index(str(index_path))

    # Load metadata and documents
    meta_path = index_dir / "metadata.json"
    docs_path = index_dir / "documents.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    documents = json.loads(docs_path.read_text(encoding="utf-8"))

    # Embed question
    embedding_model = runtime["embedding_model"]
    print(f"Embedding question with {embedding_model}...")
    q_embedding = np.array([get_embedding(question, runtime)], dtype=np.float32)
    faiss.normalize_L2(q_embedding)

    # Search
    scores, indices = index.search(q_embedding, top_k)

    retrieved = []
    for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
        if idx < 0:
            continue
        meta = metadata[idx]
        retrieved.append({
            "chunk_id": meta["chunk_id"],
            "chapter_no": meta["chapter_no"],
            "chapter_title": meta["chapter_title"],
            "text": documents[idx],
            "score": float(score),
        })

    print(f"Retrieved {len(retrieved)} chunks\n")

    # Generate answer
    llm_model = runtime["llm_model"]
    print(f"Generating answer with {llm_model}...\n")
    answer = query_llm(question, retrieved, runtime)

    # Output
    print("=" * 60)
    print("回答：")
    print(answer)
    print()
    print("引用章节：")
    seen_chapters = set()
    for r in retrieved:
        ch_key = (r["chapter_no"], r["chapter_title"])
        if ch_key not in seen_chapters:
            seen_chapters.add(ch_key)
            print(f"  第{r['chapter_no']}章 {r['chapter_title']}")
    print()
    print("命中片段：")
    for r in retrieved:
        preview = r["text"][:120].replace("\n", " ")
        print(f"  [{r['chunk_id']}] (相似度:{r['score']:.4f}) {preview}...")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Query the RAG system")
    parser.add_argument("--project", required=True, help="Project ID")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--top-k", type=int, default=None, help="Number of chunks to retrieve")
    args = parser.parse_args()
    query(args.project, args.question, args.top_k)


if __name__ == "__main__":
    main()
