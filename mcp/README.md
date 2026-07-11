# MCP 接入历史记录

本目录曾保存本项目的本地 MCP Server 设计、运行手册和工具契约。

自 2026-07-11 起，项目采用 CLI-only 架构：

- 已移除 `.mcp.json`、`mcp/server/` 及其 Node.js 依赖和编译产物。
- 当前唯一支持的运行入口是 `scripts/` 下的 CLI。
- 自动化流程使用 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>` 获取机器可读结果。
- 本文件只保留历史路径说明，不是当前 MCP 契约或运行手册。

当前决策见 [ADR 0002：CLI-only 工作流，移除 MCP Server](../docs/adr/0002-cli-only-workflow.md)，迁移过程见 [CLI-only 工作流迁移计划](../docs/plans/cli-only-migration.md)。
