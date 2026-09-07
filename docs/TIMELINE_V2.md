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
