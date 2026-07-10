# 计划：自动化 PDF 解析流水线

## 背景

长 PDF 使用 MinerU 单次全量解析时，macOS 上的 PyTorch/MPS 缓存和 MinerU 中间结果会让内存持续增长。分段解析可以让每段结束后释放进程缓存，内存更稳定。

用户还需要减少人工逐页验证成本，因此需要建立“分段解析、自动验证、问题段重跑、再验证、人工兜底”的闭环，并为后续 Claude Code/MCP 接入保留清晰工具边界。

## 事实源职责

本文档是 `automated-pdf-pipeline` 的实施细节事实源，记录目标、范围、公共契约、阶段路线图、Step 0/完成证据、验证方式、风险、回滚和未决问题。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。历史 superpowers 计划和规格只作为归档实施记录，不作为当前字段级方案或完成定义事实源。

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
- `docs/plans/pdf-output-package-layout.md`
- `docs/plans/coverage-validation-optimization.md`
- `docs/plans/minimal-automation-runbook.md`
- `mcp/README.md`
- `docs/adr/0001-cli-first-mcp-ready.md`

## 公共契约变化

当前阶段的 CLI 契约：

- `scripts/pdf <pdf>`：单次解析，输出 `<文件名>-mineru-output/`。
- `scripts/pdf-seg <pdf>`：分段解析，默认输出 `<package>/segments/p0000-0000/` 等分段目录，同时生成 `manifest.json` 和 `images/`、`data/` 占位目录。
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
| 阶段 6 | MCP 端到端验收与运行手册固化 | 阶段 5 已完成 | Claude Code 通过 MCP 跑通真实样本并覆盖主要返回路径 | 已完成 |
| 阶段 7 | 覆盖率验证口径优化 | 阶段 6 已完成，存在无效 high 重跑样本 | 区分可重跑问题和仅需人工复核问题 | 已完成 |
| 阶段 8 | PDF 输出包目录结构 | 阶段 7 已完成，需要统一后续 V2 和入库草案目录 | 输出包结构、manifest 和默认路径稳定 | 已完成 |

## 当前阶段

阶段 7 已完成（2026-06-28）。阶段 8 已完成（2026-06-30），专项计划为 [PDF 输出包目录结构](pdf-output-package-layout.md)。

阶段 8 核心成果：
- 输出包根目录 = `dirname(pdf_path)`，所有产物统一在 `<package>/` 下。
- `pdf-seg` 生成 `manifest.json`、`images/`、`data/`、`segments/`。
- `pdf-merge` 默认输出 `<package>/<package名>.md`。
- `pdf-auto` 默认输出 `<package>/<pdf_stem>.md` + `<package>/review.md`。
- `PDF_MERGE_OUTPUT` / `PDF_AUTO_MERGE_OUTPUT` 兼容保留。
- `needs_review` 首次验证分支 bug 已修复。
- MinerU 环境兼容：隔离 venv（`~/Documents/models/.venv`）解决 transformers 5.x 不兼容问题。
- 验收证据见 [PDF 输出包目录结构计划验收记录](pdf-output-package-layout.md#验收记录2026-06-30)。

阶段 7 专项计划为 [覆盖率验证口径优化](coverage-validation-optimization.md)。主要成果：
- `pdf-validate` 新增 `page_type`、`decision`、`rerunnable`、`reason`、`page_type_summary` 字段
- `pdf-auto` 改为只重跑 `rerunnable == true` 的段
- demo20 样本无效 high 重跑从 9 降为 0
- 验收证据见 [覆盖率验证口径优化验收记录](coverage-validation-optimization.md#验收记录2026-06-28)

## 完成证据

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
- CLI 状态映射：`all_passed` → `passed`，`needs_review` → `needs_review`，`error`/调用失败 → `failed`。
- 子进程使用白名单环境变量（`PDF_AUTO_JSON=1`、`PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT`、`PDF_AUTO_MERGE_OUTPUT`），无其他 env 注入。
- 项目根通过源文件位置推导（`__dirname` → 上溯 3 层），确保从任意 cwd 启动都能找到 `scripts/pdf-auto`。
- MCP 协议验证通过：`initialize` 和 `tools/list` 响应正确，`run_pdf_auto` 工具含完整 inputSchema。
- TypeScript 编译通过，产物位于 `mcp/server/dist/`。



### 阶段 6 完成证据

- MCP 三类返回路径全部验证通过：
  - `passed`：demo20.pdf + threshold=0.5，覆盖率 0.77 > 0.5 → 直接合并 → merged.md (15K/261 行)
  - `needs_review`：demo20.pdf + threshold=0.82，覆盖率 0.77 < 0.82 → 子段拆分重跑 → 仍可疑 → merged.md + review.md
  - `failed`：不存在 /nonexistent/fake.pdf → 校验失败 → stderr 提示文件不存在
- `mcp/README.md` 已更新运行手册：安装/构建/配置/调用/状态说明/排障清单。
- 项目根 `.mcp.json` 已配置，Claude Code 可自动发现 MCP server。
- 阶段 7 候选事项已整理（拆分式工具、无文本层 PDF、OCR/VLM、批量处理）。
- 计划治理检查通过。

### 阶段 7 设计入口

阶段 7 聚焦覆盖率验证口径，不改变 MCP 第一版工具边界。事实源见 [覆盖率验证口径优化计划](coverage-validation-optimization.md)。

阶段 7 的核心方向：

- 将低覆盖问题区分为 `rerun` 和 `review_only`。
- 只对可能被 high 重跑修复的文本页低覆盖触发重跑。
- 目录页、图片稀疏页和初期表格页优先进入人工复核清单。
- 保持 `PDF_VALIDATE_JSON=1` 与 `PDF_AUTO_JSON=1` 向后兼容。

### 阶段 7 完成证据

详见 [覆盖率验证口径优化验收记录](coverage-validation-optimization.md#验收记录2026-06-28)。

### 阶段 8 设计入口

阶段 8 聚焦输出包目录结构，事实源见 [PDF 输出包目录结构计划](pdf-output-package-layout.md)。

阶段 8 的核心方向：

- 默认输出从旧的 `<stem>-output/segments` 收敛到 `<stem>/segments`。
- 合并 Markdown 默认写入 `<stem>/<stem>.md`，等价于旧 `merged.md`。
- review 默认写入 `<stem>/review.md`。
- 输出包保留 `images/`、`data/` 和 `manifest.json`，供后续 V2 图文浏览和入库草案使用。

阶段 8 的拟议契约、Step 0 证据、验证方式和完成条件见 [PDF 输出包目录结构计划](pdf-output-package-layout.md)。

### 阶段 8 复验记录

2026-06-30 验收完整记录见 [PDF 输出包目录结构计划验收记录](pdf-output-package-layout.md#验收记录2026-06-30)。

已验证要点：

- demo5.pdf（5 页）真实样本全部路径验证通过：`all_passed`（合并 Markdown 149 行）和 `needs_review`（review.md）两条路径。
- 输出包 `<package>/` 结构完整生成，manifest.json / images/ / data/ / segments/ / review.md / 合并 Markdown 均在正确位置。
- `review_only` 误触发合并 bug 已修复，环境兼容通过隔离 venv 解决。
- 静态检查、治理检查、MCP 编译全部通过。

最终验收结论（2026-06-30）：

- `pdf-seg` 和 `pdf-auto` 的 `_api_arg[@]` 空数组 `set -u` 兼容问题已修复：改用 `if/else` 分支。
- demo5.pdf（5 页）无 API 临时服务路径验收通过，退出码 `0`。
- `all_passed`（阈值 0.4）→ `demo5.md`（149 行）；`needs_review`（阈值 0.82）→ `review.md`，两条 MCP 路径均正常。
- 阶段 8 状态更新为 **已完成**。

## 验证方式

```bash
bash -n scripts/pdf-seg && bash -n scripts/pdf-merge && bash -n scripts/pdf-auto
cd mcp/server && npm run build
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
MINERU_SEGMENT_SIZE=5 scripts/pdf-seg pdf/demo5/demo5.pdf
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 无文本层 PDF 如何验证 | 后续增加 OCR/VLM 对照验证策略 | 否 | 已延后 |
| 覆盖率低页面触发无效 high 重跑 | 阶段 7 区分 `rerun` 与 `review_only`，只重跑可修复段 | 否 | 设计中 |
| 输出产物分散在旧目录 | 阶段 8 已完成：统一为 `<package>/` 输出包结构，demo5 真实样本验收通过 | 否 | 已解决 |
| 真实样本 `pdf-seg` 环境依赖未满足 | 已通过隔离 venv 解决 transformers 版本兼容问题，demo5 真实样本验收通过 | 否 | 已解决 |
| 可疑段重跑覆盖原目录还是写入 `rerun-high/` | 写入独立 `-rerun/` 目录，合并前覆盖原始 .md | 否 | 已确认 |
| `pdf-auto` 暂无 JSON summary | 阶段 4 优先补 `PDF_AUTO_JSON=1`，再实现 MCP server | 否 | 已完成 |
| MCP server 尚未实现 | 阶段 5 已实现，`mcp/server/` 项目已就绪 | 否 | 已解决 |
| `pdf-auto` 重跑分支在 `set -e` 下可能无法进入失败兜底 | 将 `mineru` 重跑调用改为 `if mineru ...; then ... else ... fi` 或局部关闭 `errexit` 后读取退出码，并补一个模拟 `mineru` 非 0 的回归验证 | 否 | 已记录 |

## 风险和回滚

风险：

- PDF 无文本层时，覆盖率验证失效。
- `high` 不一定修复所有单字符错误。
- MinerU 中间输出结构可能随版本变化。
- 分段合并可能在跨页表格、跨页段落处产生断裂。
- 页面类型分类如果过于激进，可能把真实解析缺失误归为人工复核问题。
- `pdf-auto` 重跑分支当前在 `set -e` 下直接执行 `mineru` 后再读取 `$?`。如果 `mineru` 返回非 0，脚本可能在记录失败、保留原始结果和生成兜底清单前直接退出；后续修复应补充失败路径回归验证。

回滚：

- 保留原始 PDF。
- 每段输出独立保存，可以删除单个分段后重跑。
- 合并文件可重新生成，不作为唯一源数据。
- JSON 输出开关必须不影响默认人类可读输出。
- 阶段 7 必须保留旧 JSON 字段语义，新增字段采用向后兼容方式。

## 关联 ADR、迁移、spec 或 issue

- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)
- [MCP 接入设计](../../mcp/README.md)
- [superpowers pdf-auto 实施记录](../superpowers/plans/2026-06-27-pdf-auto-plan.md)
- [superpowers pdf-auto JSON 模式实施记录](../superpowers/plans/2026-06-28-pdf-auto-json-mode-plan.md)
