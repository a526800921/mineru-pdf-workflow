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
| 阶段 4 | MCP 接入准备 | CLI 契约稳定 | MCP 工具契约和脚本输出对齐 | 已完成 |
| 阶段 5 | MCP server 最小实现 | `PDF_AUTO_JSON=1` 可用且工具边界已固定 | `run_pdf_auto` 返回结构化结果 | 已完成 |
| 阶段 6 | MCP 端到端验收与运行手册固化 | 阶段 5 已完成 | Claude Code 通过 MCP 跑通真实样本并覆盖主要返回路径 | 待实施 |

## 当前阶段

阶段 5 已完成，下一阶段为阶段 6（MCP 端到端验收与运行手册固化）。

### 阶段 3 完成证据

- `scripts/pdf-auto` 实现完整验证-重跑-再验证-合并-兜底流水线。
- 在 191 页摩托车说明书样本上验证通过：首次验证检出 1 个可疑段（p0000-0019，覆盖率 0.77），自动 high 精读重跑，二次验证后合并，输出 merged.md。
- 重跑结果写入独立 `-rerun/` 目录，不覆盖原始分段数据。
- 退出码约定：0=全部通过，1=脚本错误，2=合并完成但有段需人工复核（附带 review.md）。
- `PDF_AUTO_MERGE_OUTPUT`、`PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT` 环境变量控制行为。
- 计划治理检查通过。
- superpowers 实施计划归档为执行记录，正式事实来源以本文档和 [PLAN_MAP](../PLAN_MAP.md) 为准。

### 阶段 4 完成证据

- `scripts/pdf-auto --help` 可运行，已声明 `PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT`、`PDF_AUTO_MERGE_OUTPUT`、`PDF_AUTO_JSON=1`。
- `scripts/pdf-validate --help` 可运行，已支持 `PDF_VALIDATE_JSON=1`。
- `scripts/pdf-merge --help` 可运行，已支持 `PDF_MERGE_OUTPUT`。
- 191 页说明书样本的 `pdf-validate` JSON 摘要已固定：10 个分段，9 个 `passed`，1 个 `suspicious`，阈值 0.82。
- `mcp/README.md` 已将 MCP 第一版边界固定为 `run_pdf_auto`，拆分式工具保留为后续扩展。

### 阶段 5 完成证据

- `mcp/server/` 已包含 Node.js / TypeScript MCP server 项目。
- 只暴露 `run_pdf_auto` 工具，不实现拆分式工具。
- 工具通过 `execFile("bash", [scriptPath, pdf, segDir])` 调用 `PDF_AUTO_JSON=1 scripts/pdf-auto`。
- Zod schema 校验 `pdf_path`、`segments_dir`（必填）和 `threshold`、`rerun_effort`、`merge_output`（可选）。
- 运行时校验在启动子进程前检查 PDF 路径扩展名、文件存在性、分段目录存在性。
- stdout JSON 是状态判断的唯一事实来源；stderr 作为诊断信息返回。
- CLI 状态映射：`all_passed` → `passed`，`merged_with_issues` → `needs_review`，`error`/调用失败 → `failed`。
- 子进程使用白名单环境变量（`PDF_AUTO_JSON=1`、`PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT`、`PDF_AUTO_MERGE_OUTPUT`），无其他 env 注入。
- 项目根通过源文件位置推导（`__dirname` → 上溯 3 层），确保从任意 cwd 启动都能找到 `scripts/pdf-auto`。
- MCP 协议验证通过：`initialize` 和 `tools/list` 响应正确，`run_pdf_auto` 工具含完整 inputSchema。
- TypeScript 编译通过，产物位于 `mcp/server/dist/`。



### 阶段 6 实施计划

目标：在阶段 5 完成最小 MCP server 后，用真实样本验证 `run_pdf_auto` 能稳定完成 PDF 自动解析闭环，并把安装、启动、配置、调用和排障流程固化成可重复执行的手册。

确认状态：不需要额外产品或架构确认。阶段 6 的执行边界、状态覆盖和非目标已固定；真实样本路径、MCP 配置位置和具体运行输出在执行时作为验证证据记录。

实施标准：

- 阶段 6 必须在阶段 5 完成后开始。
- 以 Claude Code 通过 MCP 调用 `run_pdf_auto` 为验收入口，不直接用 shell 调用替代端到端验收。
- 至少使用一个真实 PDF 样本完成 `passed` 路径验证。
- `needs_review` 和 `failed` 可以使用真实样本，也可以使用最小模拟样例，但必须记录输入、返回 JSON 和诊断信息。
- 验收过程只固化运行手册和排障清单，不新增 MCP 工具。
- 阶段 6 发现的新能力需求一律进入阶段 7 候选，不在阶段 6 扩大范围。

范围：

- 通过 Claude Code MCP 调用 `run_pdf_auto`。
- 使用真实 PDF 样本跑完整流程。
- 验证 `passed`、`needs_review`、`failed` 三类返回路径。
- 固化 MCP server 使用文档和排障清单。
- 收集阶段 7 候选问题。

非目标：

- 不新增拆分式 MCP 工具。
- 不实现批量 PDF 队列。
- 不引入 OCR/VLM 验证策略。
- 不改写 `pdf-auto` 的核心调度逻辑，除非阶段 6 验收发现必须修复的缺陷。

进入条件：

- 阶段 5 已完成。
- `mcp/server/` 中已有 Node.js / TypeScript MCP server。
- `run_pdf_auto` 已能调用 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`。
- MCP 对外状态映射已实现：`passed`、`needs_review`、`failed`。

Step 0 证据：

- 一个已知可通过的真实 PDF 样本及其分段目录。
- 一个可触发 `needs_review` 的样本或最小模拟。
- 一个可触发 `failed` 的最小失败样例，例如不存在的 PDF 路径或非法分段目录。
- 当前 Claude Code MCP 配置方式截图或文本记录。

默认决策：

- 真实样本优先复用阶段 3 使用过的 191 页说明书样本。
- `failed` 路径默认使用不存在的 PDF 路径或不存在的分段目录模拟。
- `needs_review` 路径优先复用已知低覆盖率分段；如果真实样本不稳定，则使用最小模拟输出验证 MCP 状态映射。
- 运行手册写入 [MCP 接入设计](../../mcp/README.md)，完成证据写入 [PLAN_MAP](../PLAN_MAP.md) 和本计划。

实施任务：

1. 记录 MCP server 安装、构建、启动命令。
2. 记录 Claude Code MCP 配置示例。
3. 用真实 PDF 调用 `run_pdf_auto`，保存返回 JSON 和输出文件路径。
4. 验证 `passed` 路径：合并文件存在，`review_markdown` 为空。
5. 验证 `needs_review` 路径：合并文件存在，`review_markdown` 存在。
6. 验证 `failed` 路径：错误可读，stderr 或诊断信息可定位问题。
7. 更新 [MCP 接入设计](../../mcp/README.md) 的运行手册和排障表。
8. 更新 [PLAN_MAP](../PLAN_MAP.md) 和本计划完成证据。
9. 运行 `python3 scripts/check_plan_governance.py .`。

完成条件：

- Claude Code 能通过 MCP 调用 `run_pdf_auto` 跑通至少一个真实样本。
- 三类返回状态都有验证证据或最小模拟。
- MCP 使用手册足够让后续会话按步骤复现。
- 阶段 7 候选项已整理，不在阶段 6 扩大范围。
- 计划治理检查通过。

阶段 7 候选：

- 拆分式 MCP 工具。
- 无文本层 PDF 验证策略。
- OCR/VLM 辅助验收。
- 批量处理和任务队列。
- 更结构化的 review 报告。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 无文本层 PDF 如何验证 | 后续增加 OCR/VLM 对照验证策略 | 否 | 已延后 |
| 可疑段重跑覆盖原目录还是写入 `rerun-high/` | 写入独立 `-rerun/` 目录，合并前覆盖原始 .md | 否 | 已确认 |
| `pdf-auto` 暂无 JSON summary | 阶段 4 优先补 `PDF_AUTO_JSON=1`，再实现 MCP server | 否 | 已完成 |
| MCP server 尚未实现 | 阶段 5 已实现，`mcp/server/` 项目已就绪 | 否 | 已解决 |

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
