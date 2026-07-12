# 计划：pdf-table-repair 页级表格候选重建

## 计划状态

- 状态：候选
- 当前阶段：阶段 0：页级修复契约与最小样本冻结
- 最后更新：2026-07-12

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

状态：设计中。

1. 确认 `pdf-table-audit` 输出字段能满足页级 repair 输入。
2. 确认现有 `pdf-apply-fixes` 是否已覆盖 draft 到 canonical Markdown 的安全应用边界。
3. 固定 p34、p47/p48、p73、p77 为结构修复样本，固定 p87/p90 为 8192 候选样本。
4. 冻结 `fix_id`、`table_id`、页锚点、来源 hash、人工状态和 VLM证据字段。
5. 明确 draft、人工确认、应用成功、拒绝和回滚的状态转换。

准入条件：至少一个页级 draft 可复现，且能证明原始 Markdown、segments 和未确认事实不被修改。

### 阶段 1：页级候选重建器

1. 实现单页/多页参数和页锚点定位。
2. 复用 audit 的 PDF 文本、bbox、原始/fallback HTML，生成 draft。
3. 将 pretty-print、文本缺失补候选、列位置候选和结构警告分开记录。
4. 对 p47/p48 生成跨页 `table_id` 候选，但不物理合并 Markdown。
5. 增加重复页锚点、全局 replace 漂移和 draft 不完整时的失败测试。

完成条件：指定页可生成可读、可追溯、明确 `needs_human` 的候选表格，未确认时不修改 canonical Markdown。

### 阶段 2：人工/VLM确认与安全应用

1. skill 固定人工检查顺序：原页 → PDF 原生文本/bbox → draft → VLM文字证据 → 人工采纳/拒绝。
2. VLM 固定为 `qwen3-vl-8b`，ModelPad API `http://127.0.0.1:9999`，VLM endpoint `http://127.0.0.1:9005`；不得让 VLM决定行列结构。
3. 只允许已确认的 draft 转换为 `manual_fixes.jsonl` 应用记录。
4. 使用页锚点和预期命中次数限制写回范围，禁止全局文本替换。
5. Markdown、修复记录和 manifest 原子更新；失败时完整回滚。

完成条件：p34、p47/p48、p73、p77 至少各有一条确认/拒绝路径，且 p47/p48 不再出现跨页误命中。

### 阶段 3：真实样本扩展

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
