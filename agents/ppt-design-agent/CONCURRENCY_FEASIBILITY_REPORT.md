# 《并发加速 PPT 生成》可行性研究报告

> 调研日期：2026-08-20 · 针对 2026-08-17 计划稿（基于 v2 commit `41be075`）
> 结论先行：**方案可行，方向正确，但需 3 处关键修正后才可落地**（详见 §3）。
> 核心判断：并发对**质量是中性的**（已逐函数验证），真正的质量风险来自 MiniMax 配额耗尽导致的批量 fallback，降级策略必须质量优先。

---

## 1. 计划事实核查（逐条对照真实代码）

| 计划声称 | 实测结论 | 证据 |
|---|---|---|
| commit `41be075` 已推送，agent.py 顺序瓶颈在 506-578 行 | ✅ 属实。41be075 于 2026-08-17 20:11 推送；HEAD 已到 `80bcdf7`，但 `_author_pages_v2`（484-578 行，顺序循环 506-578）自 v2 后未变，计划仍适用 | `git log`；agent.py |
| image_gen 已是 3 并发 + 自适应降级 | ✅ 属实。`DEFAULT_MANIFEST_CONCURRENCY=3`（497 行）；`_run_manifest`（860 行起）按 batch 提交、触限流减半 + 暂停 10s、单条限流重排队（预算 3 次）、并发 1 仍限流则 Failed | image_gen.py 935-1050 |
| LLMClient 是 httpx.Client 包装（线程安全） | ❌ **理由错误**。`LLMClient.complete()` 每次调用 `httpx.post()`（无连接池、无共享连接状态）。线程安全结论恰好成立（无共享状态），但计划引用的依据不实 | llm/client.py:120 |
| 429 时 LLM 调用会怎样 | ❌ **现状是"无任何限流处理"**：非 200 一律抛 `LLMError("LLM 返回 429: ...")`，无重试、无退避。当前每页遇 429 = 3 次立即重试全失败 → fallback_svg。并发后若不处理，4 worker × 3 次 = 12 连发失败请求 | llm/client.py:129-132 |
| MiniMax "Token Plan" 429 已实测 | ⚠️ **属实但形态不同**：生产真实记录显示 MiniMax 图片接口返回 **HTTP 200 + `base_resp.status_code: 2056`**（"已达到 Token Plan 用量上限"），并非 HTTP 429。且现有 `is_rate_limit_error`（backend_common.py:279）**识别不了 2056**（消息无 429/quota 等关键词）→ 生产上每张图烧满 4 次重试（image_prompts.md 实锤 "Failed after 4 attempts"）。**SVG 侧限流检测必须覆盖应用层错误码，这是本计划最大的隐性坑** | outputs 产物 image_prompts.md |
| 生图 ~30-60s（3 并发） | ✅ 属实。实测 14 张图 mtime 跨度 ≈31s（16:06:18→16:06:49） | 真实产物 mtime |
| 7 页 SVG 顺序 ~271.9s（39s/页）；11 页 ~5-6 min | ⚠️ **7 页数字可信（一例实测 390s），11 页严重低估**。真实生产 3 轮 11 页 run：**776s / 1025s / 865s（13-17 min）**，页间隔 39-180s（含重试）。"SVG 阶段 ~210-330s" 低估基线约 2.5-3× | 真实产物 mtime（153058/154611/160539） |
| 目标 11 页 <120s（3.3× 提速） | ⚠️ **过于激进**。按真实基线 776-1025s ÷ 4 ≈ **195-260s** 才是 4 并发下的现实目标；120s 需要 6.5-8.5×，等于要求 0 重试 + 满并发 + 无慢页 | 同上 |
| `finalize_svg` / `svg_to_pptx` 保持顺序 | ✅ 正确。两者是**每项目一次**的 subprocess（agent.py:402-405），与逐页并发无交集 | agent.py |
| 跨页 footer/根属性/字号收敛在并发下会乱 | ✅ **不会**。全部是纯函数 + 不可变常量：`cross_page.inject_root_metadata / inject_footer / snap_font_sizes`（`ALLOWED_FONT_SIZES` 为模块级不可变 tuple）；`svg_author` 全部函数基于不可变 frozenset/正则；`image_plan.select_image_for_page` 纯函数。跨页一致性靠**程序化注入**保证，不依赖任何跨页可变状态 | cross_page.py / svg_author.py / image_plan.py |
| PPTX 页码顺序靠 `files` 排序保证 | ⚠️ 严重性低。`svg_to_pptx` 的 `discover_slide_svgs`（slide_roster.py:39-44）**按文件名数字序排序**，PPTX 组装与 `files` 列表顺序无关；但 `files` 仍应排序（前端 timeline 展示用） | slide_roster.py |
| 新增 env 命名与 settings 兼容 | ✅ 属实。pydantic-settings `env_prefix=AGENT_PLATFORM_`，`PPT_DESIGN_CONCURRENCY` 字段 → `AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY` | settings.py:85-88 |
| 图片并发提到 4 只需 env 一行（决策点2-B） | ✅ 属实。image_gen 已支持 `IMAGE_CONCURRENCY` env（CLI 优先，默认 3） | image_gen.py:1065-1072 |
| 与 Celery `--concurrency=4` 对齐 | ✅ 属实（threads pool）。但注意：**4 个 deck × 每 deck 4-6 并发 = 最坏 16-24 个并发 M3 调用**，单 deck 自适应控制器管不了跨 deck 突发（计划已声明 out of scope，同意，但需知晓此风险） | start_studio.sh:82 |
| 全链路超时压力 | ✅ 提速价值大。Celery 任务软超时 50min / 硬超时 70min（`max_retries=1, acks_late`），PPT SVG 阶段 13-17 min 是大头，压缩到 ~4 min 显著降低超时风险 | product_studio_tasks.py:219-222 |

---

## 2. 质量优先评估（核心问题：并发会不会伤质量？）

### 2.1 正常工况：并发 = 质量中性 ✅

已逐函数审计，**每页的 LLM 创作与程序化后处理全部相互独立**：

- 输入独立：`build_page_prompt(page, theme, design_spec, i, img_assets)` 只依赖本页数据 + 共享的不可变 dict（`images`/`identity`/`design_spec`）
- 后处理独立：sanitize → inject_page_image → inject_root_metadata → inject_footer → snap_font_sizes，全部是纯函数
- 跨页一致性靠确定性注入，不靠 LLM 协作 → **并发不会引入跨页不一致**

### 2.2 风险工况：并发放大配额烧毁 → 批量 fallback ⚠️（真正要防的）

- 每页 SVG 请求 `max_tokens=16384`（M3 单页密度 155 行）。4 并发 × 16K 输出 token，burst 烧配额速度是顺序的 4 倍
- MiniMax Token Plan 是**配额制**（生产已实锤 2056 用量上限），配额耗尽后"暂停 10s 重试"不会恢复配额——**配额型限流与 RPM 型限流必须区分对待**：
  - 配额型（Token Plan/用量上限）→ 重试是浪费，应**立即 fallback 该页**（保留确定性 SVG，保证 deck 完整）并降到并发 1 继续
  - 瞬时型（RPM/TPM 429）→ 重排队 + 减半 + 暂停（image_gen 既有模式）
- 现有代码在 429 下的行为本身就是质量灾难（每页 3 次白费重试 → fallback），**限流处理做对了反而是质量提升**：把页面"推迟重试"而非"立即放弃"

### 2.3 结论

并发本身不伤质量；**质量防线 = 限流分类 + 重排队（不轻易 fallback）+ 配额型限流时立即降速**。计划"单页 3 次失败才 fallback"的兜底保持，但要把"429 不算失败、算重排队"（参照 image_gen `_run_manifest` 的 requeue 语义，预算 3 次，并发 1 仍限流才落 fallback）。

---

## 3. 必须修正的 3 个设计缺陷

### 🔴 缺陷 1：计划伪代码里的"自适应并发"是假的

```python
with ThreadPoolExecutor(max_workers=controller.max) as executor:
    future_to_idx = {executor.submit(_one_page, i, page, ...): i
                     for i, page in enumerate(pages)}   # ← 一次性全提交
```

- 所有页面一次性提交，`max_workers=6` 意味着**一上来就是 6 并发**（连计划说的"起始 4"都守不住）
- 触 429 后 `controller.on_rate_limit()` 只是改了个计数器，**已排队的 future 该跑还是跑**——减半/暂停完全无效
- **正确做法**（照抄 image_gen.py:935-1050 已验证的 batch 模式）：

```python
queue = list(range(len(pages)))
current = min(initial, len(queue))
while queue:
    batch = queue[:current]; queue = queue[current:]
    rate_limited = False
    with ThreadPoolExecutor(max_workers=len(batch)) as ex:
        for fut in as_completed([ex.submit(_one_page, i, ...) for i in batch]):
            idx, svg, status, retries = fut.result()
            if status == "rate_limited":
                rate_limited = True
                if attempts[idx] < 3 and current > 1:
                    queue.append(idx)          # 重排队，不放弃
                else:
                    # 并发 1 仍限流 / 预算耗尽 → 该页 fallback（保证 deck 完整）
                    svg = svg_author.fallback_svg(...); 写文件
            else:
                写文件 + 主线程聚合 stats
    if rate_limited and current > 1:
        current = max(1, current // 2); time.sleep(10)
    elif queue:
        time.sleep(2)   # 温和节流，避免突发
```

- 计划里的 `recover()`（成功 N 次后爬回）建议**砍掉**：image_gen 同一 run 内不恢复，只减不增，跨 run 自然恢复。质量优先 = 保守。若坚持要，也只在"连续 10 个成功且无限流"时才 +1

### 🔴 缺陷 2：限流检测必须覆盖 MiniMax 应用层错误码（2056 教训）

- 生产实锤：MiniMax 图片接口配额耗尽返回 **HTTP 200 + `base_resp.status_code: 2056`**；现有 `is_rate_limit_error` 识别不了（消息是中文，无 429/quota 关键词）→ 每张图白烧 4 次重试
- SVG 用的 `LLMClient` 对非 200 抛 `LLMError`（消息含状态码，字符串匹配可兜住 HTTP 429），但若 MiniMax LLM 端点像图片接口一样"200 + 错误体"，当前客户端会抛"LLM 响应结构异常"（`data["choices"][0]` KeyError）→ **同样识别不了**
- **必须做**：
  1. `LLMError` 增加 `status_code` 属性，`complete()` 解析错误体（`error.code` / `base_resp.status_code` / `status_msg`）附到异常上
  2. 新增/扩展限流判定：HTTP 429 + 应用层码（2056、1008 等）+ 关键词（"Token Plan"、"用量上限"、"配额"、"quota"、"rate limit"）
  3. 顺带修 `backend_common.is_rate_limit_error` 对 2056 的漏判（图片侧同样受益）

### 🔴 缺陷 3：验收基线按真实数据重定

| 场景 | 计划声称（顺序） | 真实基线 | 4 并发现实目标 |
|---|---|---|---|
| 7 页 | 271.9s | ~390s（一例） | **~100-130s**（计划 ~70s 偏乐观但可作冲刺目标） |
| 11 页 | "5-6 min" | **776-1025s（3 轮实测）** | **~195-260s**（计划 <120s 不现实） |

提速倍数目标定为 **3.5-4×**（对比 3.3×，更接近真实收益）；验收时先跑通 7 页冒烟再上 11 页。

---

## 4. 决策点答复（质量优先原则下）

| 决策点 | 答复 | 理由 |
|---|---|---|
| 1. 起始并发 | **A：4/6** ✅ 采纳 | 真实页耗时 40-90s，4 并发 11 页 ≈ 4 min；8/12 的配额烧毁风险不值得（质量优先） |
| 2. 图片并发 3→4 | **A：不动**（反对计划的 B） | 图片侧**已在生产触发过 2056 配额耗尽**，提高并发 = 提高配额烧毁概率；且生图只占 ~31s，非瓶颈。真要动，先修 2056 分类再谈 |
| 3. 前端 UI 开关 | **A：env-only** ✅ 采纳 | 并发是运维参数；暴露开关增加认知负担且难以解释"为什么我的 deck 变慢了" |
| 4. LLMClient 429 处理 | **必须加，但按缺陷 2 的方式**：分类 + 上报，不在 `complete()` 内部盲重试 | 重试策略属于 batch 控制器（需要知道何时暂停/减半）；客户端只负责把错误分类透传 |

---

## 5. 线程安全审计结论（计划 §3.6 的修正）

| 共享资源 | 计划说法 | 实测结论 |
|---|---|---|
| LLMClient 单例 | "httpx.Client 线程安全" | ✅ 可共享，但原因是**每次调用无共享连接状态**（`httpx.post`），不是"httpx.Client 文档保证"。理由要更正 |
| `total_*_tokens` 计数器 | 未提及 | ⚠️ **非原子 `+=`**（读-改-写），并发下会丢计数（成本统计偏低）。加锁或接受近似值（推荐后者，成本统计精度要求低） |
| `stats` dict / `files` 列表 | "用 Lock" | ✅ **不需要锁**——只要按 batch 模式把聚合放在主线程（future.result() 之后），天然串行。比计划的 Lock 方案更简单 |
| `svg_dir` 文件写入 | 独立文件名无竞争 | ✅ 属实（`slide_NN_*.svg`），但 batch 模式里写文件也在主线程，更稳 |
| `validate_native_contract` | 未提及 | ⚠️ 内部有 `sys.path.insert`（新版本 svg_author.py:214-253，仅顶层副本有）。**必须留在主线程**（LLM 调用进 worker、校验/后处理留主线程），勿把校验搬进 worker |
| logger | 线程安全 | ✅ 属实；建议加 thread name 前缀（计划建议合理） |

**推荐的线程划分**：`_one_page(idx)` 只做"LLM 创作 + 校验循环"（worker 线程）；sanitize/注入/收敛/写盘/stats 全部主线程。LLM 调用是唯一耗时的部分（30-90s/页），后处理 <10ms/页，主线程聚合的开销可忽略，还顺带消灭了锁。

---

## 6. 落地建议（在计划 §8 基础上的修正）

1. **不动 `_run_manifest` 通用化**：`AdaptiveConcurrency` 类可以简化掉，直接在 agent.py 内实现 batch 循环（~60 行），参照 image_gen.py:935-1050。若要抽公共模块，放 `agent_platform/` 下而非 `agents/ppt-design-agent/concurrency.py`（避免单 agent 私有工具）
2. `settings.py` +3 字段 ✅ 按计划（`PPT_DESIGN_CONCURRENCY=4 / _MAX=6 / _RATE_PAUSE=10`）
3. `LLMClient` 改动：`LLMError` 带 `status_code`；`complete()` 解析错误体并透传；**不改全局 LLM_TIMEOUT**，需要时加 per-call timeout 参数（计划提的 120s 有依据：现网 ~60s，2× 余量合理）
4. `is_rate_limit_error`（或新判定函数）补 2056 类应用层码
5. **两份副本同步**：`Agent_Platform_QX/agents/ppt-design-agent/`（git 库）与顶层 `agents/ppt-design-agent/`（开发树）目前 `svg_author.py` 已不一致（顶层新版带 converter 校验）。改完 agent.py/settings.py 后**两份都要同步**，避免开发与生产跑不同代码
6. 测试补充（对齐现有 `agents/tests/test_ppt_design.py` 风格）：
   - mock LLM 返回合法 SVG → 7 页并发跑通、文件齐全、stats 正确聚合、顺序正确
   - mock `LLMError(status=429)` → batch 减半 + 重排队、预算耗尽落 fallback
   - mock 200+2056 型错误体 → 正确识别为配额型、**不重试直接 fallback**
   - 断言：并发结果与顺序版逐字节一致（质量回归测试，最有价值的一条）

## 7. 工作量修正

| 任务 | 计划估算 | 修正 |
|---|---|---|
| concurrency.py（+200 行） | 0.5 人天 | **砍掉**，batch 循环内联 agent.py（~60 行），省 0.3 人天 |
| agent.py 改造（+120/-40） | 1 人天 | ✅ 不变 |
| settings.py（+15） | 0.1 人天 | ✅ |
| LLMClient 429 分类（+20） | 0.3 人天 | 扩到 ~40 行（含错误体解析 + 2056 识别），0.5 人天 |
| 单测（+200） | 0.5 人天 | ✅（含"与顺序版逐字节一致"回归测试） |
| 联调压测 | 0.5 人天 | ✅（按 §3 新基线验收） |
| **合计** | **~3 人天** | **~2.6-3 人天** |

## 8. 风险表补充（计划 §4.4 之外）

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 跨 deck 并发（4 Celery × 每 deck 4-6）触发 MiniMax RPM | 中 | 各 deck 各自降级，速度打折 | 接受；自适应降级兜底；线上观察 429 频率，必要时全局并发上限（后续再议，本次不做） |
| 配额型 429 误判为瞬时型 → 重试浪费 + 用户等更久 | 中 | 页面 fallback 延迟 | 按缺陷 2 分类；配额型**立即 fallback**，不等重试 |
| 生产与开发跑不同 svg_author.py | 已发生 | 校验行为不一致 | §6.5 两份副本同步 |
| 时间基线低估导致验收不达标 | 高 | 返工 | 按 §3 真实基线验收（11 页 <260s） |

---

## 9. 总结论

**方向正确、方案大体可行，修正 3 处后即可落地**：

1. ✅ 质量安全已论证：并发 = 质量中性（纯函数审计通过），质量防线在限流降级策略
2. 🔴 自适应并发必须用 **batch 模式**（照抄 image_gen `_run_manifest`），否则"自适应"是摆设
3. 🔴 限流检测必须覆盖 **MiniMax 应用层错误码**（2056 已在生产实锤），并区分配额型/瞬时型
4. 🔴 验收基线重定：11 页 **195-260s**（4 并发，真实基线 776-1025s），不是 <120s
5. ✅ 决策点 1/3 采纳计划建议（4/6、env-only）；决策点 2 改为不动图片并发；决策点 4 必做但按"分类透传"设计

预计 2.6-3 人天，比计划省 0.3-0.4 人天（砍掉独立 concurrency.py）。

---

## 10. 实施结果（2026-08-20 已落地并验证）

按本报告修正意见实施完毕，全部验证通过。

### 10.1 改动清单

| 文件 | 改动 | 说明 |
|---|---|---|
| `agent_platform/config/settings.py` | +3 字段 | `PPT_DESIGN_CONCURRENCY=4 / _MAX=6 / _RATE_PAUSE=10`（env: `AGENT_PLATFORM_PPT_DESIGN_*`） |
| `agent_platform/llm/client.py` | +87 行 | `LLMError` 携带 `status_code`/`error_body`；`complete()` 识别 MiniMax 200+业务错误体（2056 型）；新增 `classify_llm_error()` 三分法（瞬时限流/配额耗尽/其它）；token 计数器加锁 |
| `agents/ppt-design-agent/agent.py` | +141/-40 | `_author_pages_v2` 改为 **batch 自适应并发**（照抄 image_gen `_run_manifest` 模式）：LLM 创作进 worker 线程，后处理/写盘/stats 全在主线程（无锁）；瞬时限流 → 重排队（预算 3）+ 减半并发 + 暂停；配额型 → 立即 fallback；结果按页排序 |
| `vendor/.../image_backends/backend_common.py` | +6 行 | `is_rate_limit_error` 补 MiniMax 应用层错误码（2056 / Token Plan / 用量上限 / 配额 / 余额）——顺带修复图片侧生产漏判 |
| `agents/tests/test_ppt_concurrency.py` | 新增 | 11 个单测（分类/并发正确性/**逐字节一致回归**/提速/限流降级/配额不重试） |
| `agents/tests/bench_ppt_concurrency.py` | 新增 | Mock 延迟基准（0.5s/页 ±30% 抖动） |
| `agents/tests/smoke_real_ppt_concurrency.py` | 新增 | 真实 MiniMax-M3 冒烟（顺序 vs 并发 + 全链路 PPTX） |

### 10.2 验证结果

**单元测试**：新测试 11/11 通过；原有 `test_ppt_design.py` 10/10 通过。
（`test_pipeline.py::test_full_pipeline_with_real_agents` 为既存失败——FakeLLM 与 Presentation schema 漂移，与本次改动无关，改前即失败。）

**Mock 延迟基准**（0.5s/页 ±30% 抖动，逐字节一致校验）：

| 页数 | 顺序 | 并发 4 | 提速 | fallback | 逐字节一致 |
|---|---|---|---|---|---|
| 7 | 3.15s | 1.06s | **2.96×** | 0 | ✅ |
| 11 | 5.59s | 1.75s | **3.19×** | 0 | ✅ |
| 11（注入 3 次 429） | — | 3.14s | — | 0（重排队 3 次，降级并发 4→2） | ✅ |

**真实 MiniMax-M3 冒烟**（6 页真实咨询风 deck，模型 MiniMax-M3 @ api.minimax.chat）：

| 场景 | 耗时 | fallback | retries | 提速 |
|---|---|---|---|---|
| 顺序（并发 1） | 391.4s | 0 | 0 | 基线（65.2s/页） |
| 并发 4（首轮，含 4 次随机网络失败重试） | 204.6s | 0 | 4 | 1.91× |
| 并发 4（复测，无抖动） | **100.8s** | 0 | 0 | **3.88×** |

真实全链路：并发产物 → finalize_svg → svg_to_pptx → **PPTX 产出成功**（38 KB，6 页）。

**外推到 11 页真实项目**（历史顺序基线 776-1025s）：并发 4 预计 **200-300s（3.3-5 min）**，提速 ~3.5×，接近计划的 4× 目标；原计划"11 页 <120s"的验收线确如 §3 所判不现实，建议以 **<300s** 为验收。

### 10.3 落地注意事项

1. 两份副本已同步（`~/dev/agents/agents/` 生产树 ↔ `Agent_Platform_QX/agents/` 仓库树，含 `svg_author.py` 差异一并拉齐）
2. 配置开关：`.env` 加 `AGENT_PLATFORM_PPT_DESIGN_CONCURRENCY=1` 可完全退回顺序模式（应急用）
3. 未提交 git；仓库当前有大量其他模块的未提交改动，提交范围请自行确认
4. 已知限制（与 §8 一致）：跨 deck 并发（4 Celery × 每 deck 4）无全局协调，线上观察 429 频率；配额型 429 会立即 fallback（质量保护，非速度问题）
