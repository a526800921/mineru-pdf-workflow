# CLI-only 工作流迁移计划

## 状态

已完成

## 目标

移除本项目的 MCP Server 适配层，统一使用 `scripts/` 下的 CLI 工作流。保留现有 PDF 解析、验证、重跑、合并、结构化抽取和 JSON 输出能力，不改变 CLI 的参数、退出码或 JSON 字段契约。

## 范围

- 删除项目根 `.mcp.json`，不再让 Claude Code 自动发现本项目 MCP Server。
- 删除 `mcp/server/` 的 TypeScript Server、依赖声明和编译产物。
- 将 README、项目级 `pdf2md` skill 和用户级同步 skill 改为 CLI-only 说明。
- 更新项目 `AGENTS.md` 中已过时的 MCP 第一版边界，避免协作规则与当前架构漂移。
- 保留 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`，作为机器调用和后续自动化的稳定入口。
- 保留 `mcp/README.md` 作为历史迁移说明，明确 MCP Server 已移除，不再作为运行手册或契约事实源。
- 新增 ADR 记录 CLI-only 决策，并将 ADR 0001 标记为已替代。

## 非目标

- 不修改 `scripts/pdf`、`scripts/pdf-seg`、`scripts/pdf-validate`、`scripts/pdf-auto`、`scripts/pdf-rerun`、`scripts/pdf-merge` 及其他 CLI 的业务逻辑。
- 不删除 CLI 的 JSON 输出模式、输出包结构、ModelPad 服务编排或结构化数据流程。
- 不安装依赖、不引入新的运行时服务。

## Step 0 证据（2026-07-11）

当前 MCP 与 CLI 基线已固定：

- MCP 侧存在 `.mcp.json`、`mcp/server/src/index.ts` 和 `mcp/server/dist/index.js`。
- 对编译产物发送 `initialize` 和 `tools/list` 请求成功，Server 返回 `mineru-pdf-workflow`，版本 `1.0.0`，当前注册 9 个工具。
- CLI `scripts/pdf-auto --help` 可运行，明确支持 `PDF_AUTO_JSON=1`；`bash -n` 对核心 CLI 脚本全部通过。
- GitNexus 影响分析：`main` 上游风险 `LOW`，直接依赖仅为入口文件；`runPdfAuto` 上游风险 `LOW`，仅影响同一 MCP 入口的 `main → RunScript` 流程，未发现 CLI 业务脚本依赖。

## 迁移步骤

1. 更新治理文档、ADR、README 和 `pdf2md` skill，明确 CLI-only 契约。
2. 删除 MCP 配置、Server 源码、依赖和编译产物；把原 MCP README 改为历史说明。
3. 同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。
4. 运行 CLI 语法检查、现有脚本回归、治理检查和残留引用检查。

## 验证方式

```bash
bash -n scripts/pdf scripts/pdf-seg scripts/pdf-validate scripts/pdf-merge \
  scripts/pdf-auto scripts/pdf-rerun scripts/pdf-review \
  scripts/pdf-read-page scripts/pdf-search-content scripts/pdf-export-chunks
bash scripts/test-phase1.sh
bash scripts/test-phase2.sh
python3 scripts/check_plan_governance.py .
rg -n -i 'mcp/server|\.mcp\.json|run_pdf_auto|MCP server' README.md skills docs/PLAN_MAP.md docs/plans docs/adr mcp
```

验收时允许历史记录中出现 MCP 术语，但不得再有可运行配置、Server 源码、构建命令或“当前可通过 MCP 调用”的说明。

## 完成条件

- `.mcp.json` 和 `mcp/server/` 不存在。
- `scripts/` CLI 入口和 `PDF_AUTO_JSON=1` 机器接口可用。
- README、治理文档、ADR、项目级和用户级 skill 对当前入口的描述一致。
- CLI 回归、治理检查和 `git diff --check` 通过。

## 完成证据（2026-07-11）

- `.mcp.json`、`mcp/server/`、Node.js 依赖和编译产物已删除。
- 项目级 `skills/pdf2md/SKILL.md` 已同步到 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`，两者 `cmp` 一致。
- CLI 语法检查通过：`CLI_SYNTAX_OK`。
- `bash scripts/test-phase1.sh`：10/10 通过。
- `bash scripts/test-phase2.sh`：38/38 通过。
- `python3 scripts/check_plan_governance.py .`：计划治理检查通过。
- `git diff --check`：通过。
- 最终检查确认 MCP 运行资产不存在；残留 MCP 文字仅位于 ADR、迁移计划和历史记录中。

## 风险与回滚

风险：依赖旧 MCP 配置的本地 Claude Code 会失去自动发现；MCP 工具名不再提供兼容入口。

回滚：恢复 `.mcp.json`、`mcp/server/` 及原运行手册即可恢复旧适配层；CLI 输出和解析产物不需要回滚。

## 未决问题

| 问题 | 处理 | 状态 |
|---|---|---|
| 是否保留 MCP 历史设计文档 | 保留 `mcp/README.md` 作为迁移记录，不再承载当前契约 | 已确认 |
| 是否继续维护 MCP 工具兼容层 | 不维护；如未来需要，另立迁移计划和 ADR | 已确认 |
