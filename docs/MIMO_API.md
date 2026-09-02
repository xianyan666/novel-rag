# Mimo API 配置

项目根目录支持 `.env` 文件。复制 `.env.example` 为 `.env`，然后填写 mimo API：

```env
RAG_LLM_PROVIDER=mimo
MIMO_API_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your-api-key
MIMO_MODEL=mimo-v2.5-pro
RAG_LLM_CHAT_PATH=/v1/chat/completions
```

如需通过本地代理访问 MiMo，可额外配置：

```env
RAG_API_PROXY=http://127.0.0.1:7890
```

默认只替换生成模型，embedding 仍使用本地 `bge-m3`：

```env
RAG_EMBEDDING_PROVIDER=ollama
RAG_EMBEDDING_MODEL=bge-m3
```

这样可以继续使用现有 `C:/rag_index/reincarnation_paradise` 索引。

小米 MiMo 官方 API 当前没有 embedding 端点，不能把 embedding provider 设为 `mimo`。如需改用远程 embedding，需要选择另一个兼容 OpenAI `/v1/embeddings` 的向量服务并配置：

```env
RAG_EMBEDDING_PROVIDER=openai_compatible
RAG_EMBEDDING_API_BASE_URL=https://your-embedding-api-host/v1
RAG_EMBEDDING_API_KEY=your-api-key
RAG_EMBEDDING_MODEL=your-embedding-model
RAG_EMBEDDING_PATH=/v1/embeddings
```

然后重建索引：

```powershell
python scripts/build_index.py --project reincarnation_paradise
```

启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -SkipInstall -NoBrowser
```
