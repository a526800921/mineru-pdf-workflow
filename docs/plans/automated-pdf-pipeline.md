# 计划：自动化 PDF 解析流水线

## 背景

长 PDF 使用 MinerU 单次全量解析时，macOS 上的 PyTorch/MPS 缓存和 MinerU 中间结果会让内存持续增长。分段解析可以让每段结束后释放进程缓存，内存更稳定。

用户还需要减少人工逐页验证成本，因此需要建立“分段解析、自动验证、问题段重跑、再验证、人工兜底”的闭环，并为后续 Claude Code/MCP 接入保留清晰工具边界。

## 目标

建立一条可重复执行的 PDF 解析流水线：

```text
分段解析 -> 自动验证 -> 可疑段高精度重跑 -> 再验证 -> 合并 Markdown -> 人工兜底清单
```

## 非目标

- 不保证完全无人工复核。
- 不做 PDF 版式还原。
- 不把模型判断作为唯一验收依据。
- 不在当前阶段实现完整 MCP server。
- 不固定 MinerU 所有中间 JSON 产物的长期保留策略。

## 不变量

- 原始 PDF 不被修改或删除。
- 分段输出目录必须可独立删除和重跑。
- 合并 Markdown 可重新生成，不能作为唯一源数据。
- 自动验证只能筛出可疑段，不能替代最终人工兜底。
- 同一事实只在计划或 ADR 中定义一次，其他文档通过链接引用。

## 影响模块或文件

- `scripts/pdf`
- `scripts/pdf-seg`
- `scripts/pdf-merge`
- `scripts/pdf-validate`
- `docs/PLAN_MAP.md`
- `docs/plans/minimal-automation-runbook.md`
- `mcp/README.md`
- `docs/adr/0001-cli-first-mcp-ready.md`

## 公共契约变化

当前阶段的 CLI 契约：

- `scripts/pdf <pdf>`：单次解析，输出 `<文件名>-mineru-output/`。
- `scripts/pdf-seg <pdf>`：分段解析，输出 `<文件名>-mineru-segments/p0000-0019/` 等分段目录。
- `scripts/pdf-validate <pdf> <segments_dir>`：输出每段覆盖率和可疑段。
- `scripts/pdf-merge <segments_dir>`：合并分段 Markdown。
- `scripts/pdf-auto <pdf> <segments_dir>`：自动执行验证、可疑段 high 重跑、再验证、合并和人工兜底清单生成。

已实现的机器可读契约：

- `pdf-validate` 支持 `PDF_VALIDATE_JSON=1`，输出可被 MCP 调度读取的 JSON。
- MCP 工具只包装稳定 CLI 或复用其内部逻辑，不直接让模型拼复杂 shell 命令。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 建立样本和运行基线 | 有真实 PDF 样本 | Step 0 证据存在 | 已完成 |
| 阶段 1 | 固化基础 CLI 脚本 | MinerU CLI 可用 | 脚本语法和帮助命令通过 | 已完成 |
| 阶段 2 | 验证报告机器化 | `pdf-validate` 人类输出已验证有效 | JSON 输出可被程序消费 | 已完成 |
| 阶段 3 | 自动闭环 | JSON 报告可用 | 可疑段 high 重跑、再验证、合并并按需生成 review 文件 | 已完成 |
| 阶段 4 | MCP 接入准备 | CLI 契约稳定 | MCP 工具契约和脚本输出对齐 | 设计中 |

## 当前阶段

阶段 3 已完成，superpowers 中的 `pdf-auto` 进度 3 已合并到本计划。下一阶段为阶段 4（MCP 接入准备）。

### 阶段 3 完成证据

- `scripts/pdf-auto` 实现完整验证-重跑-再验证-合并-兜底流水线。
- 在 191 页摩托车说明书样本上验证通过：首次验证检出 1 个可疑段（p0000-0019，覆盖率 0.77），自动 high 精读重跑，二次验证后合并，输出 merged.md。
- 重跑结果写入独立 `-rerun/` 目录，不覆盖原始分段数据。
- 退出码约定：0=全部通过，1=脚本错误，2=合并完成但有段需人工复核（附带 review.md）。
- `PDF_AUTO_MERGE_OUTPUT`、`PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT` 环境变量控制行为。
- 计划治理检查通过。
- superpowers 实施计划归档为执行记录，正式事实来源以本文档和 [PLAN_MAP](../PLAN_MAP.md) 为准。

### 阶段 4 实施计划

目标：把现有 `pdf-auto` CLI 自动闭环整理成 MCP 可以稳定包装的最小契约。

实施任务：

1. 固定 Step 0 证据：记录 `pdf-auto`、`pdf-validate`、`pdf-merge` 的帮助输出、治理检查结果，以及 191 页样本的 `pdf-validate` JSON 摘要。
2. 定义 MCP 第一版边界：只暴露 `run_pdf_auto(pdf_path, segments_dir, threshold?, rerun_effort?, merge_output?)`。
3. 决策 CLI JSON summary：推荐新增 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`，让 MCP 不解析中文日志。
4. 更新 [MCP 接入设计](../../mcp/README.md)：把拆分工具降级为后续扩展，第一版以 `run_pdf_auto` 为准。
5. 运行计划治理检查。

### 阶段 4 Step 0 证据

- `scripts/pdf-auto --help` 可运行，当前支持 `PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT`、`PDF_AUTO_MERGE_OUTPUT`。
- `scripts/pdf-validate --help` 可运行，当前支持 `PDF_VALIDATE_JSON=1`。
- `scripts/pdf-merge --help` 可运行，当前支持 `PDF_MERGE_OUTPUT`。
- `python3 scripts/check_plan_governance.py .` 通过。
- 191 页说明书样本的 `pdf-validate` JSON 摘要：10 个分段，9 个 `passed`，1 个 `suspicious`，阈值 0.82。

### 阶段 4 契约决策

第一版 MCP 工具只包装 `scripts/pdf-auto`：

```text
run_pdf_auto(pdf_path, segments_dir, threshold?, rerun_effort?, merge_output?)
```

暂不在第一版拆分 `parse_pdf_segmented`、`validate_segments`、`rerun_segments`、`merge_segments`、`create_review_report`。这些工具保留为后续扩展。

推荐先补 `pdf-auto` 的 JSON summary 模式：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
```

目标输出包含 `status`、`exit_code`、`merged_markdown`、`review_markdown`、`rerun_segments`，并保留现有退出码语义。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 无文本层 PDF 如何验证 | 后续增加 OCR/VLM 对照验证策略 | 否 | 已延后 |
| 可疑段重跑覆盖原目录还是写入 `rerun-high/` | 写入独立 `-rerun/` 目录，合并前覆盖原始 .md | 否 | 已确认 |
| `pdf-auto` 暂无 JSON summary | 阶段 4 优先补 `PDF_AUTO_JSON=1`，再实现 MCP server | 是 | 待实施 |

## 风险和回滚

风险：

- PDF 无文本层时，覆盖率验证失效。
- `high` 不一定修复所有单字符错误。
- MinerU 中间输出结构可能随版本变化。
- 分段合并可能在跨页表格、跨页段落处产生断裂。

回滚：

- 保留原始 PDF。
- 每段输出独立保存，可以删除单个分段后重跑。
- 合并文件可重新生成，不作为唯一源数据。
- JSON 输出开关必须不影响默认人类可读输出。

## 关联 ADR、迁移、spec 或 issue

- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [MCP 接入设计](../../mcp/README.md)
- [superpowers pdf-auto 实施记录](../superpowers/plans/2026-06-27-pdf-auto-plan.md)
