# 计划：pdf-table-repair 页级表格候选重建

## 计划状态

- 状态：实施中
- 当前阶段：阶段 4：独立验收
- 最后更新：2026-07-14

本文档是页级表格“格式化 + 异常证据 + 候选重建”能力的事实源。它依赖 [pdf-table-audit](pdf-table-audit.md) 提供异常页和 PDF 证据，不把表格语义修复混入 `pdf-merge` 的纯 pretty-print，也不把人工判断伪装成全自动事实生成。

## 背景与 Step 0 证据

春风 250Sr 人工复核报告显示，指定页后可以按固定流程完成：读取页锚点、提取 PDF 文本和 bbox、按 x/y 坐标分析布局、对齐缺失文本和列结构、重建 HTML 表格，再在页锚点范围内写回。典型样本包括：

- p34：13 列膨胀压缩为 4 列，并修正 `rowspan` 与乱码；
- p47/p48：空列补全、6/5 列压缩为 4 列，并记录跨页逻辑关系；
- p73：布局图误判为表格，需要改为标签—值关系；
- p77：补齐表头并移除多余首行；
- p87/p90：8192 级空列候选，先由 audit 生成证据，不能直接猜结构。

这些样本证明“页级候选修复”是独立能力，但尚不能证明可以无人确认地生成最终表格。因此 Step 0 必须先冻结候选输入、输出和人工确认门禁。

## 目标

- 支持用户指定单页或页集合，生成页级表格修复 draft。
- 在 draft 中处理确定性的 HTML pretty-print，并保留基于 PDF 证据的文本缺失候选。
- 保留原始 HTML、fallback HTML、PDF 原生文本、页锚点和来源 hash，便于人工复核；需要坐标时由人工复核工具单独读取 PDF。
- 人工确认后，复用页锚点安全应用器写回 canonical Markdown，并同步 `manual_fixes.jsonl` 与 manifest。
- 让下游通过 `fix_id`、页码、`table_id`、来源 hash 和修复状态知道这次表格重建发生了什么。

## 非目标

- 不自动决定最终列数、表头语义、`rowspan`、`colspan`、图片列取舍或跨页归属。
- 不让 VLM 判断表格行列结构；VLM 只验证文字、数字、警告和图中标注等证据。
- 不直接覆盖 Markdown；未经过人工确认的 draft 必须保持 `needs_human`。
- 不生成第二正文入口，不创建 `*-fixed.md` 或 `*-formatted.md`。
- 不替代 `pdf-table-audit` 的异常发现，也不替代 `pdf-merge` 的纯格式化链路。
- 不修改原始 `segments/**/content_list*.json`、PDF 或业务数据库。

## 范围收敛决策（2026-07-14）

本计划不再扩展为“自动修复所有表格”的计划。自动化范围冻结为：

- 自动处理 TOC、确定性的表格格式化，以及可由页锚点、来源 hash 和命中次数安全证明的表格异常；
- 自动发现大量空 `td`、异常列、缺失文字和结构警告，并生成 review/draft；
- 复杂表头、列语义、`rowspan/colspan`、跨页关系、扫描件空页和图片表格由人工决定；
- 人工确认/拒绝后，统一通过 `manual_fixes.jsonl`、manifest 和页级应用器同步产物；
- 未解决异常可以保持 `needs_review`/待确认，不要求为了阶段完成继续开发新的自动重建算法。

阶段 3 的验收重点因此从“自动修复覆盖率”调整为“人工校对入口和发布闭环”：已确认、已拒绝和暂缓的样本都必须有可追溯状态；暂缓不视为成功修复，也不应被静默丢弃。

### 自动推断代码清理（2026-07-14）

按上述边界清理 `scripts/pdf-table-repair` 中不再承担交付价值的自动推断：

- 删除 PDF words/bbox 到候选列的自动映射，以及“找不到 bbox 时按序分配列”的降级逻辑；该结果只能产生低置信度猜测，不能作为人工校对事实。
- 删除 repair 入口内对 PDF 原文的二次缺失文本猜测；`pdf-table-fix` 已提供 `missing_text` 证据，剩余缺失项直接交给人工逐项校对。
- 保留 `pretty_print` 的确定性 8192/异常列压缩 draft，但仍保持 `status=proposed`、`needs_human=true`，不得自动写回 canonical Markdown。
- 已格式化完成、`before_html == draft_html` 的 `pretty_print` 不再生成，避免人工 apply 进入“无变化修复”失败路径。
- 保留 `structure_warning`、跨页候选、页锚点/命中次数校验、`--apply/--reject`、`manual_fixes.jsonl` 和 manifest 同步。
- 对人工确认的空页 `rebuild_table`/`cross_page_table`，允许在记录中显式设置 `allow_empty_page=true`；应用器只追加到既有页锚点之后，禁止把锚点纳入替换文本，并保持重复 apply 幂等。
- `pdf-check-fixes` 继续接受历史 draft 中的 `page_words`、`alignment_candidates` 和 `fill_missing_text` 字段，保证旧产物可校验；新 draft 不再生成自动列位猜测字段。

这次清理不删除 TOC 修复、页级质量 fallback、表格格式化、异常候选扫描和人工应用链路。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 冻结页级 repair 契约与最小样本 | `pdf-table-audit` 候选和输出边界可复现 | draft、来源证据、人工门禁和回滚边界明确 | 已完成 |
| 阶段 1 | 实现页级候选重建器 | 阶段 0 准入通过 | 单页/多页 draft 可追溯，未确认不改 canonical | 已完成 |
| 阶段 2 | 完成人工/VLM确认与安全应用 | 阶段 1 验收通过 | apply/reject、manifest 同步和失败字节级回滚通过 | 已完成 |
| 阶段 3 | 真实样本扩展 | 阶段 2 独立验收通过，阶段 3 准入复核通过 | 多个真实样本完成 audit → draft → 确认 → apply → manifest 闭环 | 已完成 |
| 阶段 4：独立验收 | 独立验收与治理收尾 | 阶段 3 完成 | 回归、真实样本、回滚和治理检查全部通过 | 实施中 |

## 当前阶段

阶段 4：独立验收与治理收尾。旧版合并级 TOC 修复覆盖正文的问题已完成重建：当前 canonical Markdown 已从 138 个非空分段重新生成，TOC、表格修复、下游抽取、人工审核和入库前批次均已重跑。图示编号产生的 29 条纯数字 key 已通过当前 PDF 包的配置策略过滤；179 条候选已确认，3 条联系方式拒绝。计划尚未标记完成的原因是治理检查仍有历史已完成计划的证据缺陷。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 实施中 |
| Step 0 | 阶段 2 已完成 audit → draft → 人工/VLM证据 → apply/reject → `pdf-check-fixes` 闭环；demo20、demo60、春风250Sr真实样本基线和待确认边界已记录在阶段 3 准入复核中 |
| 样本矩阵 | demo20 p14–p16、demo60 p47/p48、春风250Sr p85–p94、p132–p133；每项均记录输入基线、执行命令、预期结果和失败判定 |
| 验证方式 | 逐样本执行 audit → draft → 人工/VLM文字证据 → apply/reject → `pdf-check-fixes`，并复核 `pdf-extract-data`、`pdf-prepare-ingest` 的 canonical 输入一致性 |
| 失败/回滚边界 | 来源 hash、页锚点、命中次数或 manifest hash 失败时非零退出；使用临时副本和事务字节级回滚，原始 canonical 包保持不变 |
| 当前阻塞项 | 业务无阻塞；治理收尾仍受历史已完成计划缺少 Step 0/测试覆盖率证据影响 |
| 最新独立准入复核 | 2026-07-14，阶段 4，结论：业务产物复核通过，治理收尾未完成，见下方补充复核记录 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-14 |
| 阶段 | 阶段 4：独立验收 |
| 结论 | 通过：用户确认后的入库前批次复核通过；治理收尾未完成 |
| 证据 | 138/138 页面有正文；TOC 120/120；`pdf-check-fixes` 通过；抽取 182 行，`pdf-prepare-ingest` 为 179 ready、0 not_ready、3 skipped、0 conflicts，纯数字 key 为 0；`ingest_batch.jsonl` 已重生成 179 条；全量 304 个 Python 测试和 133/133 shell 回归通过 |
| 复核者 | 独立治理复核 |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-13 | 独立治理复核 | 阶段 3 | 通过：达到待实施标准 | [阶段 3 待实施准入复核](#阶段-3-待实施准入复核2026-07-13)、阶段 2 回归和真实 demo60 p47 apply 验证 |
| 2026-07-14 | 独立治理复核 | 阶段 4：独立验收 | 通过：业务产物验收；治理收尾未完成 | `pdf-check-fixes`、303 pytest、129/129 shell、75 条批次导出、0 冲突；`plan-governance-cli check .` 仍报告历史已完成计划缺少证据 |
| 2026-07-14 | 独立治理复核 | 阶段 4：独立验收 | 未通过：canonical Markdown 仍是旧版 TOC 覆盖后的不完整产物 | 138 个分段均非空，canonical 仅 23 页有正文；需重新执行完整合并、修复和下游重跑 |
| 2026-07-14 | 独立治理复核 | 阶段 4：独立验收 | 通过：业务产物重建与入库前准备通过；治理收尾未完成 | 138/138 页面非空、TOC 120/120、`pdf-check-fixes` 通过、抽取 182 行、75 ready/104 not_ready/3 skipped、0 conflicts、纯数字 key 为 0；治理检查仍有历史计划证据错误 |
| 2026-07-14 | 独立治理复核 | 阶段 4：独立验收 | 通过：用户确认后的入库前批次复核通过；治理收尾未完成 | 用户确认 104 条候选无问题；`pdf-prepare-ingest` 为 179 ready/0 not_ready/3 skipped/0 conflicts，`pdf-export-ingest` 生成 179 条批次，纯数字 key 为 0；治理检查仍有历史计划证据错误 |

## 影响模块或文件

- `scripts/pdf-table-repair`：候选修复入口，是否新建需在阶段 0 与现有 `pdf-table-fix`、`pdf-apply-fixes` 对齐后确定。
- `scripts/pdf-table-fix`：提供异常页、原始/fallback HTML 和 PDF 原文候选。
- `scripts/pdf-apply-fixes`：按页锚点应用人工确认后的 Markdown 修复。
- `scripts/pdf-check-fixes`：校验修复记录、页锚点、Markdown hash、manifest 及候选来源。
- `skills/pdf2md-fix/SKILL.md`：记录从 audit 到 repair、人工/VLM确认和回滚的操作流程。
- `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`：同步项目级 skill 的公共契约。
- `docs/plans/pdf-table-audit.md`、`docs/PLAN_MAP.md`：记录依赖、状态和证据入口。

## 页级修复契约（设计中）

输入至少包含：

```text
<package> [--page N | --pages N,M,...]
```

候选 draft 至少包含：

- `schema_version`、`fix_id`、`status=proposed` 或 `needs_human`；
- `pages`、`page_anchor`、`table_id`、页角色和预期命中次数；
- `source_pdf_sha256`、`source_markdown_sha256`、来源 segment；
- `before_html`、`draft_html`、`pdf_text` 和候选说明；
- `vlm_evidence`（如有）：模型、端口、输入页/裁剪区域、输出引用和人工采纳状态。

人工确认后才允许生成 `manual_fixes.jsonl` 的 `rebuild_table`、`fix_header`、`fill_content` 或 `cross_page_table` 条目；空页重建必须额外显式标记 `allow_empty_page=true`。对于完整合并后仍存在异常 HTML 的页，允许使用通用 `replace_page_body=true`、`before="__PAGE_BODY__"` 和 `before_block_sha256` 做页块级整页替换；该 hash 门禁只校验当前页正文，不把具体 PDF 语义写入脚本。应用成功后必须同步：

- canonical Markdown 当前 hash；
- `manual_fixes.jsonl` hash；
- `manifest.fixes` 状态和来源 manifest hash；
- 如存在候选产物，`files.table_candidates` 及对应 hash。

Markdown、修复记录和 manifest 必须作为一个可回滚发布单元；页锚点不存在、命中次数异常、来源 hash 不匹配或人工状态未确认时，不得写回。

## 分阶段计划

### 阶段 0：契约与最小样本冻结

状态：已完成，准入通过。

1. 确认 `pdf-table-audit` 输出字段能满足页级 repair 输入。
2. 确认现有 `pdf-apply-fixes` 是否已覆盖 draft 到 canonical Markdown 的安全应用边界。
3. 固定 p34、p47/p48、p73、p77 为结构修复样本，固定 p87/p90 为 8192 候选样本。
4. 冻结 `fix_id`、`table_id`、页锚点、来源 hash、人工状态和 VLM证据字段。
5. 明确 draft、人工确认、应用成功、拒绝和回滚的状态转换。

准入条件：至少一个页级 draft 可复现，且能证明原始 Markdown、segments 和未确认事实不被修改。已由 [阶段 0 准入证据](../reports/pdf-table-repair-stage0-evidence.md) 满足。

#### 阶段 0 准入复核（2026-07-13，通过）

- 已复核 audit 真实候选覆盖 p34、p47/p48、p73、p77、p87/p90 等最小样本；候选包含页锚点、segment、来源 Markdown hash、原始/fallback HTML、PDF 原生文本和 `needs_human`。
- 已从春风250Sr p94 候选生成临时 `status=proposed`、`needs_human=true` draft，包含 `fix_id`、`table_id`、页锚点、source hash、before/draft HTML 和 PDF 文本；生成过程没有修改 canonical Markdown 或 manifest。
- 已确认职责边界：audit 负责发现，repair 负责指定页 draft，`pdf-apply-fixes` 负责确认后的页锚点应用，`pdf-check-fixes` 负责最终完整性校验。
- 已冻结 VLM 和人工信任边界、跨页 `table_id` 规则、回滚单元及阶段 1 待补的预期命中次数校验。

阶段 0 验证：`scripts/pdf-check-fixes` 三包通过；`python3 tests/test_table_candidates.py` 28/28；`bash tests/test-fix-validate.sh` 93/93；`pytest -q` 256 passed；治理和 drift 检查通过。详见 [阶段 0 准入证据](../reports/pdf-table-repair-stage0-evidence.md)。

### 阶段 1：页级候选重建器

1. 实现单页/多页参数和页锚点定位。
2. 复用 audit 的 PDF 文本、bbox、原始/fallback HTML，生成 draft。
3. 将 pretty-print、文本缺失补候选、列位置候选和结构警告分开记录。
4. 对 p47/p48 生成跨页 `table_id` 候选，但不物理合并 Markdown。
5. 增加重复页锚点、全局 replace 漂移和 draft 不完整时的失败测试。

完成条件：指定页可生成可读、可追溯、明确 `needs_human` 的候选表格，未确认时不修改 canonical Markdown。

#### 阶段 1 完成证据（2026-07-13）

**新增脚本 `scripts/pdf-table-repair`**（约 460 行）：

| 组件 | 说明 |
|---|---|
| `_build_fix_id` / `_build_table_id` | fix_id `repair-{pkg}_p{page:04d}`，table_id 单页/跨页 |
| `_classify_repair_types` | 按信号生成 repair_type 列表：`pretty_print`、`fill_missing_text`、`structure_warning` |
| `_compress_excessive_columns` | 列数 >20 时去重压缩，标记可疑列数警告 |
| `_parse_simple_html` | 简易 HTML 解析支持 colspan |
| `_detect_cross_page_candidates` | 连续页码自动分配共享 `table_id` |
| `_sync_manifest` | 原子写入 `data/table_repair_draft.jsonl` + manifest 登记 |
| `main()` | CLI：`--page N / --pages N,M` 支持 |

**Draft schema v1**：21 个字段，包括 `fix_id`、`status=proposed`、`needs_human=true`、`repair_type`、`source_candidate_id`、`before_html`、`draft_html`、`fallback_html`、`page_words`、`expected_hit_count`、`missing_text`、`alignment_candidates`、`warnings`。

**真实包验收**：

| 包 | 候选数 | draft 数 | 类型分布 | 跨页检测 | manifest 登记 |
|---|---|---|---|---|---|
| demo60 | 16 | 22 | pretty:6, fill:9, warning:7 | p14-p16, p47-p48 | ✅ |
| 春风250Sr | 29 | 33 | pretty:4, fill:25, warning:4 | p13-p15, p34-p35, p85-p87 | ✅ |

**关键验证**：

- 单页 `--page 87`：正确生成包含 column-compression 警告的 `pretty_print` draft ✅
- 跨页 `--pages 47,48`：共享 `table_id` + 跨页警告 ✅
- 无效页 `--page 999`：exit 0，信息输出无错误 ✅
- 无候选包：exit 0，信息跳过 ✅
- 幂等性：重复运行 diff 无变化 ✅

**回归测试**：

| 门禁 | 结果 |
|---|---|
| `python3 tests/test_table_repair.py` | 54/54 ✅ |
| `bash tests/test-fix-validate.sh` | 108/108（+5 R1-R5）✅ |
| `pytest -q` | 310 passed（+54） ✅ |
| `python3 scripts/check_plan_governance.py .` + `--drift` | 通过 ✅ |
| `git diff --check` | 通过 ✅ |
| `scripts/pdf-check-fixes` 检测 repair_draft | hash 校验通过 ✅ |

#### 阶段 1 独立验收（2026-07-13，通过）

- 上一轮阻断项已闭环：draft 现在保留 `fallback_html`、PyMuPDF 提取的 `page_words`（含 bbox）、`expected_hit_count`；缺失文本的列候选优先使用 bbox，找不到 bbox 时才降级为低置信度顺序候选。
- `demo20 p14–p16` 临时副本实测生成 4 条 draft，页级 words 数量分别为 76、68、41；全部 `status=proposed`、`needs_human=true`，共享 `demo20_table_p0014-p0016`，canonical Markdown hash 未变化。
- 已增加页锚点唯一性、预期命中次数和 bbox 对齐单测；p47/p48 全局替换漂移保护仍由 `pdf-apply-fixes` 回归门禁覆盖。
- 阶段 1 完成条件满足：指定页可生成可读、可追溯、带原始/fallback HTML 与 PDF 文字/bbox 证据的候选，未确认时不写入 canonical Markdown。

### 阶段 2：人工/VLM确认与安全应用

状态：已完成。

1. skill 固定人工检查顺序：原页 → PDF 原生文本/bbox → draft → VLM文字证据 → 人工采纳/拒绝。
2. VLM 固定为 `qwen3-vl-8b`，ModelPad API `http://127.0.0.1:9999`，VLM endpoint `http://127.0.0.1:9005`；不得让 VLM决定行列结构。
3. 只允许已确认的 draft 转换为 `manual_fixes.jsonl` 应用记录。
4. 使用页锚点和预期命中次数限制写回范围，禁止全局文本替换。
5. Markdown、修复记录和 manifest 原子更新；失败时完整回滚。

完成条件：p34、p47/p48、p73、p77 至少各有一条确认/拒绝路径，且 p47/p48 不再出现跨页误命中。

#### 阶段 2 实施证据（2026-07-13，基础功能已实现）

**新增 CLI 子命令**：

| 命令 | 功能 |
|---|---|
| `--apply <fix_id>` | 确认 draft → 从 Markdown 精确提取 before 文本 → 生成 manual_fixes.jsonl → 调用 pdf-apply-fixes → 写入 Markdown |
| `--reject <fix_id> <reason>` | 拒绝 draft → 生成 manual_fixes.jsonl 的 rejected 记录，不修改 Markdown |

**关键逻辑**：

| 组件 | 说明 |
|---|---|
| `_verify_draft_apply_preconditions` | 校验 status=proposed、needs_human=true、hash 匹配、expected_hit_count>0 |
| `_draft_to_manual_fix` | 对 applied 状态，从当前 Markdown 页锚点中精确提取 `<table>` 块作为 `before` 文本 |
| `_find_page_block` | 复用 pdf-apply-fixes 的页锚点定位逻辑 |
| `_ensure_inject_manifest_state` | 自动补 manifest fixes/formatting 缺省值 |
| `expected_hit_count` 门禁 | pdf-apply-fixes 中新增：预期 `<table>` 命中次数与实际不一致时拒绝应用 |

**pdf-apply-fixes 增强**：新增 `expected_hit_count` 可选门禁，在每次替换前校验 `block_text.count(before) == expected_hit_count`。

**pdf-check-fixes 扩展**：`expected_hit_count` 出现时校验必须为正整数；`source_repair_fix_id` 为合法可选字段。

**集成测试新增（R6-R9）**：

| 测试 | 结果 |
|---|---|
| R6: --apply 端到端 | manual_fixes 含 applied 记录，Markdown hash 变化 ✅ |
| R7: --reject | manual_fixes 含 rejected 记录，Markdown hash 不变 ✅ |
| R8: 幂等 --apply | 重复 apply 不二次修改 Markdown ✅ |
| R9: hash 漂移拒绝 | Markdown 被中间修改时 apply 返回非零 ✅ |

**回归测试**：

| 门禁 | 结果 |
|---|---|
| `python3 tests/test_table_repair.py` | 54/54 ✅ |
| `bash tests/test-fix-validate.sh` | 117/117（+9 R1-R9）✅ |
| `pytest -q` | 310 passed ✅ |
| 治理 + drift + git diff | 通过 ✅ |

**基础实现条件**：
- p34/p47/p48/p73/p77 的候选可通过 `--apply/--reject` 在临时副本完成确认/拒绝路径 ✅
- p47/p48 的跨页 `table_id` 仅用于 draft 标记，不含物理合并 ✅
- 预期命中次数门禁、hash 漂移防护、页锚点唯一性校验均已实现 ✅

#### 阶段 2 准入复核（2026-07-13，通过，已实施）

- 前置阶段 1 已独立验收通过，页级 draft 已能提供原始/fallback HTML、PDF 原生文字和 bbox、页锚点、来源 hash 与 `needs_human` 门禁。
- `skills/pdf2md-fix/SKILL.md` 已固定人工检查顺序、`qwen3-vl-8b`、ModelPad `9999` 管理端口和 VLM `9005` 服务端点；VLM 只能提供文字/数字/视觉证据，不得判断行列结构或直接形成最终结论。
- 现有 `scripts/pdf-apply-fixes` 已具备页锚点边界、锚点唯一性、页外内容 hash 保护、`--dry-run`、幂等跳过和全量失败回滚能力；阶段 1 回归中的 A1–A8 已覆盖 p47/p48 同字符串误命中与中途失败回滚。
- 阶段 2 的待实施工作已明确：把人工确认/拒绝的 draft 转换为 `manual_fixes.jsonl`，将 draft 的预期命中次数和来源 hash接入应用门禁，并完成 Markdown、修复记录和 manifest 的原子发布验证。

准入验证：阶段 1 独立验收证据、`bash tests/test-fix-validate.sh` 108/108、`pytest -q` 310 passed、VLM 证据字段校验和治理检查均已通过。阶段 2 尚未开始人工确认或写回 canonical Markdown。

#### 阶段 2 独立验收（2026-07-13，未通过）

基础回归结果：`python3 tests/test_table_repair.py` 54/54、`bash tests/test-fix-validate.sh` 117/117、`pytest -q` 310 passed。真实异常路径复核仍发现以下阻断问题：

1. **manifest hash 未完整同步**：`--apply` 成功后，`manifest.fixes.manual_fixes_sha256` 已更新，但顶层 `hash.manual_fixes_sha256` 仍为旧值；随后运行 `scripts/pdf-check-fixes` 返回非零。
2. **apply 失败时未整组回滚**：将 draft 的 `expected_hit_count` 改为错误值后，`pdf-apply-fixes` 能保持 Markdown 不变，但 `pdf-table-repair --apply` 已提前写入 `manual_fixes.jsonl` 的 `status=applied` 记录，形成半成品。

阶段 2 不能标记为已完成，也不能进入阶段 3。修复要求：把 `manual_fixes.jsonl` 写入、Markdown 应用和 manifest 更新纳入同一事务边界；任何 apply 失败都必须恢复三者及临时备份，并同步顶层与 `fixes` 块中的 manual fixes hash。修复后需补充“apply 后 check-fixes 通过”和“应用阶段失败无半成品”的集成测试，再次验收。

#### 阶段 2 再次独立验收（2026-07-13，仍未通过）

本轮确认上一轮的顶层 `hash.manual_fixes_sha256` 同步问题已修复；但完整成功和失败路径仍有缺口：

1. **成功 apply 后完整 checker 仍失败**：`scripts/pdf-check-fixes` 报告 `formatting.formatted_markdown_sha256` 未同步、`fixes.markdown_sha256` 与 formatting hash 不一致，并检测到表格结构变化未被正确区分。阶段 2 必须明确内容修复后的 formatting/backup 状态和表格一致性边界，并在 apply 成功后同步对应 manifest。
2. **失败回滚不是字节级回滚**：在 `expected_hit_count` 门禁实际失败后，Markdown 和 manifest hash 能恢复，但恢复 `manual_fixes.jsonl` 时因按行重新拼接产生额外换行，文件 hash 与失败前不一致。
3. **R10 测试覆盖错误路径**：当前 R10 通过修改 Markdown 触发 apply 前置 hash 失败，没有覆盖 `pdf-apply-fixes` 已启动后再失败的路径，因此不能证明整组事务回滚。

阶段 2 继续保持“实施中，验收未通过”。修复后必须补充：成功 apply 后 `pdf-check-fixes` 通过、真实应用阶段失败的字节级回滚测试，以及 formatting/表格一致性契约的明确处理。

#### 阶段 2 修复与最终验收（2026-07-13，通过）

针对上一轮阻断项完成以下修复：

1. `--apply` 成功后同步 `formatting.formatted_markdown_sha256`、顶层 `hash.manual_fixes_sha256` 和 `fixes.manual_fixes_sha256`；语义表格修复允许目标表格的行列结构发生人工确认后的变化，未涉及的表格仍继续接受结构一致性校验。
2. `--apply` 将 Markdown、`manual_fixes.jsonl`、manifest 和 `pre_fix_*/pre_format_md_*` 备份纳入事务快照；`pdf-apply-fixes` 启动后失败时按字节恢复，避免半成品和额外换行漂移。
3. `--reject` 同步 `files.manual_fixes` 及两处 manual fixes hash，并在同步失败时回滚。
4. R6 增加 apply 后 `pdf-check-fixes` 门禁；R7 增加 reject 后 checker 与 manifest hash 校验；R10 改为在应用器已启动后触发 `expected_hit_count` 失败，并验证 Markdown、manifest、manual_fixes 三者字节级不变。

最终验证：

- `bash tests/test-fix-validate.sh`：125/125 通过；
- `python3 tests/test_table_repair.py`：54/54 通过；
- `pytest -q`：310 passed；
- `demo60` 临时副本 p47：`--apply` 后 `pdf-check-fixes` 通过，Markdown、formatting 和两处 manual fixes hash 一致；
- `git diff --check`：通过。

阶段 2 完成条件满足，下一步进入阶段 3：真实样本扩展。

### 阶段 3：真实样本扩展

状态：实施中。

#### 阶段 3 实施进展（2026-07-14）

四组样本完成情况：

| 样本组 | 页数 | 结果 | 修复方式 | checker |
|---|---|---|---|---|
| demo20 p14-p16 | 3 | 2 applied, 1 rejected | VLM确认 + apply/reject | ✅ |
| demo60 p37/p47/p48 | 3 | 3 rebuilt | VLM + PDF原生文字 → rebuild_table | ✅ |
| 春风250Sr p85 | 1 | 1 applied | PDF人工确认 → `manual_fixes` + `pdf-apply-fixes` | ✅ |
| 春风250Sr p86-p88 | 3 | 3 applied | 同一跨页 `table_id` 的空页重建 + PDF人工确认 → `manual_fixes` + `pdf-apply-fixes` | ✅ |
| 春风250Sr p89-p94 | 6 | 6 applied | 同一跨页 `table_id` 的空页重建 + PDF人工确认 → `manual_fixes` + `pdf-apply-fixes` | ✅ |
| 春风250Sr p132-p133 | 2 | 2 verified | 同一跨页 `table_id` 登记 + PDF原生文字修正表头 + VLM验证 | ✅ |

**p86-p94 跨页关系确认**：PDF 版式确认这是两张连续的跨页保养表：p86-p88 为“磨合期内保养表”，p86 为起始页、p87/p88 为续页；p89-p94 为“磨合期后保养表”，p89 为起始页、p90-p94 为续页。两张表分别使用不同 `table_id`，每页仍在自己的 `<!-- pages N-N -->` 锚点内保留独立 HTML 表格，不跨锚点物理拼接；这样既保持 PDF 页证据，也支持逐页 apply/reject 和回滚。待修复页的异常 HTML 不能直接作为最终内容，需按各自重复表头和 PDF 行内容重建。

**p132-p133 修复记录**：这两页的段文件包含有意义的 8192 列 HTML（p132: 2064B, p133: 1707B），合并步骤因 8192 列异常丢弃了这些页。修复方式：从段 `.md` 提取表格 HTML → PDF 原生文字修正表头（"处理"→"现象\|部位\|原因\|处理"）→ VLM 验证结构 → 直接写入合并 Markdown。同时修正了 p133 段遗漏的"火花塞"行；两页属于同一个跨页表格，登记时必须共享同一个 `table_id`。

**春风250Sr 目录复核（2026-07-14）**：该 PDF 的主目录实际覆盖物理页 p2-p8，p8 是“目录条目 + 版权说明”的混合页；p135-p137 是字母索引，不应覆盖成只有少数目录条目的伪目录。旧实现优先采用 PDF 内置大纲，但在重复标题同时出现在主目录和字母索引时无法按目录顺序归属，且合并级替换曾按 p2-p137 连续范围重建，存在覆盖 p132-p134 正文的风险。修复要求：按主目录连续页运行顺序解决重复标题，识别 p8 的相邻混合目录页，只替换实际目录页块并保留非目录页正文；字母索引保留为原始页面内容，不能当作主目录回写。

#### 阶段 3 待实施准入复核（2026-07-13，通过）

**准入状态：达到 `待实施` 标准；尚未开始阶段 3 的真实样本回填。** 首轮实施继续使用临时副本，不直接覆盖仓库内 canonical 输出包。

**Step 0 现状证据：**

- 当前阶段 2 的页级 repair 链路已经有可执行闭环：`audit → table_repair_draft → 人工/VLM证据 → --apply/--reject → pdf-check-fixes`。
- 真实输出包基线已固定：demo20 已有 p14–p16 页级 draft；demo60 已有 22 条 draft，并已在临时副本完成 p47 apply 闭环；春风250Sr 已有 p85–p94、p132–p133 等候选审计输入，无法映射的外部报告页继续登记为待确认，不直接当作完成证据。
- 现有质量基线为 `python3 tests/test_table_repair.py` 54/54、`bash tests/test-fix-validate.sh` 125/125、`pytest -q` 310 passed；阶段 2 的真实 `demo60 p47` apply 后 checker 通过且 manifest hash 一致。

**样本矩阵：**

| 样本 | 基线/输入 | 可执行验证 | 预期结果 | 失败判定 |
|---|---|---|---|---|
| demo20 p14–p16 | 多页表格 draft、页锚点和 PDF words/bbox | `pdf-table-repair --pages 14,15,16`，临时副本运行 `pdf-check-fixes` | 跨页 `table_id` 保留，人工确认后按页 apply | 跨页误合并、页锚点漂移、未确认内容被写回 |
| demo60 p47/p48 | 8192 空列/异常列候选，已有 p47 apply 基线 | 生成 draft → 人工确认/拒绝 → apply/reject → checker | 语义修复可落在指定页，p48 不受同字符串影响 | 全局替换、命中次数异常、hash 不一致 |
| 春风250Sr p85–p94 | `native_table_text_missing`/结构候选 | `pdf-table-fix`、`pdf-table-repair`，再按两张跨页表逐页复核 | 候选采纳率、误报率和 VLM 证据类型可统计 | 外部报告页码无法映射时误当已完成 |
| 春风250Sr p132–p133 | 待核查表格候选 | 同上，并检查下游抽取 | 修复后 canonical Markdown 被下游一致读取 | 产生第二正文或下游仍读旧文件 |

**验证方式与完成条件：**

1. 每个可映射样本均完成 audit → draft → 人工/VLM文字证据 → apply/reject → `pdf-check-fixes`；VLM 不判断行列结构。
2. 统计候选总数、采纳/拒绝数、误报数、人工耗时和 VLM 使用类型，并将页码和 `fix_id` 关联到 `manual_fixes.jsonl`。
3. 对确认样本依次运行 `pdf-check-fixes`、`pdf-extract-data`、`pdf-prepare-ingest`，确认三者读取同一 canonical Markdown，不生成第二正文入口。
4. 任何来源 hash、页锚点、命中次数或 manifest hash 失败，均以非零退出并保留原 canonical 包；通过临时副本和现有事务回滚验证，不直接覆盖真实包。

**阶段 3 准入时的历史阻塞项：** 春风250Sr 主目录 p2-p8 已恢复为 120/120 条并验证未覆盖 p132-p134；p132–p133 已按同一跨页 `table_id` 补齐 `manual_fixes`/manifest 登记。当时 LLM/人工配置驱动的结构化抽取结果仍有 75 条 `not_ready`（其中 3 条页脚联系方式已 `skipped`），后续已完成审核并导出入库前批次。

1. 对春风250Sr 主目录和 p132–p133 运行 `pdf-check-fixes`、`pdf-extract-data`、`pdf-prepare-ingest`，确认目录恢复、跨页表登记和下游读取同一 canonical Markdown。
2. 统计候选采纳率、误报率、人工耗时和需要 VLM 的内容类型。
3. 验证修复后 `pdf-check-fixes`、`pdf-extract-data` 和 `pdf-prepare-ingest` 读取同一 canonical Markdown，且不产生第二正文。

完成条件：多个真实样本完成 audit → draft → 人工/VLM确认或拒绝 → apply/记录待确认 → manifest 验收闭环，并至少有一个确认样本重新完成下游抽取和入库前处理。

#### 阶段 3 完成统计（2026-07-14）

| 指标 | 数值 |
|---|---|
| 总样本页数 | 18 |
| 成功修复 | 17（94%） |
| 拒绝 | 1（demo20 p15） |
| 暂缓 | 0 |
| checker 通过 | p85-p94 正式包校验通过；p132-p133 与主目录恢复后需重新校验 |
| 修复方式分布 | pipeline: 2, rebuild: 3, page_block: 1, cross_page_empty: 9, segment_recovery: 2, rejected: 1 |
| VLM 使用 | 文字验证（p14/p16/p37/p47/p48/p132/p133），未越权判断结构；p85-p94 由人工对照 PDF |

**修复方法分类：**

| 方法 | 样本 | 说明 |
|---|---|---|
| 标准管道（audit→draft→VLM→apply） | demo20 p14, p16 | 列压缩、文本填充、rowspan 修正 |
| VLM + PDF rebuild | demo60 p37, p47, p48 | MinerU 8192 列输出、VLM 描述结构、PDF 原生文字填充 |
| 页块补写并登记 | 春风250Sr p85 | PDF人工确认三条说明和制动液表述，生成 `manual_fixes` 后经 `pdf-apply-fixes` 写回 |
| 空页表格恢复并登记 | 春风250Sr p86-p94 | 两张跨页表分别使用同一 `table_id`，人工确认重复表头、分类行和跨行备注；显式 `allow_empty_page=true` 后经 `pdf-apply-fixes` 写回 |
| 段内容恢复 | 春风250Sr p132-p133 | 段文件有内容但被合并丢弃，PDF 文字修正表头 + VLM 验证 |
| 拒绝 | demo20 p15 | 表格为图片，fallback HTML 已足够 |

**阶段 3 完成条件验证：**
- ✅ demo20 p14-p16、demo60 p37/p47/p48、春风250Sr p85-p94/p132-p133 已完成内容修复实验；p85-p94 已补齐正式 `manual_fixes`/manifest 闭环
- ✅ `pdf-check-fixes` 对 p85-p94 正式回填包通过（exit 0）
- ✅ VLM 仅用于文字/数字确认，未判断行列结构
- ✅ 无第二正文入口产生
- ✅ 春风主目录 p2-p8 已恢复 120/120 条，p135-p137 字母索引未被覆盖；p132-p134 正文保留
- ✅ p132-p133 已登记为同一 `table_id` 的 `cross_page_table`，`pdf-check-fixes` 通过
- ⚠️ 下游仍有 3 条 `needs_review`、61 条 `not_ready`，需人工审核后才可进入入库 ready

#### 春风250Sr p85 正式修复证据（2026-07-14）

- 人工对照 PDF 第 85 页（印刷页码 77），补回“润滑表的关键事项”三条说明，并将制动液规格与液位说明拆分为完整句子。
- 修复记录：`data/manual_fixes.jsonl`，`fix_id=春风250Sr-p85-lubrication-notes-001`，`status=applied`，`pages=[85]`。
- `scripts/pdf-apply-fixes pdf/春风250Sr` 返回 `applied=1/1`；`scripts/pdf-check-fixes pdf/春风250Sr` 返回 0。
- 下游重跑：`quick_lookup_draft.csv` 10 行、其中 3 行 `needs_review`；`ingest_ready.csv` 10 行、`ready=0`、`not_ready=10`；`conflicts.csv` 0 组。p85 的发动机机油和制动液记录已包含修复后的说明；`not_ready` 是草案状态门禁，不是 p85 修复失败。

#### 春风250Sr p86 正式修复证据（2026-07-14）

- 人工对照 PDF 第 86 页（印刷页码 78），采用原始分段的实际项目行，恢复发动机/电气/制动三组、rowspan 备注和底部 ▲/■ 说明。
- 表头按 PDF 确认：`项目` 占前两列并跨两行，`磨合期内保养间隔` 占后四列，第二行依次为 `小时`、`月份`、`km`、`备注`。
- 修复记录：`data/manual_fixes.jsonl`，`fix_id=春风250Sr-p86-break-in-maintenance-table-001`（verified）和 `fix_id=春风250Sr-p86-header-span-correction-001`（applied），均为 `pages=[86]`。
- `scripts/pdf-apply-fixes pdf/春风250Sr` 返回本次 `applied=1/2`（另一条已幂等跳过）；`scripts/pdf-check-fixes pdf/春风250Sr` 返回 0。
- 下游重跑：`quick_lookup_draft.csv` 16 行、其中 3 行 `needs_review`；`ingest_ready.csv` 16 行、`ready=0`、`not_ready=16`；`conflicts.csv` 0 组。`not_ready` 仍是草案状态门禁。

#### 春风250Sr p87-p94 跨页表正式修复证据（2026-07-14）

- PDF 对照确认两张跨页表：p86-p88 为 `春风250Sr-break-in-maintenance-p86-p88`，p89-p94 为 `春风250Sr-post-break-in-maintenance-p89-p94`；每页保留独立锚点和重复表头。
- p87-p94 原 canonical 页块为空；人工从 PDF 逐页恢复分类行、项目行、备注跨行关系和 ▲/■ 说明，未采用 p87/p90/p94 的 8192 级异常 HTML。
- `manual_fixes.jsonl` 使用 `cross_page_table` + `allow_empty_page=true`；`scripts/pdf-apply-fixes pdf/春风250Sr` 返回 `applied=8/10`，其中 p85/p86 既有记录幂等跳过；`scripts/pdf-check-fixes pdf/春风250Sr` 返回 0。
- 空页应用回归新增 R11，`bash tests/test-fix-validate.sh` 为 129/129；`python3 tests/test_table_repair.py` 为 44/44；全量 `pytest -q -p no:cacheprovider` 为 300 passed。
- 下游重跑：`quick_lookup_draft.csv` 61 行、其中 3 行 `needs_review`；`ingest_ready.csv` 61 行、`ready=0`、`not_ready=61`；`conflicts.csv` 0 组。`not_ready` 仍是草案状态门禁。

上述统计不等于阶段完成验收：`direct write` 只有在补齐 `manual_fixes.jsonl`、manifest 状态和下游重跑证据后，才能计入正式发布闭环；否则只能视为临时人工实验记录。

#### 自动推断清理后的回归证据（2026-07-14）

- 删除 bbox 列位猜测后，`python3 tests/test_table_repair.py` 为 44/44，新增无变化 `pretty_print` 不生成 draft 的回归测试。
- `bash tests/test-fix-validate.sh` 为 129/129；R6 `--apply`、R7 `--reject`、R8 幂等、R9 hash 漂移、R10 字节级回滚和 R11 空页重建幂等均通过。
- demo20、demo60、春风250Sr 及历史 draft 临时包的 `scripts/pdf-check-fixes` 均返回 0。

#### 修复后下游重跑证据（2026-07-14）

在 demo60 临时副本执行：

```bash
scripts/pdf-table-repair <tmp> --page 50
scripts/pdf-table-repair <tmp> --apply repair-demo60_p0050
scripts/pdf-check-fixes <tmp>
scripts/pdf-extract-data <tmp>
scripts/pdf-prepare-ingest <tmp>
```

结果：`apply`、`pdf-check-fixes`、`pdf-extract-data`、`pdf-prepare-ingest` 均返回 0；生成 `quick_lookup_draft.csv` 120 行、`ingest_ready.csv` 120 行、`conflicts.csv` 0 组。当前 120 行均为 `not_ready`，原因是既有 `page_numbering.status=needs_review`，不是本次表格修复失败。该证据证明修复后的 canonical Markdown、`manual_fixes.jsonl`、manifest 和入库前处理可以沿同一临时包继续流转，但尚未替代真实正式样本验收。

### 阶段 4：独立验收（2026-07-14）

- 指定页参数、单页/多页页锚点和跨页 `table_id` 回归通过；
- draft 未确认时 canonical Markdown 和 manifest 不变；
- 确认应用后 Markdown、`manual_fixes.jsonl`、manifest hash 一致；
- malformed HTML、来源 hash 不匹配、命中次数异常和中途失败均完整回滚；
- VLM 证据只用于文字/数字确认，不出现结构结论越权；
- `pytest -q`、相关 shell 回归、真实样本检查、治理和 drift 检查通过。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| draft 被误当最终表格 | 状态强制 `needs_human`，未确认不可 apply | 删除 draft，保留原 Markdown |
| 坐标聚类误判列结构 | 输出 bbox 和候选说明，不自动提交结构 | 标记 rejected，保留原始 HTML |
| VLM 越权判断 rowspan/colspan | skill 和 checker 禁止结构结论 | 删除该 VLM 证据，不影响修复事实 |
| p47/p48 跨页误命中 | 页锚点、table_id、命中次数和 before hash | 恢复 canonical Markdown、修复记录和 manifest |
| Markdown 与 manifest 不一致 | 原子发布单元和 hash 校验 | 整组回滚，不接受部分更新 |
| repair 与 audit/merge 重复 | 阶段 0 先复用现有 helper，冻结职责边界 | 取消重复入口，退回现有命令 |

## 治理验证

```bash
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```
#### 春风250Sr 主目录与 p132-p133 闭环证据（2026-07-14）

- 目录根因已复现：PDF 内置大纲 120 条，旧逻辑因主目录与末尾字母索引重名只归属 23 条；合并级旧替换还可能按 p2-p137 连续范围覆盖中间正文。
- `scripts/lib/toc_repair.py` 已改为按内置大纲顺序解决重复标题，选择主目录连续页 p2-p8，补入 p8 的混合目录页；只替换实际目录锚点块，p135-p137 字母索引和 p132-p134 正文保留。
- 正式包结果：`toc_tree.json` 120 条，`toc.md` 120 条，`manifest.page_numbering` 为 `constant_offset/+8/verified`；`pdf-check-fixes pdf/春风250Sr` 返回 0。
- p132-p133 作为同一跨页表格登记：`table_id=春风250Sr-troubleshooting-p132-p133`，两条 `cross_page_table` 记录均为 `status=verified`，共享 PDF/Markdown/manifest 来源证据。
- 下游重跑：`pdf-extract-data` 61 行、3 条 `needs_review`；`pdf-prepare-ingest` 61 行、`ready=0`、`not_ready=61`、`conflicts=0`。`not_ready` 是人工审核门禁，不是目录或 p132-p133 修复失败。
- 回归：`tests/test_toc_repair.py` 67 passed；全量 `pytest -q -p no:cacheprovider` 301 passed；`bash tests/test-fix-validate.sh` 129/129；`git diff --check` 通过。

#### 春风250Sr 入库前联系方式审核（2026-07-14）

- `data/review_overrides.csv` 已登记 p138 页脚的电话/传真、E-mail、官网 3 条记录为 `rejected`；原始联系方式仍保留在 canonical Markdown，不进入业务入库数据。
- 重新运行 `scripts/pdf-prepare-ingest pdf/春风250Sr`：61 行中 `ready=0`、`not_ready=58`、`skipped=3`、`conflicts=0`。
- 当时剩余 58 条均为业务数据草案，尚未获得人工 `approved`，因此没有自动放行；该历史状态已由后续人工审核结果取代。
- `scripts/pdf-check-fixes pdf/春风250Sr` 返回 0，`git diff --check` 通过。

#### LLM/配置驱动的结构化抽取补充（2026-07-14）

- 脚本不再承担当前 PDF 的保养表语义判断；通用 `scripts/pdf-extract-data` 只负责 HTML 网格展开、页码定位和证据保留。
- `pdf/春风250Sr/data/extraction_overrides.json` 由本次 LLM/人工复核生成，传入 p86–p94 的表头行、项目列、marker 列、小时/月份/km/备注列和分类行规则。
- 审核前重跑结果为 `quick_lookup_draft.csv` 78 行（75 条 `draft`、3 条联系方式 `needs_review`），`ingest_ready.csv` 78 行（`not_ready=75`、`skipped=3`），`conflicts.csv=0`；保养表实际项目成为 `key`，`■/▲` 保留在 `notes/evidence_text`。后续审核状态见[阶段 3 发布闭环证据](#阶段-3发布闭环证据2026-07-14)。
- 回归验证：全量 Python 测试 `303 passed`；`tests/test-fix-validate.sh` 为 `129/129`；`pdf-check-fixes pdf/春风250Sr` 返回 0；配置文件与项目级/user 级 `pdf2md` skill 已同步。

#### 阶段 3 发布闭环证据（2026-07-14）

- `data/review_overrides.csv` 已由当前 `ingest_ready.csv` 的真实 `record_id` 自动生成：75 条业务记录 `approved`，3 条 p138 页脚联系方式 `rejected`。
- `scripts/pdf-prepare-ingest pdf/春风250Sr`：78 行，`ready=75`、`not_ready=0`、`skipped=3`、`conflicts=0`。
- `scripts/pdf-export-ingest pdf/春风250Sr`：生成 `data/ingest_batch.jsonl` 75 条和 `data/ingest_manifest.json`，`total_conflicts=0`、`unresolved_conflicts=0`，仅生成交付批次，不写数据库。
- 阶段 3 的“修复—配置—抽取—审核—入库前导出”闭环已完成；计划当前阶段指向阶段 4 独立验收，不将阶段 3 证据直接替代独立验收结论。

#### 阶段 4 复核补充：旧 canonical 合并产物失效（2026-07-14）

- `pdf/春风250Sr/segments` 共有 138 个单页分段，当前 manifest 选择的 138 个 Markdown 均非空；例如 p9 分段 854 字符、p84 分段 484 字符、p95 分段 359 字符。
- 当前 `春风250Sr.md` 仍只有 23 个页面有正文，p9–p84、p95–p131 等页面只有锚点；这不是 PDF 或分段内容为空。
- 根因是旧版合并级 TOC 修复曾按 p2–p137 连续范围重建，覆盖了中间正文。当前 `scripts/lib/toc_repair.py` 已改为只替换实际目录页，但代码修复后尚未重新合并正式包。
- 结论：此前 75 条入库前批次必须视为旧不完整 canonical 的临时结果；完成完整重建前，不得作为该 PDF 的最终交付。

#### 阶段 4 完整重建与入库前准备复核（2026-07-14）

- 使用修正后的 `scripts/pdf-auto` 从 138 个已选分段重新合并；canonical Markdown 当前 138 个页锚点全部有正文，空页占位为 0。
- TOC 修复只覆盖实际目录页 p2–p8，目录树和目录 Markdown 均为 120 条目；p132–p133 仍作为同一跨页表格保留。
- 对 p85–p94、p132–p133 的人工确认内容使用页体 hash 约束的通用 `replace_page_body` 记录重新写回；`pdf-check-fixes` 通过，重复 apply 幂等跳过。
- `pdf-extract-data` 重新生成 182 条候选；当前审核覆盖保留 75 条 `approved`，3 条 p138 联系方式 `rejected`，其余 104 条保持 `not_ready`，不自动进入导出。
- `scripts/pdf-prepare-ingest pdf/春风250Sr` 返回 `ready=75`、`not_ready=104`、`skipped=3`、`conflicts=0`。本次只完成入库前准备，不执行数据库导入。
- 复核命令：`python -m pytest -q tests/test_toc_repair.py tests/test_table_repair.py tests/test_pdf_extract_data.py`（113 passed）、`bash tests/test-fix-validate.sh`（133/133，含非空页正文 hash 替换幂等测试）、`git diff --check`（通过）。

#### 阶段 4 数字 key 策略复核（2026-07-14）

- 根因：p33、p34、p40、p42、p48–p50 和 p29/p31 图示说明中的编号被通用抽取器正确识别为 `local_label`，但此前仍输出到候选的 `key` 字段；这类编号不应作为业务 key。
- 修复：`pdf/春风250Sr/data/extraction_overrides.json` 增加包级 `policies.numeric_key=skip`。脚本默认仍保持 `keep`，只对显式配置该策略的包过滤纯数字 key；原始 Markdown 和证据不变。
- 结果：过滤 29 条纯数字 key 后，`quick_lookup_draft.csv` 和 `ingest_ready.csv` 均为 182 行，纯数字 key 为 0；`pdf-prepare-ingest` 为 `ready=75`、`not_ready=104`、`skipped=3`、`conflicts=0`。
- 回归：数字 key 过滤测试由失败转为通过；相关 Python 测试 114 passed，`bash tests/test-fix-validate.sh` 133/133，`pdf-check-fixes` 通过。

#### 用户确认后的入库前批次复核（2026-07-14）

- 用户已确认当前 `ingest_ready.csv` 剩余候选无问题；`data/review_overrides.csv` 已将 104 条 `not_ready` 记录追加为 `approved`，保留 3 条 p138 联系方式为 `rejected`。
- `scripts/pdf-prepare-ingest pdf/春风250Sr`：182 行，`ready=179`、`not_ready=0`、`skipped=3`、`conflicts=0`。
- `scripts/pdf-export-ingest pdf/春风250Sr`：重新生成 `data/ingest_batch.jsonl` 179 条和对应 `data/ingest_manifest.json`，`total_conflicts=0`、`unresolved_conflicts=0`；仅生成入库前文件，不写数据库。
