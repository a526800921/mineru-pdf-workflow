# MCP 接入设计

本目录用于后续把 MinerU PDF 工作流接入 Claude Code。

## 接入策略

优先实现一个本地 MCP server，封装项目内脚本，而不是让 Claude Code 直接拼接复杂 shell 命令。

推荐分两步：

1. 先让 CLI 输出稳定的机器可读 JSON。
2. 再实现 MCP server，把 JSON 作为工具返回值。

## 第一版工具契约

第一版只暴露一个高层工具，包装当前已经稳定的 `scripts/pdf-auto` 闭环。拆分式工具保留为后续扩展，避免 MCP 第一版重复实现 CLI 编排逻辑。

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

当前 `scripts/pdf-auto` 已有稳定退出码和输出文件约定，但没有机器可读 summary。MCP 可以先通过退出码和路径推导结果，但这会让 server 解析中文日志或重复推导默认路径。

推荐在实现 MCP server 前，先给 `scripts/pdf-auto` 增加可选 JSON summary：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
```

推荐输出：

```json
{
  "status": "passed",
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

## Claude Code 配置草案

后续实现 MCP server 后，可以在 Claude Code 配置中加入类似条目：

```json
{
  "mcpServers": {
    "mineru-pdf-workflow": {
      "command": "python",
      "args": [
        "/Users/jafish/Documents/work/mineru-pdf-workflow/mcp/server.py"
      ]
    }
  }
}
```

## 实现前置条件

- `scripts/pdf-validate` 已支持 JSON 输出。
- `scripts/pdf-auto` 增加 JSON summary，或 MCP server 明确使用退出码和文件路径推导结果。
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
