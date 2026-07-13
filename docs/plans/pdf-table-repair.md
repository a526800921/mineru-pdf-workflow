# 计划：pdf-table-repair 页级表格候选重建

## 计划状态

- 状态：实施中
- 当前阶段：阶段 3：真实样本扩展（待实施）
- 最后更新：2026-07-13

本文档是页级表格“格式化 + 数据对齐 + 候选重建”能力的事实源。它依赖 [pdf-table-audit](pdf-table-audit.md) 提供异常页和 PDF 证据，不把表格语义修复混入 `pdf-merge` 的纯 pretty-print，也不把人工判断伪装成全自动事实生成。

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
- 在 draft 中同时处理确定性的 HTML pretty-print 和基于 PDF 证据的文本/列位置对齐候选。
- 保留原始 HTML、fallback HTML、PDF 原生文本、words/bbox、页锚点和来源 hash，便于人工复核。
- 人工确认后，复用页锚点安全应用器写回 canonical Markdown，并同步 `manual_fixes.jsonl` 与 manifest。
- 让下游通过 `fix_id`、页码、`table_id`、来源 hash 和修复状态知道这次表格重建发生了什么。

## 非目标

- 不自动决定最终列数、表头语义、`rowspan`、`colspan`、图片列取舍或跨页归属。
- 不让 VLM 判断表格行列结构；VLM 只验证文字、数字、警告和图中标注等证据。
- 不直接覆盖 Markdown；未经过人工确认的 draft 必须保持 `needs_human`。
- 不生成第二正文入口，不创建 `*-fixed.md` 或 `*-formatted.md`。
- 不替代 `pdf-table-audit` 的异常发现，也不替代 `pdf-merge` 的纯格式化链路。
- 不修改原始 `segments/**/content_list*.json`、PDF 或业务数据库。

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
- `before_html`、`draft_html`、`pdf_text`、words/bbox 证据和候选说明；
- `alignment_candidates`：文本落在哪个候选列/行，只表达候选，不表达最终事实；
- `vlm_evidence`（如有）：模型、端口、输入页/裁剪区域、输出引用和人工采纳状态。

人工确认后才允许生成 `manual_fixes.jsonl` 的 `rebuild_table`、`fix_header`、`fill_content` 或 `cross_page_table` 条目。应用成功后必须同步：

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
| `_extract_html_cell_texts` / `_detect_missing_text` | 从 PDF 原生文本检测 HTML 中缺失的文本，生成 alignment 候选 |
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

状态：待实施。

#### 阶段 3 待实施准入复核（2026-07-13，通过）

**准入状态：达到 `待实施` 标准；尚未开始阶段 3 的真实样本回填。** 首轮实施继续使用临时副本，不直接覆盖仓库内 canonical 输出包。

**Step 0 现状证据：**

- 当前阶段 2 的页级 repair 链路已经有可执行闭环：`audit → table_repair_draft → 人工/VLM证据 → --apply/--reject → pdf-check-fixes`。
- 真实输出包基线已固定：demo20 已有 p14–p16 页级 draft；demo60 已有 22 条 draft，并已在临时副本完成 p47 apply 闭环；春风250Sr 已有 p85–p93、p132–p133 等候选审计输入，无法映射的外部报告页继续登记为待确认，不直接当作完成证据。
- 现有质量基线为 `python3 tests/test_table_repair.py` 54/54、`bash tests/test-fix-validate.sh` 125/125、`pytest -q` 310 passed；阶段 2 的真实 `demo60 p47` apply 后 checker 通过且 manifest hash 一致。

**样本矩阵：**

| 样本 | 基线/输入 | 可执行验证 | 预期结果 | 失败判定 |
|---|---|---|---|---|
| demo20 p14–p16 | 多页表格 draft、页锚点和 PDF words/bbox | `pdf-table-repair --pages 14,15,16`，临时副本运行 `pdf-check-fixes` | 跨页 `table_id` 保留，人工确认后按页 apply | 跨页误合并、页锚点漂移、未确认内容被写回 |
| demo60 p47/p48 | 8192 空列/异常列候选，已有 p47 apply 基线 | 生成 draft → 人工确认/拒绝 → apply/reject → checker | 语义修复可落在指定页，p48 不受同字符串影响 | 全局替换、命中次数异常、hash 不一致 |
| 春风250Sr p85–p93 | `native_table_text_missing`/结构候选 | `pdf-table-fix`、`pdf-table-repair`，再按候选逐页复核 | 候选采纳率、误报率和 VLM 证据类型可统计 | 外部报告页码无法映射时误当已完成 |
| 春风250Sr p132–p133 | 待核查表格候选 | 同上，并检查下游抽取 | 修复后 canonical Markdown 被下游一致读取 | 产生第二正文或下游仍读旧文件 |

**验证方式与完成条件：**

1. 每个可映射样本均完成 audit → draft → 人工/VLM文字证据 → apply/reject → `pdf-check-fixes`；VLM 不判断行列结构。
2. 统计候选总数、采纳/拒绝数、误报数、人工耗时和 VLM 使用类型，并将页码和 `fix_id` 关联到 `manual_fixes.jsonl`。
3. 对确认样本依次运行 `pdf-check-fixes`、`pdf-extract-data`、`pdf-prepare-ingest`，确认三者读取同一 canonical Markdown，不生成第二正文入口。
4. 任何来源 hash、页锚点、命中次数或 manifest hash 失败，均以非零退出并保留原 canonical 包；通过临时副本和现有事务回滚验证，不直接覆盖真实包。

**当前阻塞项：无。** 外部报告页码与当前包无法对应的样本不阻塞阶段启动，只能标记为 `待确认`，不得写入阶段完成证据。

1. 在临时副本验证 p85–p93、p132–p133 等报告样本；无法对应当前输出包时只登记为待确认。
2. 统计候选采纳率、误报率、人工耗时和需要 VLM 的内容类型。
3. 验证修复后 `pdf-check-fixes`、`pdf-extract-data` 和 `pdf-prepare-ingest` 读取同一 canonical Markdown，且不产生第二正文。

完成条件：多个真实样本完成 audit → draft → 人工/VLM确认 → apply → manifest 验收闭环。

### 阶段 4：独立验收

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
