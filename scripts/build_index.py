"""构建向量索引：读取 chunks.jsonl，调用 Ollama embedding，写入 FAISS。"""

import argparse
import json
import os
import sys
from pathlib import Path

import faiss
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

from backend.app.config import load_runtime
from backend.app.services.model_client import get_embeddings

CONFIG_PATH = ROOT / "config" / "projects.json"
RUNTIME_PATH = ROOT / "config" / "runtime.json"


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


def check_embedding_provider(runtime: dict) -> bool:
    provider = runtime.get("embedding_provider", "ollama").lower()
    if provider != "ollama":
        return True
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        needed = runtime.get("embedding_model", "bge-m3")
        for m in models:
            if m == needed or m.startswith(needed + ":"):
                return True
        print(f"WARNING: Embedding model '{needed}' not found in Ollama.")
        print(f"Available models: {models}")
        print(f"Run: ollama pull {needed}")
        return False
    except Exception:
        return False


def build_index(project_id: str, batch_size: int = 64) -> None:
    project, runtime = load_config(project_id)

    if not check_embedding_provider(runtime):
        print("ERROR: Ollama not ready. Start Ollama and pull the embedding model first.")
        sys.exit(1)

    chunks_path = ROOT / "data" / project_id / "chunks.jsonl"
    if not chunks_path.exists():
        print(f"ERROR: {chunks_path} not found. Run ingest.py first.")
        sys.exit(1)

    # Read chunks
    chunks = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    if not chunks:
        print("ERROR: No chunks found.")
        sys.exit(1)

    print(f"Loaded {len(chunks)} chunks for project '{project_id}'")

    embedding_model = runtime["embedding_model"]

    # Setup output directory (use index_base_dir if configured, to avoid Unicode path issues)
    base = runtime.get("index_base_dir")
    if base:
        index_dir = Path(base) / project_id
    else:
        index_dir = ROOT / "index" / project_id
    index_dir.mkdir(parents=True, exist_ok=True)

    # Batch embed
    all_embeddings = []
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = get_embeddings(texts, runtime)
        all_embeddings.extend(embeddings)
        done = min(i + batch_size, total)
        print(f"  Embedded {done}/{total} chunks")

    # Build FAISS index
    dim = len(all_embeddings[0])
    vectors = np.array(all_embeddings, dtype=np.float32)

    # Normalize for cosine similarity
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(dim)  # Inner product = cosine for normalized vectors
    index.add(vectors)

    # Save index
    faiss.write_index(index, str(index_dir / "index.faiss"))

    # Save metadata
    metadata = []
    for c in chunks:
        metadata.append({
            "chunk_id": c["chunk_id"],
            "chapter_no": c["chapter_no"],
            "chapter_title": c["chapter_title"],
            "source_file": c["source_file"],
            "chunk_index": c["chunk_index"],
        })
    meta_path = index_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    # Save documents for retrieval
    docs_path = index_dir / "documents.json"
    docs = [c["text"] for c in chunks]
    docs_path.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")

    print(f"\nIndex built: {index_dir}")
    print(f"  Vectors: {index.ntotal}, Dimension: {dim}")


def main():
    parser = argparse.ArgumentParser(description="Build vector index")
    parser.add_argument("--project", required=True, help="Project ID")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    args = parser.parse_args()
    build_index(args.project, args.batch_size)


if __name__ == "__main__":
    main()
