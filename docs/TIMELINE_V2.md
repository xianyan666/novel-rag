# 时间线 v2：通用事件 + follows 边

## 目标

把时间线从《轮回乐园》关键词打点，升级为面向文学作品的通用叙事事件序列。

当前只建模：

1. **Event**：可引用的最小叙事单元（类型、摘要、证据、参与者）
2. **follows 边**：按章节/chunk 顺序的相邻关系（**不是因果**）

明确不做（后续再加）：`causes` / `enables` / `blocks`，以及叙述者可靠性标注。

## 事件类型

| type | 含义 |
|------|------|
| encounter | 遭遇 |
| conflict | 冲突 |
| rule_reveal | 规则揭示 |
| ability_change | 能力变化 |
| death_or_seal | 死亡或封印 |
| alliance_or_break | 结盟或决裂 |
| clue | 线索 |
| state_change | 状态变化 |
| other | 其他 |

## 重建

```powershell
python scripts/build_timeline.py --project mystic_recovery
```

## API

- `POST /api/projects/{id}/timeline/build`
- `GET /api/projects/{id}/timeline/events`
- `GET /api/projects/{id}/timeline/edges?relation=follows`

## 因果边（v2.3）

在 `follows` 之外，额外写入保守启发式因果边：

| relation | 含义 |
|----------|------|
| causes | 更强的导致 |
| enables | 使后续可能发生 |
| blocks | 规则/约束阻断某类结果 |

约束：章距 ≤ 3；跨 2 章以上需要共享主体或因果提示词（因为/导致/于是…）。证据写在 `edge.evidence`。

查询：`timeline_summary` / `sequence_*` 会在 follows 展开后再扩一层因果邻居。
可用 `GET /api/projects/{id}/timeline/edges?relation=causes` 筛选。


## v2.4 折中：收紧因果 + 「为什么」路由

因果边收紧：
- `enables` 必须共享主体
- `causes` 跨章必须共享主体；同章需共享主体或强提示词
- 去掉弱提示词「才」；章距上限 2；置信度门槛约 0.68

问答：问题含「为什么/为何/怎么会/原因是」时，`query_type=causal_why`，检索走 causal+timeline+keyword+vector，并把因果候选边注入回答提示。
