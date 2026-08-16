# 咨询风视觉体系（8 套，映射到 theme palette tokens）

改编自 CyberPPT visual-system 的 8 套固定风格。每套映射为 DSL theme 的
palette tokens：`bg / surface / primary / accent / text / muted`。

**风格锁定规则**：选 1 套写入 theme（id/name/palette），全篇不漂移；
封面与内页同一风格，禁止页间切换。

| # | 风格 id（theme.id） | 名称 | bg | surface | primary | accent | text | muted |
|---|---|---|---|---|---|---|---|---|
| 1 | `cyber-crimson` | 经典深红咨询 | `#F3F4EF` | `#FFFFFF` | `#8B1E1E` | `#B54B4B` | `#111111` | `#555555` |
| 2 | `cyber-burgundy` | 冷灰+勃艮第红 | `#F5F5F2` | `#FFFFFF` | `#7A1F2B` | `#A04A55` | `#000000` | `#6B6B6B` |
| 3 | `cyber-ivory-wine` | 暖象牙白+暗酒红 | `#F4F1EA` | `#FFFFFF` | `#8A1538` | `#B04A67` | `#121212` | `#77736C` |
| 4 | `cyber-ivory-navy` | 象牙白+深蓝 | `#F7F6F0` | `#FFFFFF` | `#12355B` | `#3D6491` | `#101820` | `#6F7275` |
| 5 | `cyber-grey-green` | 浅灰白+墨绿 | `#F2F3EF` | `#FFFFFF` | `#1F5B4D` | `#4E8577` | `#111111` | `#666666` |
| 6 | `cyber-paper-copper` | 纸张米色+铜棕 | `#F4F0E8` | `#FFFFFF` | `#9A5A2E` | `#C08A5C` | `#161616` | `#76716A` |
| 7 | `cyber-black-gold` | 纯净浅灰+黑金 | `#F6F6F4` | `#FFFFFF` | `#2B2A26` | `#A87932` | `#000000` | `#707070` |
| 8 | `cyber-deep-purple` | 冷白灰+深紫 | `#F4F5F6` | `#FFFFFF` | `#4B2E83` | `#7A5FA8` | `#111111` | `#6D7175` |

## 适配说明

- 原体系 token（背景/标题/正文/次级/线条/强调）→ 本平台
  `bg/text/muted/primary/accent/surface`：背景与文本对比必须达标（咨询风
  黑白灰基底 + 单强调色），surface 统一 `#FFFFFF` 保证卡片可读
- 图表语言：柱/线/饼/象限统一使用 primary/accent 双色，灰点为弱化对象
  （竞品），强调色突出本产品（与既有 ECharts 规则一致）
- 字体：沿用平台默认 Noto Sans SC / Noto Serif SC 组合，font_scale=1.0

## 自检

- [ ] theme.id 是否为上表 8 个 id 之一（或平台预置 `default`）
- [ ] palette 六键齐全且与上表一致（禁止自创色板）
- [ ] 全篇 theme 未在页间变化
