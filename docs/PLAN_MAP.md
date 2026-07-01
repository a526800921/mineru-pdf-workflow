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
| [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | 已完成 | 阶段 8：PDF 输出包目录结构 | MinerU CLI、PDF 文本层、分段输出目录、JSON 验证报告、`pdf-auto` 闭环脚本、`PDF_AUTO_JSON=1` | [阶段 8 完成证据](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| [pdf-output-package-layout](plans/pdf-output-package-layout.md) | 已完成 | 无/有 API 双路径验收通过，`_api_arg[@]` 修复 | automated-pdf-pipeline、coverage-validation-optimization | [验收记录](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| [coverage-validation-optimization](plans/coverage-validation-optimization.md) | 已完成 | 阶段 5：验证、治理收尾和运行说明同步 | automated-pdf-pipeline、demo20 或等价真实样本、`content_list_v2.json` | [验收记录](plans/coverage-validation-optimization.md#验收记录2026-06-28) |
| [minimal-automation-runbook](plans/minimal-automation-runbook.md) | 已完成 | 最小人工执行版 | automated-pdf-pipeline | [Step 0 证据](plans/minimal-automation-runbook.md#step-0-证据)、[验证方式](plans/minimal-automation-runbook.md#验证方式) |
| [marker-feature-absorption](plans/marker-feature-absorption.md) | 已完成 | 全阶段（0-4） | pdf-output-package-layout、automated-pdf-pipeline | [阶段 4 完成证据](plans/marker-feature-absorption.md#阶段-4-完成证据2026-06-30) |

允许状态：`候选`、`设计中`、`待实施`、`实施中`、`已完成`、`已替代`、`已合并`、`已废弃`。

## 推荐顺序

1. `automated-pdf-pipeline`
2. `pdf-output-package-layout`
3. `coverage-validation-optimization`
4. `marker-feature-absorption`
5. `minimal-automation-runbook`

## 依赖关系

| 计划 | 依赖 | 原因 |
|---|---|---|
| automated-pdf-pipeline | MinerU CLI | 实际解析由 MinerU 执行 |
| automated-pdf-pipeline | PDF 文本层 | 当前验证策略依赖原 PDF 文本抽取 |
| pdf-output-package-layout | automated-pdf-pipeline | 调整流水线默认输出路径和文件命名 |
| pdf-output-package-layout | coverage-validation-optimization | 沿用 `review_only`、TOC 修复和 review 生成结果 |
| coverage-validation-optimization | automated-pdf-pipeline | 作为自动化流水线阶段 7，优化验证和重跑策略 |
| coverage-validation-optimization | `content_list_v2.json` | 页面类型识别和结构化文本提取依赖 MinerU 中间结构 |
| marker-feature-absorption | pdf-output-package-layout | 段级汇总、进度输出和幂等验收基于输出包结构 |
| marker-feature-absorption | automated-pdf-pipeline | 变更集中在 `pdf-auto`，属于流水线主脚本 |
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
| 覆盖率低页面触发无效 high 重跑 | 已实现：区分 `rerun` 与 `review_only`，只重跑可修复段 | `pdf-validate`、`pdf-auto`、MCP 诊断输出 | 否 | 已解决 |
| 输出产物分散在旧目录 | 阶段 8 已完成：统一为 `<package>/` 输出包结构，demo5 无/有 API 双路径验收通过 | `pdf-seg`、`pdf-merge`、`pdf-auto`、MCP 返回路径 | 否 | 已解决 |
| 首次验证 `review_only` 段误触发合并（`pdf-auto` 行 230） | 已修复 Python 分支 + bash `needs_review` 处理分支，复验返回 `needs_review` 并生成 `<package>/review.md` | `pdf-auto` | 否 | 已解决 |
| 真实样本 `pdf-seg` 环境依赖未满足 | 根因 `transformers 5.x` 不兼容；已创建隔离 venv（`~/Documents/models/.venv`, `transformers 4.57.6`），scripts 自动检测优先使用 | Phase 8 端到端验收 | 否 | 已解决 |
| 未检测到 MinerU API 时 `pdf-seg` 因 `_api_arg[@]` 未绑定失败 | 已修复：`if/else` 分支替代空数组 `set -u` 展开，无 API 时自动启动临时服务 | Phase 8 端到端验收、无 API 服务启动路径 | 否 | 已解决 |

## 完成证据

| 计划 | 阶段 | 证据 |
|---|---|---|
| automated-pdf-pipeline | 阶段 1-7 | 详见 [自动化 PDF 解析流水线计划](plans/automated-pdf-pipeline.md#阶段-7-完成证据) |
| pdf-output-package-layout | Phase 8 复验 | 详见 [PDF 输出包目录结构计划验收记录](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| coverage-validation-optimization | 阶段 0-5 | 详见 [覆盖率验证口径优化计划](plans/coverage-validation-optimization.md#验收记录2026-06-28) |
| marker-feature-absorption | 阶段 0-4 | 详见 [marker 特性吸纳计划](plans/marker-feature-absorption.md#阶段-4-完成证据2026-06-30) |
| minimal-automation-runbook | 最小人工执行版 | 详见 [最小自动化执行手册](plans/minimal-automation-runbook.md#step-0-证据) |
