"""配置加载。"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "projects.json"
RUNTIME_PATH = ROOT / "config" / "runtime.json"
ENV_PATH = ROOT / ".env"

_ENV_LOADED = False


def load_env_file() -> None:
    """Load simple KEY=VALUE pairs from .env without adding a dependency."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_projects() -> list[dict]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_project(project_id: str) -> dict:
    for p in load_projects():
        if p["project_id"] == project_id:
            return p
    return None


def load_runtime() -> dict:
    load_env_file()
    runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))

    env_overrides = {
        "RAG_LLM_PROVIDER": "llm_provider",
        "RAG_LLM_MODEL": "llm_model",
        "RAG_LLM_API_BASE_URL": "llm_api_base_url",
        "RAG_LLM_API_KEY": "llm_api_key",
        "RAG_LLM_CHAT_PATH": "llm_chat_path",
        "RAG_LLM_COMPLETIONS_PATH": "llm_completions_path",
        "RAG_API_PROXY": "api_proxy",
        "RAG_EMBEDDING_PROVIDER": "embedding_provider",
        "RAG_EMBEDDING_MODEL": "embedding_model",
        "RAG_EMBEDDING_API_BASE_URL": "embedding_api_base_url",
        "RAG_EMBEDDING_API_KEY": "embedding_api_key",
        "RAG_EMBEDDING_PATH": "embedding_path",
        "RAG_TEMPERATURE": "temperature",
        "RAG_TOP_K": "top_k",
        "RAG_CONTEXT_CHUNKS": "context_chunks",
        "RAG_INDEX_BASE_DIR": "index_base_dir",
    }
    for env_key, runtime_key in env_overrides.items():
        value = os.environ.get(env_key)
        if value not in (None, ""):
            if runtime_key in {"temperature"}:
                runtime[runtime_key] = float(value)
            elif runtime_key in {"top_k", "context_chunks"}:
                runtime[runtime_key] = int(value)
            else:
                runtime[runtime_key] = value

    if os.environ.get("MIMO_API_BASE_URL"):
        runtime["llm_api_base_url"] = os.environ["MIMO_API_BASE_URL"]
    if os.environ.get("MIMO_API_KEY"):
        runtime["llm_api_key"] = os.environ["MIMO_API_KEY"]
    if os.environ.get("MIMO_MODEL"):
        runtime["llm_model"] = os.environ["MIMO_MODEL"]

    return runtime


def data_dir(project_id: str) -> Path:
    return ROOT / "data" / project_id


def index_dir(project_id: str) -> Path:
    runtime = load_runtime()
    base = runtime.get("index_base_dir")
    if base:
        return Path(base) / project_id
    return ROOT / "index" / project_id
