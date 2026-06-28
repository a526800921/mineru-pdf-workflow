# MCP 接入设计

本目录用于后续把 MinerU PDF 工作流接入 Claude Code。

## 接入策略

优先实现一个本地 MCP server，封装项目内脚本，而不是让 Claude Code 直接拼接复杂 shell 命令。

推荐分两步：

1. 先让 CLI 输出稳定的机器可读 JSON。
2. 再实现 MCP server，把 JSON 作为工具返回值。

## 第一版工具契约

第一版只暴露一个高层工具，包装当前已经稳定的 `scripts/pdf-auto` 闭环。拆分式工具保留为后续扩展，避免 MCP 第一版重复实现 CLI 编排逻辑。

## 第一版实现标准

- 技术栈使用 Node.js / TypeScript。
- 代码放在 `mcp/server/`。
- 只实现 `run_pdf_auto`，不实现 `parse_pdf_segmented`、`validate_segments`、`rerun_segments`、`merge_segments`、`create_review_report`。
- 工具内部调用 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`。
- stdout JSON 是状态判断的唯一事实来源；stderr 只作为诊断日志返回或记录。
- 不解析中文日志决定状态，不在 MCP 层重新实现验证、重跑、合并调度逻辑。
- CLI 状态映射为 MCP 对外状态：`all_passed` -> `passed`，`merged_with_issues` -> `needs_review`，`error` 或调用失败 -> `failed`。

### `run_pdf_auto`

输入：

```json
{
  "pdf_path": "/abs/path/manual.pdf",
  "segments_dir": "/abs/path/manual-mineru-segments",
  "threshold": 0.82,
  "rerun_effort": "high",
  "merge_output": "/abs/path/manual-merged.md"
}
```

字段说明：

- `pdf_path`：必填，绝对路径，必须指向存在的 `.pdf` 文件。
- `segments_dir`：必填，绝对路径，必须指向已存在的分段目录。
- `threshold`：可选，映射到 `PDF_VALIDATE_THRESHOLD`。
- `rerun_effort`：可选，映射到 `MINERU_RERUN_EFFORT`。
- `merge_output`：可选，映射到 `PDF_AUTO_MERGE_OUTPUT`。

输出：

```json
{
  "status": "passed",
  "exit_code": 0,
  "merged_markdown": "/abs/path/manual-merged.md",
  "review_markdown": null,
  "stdout": "...",
  "stderr": "..."
}
```

`status` 取值：

- `passed`：`pdf-auto` 退出码为 0，合并完成且无人工兜底项。
- `needs_review`：`pdf-auto` 退出码为 2，合并完成但生成人工兜底清单。
- `failed`：`pdf-auto` 退出码为 1 或调用前校验失败。

失败模式：

- PDF 不存在或不是 `.pdf` 文件。
- 分段目录不存在，或缺少 `pXXXX-YYYY` 分段目录。
- `scripts/pdf-auto` 返回脚本错误。
- `scripts/pdf-auto` 输出无法映射到预期合并文件或 review 文件。

## CLI JSON 决策

`scripts/pdf-auto` 已实现可选 JSON summary：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
```

CLI JSON 输出结构：

```json
{
  "status": "all_passed",
  "exit_code": 0,
  "merged_markdown": "/abs/path/manual-merged.md",
  "review_markdown": null,
  "rerun_segments": ["p0000-0019"]
}
```

JSON 模式应保留现有退出码语义：

- `0`：全部通过，合并完成。
- `1`：脚本自身错误。
- `2`：合并完成，但有段需要人工兜底。

CLI `status` 当前取值：

- `all_passed`：`pdf-auto` 退出码为 0，合并完成且无人工兜底项。
- `merged_with_issues`：`pdf-auto` 退出码为 2，合并完成但生成人工兜底清单。
- `error`：`pdf-auto` 退出码为 1，或调用前校验失败。

MCP server 第一版必须读取 stdout JSON 判断状态；stderr 只作为诊断日志返回或记录，不能依赖中文日志解析决定工具状态。MCP 对外返回可以把 CLI 状态映射为 `passed`、`needs_review`、`failed`。

## 阶段 6 验收与运行手册

阶段 6 在最小 MCP server 完成后执行，目标是用真实样本证明 `run_pdf_auto` 可被 Claude Code 稳定调用，并把运行流程固化为手册。

阶段 6 不需要额外产品或架构确认；真实样本路径、MCP 配置位置和具体运行输出在执行时作为验证证据记录。

验收范围：

- Claude Code 通过 MCP 调用 `run_pdf_auto`。
- 至少一个真实 PDF 样本跑完整流程。
- 覆盖 `passed`、`needs_review`、`failed` 三类返回路径。
- 记录安装、构建、启动、配置、调用和排障流程。

阶段 6 不扩展工具面，不新增拆分式 MCP 工具，不引入 OCR/VLM 验证策略，不在 MCP 层重写 `pdf-auto` 调度逻辑。

默认决策：

- 真实样本优先复用阶段 3 使用过的 191 页说明书样本。
- `failed` 路径默认使用不存在的 PDF 路径或不存在的分段目录模拟。
- `needs_review` 路径优先复用已知低覆盖率分段；如果真实样本不稳定，则使用最小模拟输出验证 MCP 状态映射。
- 阶段 6 发现的新能力需求进入后续阶段候选，不在本阶段扩大范围。

运行手册需要包含：

1. MCP server 安装和构建命令。
2. MCP server 启动命令。
3. Claude Code MCP 配置示例。
4. `run_pdf_auto` 调用示例。
5. `passed`、`needs_review`、`failed` 返回样例。
6. 常见失败模式和排障步骤。

完成阶段 6 时，需要把真实样本运行证据同步回 `docs/PLAN_MAP.md` 和 `docs/plans/automated-pdf-pipeline.md`。

## 后续扩展工具草案

以下工具暂不作为第一版 MCP 范围。后续如果需要细粒度编排，再从 `run_pdf_auto` 拆分。

### `parse_pdf_segmented`

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segment_size": 20,
  "backend": "hybrid-engine",
  "effort": "medium",
  "method": "auto",
  "lang": "ch"
}
```

输出：

```json
{
  "segments_dir": "/path/to/manual-mineru-segments",
  "segments": [
    {
      "name": "p0000-0019",
      "start_page": 0,
      "end_page": 19,
      "status": "done"
    }
  ]
}
```

失败模式：

- PDF 不存在。
- MinerU 退出码非 0。
- 分段目录缺少 Markdown。

### `validate_segments`

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segments_dir": "/path/to/manual-mineru-segments",
  "threshold": 0.82
}
```

输出：

```json
{
  "passed": false,
  "threshold": 0.82,
  "segments": [
    {
      "name": "p0000-0019",
      "start_page": 0,
      "end_page": 19,
      "coverage": 0.77,
      "status": "suspicious",
      "missing_tokens": [
        ["车", 19],
        ["置", 19]
      ],
      "markdown_path": "/path/to/manual-mineru-segments/p0000-0019/manual.md"
    },
    {
      "name": "p0100-0119",
      "start_page": 100,
      "end_page": 119,
      "coverage": null,
      "status": "skipped",
      "reason": "no_text_layer",
      "missing_tokens": [],
      "markdown_path": "/path/to/manual-mineru-segments/p0100-0119/manual.md"
    }
  ]
}
```

status 取值：
- `passed`：覆盖率 >= 阈值
- `suspicious`：覆盖率 < 阈值
- `skipped`：原 PDF 文本层为空，无法对比
- `failed`：缺少 Markdown 文件

`coverage` 在 skipped/failed 时为 `null`，`reason` 仅在 skipped/failed 时存在。

### `rerun_segments`

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segments": [
    {
      "start_page": 0,
      "end_page": 19
    }
  ],
  "effort": "high"
}
```

输出：

```json
{
  "rerun_segments": [
    {
      "name": "p0000-0019",
      "status": "done"
    }
  ]
}
```

### `merge_segments`

输入：

```json
{
  "segments_dir": "/path/to/manual-mineru-segments"
}
```

输出：

```json
{
  "merged_markdown": "/path/to/manual-merged.md"
}
```

### `create_review_report`

输入：

```json
{
  "validation_report": {},
  "merged_markdown": "/path/to/manual-merged.md"
}
```

输出：

```json
{
  "review_markdown": "/path/to/manual-review.md",
  "items": [
    {
      "segment": "p0000-0019",
      "reason": "coverage_below_threshold",
      "suggested_action": "人工核对目录和章节标题"
    }
  ]
}
```

## Claude Code 配置

MCP server 已实现，在 Claude Code 中添加：

```json
{
  "mcpServers": {
    "mineru-pdf-workflow": {
      "command": "node",
      "args": [
        "/Users/jafish/Documents/work/mineru-pdf-workflow/mcp/server/dist/index.js"
      ]
    }
  }
}
```

## 实现状态（阶段 5 已完成）

- `mcp/server/` Node.js / TypeScript 项目已就绪。
- 只暴露 `run_pdf_auto` 工具，符合第一版边界。
- 项目根通过源文件位置推导，无需在配置中指定 `cwd`。
- 子进程使用白名单环境变量，不注入任意 env。
- MCP 协议验证通过（`initialize`、`tools/list`）。
- 构建命令：`cd mcp/server && npm install && npm run build`。
- 本地验证：`npx @modelcontextprotocol/inspector node dist/index.js`。

## 实现前置条件（已满足）

- ✅ `scripts/pdf-validate` 已支持 JSON 输出。
- ✅ `scripts/pdf-auto` 已实现 `PDF_AUTO_JSON=1` JSON summary。
- `scripts/pdf-seg` 的只生成计划能力不属于第一版范围。
- `scripts/pdf-merge` JSON 输出不属于第一版范围。

## 安全边界

- MCP server 只允许访问用户显式传入的本地 PDF 和对应输出目录。
- 第一版只调用仓库内固定脚本：`scripts/pdf-auto`。
- 只接受绝对路径。
- 只允许设置白名单环境变量：`PDF_VALIDATE_THRESHOLD`、`MINERU_RERUN_EFFORT`、`PDF_AUTO_MERGE_OUTPUT`。
- 不删除原始 PDF。
- 重跑只覆盖对应分段输出，不改其他分段。
- 任何人工修订文件应输出为新文件，不覆盖 MinerU 原始结果。
