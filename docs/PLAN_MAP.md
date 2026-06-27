# PLAN_MAP

## 治理范围

本文件只跟踪跨阶段、依赖真实运行反馈、会被后续 MCP 接入复用的计划。普通一次性任务不加入这里。

## 计划索引

| 计划 | 状态 | 当前阶段 | 依赖 | 证据 |
|---|---|---|---|---|
| [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | 实施中 | 阶段 4：合并与人工兜底 | MinerU CLI、PDF 文本层、分段输出目录、JSON 验证报告 | 已在 191 页说明书上验证完整流水线（分段解析→自动重跑→再验证→合并） |
| [minimal-automation-runbook](plans/minimal-automation-runbook.md) | 已完成 | 最小人工执行版 | automated-pdf-pipeline | 脚本帮助命令和语法检查通过 |

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
| - | - | - | - |

## 当前阻塞项

| 问题 | 推荐方案 | 影响范围 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|---|
| `pdf-validate` 暂未输出 JSON | 已实现 `PDF_VALIDATE_JSON=1` | MCP 自动调度重跑前需要机器可读报告 | 否 | 已解决 |

## 完成证据

| 计划 | 阶段 | 证据 |
|---|---|---|
| automated-pdf-pipeline | 阶段 1：脚本固化 | `scripts/pdf`、`scripts/pdf-seg`、`scripts/pdf-merge`、`scripts/pdf-validate` 已复制到项目并通过语法检查 |
| automated-pdf-pipeline | 阶段 2：验证报告机器化 | `PDF_VALIDATE_JSON=1` 在 191 页说明书样本上输出有效 JSON，可疑段（p0000-0019，覆盖率 0.77）与人类可读输出一致，`mcp/README.md` 契约字段与脚本输出一致 |
| automated-pdf-pipeline | 阶段 3：自动重跑 | `scripts/pdf-auto` 实现完整验证→重跑→再验证→合并→兜底流水线，在 191 页摩托车说明书上测试通过，可疑段自动 high 精读重跑，二次验证后合并输出 merged.md |
| minimal-automation-runbook | 最小人工执行版 | 已记录解析、验证、合并、人工兜底流程，并通过计划治理检查 |
