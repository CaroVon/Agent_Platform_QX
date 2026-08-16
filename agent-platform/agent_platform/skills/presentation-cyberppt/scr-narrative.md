# SCR 叙事框架（适配 Presentation DSL 页型）

改编自 CyberPPT storyline 方法论。核心：全篇是一条完整的
**Situation → Complication → Resolution** 论证链，页序即论证顺序。

## 三幕 → 页型映射

| 幕 | 叙事任务 | 页型（Layout Library 枚举） | 必含内容 |
|---|---|---|---|
| **S 现状** | 市场有多大、在发生什么 | `cover` → `summary` → `market_overview` | 规模数字（TAM/SAM/SOM/CAGR）、趋势、一句话结论 |
| **C 矛盾** | 哪里有机会/痛点/缺口 | `competitor_matrix` → `user_persona` → `user_journey` | 竞品劣势、用户痛点、差异化机会、旅程断点 |
| **R 解法** | 我们怎么赢、何时兑现 | `feature_priority` → `product_architecture` → `roadmap` → `closing` | 定位、功能清单、架构、路线图、行动号召 |

## 每页论证单元

每页 = 一个论证单元，结构固定：

```
标题（信息型结论，不是主题名）
insight（数据 + SO WHAT，一句话）
组件（证据：数字/对比/清单/图表）
```

- 标题示例："120亿市场年增30%，中端国潮缺口显著"（优于"市场分析"）
- insight 必须包含 **SO WHAT**：这个数字对产品意味着什么
- 组件是证据载体：metric 放关键数字、card 放清单、chart/matrix 放对比、
  table 放明细、timeline 放阶段

## 衔接规则

- 上一页的结论 = 下一页的引子（页间递进，不重复）
- 全篇最多 2 个转折点：S→C 一次、C→R 一次，其余页是深化
- cover 与 closing 承担"提出结论/收回结论"，不承担论证

## 反例（禁止）

- 页序 = 上游文档章节顺序的机械复制（无论证逻辑）
- 每页自说自话、页间无递进（碎片化）
- S/C/R 缺幕（例如只有现状和解法、缺矛盾幕，说服力断层）
