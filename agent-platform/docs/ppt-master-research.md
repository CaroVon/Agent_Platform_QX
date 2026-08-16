# hugohe3/ppt-master 嵌入调研（2026-08）

仓库：https://github.com/hugohe3/ppt-master（MIT，47k★，Python，2025-12 创建，
活跃维护；注意：之前调研的 macrochen/ppt-master-skill 并非本项目，勿混淆）

## 是什么

AI 演示工作流 Skill（v4.7.0，MIT，内置 attribution_guard 完整性门）：
文档/主题 → 原生可编辑 PPTX（原生形状/转场动画/数据图表/表格/旁白/公式）。

核心管线（generate-pptx 路由）：初始材料 → 事实调研 → 创建项目 →
模板候选 → Stage-1 确认（⛔ 用户门）→ Stage-2 方案 → 图片获取 →
**Executor 逐页手写 SVG**（P01 → 首页门 → 剩余页）→ 质量检查 →
后处理 → `svg_to_pptx.py` 导出原生 DrawingML 形状

## 结构与依赖

- `skills/ppt-master/`：SKILL.md + workflows（7 条路由：Generate/Beautify/
  Image-to-PPTX/Quick/Create Template/Fill/Enhance + profiles/stages 分层）
  + templates（brands/charts/decks/icons/layouts/scaffolds/schemas 设计系统）
  + scripts（239 个 .py：svg_to_pptx 编译器包、pdf/doc/web→md、finalize_svg、
  chart_recall、image_gen 后端、动画/旁白）
- 依赖轻量：多数工具纯标准库；可选 python-pptx/XlsxWriter/skia-pathops/
  uharfbuzz（文字轮廓）/edge-tts（旁白）/PyMuPDF（PDF→MD）
- **模型无关**（README 明确 no model lock-in）→ 天然适配 MiniMax 分工

## 嵌入可行性评估

| 维度 | 结论 |
|---|---|
| 法律 | ✅ MIT，可收编（保留版权声明，尊重 attribution_guard） |
| 形态 | agent skill（逐页手写 SVG + 用户确认门），非库/服务 —— 与我们的自动流水线（critic 门）需适配 |
| 技术价值 | **svg_to_pptx：SVG → 原生可编辑 PPTX**（DrawingML 形状、真实图表、动画）—— 直击我们当前 PptxGenJS 渲染器"视觉深度不足"；设计系统分层（brands/layouts/icons/charts）可借鉴 |
| 成本 | scripts 子集纯 Python 可收编；重依赖集中在可选路径（文字轮廓 skia/uharfbuzz） |
| 冲突点 | 其「SVG 是页面设计唯一来源」与我们的 DSL canonical 冲突 —— 需保持 DSL 为唯一事实源，SVG 作为导出中间产物 |

## 推荐路线

1. **方法论吸收（免费，推荐）**：提炼「SVG 页设计契约 + 设计系统分层 + 门禁纪律」
   为自有 skill 参考（MIT 标注来源），DSL canonical 不变
2. **SVG 导出实验模式（P3+）**：收编 svg_to_pptx 编译器 → export-pptx 增加
   `--backend svg`：DSL → 确定性逐页 SVG（复用 theme+组件体系）→ svg_to_pptx
   导出原生可编辑 PPTX。视觉深度向 demo 靠拢，DSL 仍是唯一事实源
3. **不推荐**：整体替换流水线（agent 逐页手写 + 用户门与自动化冲突）

## 与 MiniMax 分工

- ppt-master 模型无关 → 其 LLM 步骤可由 MiniMax-Text-01（PRESENTATION_LLM_*）
  承接，DeepSeek 继续主流水线
- 若启用图片阶段：MiniMax-Image-01 可接入其可插拔 image_backends
