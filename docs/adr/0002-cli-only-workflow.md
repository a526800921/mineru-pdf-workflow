# ADR 0002：CLI-only 工作流，移除 MCP Server

## 状态

已接受

## 背景

项目已经验证过本地 MCP Server，但当前实际能力由 `scripts/` 下的 CLI 提供。MCP 适配层重复维护参数校验、子进程调用、状态映射和 Node.js 依赖，却没有被 CLI 流程依赖。

## 决策

项目当前只维护 CLI 入口：

- PDF 主流程使用 `scripts/pdf-auto`。
- 分段、验证、重跑、合并、按页读取、内容搜索和 chunks 导出使用对应的 `scripts/*` 命令。
- 需要机器可读结果时使用 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>` 或各 CLI 自身的 JSON 模式。
- 删除 `.mcp.json` 和 `mcp/server/`，不提供本地 MCP Server。

## 后果

优点：

- 运行时依赖更少，不需要 Node.js MCP SDK 和单独构建步骤。
- CLI、脚本测试和人工排障共用同一条执行路径。
- 不再维护 MCP 工具名、协议版本和 CLI 状态映射两套契约。

代价：

- Claude Code 不再通过 MCP 工具自动发现本项目能力，需要执行 CLI 命令。
- 原 `run_pdf_auto` 等 MCP 工具名不再提供兼容入口。

## 相关文档

- [CLI-only 工作流迁移计划](../plans/cli-only-migration.md)
- [ADR 0001：先 CLI 固化，再 MCP 接入（已替代）](0001-cli-first-mcp-ready.md)
