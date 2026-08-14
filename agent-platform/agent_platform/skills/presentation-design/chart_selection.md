# Chart Selection —— 图表选择决策

| 信息形态 | 组件类型 | data 结构约定 |
|----------|----------|---------------|
| 单一关键数值 | metric | {"value": "2000亿", "label": "市场规模"} |
| 对比/趋势（2-6 项） | chart | {"chart_type": "bar", "items": [{"label": "...", "value": 42}]} |
| 二维定位（x/y 两轴） | matrix | {"chart_type": "quadrant", "x_axis": "...", "y_axis": "...", "points": [{"name": "A", "x": 0.7, "y": 0.4, "kind": "competitor"}]} |
| 多行多列明细 | table | {"columns": [...], "rows": [[...]]} |
| 阶段序列 | timeline | {"phases": [{"name": "...", "period": "...", "milestones": [...]}]} |
| 决策规则 | —— | 能象限化不做表格；能表格化不做散文 |

- chart_type 只允许：bar / line / pie / quadrant / radar
- 所有数值必须来自上游资产包，禁止推算
