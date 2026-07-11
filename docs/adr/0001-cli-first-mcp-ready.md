# ADR 0001：先 CLI 固化，再 MCP 接入

## 状态

已替代

> MCP 接入决策已由 [ADR 0002：CLI-only 工作流，移除 MCP Server](0002-cli-only-workflow.md) 替代。本文件保留历史背景和当时的 CLI-first 设计记录。

## 背景

当前 MinerU 能通过本地 CLI 跑通 PDF 解析。用户希望后续能通过 Claude Code 使用自动化能力，并考虑 MCP 接入。

直接先做 MCP 会把调试面扩大到：

- MinerU CLI
- 分段调度
- 验证阈值
- MCP 协议
- Claude Code 工具调用

这不利于定位问题。

## 决策

先把能力固化为稳定 CLI：

- `pdf`
- `pdf-seg`
- `pdf-validate`
- `pdf-merge`
- `pdf-auto`

后续 MCP 只包装这些稳定 CLI 或复用其内部逻辑。

## 后果

优点：

- 本地命令行可直接用。
- MCP 接入边界清晰。
- Claude Code 不需要拼复杂 shell 命令。

代价：

- 早期自动化还不是一个完整 MCP 服务。
- MCP 第一版需要等待 CLI JSON 契约稳定后再封装。

## MCP 工具边界

MCP 服务不直接解释 PDF 内容，只负责流程编排和报告返回。

第一版只暴露一个高层工具，包装已经稳定的 `scripts/pdf-auto`：

```text
run_pdf_auto(pdf_path, segments_dir, threshold?, rerun_effort?, merge_output?)
```

以下拆分式工具保留为后续扩展：

```text
parse_pdf_segmented(pdf_path, segment_size, backend, effort)
validate_segments(pdf_path, segments_dir, threshold)
rerun_segments(pdf_path, segments, effort)
merge_segments(segments_dir)
```

人工语义判断仍交给 Claude Code 或用户。
