"""向量检索服务：embedding + FAISS 检索。"""

import json
import os

import faiss
import numpy as np

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

from ..config import load_runtime, index_dir
from .model_client import get_embedding
from .world_service import get_chapter_world


def retrieve_chunks(
    project_id: str,
    question: str,
    top_k: int,
    world_ids: set[str] | None = None,
) -> list[dict]:
    runtime = load_runtime()

    idx_dir = index_dir(project_id)
    index_path = idx_dir / "index.faiss"
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found for project '{project_id}'")

    index = faiss.read_index(str(index_path))

    meta_path = idx_dir / "metadata.json"
    docs_path = idx_dir / "documents.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    documents = json.loads(docs_path.read_text(encoding="utf-8"))

    q_embedding = np.array([get_embedding(question, runtime)], dtype=np.float32)
    faiss.normalize_L2(q_embedding)

    # World filtering happens after FAISS search. Use a wider candidate pool so
    # a valid world-local result is not discarded merely because global Top K
    # is dominated by another arc with similar wording.
    candidate_count = min(index.ntotal, max(top_k * 100, 500)) if world_ids else top_k
    scores, indices = index.search(q_embedding, candidate_count)

    retrieved = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        meta = metadata[idx]
        world = get_chapter_world(project_id, meta["chapter_no"])
        if world_ids and (not world or world["world_id"] not in world_ids):
            continue
        retrieved.append({
            "chunk_id": meta["chunk_id"],
            "chapter_no": meta["chapter_no"],
            "chapter_title": meta["chapter_title"],
            "text": documents[idx],
            "score": float(score),
            "source": "vector",
            "world_id": world.get("world_id") if world else None,
            "world_name": world.get("world_name") if world else None,
        })
        if len(retrieved) >= top_k:
            break
    return retrieved
