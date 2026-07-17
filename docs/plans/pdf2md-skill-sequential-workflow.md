# 计划：pdf2md skill 顺序工作流收敛

## 计划状态

- 状态：已完成
- 当前阶段：阶段 1：顺序入口与阶段门禁改写（已完成）
- 最后更新：2026-07-17

本文档是本次 `pdf2md` skill 流程重排的实施细节事实源。已有解析、人工协作、结构化抽取和下游交付计划继续保留其领域事实；本计划只负责把这些能力收敛为一个可执行的生命周期入口。

## 背景与问题

当前 `skills/pdf2md/SKILL.md` 已覆盖完整能力，但主要按主题组织：前置条件、输出包、核心流程、结构化数据、动态脚本、页面类型和排障彼此分散。使用者需要自行判断先运行哪个 CLI、何时停下、何时请求用户确认，以及哪些产物必须同步。

本次改动只调整 skill 的信息架构和执行顺序，不改变现有 CLI、输出字段、状态枚举、页码门禁、动态脚本安全边界或 MCP/数据库边界。

## 目标

- 建立从输入检查到下游交付的单一顺序入口。
- 将流程拆成 0～9 个阶段，并为每阶段明确目标、输入、tool、输出、成功条件和失败处理。
- 按用户交付目标提供可提前结束的路径：Markdown、复核后的 Markdown、结构化草案、入库候选、最终交付包。
- 固化阶段门禁，避免未完成前置校验时跳过人工复核、页码验证或审核状态门禁。
- 保持项目级 skill 为事实源，并同步用户级 skill。

## 非目标

- 不修改 `scripts/`、CLI 行为、JSON/CSV Schema 或真实 PDF 输出包。
- 不新增 MCP Server、数据库导入能力或第二个 skill 入口。
- 不把历史专项计划重新改写为本计划的事实源。
- 不新增固定模板；阶段说明直接写入 `SKILL.md`。

## Step 0 证据

基线类型：现状 skill 结构快照 + 已完成专项计划的反向核对 + 用户实际使用反馈。

- 当前 skill 存在“核心流程”但没有阶段级输入/输出/门禁定义，后续章节又分别重复描述结构化抽取、动态脚本和下游交付。
- 已完成计划已经分别冻结了解析、修复、审核、页码和下游契约，因此可以在不改变公共行为的前提下做编排层重排。
- 用户反馈明确指出：当前 skill “没有顺序性”，需要按步骤说明每步做什么以及使用哪些 tool。

## 阶段设计

| 阶段 | 目标 | 主要 tool | 主要门禁 |
|---|---|---|---|
| 0 | 任务分级、定位项目根目录、确认交付终点 | 读取 skill/manifest；项目根目录校验 | 明确交付等级 |
| 1 | 检查 PDF、ModelPad、MinerU 和输出位置 | `pdf-seg`、ModelPad health/API | 输入和服务有效 |
| 2 | 自动解析并生成基础 Markdown | `pdf-auto` | canonical Markdown、manifest、review 已生成 |
| 3 | 分类质量异常并决定是否 fallback/VLM | `pdf-read-page`、`pdf-search-content`、`pdf-rerun`、`pdf-eval-vlm` | 所有异常页均已分类 |
| 4 | 执行人工/LLM 修复并记录事实 | `pdf-table-repair`、`pdf-table-fix`、`pdf-run-helper` | 用户确认项已显式列出 |
| 5 | 同步 canonical Markdown、TOC、修复记录和 manifest | `pdf-merge`、`pdf-check-fixes` | 目录、hash、页码坐标系一致 |
| 6 | 生成结构化候选 | `pdf-extract-data` | 抽取基于 canonical Markdown |
| 7 | 审核候选并处理升级队列 | `review_decisions.jsonl`、`escalation_queue.jsonl` | 歧义项不得静默批准 |
| 8 | 生成入库候选并导出批次 | `pdf-prepare-ingest`、`pdf-export-ingest` | `page_numbering=verified`，仅 approved + ready 导出 |
| 9 | 生成下游导航和可选 chunks | `pdf-export-chunks`、`downstream_delivery.md` | 交付导航与实际文件一致 |

## 交付等级

- Markdown：阶段 0～3。
- 复核后的 Markdown：阶段 0～5。
- 结构化草案：阶段 0～6。
- 入库候选：阶段 0～7。
- 最终下游交付包：阶段 0～9。

## 验证方式

```bash
python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pdf2md
cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md
rg -n "阶段 0|阶段 9|G0|G5|downstream_delivery" skills/pdf2md/SKILL.md
git diff --check
plan-governance-cli check . --strict-readiness
```

## 完成条件

- 两份 skill 使用同一份顺序工作流说明。
- skill 开头提供阶段总览、交付等级和门禁，后续细节可按阶段定位。
- 每个阶段明确目标、输入、tool、输出、成功条件、失败处理和下一步。
- 不改变现有 CLI、文件契约和安全边界；反向引用检查无旧流程成为新的事实源。
- skill 校验、同步校验、差异检查和严格治理检查通过。

## 测试覆盖率

本计划只修改 Markdown 治理文档和两份 `SKILL.md`，不修改代码、CLI 或运行时逻辑，因此业务单元测试/覆盖率不适用。替代验证证据为 skill frontmatter 校验、两份 skill `cmp`、阶段关键字反向检查、`git diff --check` 和 `plan-governance-cli check . --strict-readiness`。

## 失败与回滚边界

- 本计划只修改治理文档和两份 skill，不写入 PDF、segments、真实输出包或代码。
- 若 skill 校验或同步检查失败，恢复本次文档变更，不宣称流程收敛完成。
- 若发现阶段说明与已有公共契约冲突，暂停修改并回到相关专项计划或 ADR 修正事实源。

## 当前阻塞项

无。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 1：顺序入口与阶段门禁改写 | 核对阶段 0～9 顺序入口、门禁和两份 skill 同步 | 实施证据已记录，验收命令可复现 | skill 校验、同步校验、反向引用和严格治理检查 | 已完成 |

## 当前阶段

阶段 1：顺序入口与阶段门禁改写。实施内容已落地，正在基于当前仓库内容和可复现命令进行独立核对。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已读取 `PLAN_MAP.md`、相关专项计划、ADR 0003 和 PDF 下游交付契约；确认问题属于 skill 信息架构缺少生命周期顺序，不需要代码变更 |
| 样本矩阵 | 项目级 skill；用户级 skill；计划和 `PLAN_MAP.md`；两份 skill 同步关系；frontmatter；阶段 0～9、G0～G5 关键入口 |
| 验证方式 | `quick_validate.py`、`cmp`、`rg` 阶段入口反向检查、`git diff --check`、`plan-governance-cli check . --strict-readiness` |
| 失败/回滚边界 | 只修改计划、`PLAN_MAP.md` 和两份 `SKILL.md`；校验失败时不进入实施完成，不修改代码、PDF、segments 或真实输出包 |
| 当前阻塞项 | 无 |
| 最新独立准入复核 | 2026-07-17，阶段 1，结论：通过，阶段完成；证据为实施证据和全部独立验收命令 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-17 |
| 阶段 | 阶段 1：顺序入口与阶段门禁改写 |
| 结论 | 通过：阶段完成，计划关闭 |
| 证据 | 项目级/用户级 skill 校验通过，`cmp` 通过，阶段 0～9 和 G0～G5 计数通过，`git diff --check` 和严格治理检查通过 |
| 复核者 | Codex |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-17 | Codex | 阶段 1：顺序入口与阶段门禁改写 | 通过：达到待实施标准 | 已完成相关事实源核对、Step 0 基线和文档-only 回滚边界确认 |
| 2026-07-17 | Codex | 阶段 1：独立验收 | 通过：阶段完成，计划关闭 | 项目级/用户级 skill 校验通过，`cmp` 通过，阶段 0～9 和 G0～G5 计数通过，`git diff --check` 和严格治理检查通过 |

## 阶段 1 实施证据（2026-07-17）

- `skills/pdf2md/SKILL.md` 已新增执行顺序总览、阶段 0～9、五级交付等级和 G0～G5 门禁。
- 原有阶段命令速查已明确为辅助入口，不能绕过阶段门禁；现有 CLI、输出包、Schema、页码门禁、动态脚本和 CLI-only 边界未改动。
- 项目级和用户级 skill 已同步；当前两份文件通过 `cmp` 一致性校验。
- 实施范围仅涉及 `docs/PLAN_MAP.md`、本专项计划和两份 `SKILL.md`，未修改代码、PDF、segments 或真实 PDF 输出包。

## 阶段 1 独立验收证据（2026-07-17）

- 项目级 `skills/pdf2md/SKILL.md` 新增阶段 0～9 顺序入口、五级交付等级和 G0～G5 阶段门禁。
- 阶段说明覆盖目标、执行动作、tool、成功条件和失败处理；原有 CLI、输出包和安全边界未改动。
- `python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pdf2md` 通过。
- `cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md` 通过。
- `git diff --check` 通过；未写入 PDF、segments、真实输出包或代码。

独立验收命令：

```bash
python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pdf2md
python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/jafish/.claude/skills/pdf2md
cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md
git diff --check
plan-governance-cli check . --strict-readiness
```

结果：全部通过；计划完成条件满足。
