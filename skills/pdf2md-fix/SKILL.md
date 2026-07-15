---
name: pdf2md-fix
description: Use when pdf-auto 已完成且存在 review.md，需要人工复核或修复 PDF 转换结果、TOC、跨页表格、异常 td、字段遗漏、章节归属、页锚点、VLM 证据、manual_fixes.jsonl、manifest 或 review_overrides.csv；本名称现为兼容入口，统一流程由 pdf2md 编排。
---

# pdf2md-fix 兼容入口

`pdf2md-fix` 保留为历史触发名称，但不再维护第二套人工修复流程。当前用户入口统一为 [`pdf2md`](../pdf2md/SKILL.md)：用户不需要学习或执行脚本，LLM 负责读取产物、展示 PDF 证据、请求确认、编排 CLI/受控动态 helper、更新配置并验证入库前数据准备结果。

## 兼容行为

当用户以 `pdf2md-fix` 名称触发时，继续当前会话并按 `pdf2md` 的统一流程处理：

```text
pdf-auto
  → 读取 manifest/review.md/canonical Markdown
  → 分类自动处理、需要用户确认、需要动态 helper 或保留待复核
  → 按页锚点处理 TOC、表格、缺失文本和章节归属
  → 同步 manual_fixes.jsonl / extraction_overrides.json / manifest
  → 抽取、人工审核和 review_overrides.csv
  → pdf-prepare-ingest
  → pdf-export-ingest
  → 交付入库前数据，不导入数据库
```

兼容入口必须明确说明：`pdf2md` 是唯一主入口，`pdf2md-fix` 只负责把历史触发方式导向同一流程；不得在本文件恢复旧版逐步操作手册、字段表或业务修复规则。

## 用户确认边界

用户仍只确认 PDF 事实和结构化候选：

- TOC 条目、物理目录页和正文页归属；
- 跨页表格是否属于同一逻辑表，以及表头和列语义；
- Markdown、表格或缺失文本候选是否符合 PDF；
- 结构化候选的 key/value/unit/section_path；
- 记录应 `approved`、`rejected` 还是继续 `needs_review`。

LLM 不得把推断当事实、自动批准候选或让用户执行 CLI。用户确认后，LLM 才能分别更新 `manual_fixes.jsonl`、`extraction_overrides.json` 或 `review_overrides.csv`。

## 安全与入库边界

- 原始 PDF、`segments/` 和 `content_list*.json` 始终只读。
- 动态辅助脚本必须经过 `scripts/pdf-run-helper` 的备份、dry-run、allowlist、验证和整组回滚；不得修改审核或入库前门禁产物。
- `pdf-check-fixes`、`pdf-prepare-ingest` 和 `pdf-export-ingest` 仍是统一流程的确定性 CLI；最终只交付入库前数据，不连接数据库。
- `pdf2md-fix` 不负责 MinerU 解析、ModelPad 生命周期、VLM 最终裁决或数据库导入。

## 事实源与兼容窗口

字段契约、Schema、枚举、VLM 证据、页锚点修复、表格修复和结构化审核规则继续以专项计划和 ADR 为事实源：

- [LLM/人工协作入口迁移计划](../../docs/plans/llm-human-collaboration-migration.md)
- [pdf2md-fix 人工复核与内容修复计划](../../docs/plans/pdf2md-fix-manual-workflow.md)
- [ADR 0003：LLM 编排与受控动态辅助脚本](../../docs/adr/0003-llm-orchestrated-dynamic-assistants.md)

阶段3只收敛入口，不删除本 skill，不删除 `pdf2md-fix` 触发名称，也不改写历史完成证据。兼容窗口持续到阶段4/5独立验收完成；届时再决定将本入口标记为 `已合并` 或 `已废弃`。若兼容验证失败，直接恢复本文件的上一版本，不改动 PDF 包或下游数据。
