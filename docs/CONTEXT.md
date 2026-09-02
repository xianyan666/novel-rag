# 开发进度与状态

版本：v0.3.1
更新时间：2026-07-04
关联文档：[PRD.md](./PRD.md)、[AGENT_SPEC.md](./AGENT_SPEC.md)、[V0.2_DESIGN.md](./V0.2_DESIGN.md)、[V0.2_AGENT_SPEC.md](./V0.2_AGENT_SPEC.md)、[V0.3_DESIGN.md](./V0.3_DESIGN.md)、[V0.3_AGENT_SPEC.md](./V0.3_AGENT_SPEC.md)、[V0.3.1_FIX_PLAN.md](./V0.3.1_FIX_PLAN.md)

## 1. 总体进度

| 阶段 | 内容 | 状态 | 备注 |
|------|------|------|------|
| 1 | 项目配置文件 | 完成 | `config/projects.json`、`config/runtime.json` |
| 2 | 章节解析脚本 | 完成 | `scripts/ingest.py`，4143 章节成功解析 |
| 3 | 文本切分 | 完成 | 集成在 `ingest.py` 中，19719 chunks 生成 |
| 4 | 向量索引构建 | 完成 | 方案 A：索引目录 `C:/rag_index/`，19719 向量，维度 1024 |
| 5 | CLI 查询验证 | 完成 | 端到端测试通过 |
| 6 | FastAPI 后端 | 完成 | 8 个基础 API + 时间线 + 实体 API（共 17 个端点） |
| 7 | Vue 前端 | 完成 | 澎湃风格启发，12 个组件，实体库/详情抽屉 |
| 8 | 问题分类器 | 完成 | `question_classifier.py`，规则分类 10 种问题类型（含 5 种实体类型） |
| 9 | 时间线索引 | 完成 | `build_timeline.py`，3704 事件（world_entry/return/task） |
| 10 | 多路检索路由 | 完成 | `retrieval_router.py`，向量+关键词+时间线+实体混合检索 |
| 11 | 证据保护层 | 完成 | `guard_evidence()`，顺序型问题 + 实体问题保护 |
| 12 | 前端 V0.2 增补 | 完成 | 问题分析、时间线候选、证据警告、调试开关 |
| 13 | 实体种子配置 | 完成 | `config/entities.seed.json`，4 个种子实体（苏晓、斩龙闪、莫蕾、青钢影） |
| 14 | 实体构建脚本 | 完成 | `scripts/build_entities.py`，规则匹配抽取 |
| 15 | 实体后端服务 | 完成 | `entity_service.py`、`entity_build_service.py`、`entity_query_router.py` |
| 16 | 实体 API | 完成 | 9 个实体端点（构建、列表、搜索、详情、提及、时间线、关系） |
| 17 | 实体数据产物 | 完成 | entities(4)、mentions(22959)、timeline(16216)、relations(4976) |
| 18 | 查询服务集成 | 完成 | 实体查询路由 + LLM prompt 实体证据块 |
| 19 | 前端实体组件 | 完成 | EntityPanel/Search/Timeline/Mentions/Relations/DetailDrawer/RelationGraph/EvidenceBadge |
| 20 | 前端风格改造 | 完成 | 澎湃 OS 风格启发，浅色通透主题 |
| 21 | 实体首次出现保护 | 完成 | V0.3.1，entity_first_seen 受保护结论，向量降权为补充 |
| 22 | 实体时间线降噪 | 完成 | V0.3.1，附近窗口匹配(120字)，同章同事件去重，置信度过滤 |
| 23 | LLM 冲突后处理 | 完成 | V0.3.1，protected_answer 结构化结论块 + 章节号检查 |
| 24 | 前端证据展示 | 完成 | V0.3.1，受保护结论卡片、证据权重面板、低置信候选折叠 |

V0.1 MVP + V0.2 时间线索引 + V0.3 实体索引 + V0.3.1 实体问答保护全部完成。

## 2. 文件清单

### 配置

- `config/projects.json` — 项目配置（轮回乐园，UTF-8，章节正则 `^第([0-9一二三四五六七八九十百千万]+)章\s*(.*)$`，chunk_size=1000，chunk_overlap=200）
- `config/runtime.json` — 运行时配置（Ollama qwen2.5:7b + bge-m3，index_base_dir=C:/rag_index）
- `config/entities.seed.json` — 实体种子配置（V0.3，4 个种子：苏晓、斩龙闪、莫蕾、青钢影）

### 数据管线脚本

- `scripts/ingest.py` — 章节解析 + 文本切分，输出 `data/{project_id}/chapters.jsonl`、`chunks.jsonl`、`ingest_report.json`
- `scripts/build_index.py` — 向量索引构建（FAISS IndexFlatIP，余弦相似度）
- `scripts/query.py` — 命令行查询验证
- `scripts/build_timeline.py` — 时间线事件抽取（规则匹配，输出 timeline_events.jsonl + timeline_index.json）
- `scripts/build_entities.py` — 实体索引构建（V0.3，种子+规则匹配；V0.3.1 附近窗口匹配 120 字+同章同事件去重）

### 后端 (FastAPI)

- `backend/app/main.py` — FastAPI 主入口，17 个 API 端点（基础 8 + 时间线 2 + 实体 7）
- `backend/app/config.py` — 配置加载（项目配置、运行时配置、数据目录、索引目录）
- `backend/app/schemas.py` — Pydantic 数据模型（含 QueryAnalysis、TimelineEventResponse、RetrievalDebug、EntityInfo、EntityMentionResponse、EntityTimelineEventResponse、EntityRelationResponse、EntityAnalysis、ProtectedAnswer、EvidenceScore）
- `backend/app/services/project_service.py` — 项目管理服务
- `backend/app/services/ingest_service.py` — 导入服务（调用 ingest.py）
- `backend/app/services/index_service.py` — 索引构建服务（调用 build_index.py）
- `backend/app/services/query_service.py` — 查询服务（检索路由 + LLM 生成 + protected_answer 结构化结论块 + 冲突后处理）
- `backend/app/services/question_classifier.py` — 问题分类器（规则匹配 10 种类型，含 5 种实体类型）
- `backend/app/services/timeline_service.py` — 时间线事件加载与查询
- `backend/app/services/timeline_build_service.py` — 时间线索引构建服务
- `backend/app/services/keyword_service.py` — 关键词检索服务
- `backend/app/services/vector_service.py` — 向量检索服务（FAISS + Ollama embedding）
- `backend/app/services/retrieval_router.py` — 多路检索路由 + 证据保护（含实体查询路由集成；V0.3.1 实体优先路由，向量降权为补充）
- `backend/app/services/entity_service.py` — 实体服务（加载、搜索、查询实体/提及/时间线/关系）
- `backend/app/services/entity_build_service.py` — 实体构建服务（调用 build_entities.py）
- `backend/app/services/entity_query_router.py` — 实体查询路由（实体检测 + 按查询类型路由检索 + 实体评分 + protected_answer 构建）（V0.3.1 增加评分函数和保护逻辑）
- `backend/requirements.txt` — 依赖：fastapi, uvicorn, requests, pydantic, faiss-cpu, numpy

### 前端 (Vue 3 + Vite + TypeScript)

- `frontend/package.json` — 依赖声明
- `frontend/vite.config.ts` — Vite 配置，API 代理 /api -> localhost:8000
- `frontend/tsconfig.json` — TypeScript 配置
- `frontend/index.html` — 入口 HTML
- `frontend/src/main.ts` — Vue 入口（createApp + createPinia）
- `frontend/src/App.vue` — 根组件（header + sidebar + main 布局，4 个导航 tab：项目/数据索引/问答/实体库）
- `frontend/src/api/client.ts` — API 客户端（含 timeline + entities 全部 API 方法）
- `frontend/src/types/api.ts` — TypeScript 类型定义（含 QueryAnalysis、TimelineEventInfo、RetrievalDebug、EntityInfo、EntityMention、EntityTimelineEvent、EntityRelation、EntityAnalysis、ProtectedAnswer、EvidenceScore）
- `frontend/src/stores/projectStore.ts` — Pinia store（含实体状态管理：entities、entityCount、buildEntities、openEntityDetail 等）
- `frontend/src/components/ProjectPanel.vue` — 项目列表 + 项目详情
- `frontend/src/components/IndexPanel.vue` — 索引管理（扫描、导入、构建索引、构建时间线索引 + 导入报告展示）
- `frontend/src/components/QueryPanel.vue` — 查询输入（问题输入、Top K 设置）
- `frontend/src/components/AnswerPanel.vue` — 回答展示（问题分析、时间线候选、实体证据、证据警告、调试开关、引用章节、命中片段可展开；V0.3.1 增加受保护结论卡片和证据权重面板）
- `frontend/src/components/EntityPanel.vue` — 实体库入口（实体统计、构建实体索引、实体列表、实体搜索）（V0.3）
- `frontend/src/components/EntitySearch.vue` — 实体搜索组件（V0.3）
- `frontend/src/components/EntityDetailDrawer.vue` — 实体详情抽屉（V0.3）
- `frontend/src/components/EntityTimeline.vue` — 实体生命周期展示（V0.3；V0.3.1 高/低置信度分离，低置信候选默认折叠）
- `frontend/src/components/EntityMentions.vue` — 实体出现章节列表（V0.3）
- `frontend/src/components/EntityRelations.vue` — 实体关系列表（V0.3）
- `frontend/src/components/RelationGraph.vue` — 实体关系图（V0.3）
- `frontend/src/components/EvidenceBadge.vue` — 证据类型标签（V0.3；V0.3.1 新增 protected/supplemental/low_confidence/entity_weighted 标签）
- `frontend/src/styles/main.css` — 全局样式（V0.3 改为澎湃风格启发，浅色通透主题，CSS 变量）

### 数据产物

- `data/reincarnation_paradise/chapters.jsonl` — 4143 条章节记录（约 47MB）
- `data/reincarnation_paradise/chunks.jsonl` — 19719 条切片记录（约 58MB）
- `data/reincarnation_paradise/ingest_report.json` — 导入报告
- `data/reincarnation_paradise/timeline_events.jsonl` — 3704 条时间线事件（V0.2）
- `data/reincarnation_paradise/timeline_index.json` — 时间线索引（V0.2）
- `data/reincarnation_paradise/entities.jsonl` — 4 个实体（V0.3，种子实体：苏晓、莫蕾、斩龙闪、青钢影）
- `data/reincarnation_paradise/entity_mentions.jsonl` — 22959 条实体提及（V0.3）
- `data/reincarnation_paradise/entity_timeline.jsonl` — 16216 条实体时间线事件（V0.3）
- `data/reincarnation_paradise/entity_relations.jsonl` — 4976 条实体关系（V0.3）
- `data/reincarnation_paradise/entity_index.json` — 实体快速索引（V0.3）

### V0.2 时间线事件分布

| 事件类型 | 数量 | 说明 |
|----------|------|------|
| `world_entry` | 1059 | 进入衍生世界 |
| `world_return` | 954 | 回归乐园 |
| `task_start` | 1405 | 任务开始（主线/支线/隐藏） |
| `task_complete` | 286 | 任务完成 |

时间线数据管线：`chunks.jsonl` → `build_timeline.py`（规则匹配） → `timeline_events.jsonl` + `timeline_index.json`

### V0.3 实体种子与数据统计

种子实体（`config/entities.seed.json`）：

| 名称 | 类型 | 别名 | 首次出现章节 |
|------|------|------|-------------|
| 苏晓 | character | 白夜 | 第 1 章 |
| 斩龙闪 | item (weapon) | 斩龙之刃 | 第 8 章 |
| 莫蕾 | character | — | 第 2413 章 |
| 青钢影 | skill | — | 第 24 章 |

实体数据管线：`config/entities.seed.json` + `chunks.jsonl` → `build_entities.py`（种子+规则匹配） → `entities.jsonl` + `entity_mentions.jsonl` + `entity_timeline.jsonl` + `entity_relations.jsonl` + `entity_index.json`

| 数据文件 | 记录数 | 说明 |
|----------|--------|------|
| entities.jsonl | 4 | 实体主表 |
| entity_mentions.jsonl | 22959 | 实体提及（某实体在哪些 chunk 出现） |
| entity_timeline.jsonl | 16216 | 实体生命周期事件（V0.3 构建；V0.3.1 重建后预计减少，因窗口匹配+去重） |
| entity_relations.jsonl | 4976 | 实体关系边 |

### 索引产物

- `C:/rag_index/reincarnation_paradise/index.faiss` — FAISS 索引文件（约 78MB）
- `C:/rag_index/reincarnation_paradise/documents.json` — chunk 文本文档（约 51MB）
- `C:/rag_index/reincarnation_paradise/metadata.json` — chunk 元数据（约 3.3MB）

## 3. 已解决问题：FAISS 中文路径

**问题描述**：FAISS 的 C++ 后端在 Windows 下无法处理包含中文字符的文件路径。`faiss.write_index()` 和 `faiss.read_index()` 调用时，路径中的中文字符会变成乱码，导致文件操作失败。

**尝试过的方案**：

1. **ChromaDB PersistentClient** — 写入成功但查询时报 HNSW 索引加载错误（`Error loading hnsw index`），降级/重建均无法解决，疑似 ChromaDB 1.5.9 的 bug。
2. **FAISS + tempfile 中转** — 写入时先写到临时目录再 copy 回来，可工作但增加复杂度。

**最终采用方案 A**：在 `config/runtime.json` 中增加 `index_base_dir` 配置项，将索引目录改到无中文路径 `C:/rag_index/`。

修改的文件：
- `config/runtime.json` — 增加 `"index_base_dir": "C:/rag_index"`
- `backend/app/config.py` — `index_dir()` 函数读取 `index_base_dir` 配置
- `scripts/build_index.py` — 使用 `index_base_dir` 配置确定输出目录
- `scripts/query.py` — 使用 `index_base_dir` 配置确定索引目录
- `backend/app/services/query_service.py` — 通过 `index_dir()` 函数获取索引路径

**验证结果**：19719 个向量成功构建（维度 1024），CLI 查询和 API 查询均正常工作。

## 4. Ollama 环境状态

- Ollama 版本：0.30.10
- Ollama 路径：`E:/Model/ollama/ollama`
- 已安装模型：
  - `bge-m3`（1.2GB，embedding 模型，输出 1024 维向量）
  - `qwen2.5:7b`（4.7GB，生成模型）
- 服务运行端口：11434
- **重要**：系统存在 HTTP 代理（127.0.0.1:7890），访问 Ollama 需要设置 `NO_PROXY=localhost,127.0.0.1`，已在所有脚本和后端中处理。

## 5. 已知数据问题

导入报告（`ingest_report.json`）显示：

- **缺失章节**（8 个）：704, 807, 858, 2255, 2407, 2423, 2859, 3040
- **重复章节号**（8 个）：13, 34, 58, 60, 69, 77, 84, 86 — 来自不同源文件的章节号重叠，已在切分时去重（保留文本更长的版本）
- **空内容章节**（18 个警告）：部分章节解析后正文为空

## 6. 依赖安装状态

| 依赖 | 状态 | 说明 |
|------|------|------|
| Python 3.x | 已安装 | Anaconda 环境 |
| FastAPI | 已安装 | 0.139.0 |
| uvicorn | 已安装 | ASGI 服务器 |
| faiss-cpu | 已安装 | 1.14.3，向量检索 |
| numpy | 已安装 | 向量运算 |
| requests | 已安装 | HTTP 请求（调用 Ollama） |
| pydantic | 已安装 | 数据校验 |
| chromadb | 已安装 | 1.5.9，有 bug，未使用 |
| Node.js / npm | 已安装 | 前端构建 |
| Vue 3 + Vite + TS | 已安装 | frontend/node_modules |
| Pinia | 已安装 | Vue 状态管理 |

## 7. API 接口

### GET /api/projects

返回项目列表，每个项目包含：project_id、display_name、source_dir、source_exists、has_chapters、has_chunks、has_index、report。

### GET /api/projects/{project_id}

返回单个项目详情。

### POST /api/projects/{project_id}/scan

扫描原文目录，返回 txt 文件列表和总大小。

### POST /api/projects/{project_id}/ingest

执行章节解析和文本切分，返回导入报告（章节数、切片数、缺失章节、重复章节、警告）。

### POST /api/projects/{project_id}/index

构建向量索引（调用 Ollama embedding + FAISS），同步执行，耗时较长。

### POST /api/projects/{project_id}/query

查询接口。请求体：
```json
{
  "question": "苏晓第一次接触轮回乐园是在什么情况下？",
  "mode": "evidence",
  "top_k": 8
}
```

响应体（V0.2 新增字段可选）：
```json
{
  "answer": "根据原文...",
  "citations": [
    {"chapter_no": 1, "chapter_title": "复仇者", "chunk_id": "..."}
  ],
  "retrieved_chunks": [
    {"chunk_id": "...", "chapter_no": 1, "chapter_title": "复仇者", "text_preview": "..."}
  ]
}
```

V0.2 新增返回字段：
```json
{
  "query_analysis": {
    "query_type": "sequence_first",
    "entities": ["苏晓"],
    "event_hints": ["进入世界"],
    "time_constraint": "earliest",
    "confidence": 0.9
  },
  "timeline_events": [
    {
      "event_id": "...",
      "event_type": "world_entry",
      "chapter_no": 6,
      "chapter_title": "...",
      "event_summary": "..."
    }
  ],
  "retrieval_debug": {
    "route": "timeline_plus_keyword_plus_vector",
    "vector_count": 8,
    "timeline_count": 3,
    "keyword_count": 5,
    "warnings": []
  }
}
```

V0.3.1 新增返回字段：
```json
{
  "protected_answer": {
    "type": "entity_first_seen",
    "entity_id": "...",
    "entity_name": "斩龙闪",
    "chapter_no": 8,
    "chapter_title": "斩龙之刃",
    "chunk_id": "...",
    "source": "entity_mention",
    "final_score": 0.98
  },
  "evidence_scores": [
    {
      "chunk_id": "...",
      "source": "entity_mention",
      "entity_score": 1.0,
      "order_score": 0.99,
      "keyword_score": 0.8,
      "vector_score": 0.0,
      "confidence_score": 0.95,
      "final_score": 0.98,
      "protected": true
    }
  ]
}
```

### POST /api/projects/{project_id}/timeline/build

构建时间线索引，返回状态。

### GET /api/projects/{project_id}/timeline/events

查询时间线事件。可选参数：`event_type`、`subject`。

### POST /api/projects/{project_id}/entities/build

构建实体索引（调用 `build_entities.py`），返回状态。

### GET /api/projects/{project_id}/entities

返回实体列表。可选参数：`entity_type`。

### GET /api/projects/{project_id}/entities/search

搜索实体。参数：`q`（查询字符串）。

### GET /api/projects/{project_id}/entities/{entity_id}

返回单个实体详情。

### GET /api/projects/{project_id}/entities/{entity_id}/mentions

返回实体提及列表。

### GET /api/projects/{project_id}/entities/{entity_id}/timeline

返回实体时间线事件。

### GET /api/projects/{project_id}/entities/{entity_id}/relations

返回实体关系列表。

### GET /api/projects/{project_id}/relations

查询关系。可选参数：`source`、`target`。

## 8. 运行命令

### 后端

```bash
cd backend
pip install -r requirements.txt
# 需要设置 NO_PROXY 以访问本地 Ollama
NO_PROXY=localhost,127.0.0.1 uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 默认端口 5173，API 代理到 localhost:8000
```

### 数据管线

```bash
# 1. 解析章节 + 切分
python scripts/ingest.py --project reincarnation_paradise

# 2. 构建向量索引（需要 Ollama 运行 + bge-m3 模型）
NO_PROXY=localhost,127.0.0.1 python scripts/build_index.py --project reincarnation_paradise

# 3. 构建时间线索引（V0.2，不需要 Ollama）
python scripts/build_timeline.py --project reincarnation_paradise

# 4. 构建实体索引（V0.3/V0.3.1，不需要 Ollama）
# V0.3.1 重建后实体时间线数量会减少（窗口匹配+去重）
python scripts/build_entities.py --project reincarnation_paradise

# 5. 命令行查询验证
NO_PROXY=localhost,127.0.0.1 python scripts/query.py --project reincarnation_paradise --question "苏晓第一次接触轮回乐园是在什么情况下？"
```

## 9. 检索策略（V0.3.1）

V0.3 在 V0.2 基础上新增实体检索路由，V0.3.1 增加实体优先加权和首次出现保护：

### 问题分类

| 类型 | 触发词示例 | 检索路由 |
|------|-----------|---------|
| `normal_fact` | 无特殊关键词 | 向量检索 |
| `sequence_first` | 第一个、首次、最早 | 时间线 + 关键词 + 向量 |
| `sequence_order` | 顺序、先后、依次 | 时间线 + 关键词 |
| `timeline_summary` | 时间线、经历、全过程 | 时间线 |
| `chapter_lookup` | 哪一章、在哪章 | 关键词 + 向量 |
| `entity_first_seen` | 第一次出现、首次登场 | 实体提及索引 + 向量 |
| `entity_timeline` | 后续变化、经历了什么 | 实体时间线 + 向量 |
| `entity_profile` | 档案、介绍、总结 | 实体提及 + 时间线 + 向量 |
| `entity_relation` | 关系、交集、互动 | 实体关系 + 向量 |
| `entity_mentions` | 出现在哪些章节、重要章节 | 实体提及 + 向量 |

### 检索流程

```
用户问题 → 问题分类器 → 实体检测 → 检索路由 → 多路召回 → 合并排序 → 证据保护 → LLM 生成
```

V0.3.1 实体查询链路（实体优先，向量仅作补充）：
```
用户问题 → 问题分类器 → Entity Detector → Retrieval Router
  → entity_first_seen: Entity Mention Index(protected) + Vector(max 3, supplemental) → LLM + 冲突后处理
  → entity_timeline: Entity Timeline(nearby window) + Vector(max 3, supplemental) → 按 chapter_no 升序
  → entity_relation: Entity Relations(scored) + Vector(max 3, supplemental) → 高置信优先
  → entity_profile: Entities + Mentions + Timeline + Vector(max 3, supplemental)
  → entity_mentions: Entity Mentions + Vector(max 3, supplemental)
```

### 合并评分公式

- 顺序型问题：`semantic*0.25 + keyword*0.20 + event_type*0.30 + early_chapter*0.25`
- 普通问题：`semantic*0.40 + keyword*0.30 + event_type*0.20 + early_chapter*0.10`

### 证据保护

顺序型问题（sequence_first）的保护规则：
- 无时间线事件 → 标记证据不足
- 所有候选均来自后期章节(>100章) → 警告
- 向量召回全部来自后期章节(>500章) → 不建议据此回答"第一个"

V0.3.1 实体问题保护规则：
- `entity_first_seen`：最早 explicit mention 为 protected evidence，向量仅作补充，不可覆盖
- `entity_timeline`：事件必须在实体名附近窗口(120字)内匹配，同章同事件类型去重
- `entity_relation`：`related_to`(无关系词共现) 为低置信候选
- LLM 后处理：如果输出与 protected answer 冲突(章节号不匹配)，使用程序模板覆盖

V0.3.1 评分公式：
- `entity_first_seen`：`entity*0.50 + order*0.35 + keyword*0.10 + confidence*0.02`
- `entity_timeline`：`nearby*0.35 + event_word*0.25 + confidence*0.20 + chapter*0.10`
- `entity_relation`：`pair*0.35 + relation_word*0.25 + confidence*0.20 + chapter*0.10`

### 模型配置

- Embedding：Ollama bge-m3（1024 维）
- 生成：Ollama qwen2.5:7b，温度 0.2
- Top K：8（可在 runtime.json 或查询时调整）

## 10. 后续优化方向

1. **回答质量优化**：
   - 调整 chunk_size（当前 1000）和 chunk_overlap（当前 200）
   - 增加 reranker 提高检索精度
   - 优化系统提示词

2. ~~**混合检索**~~：V0.2 已实现多路检索（向量 + 关键词 + 时间线）

3. ~~**实体抽取**~~：V0.3 已实现种子实体 + 规则抽取（4 实体，22959 提及，16216 时间线事件，4976 关系）

4. ~~**时间线**~~：V0.2 已实现时间线事件抽取与索引（3704 事件）

5. ~~**角色档案**~~：V0.3 已实现实体档案（entity_profile 查询类型 + EntityDetailDrawer）

6. **小说迁移向导**：上传新小说后自动推荐章节正则

7. **API 模型切换**：本地模型和云端模型共用同一接口

8. ~~**依赖清理**~~：已从 requirements.txt 移除 chromadb，加入 faiss-cpu 和 numpy

9. **LLM 辅助实体抽取**：在种子+规则基础上增加 LLM 辅助抽取（V0.3 当前仅规则匹配）

10. **实体关系图可视化优化**：RelationGraph.vue 当前为列表/矩阵视图，可增加图形视图

11. **实体审核与别名合并**：人工审核候选实体，合并别名冲突

12. **自动实体种子生成**：新小说迁移时自动生成实体种子
