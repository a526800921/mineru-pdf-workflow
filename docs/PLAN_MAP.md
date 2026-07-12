# PLAN_MAP

## 治理范围

本文件只跟踪跨阶段、依赖真实运行反馈或影响公共 CLI 契约的计划。普通一次性任务不加入这里。

## 文档事实源职责

- 本文件是计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据链接的事实源。
- 专项计划 `docs/plans/*.md` 是实施细节事实源，记录字段方案、Schema、枚举、Step 0 证据、验证方式、完成条件、风险、回滚和未决问题。
- 总路线图、优先级计划和索引只保留顺序、状态摘要和专项计划链接；字段级方案、枚举、Step 0 细节或完成定义必须链接到专项计划。
- 专项计划状态、字段方案、完成条件或验证结果变化时，必须同步本文件和所有引用该计划的路线图、优先级计划或索引。
- 验收治理文档时必须用 `rg` 搜索同名计划、P 编号、状态名和关键字段，检查重复定义或漂移。
- 项目级 `pdf2md` skill 事实源为 `skills/pdf2md/SKILL.md`。涉及 PDF 解析流程、输出包结构、CLI JSON 契约、ModelPad PDF 服务编排、结构化数据/入库导出流程的更新，必须先更新该项目级 skill，再同步覆盖 Claude Code 用户级 skill：`/Users/jafish/.claude/skills/pdf2md/SKILL.md`；若当次无法同步，必须在相关计划的未决问题或风险中记录原因和补同步动作。

## 计划索引

| 计划 | 状态 | 当前阶段 | 最后更新 | 依赖 | 证据 |
|---|---|---|---|---|---|
| [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | 已完成 | 阶段 8：PDF 输出包目录结构 | 2026-06-30 | MinerU CLI、PDF 文本层、分段输出目录、JSON 验证报告、`pdf-auto` 闭环脚本、`PDF_AUTO_JSON=1` | [阶段 8 完成证据](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| [pdf-output-package-layout](plans/pdf-output-package-layout.md) | 已完成 | 无/有 API 双路径验收通过，`_api_arg[@]` 修复 | 2026-06-30 | automated-pdf-pipeline、coverage-validation-optimization | [验收记录](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| [modelpad-pdf-service-lifecycle](plans/modelpad-pdf-service-lifecycle.md) | 已完成 | 全阶段（0-3） | 2026-07-03 | ModelPad app、automated-pdf-pipeline、pdf-output-package-layout | [阶段 3 完成证据](plans/modelpad-pdf-service-lifecycle.md#阶段-3-完成证据2026-07-03) |
| [modelpad-pdf-service-orchestration](plans/modelpad-pdf-service-orchestration.md) | 已完成 | 全阶段（0-3） | 2026-07-04 | modelpad-pdf-service-lifecycle、ModelPad API、pdf 模型配置 | [阶段 3 完成证据](plans/modelpad-pdf-service-orchestration.md#阶段-3-完成证据2026-07-04) |
| [structured-data-extraction](plans/structured-data-extraction.md) | 已完成 | 全阶段（0-3） | 2026-07-02 | pdf-output-package-layout、coverage-validation-optimization、demo20 输出包 | [阶段 3 完成证据](plans/structured-data-extraction.md#阶段-3-完成证据2026-07-02) |
| [data-ingestion-pipeline](plans/data-ingestion-pipeline.md) | 已完成 | 阶段 3：实际入库接口或外部系统边界 | 2026-07-02 | structured-data-extraction、pdf-output-package-layout、demo20 数据草案 | [阶段 3 完成证据](plans/data-ingestion-pipeline.md#阶段-3-完成证据2026-07-02) |
| [conflict-context-ingestion-fix](plans/conflict-context-ingestion-fix.md) | 已完成 | 全阶段（0-3） | 2026-07-04 | structured-data-extraction、data-ingestion-pipeline、春风 150AURA 真实样本 | [阶段 3 完成证据](plans/conflict-context-ingestion-fix.md#阶段-3-完成证据2026-07-04) |
| [coverage-validation-optimization](plans/coverage-validation-optimization.md) | 已完成 | 阶段 5：验证、治理收尾和运行说明同步 | 2026-06-28 | automated-pdf-pipeline、demo20 或等价真实样本、`content_list_v2.json` | [验收记录](plans/coverage-validation-optimization.md#验收记录2026-06-28) |
| [minimal-automation-runbook](plans/minimal-automation-runbook.md) | 已完成 | 最小人工执行版 | 2026-06-30 | automated-pdf-pipeline | [Step 0 证据](plans/minimal-automation-runbook.md#step-0-证据)、[验证方式](plans/minimal-automation-runbook.md#验证方式) |
| [marker-feature-absorption](plans/marker-feature-absorption.md) | 已完成 | 全阶段（0-4） | 2026-06-30 | pdf-output-package-layout、automated-pdf-pipeline | [阶段 4 完成证据](plans/marker-feature-absorption.md#阶段-4-完成证据2026-06-30) |
| [modelpad-dynamic-env-cleanup](plans/modelpad-dynamic-env-cleanup.md) | 已完成 | 全阶段（0-4） | 2026-07-04 | modelpad-pdf-service-orchestration、ModelPad API | [阶段 4 完成证据](plans/modelpad-dynamic-env-cleanup.md#阶段-4-完成证据2026-07-04) |
| [pdf-workflow-enhancement-roadmap](plans/pdf-workflow-enhancement-roadmap.md) | 已完成 | P4 拆分至 pdf-evaluation-suite 全部完成，P1-P3b 已完成 | 2026-07-10 | 所有已完成计划、P3a 检索工具、春风 150AURA 输出包 | [P3b 完成](plans/pdf-workflow-enhancement-roadmap.md#完成条件) |
| [pdf-evaluation-suite](plans/pdf-evaluation-suite.md) | 已完成 | P4a/P4b/P4c 全部已完成 | 2026-07-10 | pdf-workflow-enhancement-roadmap、coverage-validation-optimization、春风 150AURA 输出包 | [P4a 验收](plans/pdf-evaluation-suite.md#验收记录2026-07-08)、[P4b 验收](plans/pdf-evaluation-suite.md#验收记录p4b2026-07-08)、[P4c 验收](plans/pdf-evaluation-suite.md#验收记录p4c2026-07-10)、[VLM 自动启停扩展](plans/local-vlm-autostart.md) |
| [local-vlm-autostart](plans/local-vlm-autostart.md) | 已完成 | 阶段 1：ModelPad 自动启停实现与验证（已完成） | 2026-07-11 | pdf-evaluation-suite P4c、ModelPad qwen3-vl-8b 配置 | [验证记录](plans/local-vlm-autostart.md)、[mock 测试 7/7](scripts/test-vlm-service.sh)、[真实服务三路径验收](plans/local-vlm-autostart.md#阶段-1-完成证据) |
| [per-page-anchors](plans/per-page-anchors.md) | 已完成 | 全阶段（0-4） | 2026-07-10 | automated-pdf-pipeline、pdf-output-package-layout、coverage-validation-optimization、structured-data-extraction、春风 150AURA 输出包 | [阶段 4 验收](plans/per-page-anchors.md#阶段-4-验收记录2026-07-10) |
| [pdf-auto-repair-before-merge](plans/pdf-auto-repair-before-merge.md) | 已完成 | 全阶段（0-3）：修复—合并顺序、manifest 泄漏修复、真实样本验收 | 2026-07-11 | automated-pdf-pipeline、pdf-output-package-layout、coverage-validation-optimization、per-page-anchors、demo5 真实样本 | [阶段 3 验收](plans/pdf-auto-repair-before-merge.md#阶段-3-验收记录2026-07-11) |
| [single-page-segmentation-migration](plans/single-page-segmentation-migration.md) | 已完成 | 阶段 4：收敛段级遗留复杂度（已完成） | 2026-07-11 | automated-pdf-pipeline、coverage-validation-optimization、pdf-auto-repair-before-merge、per-page-anchors、demo20 第 12 页 fallback 证据、demo20 端到端验收、test-phase3 45/45 通过 | [阶段 1 验收](plans/single-page-segmentation-migration.md#阶段-1-验收记录2026-07-11)、[阶段 2 再次验收](reports/single-page-segmentation-stage2-reacceptance-2026-07-11.md)、[阶段 3 实施契约](plans/single-page-segmentation-migration.md#阶段-3-实施契约确认2026-07-11)、[阶段 3 待实施契约](plans/single-page-segmentation-migration.md#阶段-3-待实施契约用户确认2026-07-11)、[阶段 3 最终验收](plans/single-page-segmentation-migration.md#最终验收2026-07-11)、[阶段 1 补充收尾验收](plans/single-page-segmentation-migration.md#阶段-1-补充收尾验收2026-07-11)、[阶段 4 子项实施证据](plans/single-page-segmentation-migration.md#阶段-4-逐页锚点收敛子项--实施证据2026-07-11)、[阶段 4 验收（第一次）](plans/single-page-segmentation-migration.md#阶段-4-验收2026-07-11)、[阶段 4 验收（第二次）](plans/single-page-segmentation-migration.md#阶段-4-验收2026-07-11第二次)、[demo20 端到端验收](docs/plans/single-page-segmentation-migration.md#端到端验收demo20-2026-07-11)、[阶段 3 修复证据](plans/single-page-segmentation-migration.md#修复验证同次会话2026-07-11) |
| [table-text-omission-detection](plans/table-text-omission-detection.md) | 已完成 | 阶段 4：整表头/顶部列头漏报补强（已完成） | 2026-07-11 | single-page-segmentation-migration 阶段 3、pdf-evaluation-suite P4b、PyMuPDF 原生文本层、demo20 p14/p16 真实样本 | [阶段 4 最终验收](plans/table-text-omission-detection.md#阶段-4-最终验收2026-07-11) |
| [toc-page-physical-attribution-fix](plans/toc-page-physical-attribution-fix.md) | 已完成 | 全阶段（0-3） | 2026-07-11 | coverage-validation-optimization、per-page-anchors、pdf-auto-repair-before-merge、demo20/demo5/demo60 真实样本、`pdf/demo20toc2/demo20toc2.pdf` p3/p4 多页目录归属样本 | [阶段 3 再次独立验收](plans/toc-page-physical-attribution-fix.md#阶段-3-再次独立验收2026-07-11) |
| [cli-only-migration](plans/cli-only-migration.md) | 已完成 | 阶段 1 已完成：移除 MCP 适配层 | 2026-07-11 | 已验证的 CLI 脚本、`PDF_AUTO_JSON=1` JSON 契约、ADR 0002 | [完成证据](plans/cli-only-migration.md#完成证据-2026-07-11) |
| [pdf2md-fix-manual-workflow](plans/pdf2md-fix-manual-workflow.md) | 已完成 | 全阶段（0-4） | 2026-07-12 | `pdf-output-package-layout`、`pdf-merge`、`pdf-auto`、`pdf-auto-repair-before-merge`、`review.md`、`pdf-evaluation-suite`、`local-vlm-autostart`、固定 `qwen3-vl-8b`（ModelPad 9999 / VLM 9005）、`table-text-omission-detection`、`structured-data-extraction`、`data-ingestion-pipeline`、`conflict-context-ingestion-fix`、demo20/demo60 8192 空列实测、p37/p47/p48 全局 replace 漂移复盘、demo20 p14-p16、VLM hash 与跨页证据修复、demo60 候选已登记、春风冲突样本、目录三件套输出契约补充 | [VLM 固定模型契约](plans/pdf2md-fix-manual-workflow.md#vlm-固定模型契约) |
| [pdf-merge-table-formatting](plans/pdf-merge-table-formatting.md) | 待实施 | 阶段 4：独立验收与收口 | 2026-07-12 | pdf2md-fix-manual-workflow、pdf-auto-repair-before-merge、per-page-anchors、春风250Sr 87 表、demo20 11 表、demo60 29 表真实临时副本、181 个全量 pytest、38/38 阶段2回归、三个包 check-fixes 与下游流程通过 | [阶段 3 验收](plans/pdf-merge-table-formatting.md#阶段-3-验收2026-07-12) |
| [pdf-table-audit](plans/pdf-table-audit.md) | 候选 | 阶段 0：审计范围与候选契约冻结 | 2026-07-12 | pdf2md-fix-manual-workflow、pdf-merge-table-formatting、pdf-output-package-layout、PyMuPDF、现有 `scripts/pdf-table-fix` | [Step 0 证据](plans/pdf-table-audit.md#背景与-step-0-证据) |
| [pdf-table-repair](plans/pdf-table-repair.md) | 候选 | 阶段 0：页级修复契约与最小样本冻结 | 2026-07-12 | pdf-table-audit、pdf2md-fix-manual-workflow、per-page-anchors、pdf-merge-table-formatting、PyMuPDF、固定 qwen3-vl-8b | [Step 0 证据](plans/pdf-table-repair.md#背景与-step-0-证据) |

允许状态：`候选`、`设计中`、`待实施`、`实施中`、`已完成`、`已替代`、`已合并`、`已废弃`。

## 推荐顺序

1. `automated-pdf-pipeline`
2. `pdf-output-package-layout`
3. `coverage-validation-optimization`
4. `modelpad-pdf-service-lifecycle`
5. `modelpad-pdf-service-orchestration`
6. `marker-feature-absorption`
7. `structured-data-extraction`
8. `data-ingestion-pipeline`
9. `conflict-context-ingestion-fix`
10. `minimal-automation-runbook`
11. `modelpad-dynamic-env-cleanup`
12. `pdf-workflow-enhancement-roadmap`
13. `pdf-evaluation-suite`（P4；P4a/P4b/P4c 全部已完成）
14. `per-page-anchors`（合并 md 逐页锚点；已完成）
15. `pdf-auto-repair-before-merge`（TOC 修复前置、`needs_review` 合并产物、manifest 泄漏修复；已完成）
16. `single-page-segmentation-migration`（单页默认、页级重跑与 fallback；阶段 2 已按单页新输出范围通过）
17. `table-text-omission-detection`（通用表格字段缺失检测与页级 fallback 触发）
18. `toc-page-physical-attribution-fix`（目录页物理归属与过度生成修复）
19. `local-vlm-autostart`（P4c 本地 VLM 自动启动、复用与完成后关闭）
20. `pdf2md-fix-manual-workflow`（pdf2md 完成后的人工复核、内容修复和逻辑表格契约）
21. `pdf-merge-table-formatting`（canonical Markdown 表格可读性格式化落地）
22. `pdf-table-audit`（表格异常候选审计与 pdf2md-fix skill 收敛）
23. `pdf-table-repair`（指定页表格候选重建、人工确认与安全应用）

## 依赖关系

| 计划 | 依赖 | 原因 |
|---|---|---|
| automated-pdf-pipeline | MinerU CLI | 实际解析由 MinerU 执行 |
| automated-pdf-pipeline | PDF 文本层 | 当前验证策略依赖原 PDF 文本抽取 |
| pdf-output-package-layout | automated-pdf-pipeline | 调整流水线默认输出路径和文件命名 |
| pdf-output-package-layout | coverage-validation-optimization | 沿用 `review_only`、TOC 修复和 review 生成结果 |
| coverage-validation-optimization | automated-pdf-pipeline | 作为自动化流水线阶段 7，优化验证和重跑策略 |
| coverage-validation-optimization | `content_list_v2.json` | 页面类型识别和结构化文本提取依赖 MinerU 中间结构 |
| modelpad-pdf-service-lifecycle | ModelPad app | PDF 服务生命周期由 `/Users/jafish/Documents/work/ModelPad` 托管 |
| modelpad-pdf-service-lifecycle | automated-pdf-pipeline | 收敛 `pdf-seg`、`pdf-auto`、`pdf-rerun` 的服务管理副作用 |
| modelpad-pdf-service-lifecycle | pdf-output-package-layout | 保持输出包目录结构不变，只调整服务和临时目录边界 |
| modelpad-pdf-service-orchestration | modelpad-pdf-service-lifecycle | 在已收敛副作用的脚本上增加显式 ModelPad API 启停编排 |
| modelpad-pdf-service-orchestration | ModelPad API | 调用 `POST /api/models/:id/start` 和 `POST /api/models/:id/stop` |
| modelpad-pdf-service-orchestration | pdf 模型配置 | 默认模型 id 为 `40621169-461C-4018-974E-9FAC92A542E7` |
| structured-data-extraction | pdf-output-package-layout | 结构化草案输出到 `<package>/data/`，复用稳定输出包结构 |
| structured-data-extraction | coverage-validation-optimization | 复用 `content_list_v2.json`、页面类型和质量判定经验 |
| structured-data-extraction | demo20 输出包 | 阶段 0/1 需要真实含图文和 content_list 的样本 |
| data-ingestion-pipeline | structured-data-extraction | 以 `quick_lookup_draft.csv`、`verification.csv` 和 `fixtures_result.md` 为输入边界 |
| data-ingestion-pipeline | pdf-output-package-layout | 入库候选仍位于 `<package>/data/`，复用输出包目录结构 |
| data-ingestion-pipeline | demo20 数据草案 | 阶段 0/1 使用真实草案样本验证字段和状态边界 |
| conflict-context-ingestion-fix | structured-data-extraction | 需要补齐 `quick_lookup_draft.csv` 的页段和表格上下文字段 |
| conflict-context-ingestion-fix | data-ingestion-pipeline | 需要修正 `pdf-prepare-ingest` 的冲突 identity 和放行门禁 |
| conflict-context-ingestion-fix | 春风 150AURA 真实样本 | 35 组冲突误报和 390 条 not_ready 记录是本计划的 Step 0 基线 |
| marker-feature-absorption | pdf-output-package-layout | 段级汇总、进度输出和幂等验收基于输出包结构 |
| marker-feature-absorption | automated-pdf-pipeline | 变更集中在 `pdf-auto`，属于流水线主脚本 |
| minimal-automation-runbook | automated-pdf-pipeline | 执行手册描述流水线当前可用子集 |
| modelpad-dynamic-env-cleanup | modelpad-pdf-service-orchestration | 在已有启停编排上增加动态 env 传递和临时输出目录自动清理 |
| modelpad-dynamic-env-cleanup | ModelPad API | start 请求体传入 `env` 覆盖，stop 后清理临时目录 |
| pdf-workflow-enhancement-roadmap | automated-pdf-pipeline | P2-P5 增强均基于现有流水线能力 |
| pdf-workflow-enhancement-roadmap | CLI 脚本和输出包契约 | P2/P3 的 MCP 记录仅作为历史证据，当前不再推进 MCP 适配层 |
| pdf-evaluation-suite | pdf-workflow-enhancement-roadmap | P4 从路线图拆分为独立评测套件专项计划 |
| pdf-evaluation-suite | coverage-validation-optimization | P4a TOC 条目字段方案（`toc_entries`/`toc_stats`）事实源 |
| pdf-evaluation-suite | 春风 150AURA 输出包 | P4b 表格结构自检以 content_list.json 的 115 个 table 元素（104 含 table_body）为 Step 0 样本 |
| pdf-evaluation-suite | fitz（pymupdf）整页渲染 | P4c 对 image_or_sparse 页整页渲染喂 VLM，复用现有依赖零新增 |
| per-page-anchors | automated-pdf-pipeline | 逐页锚点在 `pdf-merge` 生成阶段实现 |
| per-page-anchors | pdf-output-package-layout | 扩展合并 md 锚点格式（段级锚点保留，新增逐页锚点） |
| per-page-anchors | coverage-validation-optimization | TOC 段由 `toc_repair` 后处理，逐页锚点需识别并回退段级 |
| pdf-auto-repair-before-merge | automated-pdf-pipeline、pdf-output-package-layout、coverage-validation-optimization、per-page-anchors | 调整 `pdf-auto` 的 TOC 修复时序、`needs_review` 合并产物和逐页锚点兼容边界 |
| single-page-segmentation-migration | automated-pdf-pipeline、coverage-validation-optimization、pdf-auto-repair-before-merge、per-page-anchors | 将新解析、重跑、fallback 和合并的主操作单位从 10 页段收敛到单页；旧段级输出不纳入兼容范围 |
| table-text-omission-detection | single-page-segmentation-migration、pdf-evaluation-suite、PyMuPDF 原生文本层 | 在阶段 3 已有 fallback 闭环上补充通用表格字段遗漏检测，避免把业务字段写死在代码中 |
| toc-page-physical-attribution-fix | coverage-validation-optimization、per-page-anchors、pdf-auto-repair-before-merge、demo20 目录页真实样本 | 修复 MinerU 目录过度生成和 `toc_repair` 短标题子串错页，同时保留段级锚点消费者契约 |
| per-page-anchors | structured-data-extraction | 阶段 4 复用逐页锚点收窄 `page_start/page_end` |
| per-page-anchors | 春风 150AURA 输出包 | Step 0 保真度实测与 `content_list.json` `page_idx` 基线 |
| pdf2md-fix-manual-workflow | `pdf-auto`、`review.md`、`table-text-omission-detection`、`structured-data-extraction`、`data-ingestion-pipeline`、demo20 p14-p16 | 在自动解析、人工内容修复、结构化草案和入库审核之间建立独立的修复记录与逻辑表格边界 |
| pdf2md-fix-manual-workflow | `pdf-evaluation-suite`、`local-vlm-autostart` | 复用现有 VLM 评测和 ModelPad 自动启停能力，但只在人工复核阶段按需调用，不接入 `pdf-auto` 主链路 |
| pdf2md-fix-manual-workflow | pdf-output-package-layout | 复用输出包 `manifest.json`，将 Markdown、修复记录、逻辑表格和 hash 作为同步发布契约 |
| pdf2md-fix-manual-workflow | pdf-merge | 在 canonical Markdown 生成阶段完成 HTML 表格 pretty-print，避免额外的 `*-formatted.md` 入口 |
| pdf2md-fix-manual-workflow | pdf-auto-repair-before-merge | 复用现有 TOC 段级/合并级修复顺序，最终 manifest hash 必须覆盖所有 Markdown 后处理 |

## 替代、合并和废弃

| 计划 | 关系 | 目标 | 原因 |
|---|---|---|---|
| [superpowers pdf-auto 实施计划](superpowers/plans/2026-06-27-pdf-auto-plan.md) | 已合并 | [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | superpowers 进度 3 已完成，阶段 3 证据和后续阶段边界已同步到正式治理计划 |
| [superpowers pdf-auto JSON 模式实施计划](superpowers/plans/2026-06-28-pdf-auto-json-mode-plan.md) | 已合并 | [automated-pdf-pipeline](plans/automated-pdf-pipeline.md) | JSON 模式实施记录已并入阶段 4、阶段 5 事实源 |

## 当前阻塞项

| 问题 | 推荐方案 | 影响范围 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|---|
| `pdf-validate` 暂未输出 JSON | 已实现 `PDF_VALIDATE_JSON=1` | CLI 自动调度重跑需要机器可读报告 | 否 | 已解决 |
| MCP Server 适配层已移除 | 当前统一使用 `scripts/` CLI；机器调用保留 `PDF_AUTO_JSON=1` | Claude Code 不再通过本项目 MCP 工具调用 | 否 | 已解决 |
| 阶段 6 验收未执行 | 已完成三类路径验证和手册固化 | 运行手册可被后续会话按步骤复现 | 否 | 已解决 |
| 覆盖率低页面触发无效 high 重跑 | 已实现：区分 `rerun` 与 `review_only`，只重跑可修复段 | `pdf-validate`、`pdf-auto`、CLI JSON 诊断输出 | 否 | 已解决 |
| 输出产物分散在旧目录 | 阶段 8 已完成：统一为 `<package>/` 输出包结构，demo5 无/有 API 双路径验收通过 | `pdf-seg`、`pdf-merge`、`pdf-auto`、CLI JSON 返回路径 | 否 | 已解决 |
| 首次验证 `review_only` 段误触发合并（`pdf-auto` 行 230） | 已修复 Python 分支 + bash `needs_review` 处理分支，复验返回 `needs_review` 并生成 `<package>/review.md` | `pdf-auto` | 否 | 已解决 |
| 真实样本 `pdf-seg` 环境依赖未满足 | 根因 `transformers 5.x` 不兼容；已创建隔离 venv（`~/Documents/models/.venv`, `transformers 4.57.6`），scripts 自动检测优先使用 | Phase 8 端到端验收 | 否 | 已解决 |
| 未检测到 MinerU API 时 `pdf-seg` 因 `_api_arg[@]` 未绑定失败 | 已修复：`if/else` 分支替代空数组 `set -u` 展开，无 API 时自动启动临时服务 | Phase 8 端到端验收、无 API 服务启动路径 | 否 | 已解决 |
| `pdf-auto` 重跑失败路径可能被 `set -e` 提前中断 | 阶段 2 已修复：`mineru` 重跑调用改为 `if mineru ... ; then rc=0; else rc=$?; fi` 包装，`set -e` 下失败不再提前退出 | `pdf-auto` 自动重跑、CLI JSON 失败诊断 | 否 | 已解决 |
| `pdf-merge` 图片同名冲突可能被静默跳过 | 阶段 3 已修复：SHA-256 内容校验；同名同内容跳过，同名不同内容失败并输出冲突路径 | 输出包 `images/`、合并 Markdown 图片引用 | 否 | 已解决 |
| PDF 服务生命周期将由 ModelPad app 托管 | 全阶段（0-3）已完成：脚本不再管理服务进程/shared 输出目录，`pdf-auto` 重跑失败安全兜底，`pdf-merge` 图片同名冲突检测 | `pdf-seg`、`pdf-auto`、`pdf-rerun`、运行手册 | 否 | 已解决 |
| PDF 服务未启动时需要按需调用 ModelPad start/stop | 全阶段（0-3）已完成：helper 封装启停逻辑，三个入口已接入；无服务时自启、用完自停；已有服务时只复用不停止；失败路径可诊断 | `pdf-seg`、`pdf-auto`、`pdf-rerun`、ModelPad API | 否 | 已解决 |
| `pdf-prepare-ingest` 对真实手册表格产生冲突误报 | `conflict-context-ingestion-fix` 全阶段（0-3）已完成：上下文感知冲突判定 + rowspan 父级识别，春风样本冲突 35→0 组，已知误报全部消除 | `pdf-extract-data`、`pdf-prepare-ingest`、`conflicts.csv`、`ingest_ready.csv` | 否 | 已解决 |
| P4c 多模态 VLM 需本地模型选型与验收基准 | 页面基线、qwen3-vl-8b 单页探针、JSON mode 复测、10 页混合抽样及人工核对均完成 | `pdf-evaluation-suite` P4c、本地 VLM 后端 | 否 | 已解决 |

## 完成证据

| 计划 | 阶段 | 证据 |
|---|---|---|
| automated-pdf-pipeline | 阶段 1-7 | 详见 [自动化 PDF 解析流水线计划](plans/automated-pdf-pipeline.md#阶段-7-完成证据) |
| pdf-output-package-layout | Phase 8 复验 | 详见 [PDF 输出包目录结构计划验收记录](plans/pdf-output-package-layout.md#验收记录2026-06-30) |
| structured-data-extraction | 阶段 0-3 | 详见 [输出包结构化数据抽取计划](plans/structured-data-extraction.md#阶段-3-完成证据2026-07-02) |
| data-ingestion-pipeline | 阶段 0-3 | 详见 [结构化数据入库准备管线阶段 3 完成证据](plans/data-ingestion-pipeline.md#阶段-3-完成证据2026-07-02) |
| conflict-context-ingestion-fix | 阶段 0-3 | 详见 [结构化数据冲突误报与上下文主键修正阶段 3 完成证据](plans/conflict-context-ingestion-fix.md#阶段-3-完成证据2026-07-04) |
| coverage-validation-optimization | 阶段 0-5 | 详见 [覆盖率验证口径优化计划](plans/coverage-validation-optimization.md#验收记录2026-06-28) |
| marker-feature-absorption | 阶段 0-4 | 详见 [marker 特性吸纳计划](plans/marker-feature-absorption.md#阶段-4-完成证据2026-06-30) |
| minimal-automation-runbook | 最小人工执行版 | 详见 [最小自动化执行手册](plans/minimal-automation-runbook.md#step-0-证据) |
| modelpad-pdf-service-lifecycle | 阶段 0-3 | 详见 [ModelPad 托管 PDF 服务阶段 3 完成证据](plans/modelpad-pdf-service-lifecycle.md#阶段-3-完成证据2026-07-03) |
| modelpad-pdf-service-orchestration | 阶段 0-3 | 详见 [ModelPad PDF 服务按需编排阶段 3 完成证据](plans/modelpad-pdf-service-orchestration.md#阶段-3-完成证据2026-07-04) |
| modelpad-dynamic-env-cleanup | 阶段 0-4 | 详见 [ModelPad 动态 env 与临时输出清理阶段 4 完成证据](plans/modelpad-dynamic-env-cleanup.md#阶段-4-完成证据2026-07-04) |
| pdf-evaluation-suite | P4a（TOC 条目级验证） | 详见 [PDF 评测套件 P4a 验收记录](plans/pdf-evaluation-suite.md#验收记录2026-07-08) |
| pdf-evaluation-suite | P4b（表格结构自检评测） | 详见 [PDF 评测套件 P4b 验收记录](plans/pdf-evaluation-suite.md#验收记录p4b2026-07-08) |
| pdf-evaluation-suite | P4c（多模态 VLM 图表理解） | 详见 [PDF 评测套件 P4c 验收记录](plans/pdf-evaluation-suite.md#验收记录p4c2026-07-10) |
| pdf-auto-repair-before-merge | 阶段 0（Step 0 基线） | 详见 [专项计划阶段 0 完成条件](plans/pdf-auto-repair-before-merge.md#阶段-0固定-step-0-基线) |
| pdf-auto-repair-before-merge | 阶段 1（修复—合并契约） | 详见 [专项计划阶段 1 契约](plans/pdf-auto-repair-before-merge.md#阶段-1固化修复合并顺序和状态契约) |
| pdf-auto-repair-before-merge | 阶段 2（实现流程调整） | 详见 [专项计划阶段 2 再次验收](plans/pdf-auto-repair-before-merge.md#阶段-2-再次验收记录2026-07-11) |
