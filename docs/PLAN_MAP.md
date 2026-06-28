# PLAN_MAP

## 治理范围

本文件只跟踪跨阶段、依赖真实运行反馈、会被后续 MCP 接入复用的计划。普通一次性任务不加入这里。

## 文档事实源职责

- 本文件是计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据链接的事实源。
- 专项计划 `docs/plans/*.md` 是实施细节事实源，记录字段方案、Schema、枚举、Step 0 证据、验证方式、完成条件、风险、回滚和未决问题。
- 总路线图、优先级计划和索引只保留顺序、状态摘要和专项计划链接；字段级方案、枚举、Step 0 细节或完成定义必须链接到专项计划。
- 专项计划状态、字段方案、完成条件或验证结果变化时，必须同步本文件和所有引用该计划的路线图、优先级计划或索引。
- 验收治理文档时必须用 `rg` 搜索同名计划、P 编号、状态名和关键字段，检查重复定义或漂移。

## 计划索引

| 计划 | 状态 | 当前阶段 | 依赖 | 证据 |
|---|---|---|---|---|
| [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | 待实施 | 阶段 7（候选） | MinerU CLI、PDF 文本层、分段输出目录、JSON 验证报告、`pdf-auto` 闭环脚本、`PDF_AUTO_JSON=1` | [完成证据](plans/automated-pdf-pipeline.md#阶段-6-完成证据) |
| [minimal-automation-runbook](plans/minimal-automation-runbook.md) | 已完成 | 最小人工执行版 | automated-pdf-pipeline | [Step 0 证据](plans/minimal-automation-runbook.md#step-0-证据)、[验证方式](plans/minimal-automation-runbook.md#验证方式) |

允许状态：`候选`、`设计中`、`待实施`、`实施中`、`已完成`、`已替代`、`已合并`、`已废弃`。

## 推荐顺序

1. `automated-pdf-pipeline`
2. `minimal-automation-runbook`

## 依赖关系

| 计划 | 依赖 | 原因 |
|---|---|---|
| automated-pdf-pipeline | MinerU CLI | 实际解析由 MinerU 执行 |
| automated-pdf-pipeline | PDF 文本层 | 当前验证策略依赖原 PDF 文本抽取 |
| minimal-automation-runbook | automated-pdf-pipeline | 执行手册描述流水线当前可用子集 |

## 替代、合并和废弃

| 计划 | 关系 | 目标 | 原因 |
|---|---|---|---|
| [superpowers pdf-auto 实施计划](superpowers/plans/2026-06-27-pdf-auto-plan.md) | 已合并 | [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | superpowers 进度 3 已完成，阶段 3 证据和后续阶段边界已同步到正式治理计划 |
| [superpowers pdf-auto JSON 模式实施计划](superpowers/plans/2026-06-28-pdf-auto-json-mode-plan.md) | 已合并 | [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | JSON 模式实施记录已并入阶段 4、阶段 5 事实源 |

## 当前阻塞项

| 问题 | 推荐方案 | 影响范围 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|---|
| `pdf-validate` 暂未输出 JSON | 已实现 `PDF_VALIDATE_JSON=1` | MCP 自动调度重跑前需要机器可读报告 | 否 | 已解决 |
| MCP server 尚未实现 | 已实现 `mcp/server/`，运行手册和排障清单已就绪 | Claude Code 现已可通过 MCP 调用 PDF 流水线 | 否 | 已解决 |
| 阶段 6 验收未执行 | 已完成三类路径验证和手册固化 | 运行手册可被后续会话按步骤复现 | 否 | 已解决 |

## 完成证据

| 计划 | 阶段 | 证据 |
|---|---|---|
| automated-pdf-pipeline | 阶段 1-6 | 详见 [自动化 PDF 解析流水线计划](plans/automated-pdf-pipeline.md#阶段-6-完成证据) |
| minimal-automation-runbook | 最小人工执行版 | 详见 [最小自动化执行手册](plans/minimal-automation-runbook.md#step-0-证据) |
