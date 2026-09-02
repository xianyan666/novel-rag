"""Model provider client for LLM generation and embeddings."""

import os
from urllib.parse import urljoin

import requests

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"


OPENAI_COMPATIBLE_PROVIDERS = {"openai_compatible", "openai", "mimo"}


def _join_url(base_url: str, path: str) -> str:
    if base_url.rstrip("/").endswith("/v1") and path.startswith("/v1/"):
        path = path[3:]
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _bearer_headers(api_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _external_api_proxies(runtime: dict) -> dict | None:
    proxy = runtime.get("api_proxy", "").strip()
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _runtime_value(runtime: dict, key: str, fallback_key: str | None = None, default=None):
    value = runtime.get(key)
    if value in (None, "") and fallback_key:
        value = runtime.get(fallback_key)
    return default if value in (None, "") else value


def generate_text(prompt: str, runtime: dict, timeout: int = 120) -> str:
    provider = runtime.get("llm_provider", "ollama").lower()
    model = runtime["llm_model"]
    temperature = runtime.get("temperature", 0.2)

    if provider == "ollama":
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama LLM failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()["response"]

    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        base_url = _runtime_value(runtime, "llm_api_base_url", default="https://api.openai.com")
        api_key = _runtime_value(runtime, "llm_api_key")
        chat_path = _runtime_value(runtime, "llm_chat_path", "llm_completions_path", "/v1/chat/completions")
        resp = requests.post(
            _join_url(base_url, chat_path),
            headers=_bearer_headers(api_key),
            proxies=_external_api_proxies(runtime),
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": False,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"{provider} LLM failed: {resp.status_code} {resp.text[:500]}")
        data = resp.json()
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            return choice.get("text", "")
        raise RuntimeError(f"{provider} LLM response missing choices")

    raise ValueError(f"Unsupported llm_provider: {provider}")


def get_embeddings(texts: list[str], runtime: dict, timeout: int = 300) -> list[list[float]]:
    provider = runtime.get("embedding_provider", "ollama").lower()
    model = runtime["embedding_model"]

    if provider == "mimo":
        raise ValueError(
            "MiMo official API does not currently provide an embedding endpoint. "
            "Use Ollama or an OpenAI-compatible embedding provider instead."
        )

    if provider == "ollama":
        resp = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": model, "input": texts},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama embedding failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()["embeddings"]

    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        base_url = _runtime_value(
            runtime,
            "embedding_api_base_url",
            "llm_api_base_url",
            "https://api.openai.com",
        )
        api_key = _runtime_value(runtime, "embedding_api_key", "llm_api_key")
        path = _runtime_value(runtime, "embedding_path", default="/v1/embeddings")
        resp = requests.post(
            _join_url(base_url, path),
            headers=_bearer_headers(api_key),
            proxies=_external_api_proxies(runtime),
            json={"model": model, "input": texts},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"{provider} embedding failed: {resp.status_code} {resp.text[:500]}")
        data = resp.json()
        if "data" not in data:
            raise RuntimeError(f"{provider} embedding response missing data")
        return [item["embedding"] for item in data["data"]]

    raise ValueError(f"Unsupported embedding_provider: {provider}")


def get_embedding(text: str, runtime: dict, timeout: int = 60) -> list[float]:
    return get_embeddings([text], runtime, timeout=timeout)[0]
