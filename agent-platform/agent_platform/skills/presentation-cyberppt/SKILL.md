# CyberPPT 适配 Skill（咨询风演示）

> 来源适配：[crazyykhllc-bit/CyberPPT](https://github.com/crazyykhllc-bit/CyberPPT)（MIT，2026）
> 适配目标：把「SCR 叙事 + 证据链 + 密度规划 + 咨询风视觉」方法论注入本平台
> 的 Presentation DSL 生成，同时**遵守本平台硬约束**：
> - 输出必须是 Presentation DSL（页型枚举 / 组件枚举 / theme tokens），禁止像素参数
> - 页型与组件由 Layout Library 与视觉规范 skill 约束，此处只定叙事与密度
> - 数据只能来自上游材料包（cyberppt_evidence_pack），禁止编造

## 核心方法论（三要素）

1. **SCR 叙事**：先呈现现状（Situation）→ 再揭示矛盾/缺口（Complication）→
   最后给出解法与路径（Resolution）。全篇叙事 = 一条完整 SCR 论证链，
   不是页面的机械罗列。见 `scr-narrative.md`。
2. **证据链**：每个数字、判断、建议都必须可追溯到上游材料包中的证据 ID
   （E001…）。页内 insight 必须给出"数据 + SO WHAT"两层结论。
3. **密度规划**：每页按信息区数量与组件预算规划，宁满勿空；见
   `density-planning.md`。

## 强制流程（生成节点内一次性完成，无人工确认门）

1. **通读材料包** `cyberppt_evidence_pack`（证据表 + 关键数字 + 叙事提示）：
   先建证据索引，识别最有力的 3-5 个关键数字。
2. **收敛 SCR**：按叙事提示把上游内容组织为
   S（市场现状/规模/趋势）→ C（痛点/缺口/竞争劣势/风险）→
   R（定位/差异化/功能/架构/路线图/结论），映射到页型序列。
3. **锁定风格**：从 `visual-system.md` 的 8 套咨询风中选择 1 套，
   声明风格编号，写入 theme（id/name/palette），全篇不漂移。
4. **逐页规划**：每页声明信息区数量、组件清单与密度预算后输出。

## 禁止事项

- 不得输出脱离 DSL Schema 的内容（字体/间距/像素一律禁止）
- 不得编造材料包中没有的数据；材料包缺口处允许写"数据待补充"
- 不得在页间切换风格（风格锁定后全篇一致）
- 不得输出低密度页（大面积空白页视为失败）

## 质量自检（输出前逐项核对）

- [ ] 全篇是否构成完整 SCR 论证链（S→C→R 三幕齐全）
- [ ] 每页 insight 是否为"数据 + SO WHAT"
- [ ] 关键数字（TAM/SAM/SOM/CAGR、竞品数、功能数、阶段数）是否全部入页
- [ ] 每页组件数是否在预算内（见 density-planning.md）
- [ ] theme 是否来自 8 套咨询风之一且全篇一致
