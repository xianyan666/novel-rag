# Agent 实施规格：小说原文 RAG 本地网页

版本：v0.1  
日期：2026-07-02  
依赖文档：[PRD.md](./PRD.md)  
前端技术栈：Vue 3 + Vite + TypeScript  
后端技术栈：Python + FastAPI  
模型运行：Ollama 本地优先，后期可切 API

## 1. Agent 总目标

在当前工作区内实现一个可迁移的小说原文 RAG 系统。MVP 只解决一件事：基于用户提供的小说 txt 原文，在本地网页中严格依据原文回答问题，并返回章节引用和命中片段。

当前首个小说项目是《轮回乐园》，但实现不得写死该小说名称、章节格式或文件名。系统必须通过项目配置支持后续接入其他小说，例如《西游记》。

## 2. 工作边界

Agent 可以新增和修改：

```text
config/
data/
index/
scripts/
backend/
frontend/
docs/
```

Agent 不得修改：

```text
原文/
```

除非用户明确要求，任何清洗、去重、索引生成都只能写入 `data/` 或 `index/`，不能覆盖原始 txt。

## 3. 最终目录目标

```text
RAG/
  原文/
  config/
    projects.json
    runtime.json
  data/
    reincarnation_paradise/
      chapters.jsonl
      chunks.jsonl
      ingest_report.json
  index/
    reincarnation_paradise/
  scripts/
    ingest.py
    build_index.py
    query.py
  backend/
    app/
      main.py
      config.py
      schemas.py
      services/
        project_service.py
        ingest_service.py
        index_service.py
        query_service.py
    requirements.txt
  frontend/
    package.json
    vite.config.ts
    src/
      main.ts
      App.vue
      api/
        client.ts
      components/
        ProjectPanel.vue
        IndexPanel.vue
        QueryPanel.vue
        AnswerPanel.vue
      stores/
        projectStore.ts
      types/
        api.ts
      styles/
        main.css
  docs/
    PRD.md
    AGENT_SPEC.md
```

如果采用更简单结构，必须保证职责不混乱：原文、结构化数据、索引、后端、前端分离。

## 4. 实施顺序

### 阶段 1：项目配置

创建 `config/projects.json`：

```json
[
  {
    "project_id": "reincarnation_paradise",
    "display_name": "轮回乐园",
    "source_dir": "原文",
    "encoding": "utf-8",
    "chapter_patterns": [
      "^第([0-9一二三四五六七八九十百千万]+)章\\s*(.*)$"
    ],
    "remove_duplicate_chapter_title": true,
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "language": "zh"
  }
]
```

创建 `config/runtime.json`：

```json
{
  "llm_provider": "ollama",
  "llm_model": "qwen2.5:7b",
  "embedding_provider": "ollama",
  "embedding_model": "bge-m3",
  "temperature": 0.2,
  "top_k": 8,
  "context_chunks": 5
}
```

验收：

1. 配置文件存在。
2. 配置可被 Python 正常读取。
3. 所有路径以工作区根目录为基准解析。

### 阶段 2：章节解析

实现 `scripts/ingest.py`，负责：

1. 读取 `config/projects.json`。
2. 扫描 `source_dir` 下的 `.txt` 文件。
3. 按配置编码读取。
4. 根据章节正则识别章节。
5. 去除重复章节标题行。
6. 输出 `data/{project_id}/chapters.jsonl`。
7. 输出 `data/{project_id}/ingest_report.json`。

章节 JSONL 格式：

```json
{
  "project_id": "reincarnation_paradise",
  "chapter_no": 1,
  "chapter_title": "复仇者",
  "source_file": "轮回乐园(1-500章).txt",
  "text": "章节正文"
}
```

导入报告至少包含：

```json
{
  "project_id": "reincarnation_paradise",
  "source_files": [],
  "chapter_count": 0,
  "first_chapter_no": 1,
  "last_chapter_no": 4143,
  "duplicate_chapter_numbers": [],
  "missing_chapter_numbers": [],
  "warnings": []
}
```

验收：

1. 运行 `python scripts/ingest.py --project reincarnation_paradise` 成功。
2. 不修改 `原文/`。
3. 能生成章节文件和报告。
4. 报告中能体现缺章、重复章或章节范围异常。

### 阶段 3：文本切分

可在 `ingest.py` 内完成，也可单独实现 `scripts/chunk.py`。建议 MVP 直接在导入阶段生成 `chunks.jsonl`。

切分规则：

1. 先按章节。
2. 章节内按段落聚合。
3. 目标 chunk 大小为配置中的 `chunk_size`。
4. 相邻 chunk 使用 `chunk_overlap`。
5. 不切断章节元数据。

Chunk JSONL 格式：

```json
{
  "chunk_id": "reincarnation_paradise_ch0001_0001",
  "project_id": "reincarnation_paradise",
  "chapter_no": 1,
  "chapter_title": "复仇者",
  "source_file": "轮回乐园(1-500章).txt",
  "chunk_index": 1,
  "text": "切片正文"
}
```

验收：

1. `chunks.jsonl` 存在。
2. 每个 chunk 有稳定 `chunk_id`。
3. 每个 chunk 都能追溯到章节号和章节标题。
4. chunk 文本不能为空。

### 阶段 4：索引构建

实现 `scripts/build_index.py`，负责：

1. 读取 `chunks.jsonl`。
2. 调用 Ollama embedding。
3. 写入本地向量库。
4. 索引目录按 `project_id` 隔离。

MVP 推荐使用 Chroma。若本机依赖安装困难，可先使用 FAISS 或简单本地向量文件作为过渡，但接口需要保留可替换性。

验收：

1. 运行 `python scripts/build_index.py --project reincarnation_paradise` 成功。
2. `index/reincarnation_paradise/` 生成索引文件。
3. 重复构建时可以安全覆盖当前项目索引。

### 阶段 5：命令行查询验证

实现 `scripts/query.py`，先不依赖网页，验证 RAG 核心链路。

要求：

1. 输入问题。
2. 检索相关 chunks。
3. 调用 Ollama LLM。
4. 输出回答、引用章节、命中片段。

严格考据提示词必须包含：

```text
你是小说原文考据助手。只能根据提供的原文片段回答。
如果片段不足以回答，必须说“当前证据不足”。
不要编造章节、人物关系、设定或剧情。
不要输出大段原文。
回答后列出引用章节。
```

验收问题建议：

```text
苏晓第一次接触轮回乐园是在什么情况下？
轮回乐园早期对苏晓提出了什么选择？
斩龙闪相关信息最早出现在哪里？
```

验收：

1. 回答有引用章节。
2. 证据不足时不编造。
3. 输出不包含大段原文。

### 阶段 6：FastAPI 后端

实现 `backend/app/main.py`。

API 必须包含：

```http
GET /api/projects
POST /api/projects/{project_id}/scan
POST /api/projects/{project_id}/ingest
POST /api/projects/{project_id}/index
POST /api/projects/{project_id}/query
```

查询请求：

```json
{
  "question": "苏晓第一次接触轮回乐园是在什么情况下？",
  "mode": "evidence",
  "top_k": 8
}
```

查询响应：

```json
{
  "answer": "根据第1章《复仇者》...",
  "citations": [
    {
      "chapter_no": 1,
      "chapter_title": "复仇者",
      "chunk_id": "reincarnation_paradise_ch0001_0001"
    }
  ],
  "retrieved_chunks": [
    {
      "chunk_id": "reincarnation_paradise_ch0001_0001",
      "chapter_no": 1,
      "chapter_title": "复仇者",
      "text_preview": "..."
    }
  ]
}
```

后端要求：

1. 所有接口返回 JSON。
2. 长任务 MVP 可先同步执行，后续再改后台任务。
3. 错误信息要可读，例如模型未启动、索引不存在、配置不存在。
4. CORS 允许本地 Vue dev server 访问。

验收：

1. `uvicorn app.main:app --reload` 可启动。
2. 前端能访问 API。
3. API 报错不会返回 Python 堆栈给前端。

### 阶段 7：Vue 前端

使用 Vue 3 + Vite + TypeScript。优先采用 Composition API 和 `<script setup lang="ts">`。如果需要全局状态，使用 Pinia，但避免为了少量状态过度引入复杂 store。

页面布局：

```text
顶部：项目名、索引状态、模型状态
左侧：项目与索引管理
右侧上方：问题输入与参数
右侧下方：回答、引用、命中片段
```

组件职责：

1. `ProjectPanel.vue`
   - 显示项目列表。
   - 显示当前项目配置。
   - 显示原文目录。

2. `IndexPanel.vue`
   - 扫描原文。
   - 执行导入。
   - 构建索引。
   - 展示章节数量、异常和警告。

3. `QueryPanel.vue`
   - 输入问题。
   - 设置 Top K。
   - 发起查询。
   - 显示加载状态。

4. `AnswerPanel.vue`
   - 显示回答。
   - 显示引用章节。
   - 显示命中片段。
   - 显示证据不足提示。

前端类型文件 `src/types/api.ts` 应定义：

```ts
export interface ProjectConfig {
  project_id: string
  display_name: string
  source_dir: string
}

export interface Citation {
  chapter_no: number
  chapter_title: string
  chunk_id: string
}

export interface RetrievedChunk {
  chunk_id: string
  chapter_no: number
  chapter_title: string
  text_preview: string
}

export interface QueryResponse {
  answer: string
  citations: Citation[]
  retrieved_chunks: RetrievedChunk[]
}
```

UI 约束：

1. 这是工具型网页，不做营销落地页。
2. 第一屏就是可用工作台。
3. 信息密度适中，便于反复查询。
4. 不使用大段功能介绍文案。
5. 引用和命中片段要可展开。
6. 加载、错误、空状态必须完整。
7. 不能让文本溢出按钮或面板。

验收：

1. `npm run dev` 能启动。
2. 页面能选择项目。
3. 页面能触发导入和索引。
4. 页面能提问并展示回答。
5. 回答区能展示引用章节和命中片段。

## 5. Agent 编码要求

### 5.1 Python

1. 使用类型标注。
2. 文件读写统一使用 UTF-8。
3. JSONL 一行一个 JSON。
4. 路径使用 `pathlib.Path`。
5. 脚本支持 `--project` 参数。
6. 不在业务代码中硬编码绝对路径。

### 5.2 Vue

1. 使用 Vue 3。
2. 使用 Vite。
3. 使用 TypeScript。
4. 使用 `<script setup lang="ts">`。
5. API 调用集中在 `src/api/client.ts`。
6. 组件 props 和 emits 必须有类型。
7. 避免把 API 请求散落在多个组件中。

### 5.3 错误处理

必须覆盖：

1. Ollama 未启动。
2. 模型不存在。
3. 原文目录不存在。
4. 没有解析到章节。
5. 索引不存在。
6. 查询为空。
7. 后端不可达。

## 6. 本地运行命令目标

后端：

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

数据管线：

```powershell
python scripts/ingest.py --project reincarnation_paradise
python scripts/build_index.py --project reincarnation_paradise
python scripts/query.py --project reincarnation_paradise --question "苏晓第一次接触轮回乐园是在什么情况下？"
```

## 7. 验证清单

每次阶段性完成后，Agent 必须执行或说明无法执行的验证：

1. 原文未被修改。
2. 配置可读取。
3. 章节可解析。
4. chunk 可生成。
5. 索引可构建。
6. CLI 查询可返回引用。
7. 后端 API 可访问。
8. Vue 页面可启动。
9. 页面查询链路可用。

## 8. MVP 完成定义

满足以下条件才算 MVP 完成：

1. 本地网页可打开。
2. 《轮回乐园》项目可被识别。
3. 原文可导入，章节报告可查看。
4. 向量索引可构建。
5. 用户能在 Vue 页面提问。
6. 回答严格依据检索片段。
7. 回答包含章节引用。
8. 证据不足时明确说明。
9. 代码结构支持新增第二个小说项目。

## 9. 后续扩展预留

MVP 实现时应预留但不必完成：

1. API 模型 provider。
2. BM25 关键词检索。
3. Reranker。
4. 实体抽取。
5. 角色档案。
6. 时间线。
7. AI 工作流一键迁移新小说。
8. 多项目索引管理。

