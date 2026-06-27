# MCP 接入设计

本目录用于后续把 MinerU PDF 工作流接入 Claude Code。

## 接入策略

优先实现一个本地 MCP server，封装项目内脚本，而不是让 Claude Code 直接拼接复杂 shell 命令。

推荐分两步：

1. 先让 CLI 输出稳定的机器可读 JSON。
2. 再实现 MCP server，把 JSON 作为工具返回值。

## 工具契约草案

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

- `scripts/pdf-validate` 支持 JSON 输出。
- `scripts/pdf-seg` 支持只生成计划，不执行，方便 MCP 预览任务。
- `scripts/pdf-merge` 输出合并文件路径的 JSON。

## 安全边界

- MCP server 只允许访问用户显式传入的本地 PDF 和对应输出目录。
- 不删除原始 PDF。
- 重跑只覆盖对应分段输出，不改其他分段。
- 任何人工修订文件应输出为新文件，不覆盖 MinerU 原始结果。

