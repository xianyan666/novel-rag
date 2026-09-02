# 神秘复苏 RAG 本地知识库

基于《神秘复苏》原文构建的本地 RAG（检索增强生成）系统。严格依据原文回答问题，返回章节引用和命中片段。

当前语料：《神秘复苏》（1617 章，约 17MB，4 个 txt 文件，位于上级目录 `../神秘复苏原文/`）。

本目录是独立于「轮回乐园 RAG」的新项目文件夹，复用了前者的架构，并修复了若干已知问题（见文末「相对上一版的修复」）。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3 + FastAPI |
| 前端 | Vue 3 + Vite + TypeScript + Pinia |
| 向量库 | FAISS (IndexFlatIP, 余弦相似度) |
| Embedding | Ollama `bge-m3` (1024 维) |
| LLM | Ollama `qwen2.5:7b`（默认，纯本地无 key） |
| 中文分词 | jieba（关键词召回） |

## 目录结构

```
神秘复苏RAG/
├── config/
│   ├── projects.json          # 项目配置（章节正则、chunk 参数）
│   ├── runtime.json           # 运行时配置（模型、索引路径）
│   ├── entities.seed.json     # 实体种子（杨间、鬼眼等）
│   └── worlds.seed.json       # 世界/副本种子（本作暂无，占位）
├── scripts/
│   ├── ingest.py              # 章节解析 + 文本切分
│   ├── build_index.py         # 向量索引构建
│   ├── build_entities.py      # 实体/提及/时间线/关系
│   ├── build_timeline.py      # 时间线事件
│   ├── build_world_index.py   # 世界/副本索引（本作基本用不上）
│   └── query.py               # 命令行查询
├── backend/                   # FastAPI 后端
├── frontend/                  # Vue 前端
├── data/mystic_recovery/      # 解析产物（ingest 后生成）
├── docs/                      # 上游设计文档（继承自上一版）
└── start.ps1 / stop.ps1       # 一键启动/停止
```

索引存储在 `C:/rag_index/mystic_recovery/`（FAISS 的 C++ `fopen` 用窄字符，中文路径会被按本地代码页解释导致写入失败，因此索引必须放纯 ASCII 路径；可在 `.env` 用 `RAG_INDEX_BASE_DIR` 覆盖）。

## 快速开始

### 0. 前置条件

- Python 3.10+，Node.js 18+
- Ollama 已安装并拉取模型：

```bash
ollama pull bge-m3
ollama pull qwen2.5:7b
```

### 1. 数据管线（命令行）

```powershell
# 1. 解析章节 + 切分
python scripts/ingest.py --project mystic_recovery

# 2. 构建向量索引（7250 个 chunk，Ollama 逐批 embedding，约 10~20 分钟）
python scripts/build_index.py --project mystic_recovery --batch-size 64

# 3. 查询
python scripts/query.py --project mystic_recovery --question "杨间第一次遇到鬼是在什么情况下？"
```

可选：构建实体索引（基于 `config/entities.seed.json`）：

```powershell
python scripts/build_entities.py --project mystic_recovery
```

### 2. Web 界面（一键启动）

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

脚本会自动检查 Ollama、安装依赖、启动后端 + 前端，浏览器打开 http://127.0.0.1:5173（若端口被占会自动换 5174-5199）。停止：

```powershell
powershell -ExecutionPolicy Bypass -File .\stop.ps1
```

### 3. 手动启动

```bash
# 后端
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev
```

## 配置说明

### config/projects.json

```json
{
  "project_id": "mystic_recovery",
  "display_name": "神秘复苏",
  "source_dir": "../神秘复苏原文",
  "chapter_patterns": ["^第([0-9一二三四五六七八九十百千万零]+)章\\s*(.*)$"],
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

- 章节正则同时匹配中文数字（`第一章`）和阿拉伯数字（`第1495章`），并含「零」（`第五百零一章`）。
- `source_dir` 指向上级目录的 `神秘复苏原文`（只读语料，不复制、不修改）。

### config/runtime.json 与 .env

默认全本地：`llm=qwen2.5:7b`、`embedding=bge-m3`，无需 API key。
如需切换到云端生成模型（OpenAI 兼容 / MiMo），编辑 `.env` 并取消注释对应行；embedding 仍建议保留 Ollama bge-m3，否则需重建索引。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects/{id}/scan` | 扫描原文 |
| POST | `/api/projects/{id}/ingest` | 解析导入 |
| POST | `/api/projects/{id}/index` | 构建向量索引 |
| POST | `/api/projects/{id}/query` | 查询 |
| GET | `/api/projects/{id}/history?limit=50` | 本地问答历史记录（最新在前） |

每次在网页发起的问答都会自动追加到本地 `data/<project_id>/query_history.jsonl`（每行一条 JSON，含时间戳、问题、回答、引用章节、命中片段、检索路由），方便回溯每次测试。文件随查询自动增长，也可用上面的 history 接口读取。

查询请求体：

```json
{"question": "杨间第一次遇到鬼是在什么情况下？", "mode": "evidence", "top_k": 8}
```

## 相对上一版的修复

1. 章节号中文数字解析支持「零」（上一版会丢弃 `第五百零一章` 这类章节）。
2. 跨文件章节重叠去重前移到写 `chapters.jsonl` 之前，避免重复章记录。
3. 导入时过滤站点广告行（`更多精彩小说…`、`请访问…`）与 `(本章完)` 标记。
4. 中文关键词召回改用 jieba 分词（无 jieba 时退回 n-gram），修复上一版「整句当做一个词」导致的召回失效。
5. 修复前端 `App.vue` 面板重复渲染、`EntityMentions.vue` 静态 key。
6. 新增 `.gitignore`，`.env` 不再内置任何真实 key。
7. 修复 `build_index.py` / `query.py` 独立运行时报 `No module named 'backend'`（导入前未把项目根加入 `sys.path`，上一版同样存在）。

## 关于实体/时间线/世界模块

这三个模块沿用上一版通用架构，但规则词典（事件词、关系词、世界边界词）原为《轮回乐园》术语定制（如「衍生世界」「主线任务」）。《神秘复苏》是都市灵异题材，这些规则命中率很低：

- 实体索引：按 `entities.seed.json` 逐字符子串匹配，**可用**（已内置杨间、周正、鬼眼等种子，可按需增补）。
- 时间线索引：`build_timeline.py` 的「进入衍生世界/主线任务」等模式基本不命中，产出稀少，可忽略。
- 世界索引：本作无「副本/位面」结构，`build_world_index.py` 会把所有章节归入「乐园/现实过渡」占位，可忽略。

核心的「依据原文问答 + 章节引用 + 命中片段」走向量检索，不受影响。
