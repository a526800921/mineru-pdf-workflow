# 计划：审核阶段 parent_key 建议与确认

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 已完成 |
| 当前阶段 | 阶段 2：真实 PDF 包只读演练 |
| 计划类型 | 审核阶段辅助脚本、入库前派生产物 |
| 最后更新 | 2026-07-19 |

依赖背景：[上游低影响 parent_key 补全](parent-context-upstream-enrichment.md)、[结构化数据入库准备管线](data-ingestion-pipeline.md)。本计划不重开已完成的 parent_key enrichment 阶段，只增加审核阶段的建议入口。

## 目标

在 `pdf-prepare-ingest` 生成 `data/ingest_ready.csv` 后，为空 `parent_key` 生成可审核的建议 sidecar；审核通过后复用现有 `parent_context_overrides.csv` 和 `pdf-enrich-parent-context` 应用结果。

## 范围

- 新增 `scripts/pdf-parent-context-review`，支持 `suggest` 和 `apply` 两个命令。
- `suggest` 只读取 `ingest_ready.csv`，生成 `data/parent_context_suggestions.csv` 和报告，不修改 `ingest_ready.csv`。
- 结构明确的二级及以上 `section_path` 只提出低风险建议；候选 `key` 与章节名相同、章节不足两级或记录非 ready 时不自动建议。
- `apply` 只把审核明确为 `approve` 的建议合并到 `parent_context_overrides.csv`；`reject` 和未决定项不进入 override。
- 继续由现有 `pdf-enrich-parent-context` 更新 `ingest_ready.csv`，再由 `pdf-export-ingest` 导出批次。
- 细粒度表格分组、rowspan 继承纠错和已有非空 `parent_key` 覆盖不在本阶段自动处理，继续使用人工确认和现有 override 机制。

## 非目标

- 不修改 `pdf-extract-data`、覆盖审计、`pdf-prepare-ingest` 或候选身份计算。
- 不直接改写 `ingest_ready.csv`、`quick_lookup_draft.csv`、`review_decisions.jsonl` 或业务审核状态。
- 不把所有 `section_path` 末级标题机械写入 `parent_key`。
- 不处理本次已发现的 3 条历史纠错；这些记录另行审核。
- 不改变入库 Schema；建议文件和报告属于包内审核派生产物。

## 处理契约

建议文件：

```text
candidate_id,record_id,key,current_parent_key,suggested_parent_key,decision,confidence,context_source,notes
```

- `decision` 为空表示待审核，允许填写 `approve` 或 `reject`。
- `approve` 必须有 `suggested_parent_key`，或者由审核者填写修订后的 `suggested_parent_key`。
- `parent_key == key`、定位不到当前候选、重复定位、覆盖已有非空值或非法决定时失败且不写入 override。
- `context_source=section_path_fallback` 只表示结构化建议来源，不代表业务自动批准。

## Step 0 证据

基线类型：当前审核阶段脚本契约、真实 Aura `ingest_ready.csv` 快照和现有 enrichment 定向测试。

- 现有 `pdf-enrich-parent-context` 只接受非空 `parent_context_overrides.csv`，只补空值，不能生成建议。
- 当前 Aura 包为 488 条候选，`parent_key` 已有值 417 条、为空 71 条；最终 ready batch 的统计以当前包 manifest 和导出结果为准，本计划不修改该包。
- 建议脚本必须在临时 fixture 上证明：二级路径可提出建议、单级路径保持待审核、章节标题自引用被拒绝、非 ready 记录不自动建议、未审批建议不进入 override、审批后仍由现有 enrichment 应用。
- 回滚边界：删除建议文件并跳过该脚本即可恢复原有 `prepare → enrich → export` 流程；`apply` 失败时不写入 override，`suggest` 从不写入主候选文件。

## 验证方式

- 定向测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_pdf_parent_context_review.py tests/test_pdf_enrich_parent_context.py`，预期 10 passed。
- 全量测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`，预期 366 passed，允许既有 DeprecationWarning。
- 治理与文档：`plan-governance-cli check . --strict-readiness`、`git diff --check`、两份 `pdf2md` skill `cmp` 均返回成功。
- 范围检查：提交前运行 GitNexus `detect_changes()`；新增脚本和测试纳入变更清单，抽取、覆盖审计和导出流程不得出现意外受影响项。
- 失败判定：建议阶段改写 `ingest_ready.csv`、未批准项进入 override、候选身份/状态/批次集合变化或任一命令非零退出。

## 阶段路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| 阶段 0 | 固定 sidecar 契约、规则和 fixture 基线 | 已完成 |
| 阶段 1：审核 sidecar 建议与确认 | 实现建议/确认脚本、测试和阶段 8 使用说明 | 已完成 |
| 阶段 2：真实 PDF 包只读演练 | 确认建议数量和人工审核体验 | 已完成 |

## 当前阶段

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已完成：阶段 2 使用 Aura `ingest_ready.csv` 临时副本，正式文件 hash 和不写入边界已固定 |
| 样本矩阵 | 二级 `section_path` fixture、单级路径、self-reference、非 ready、approve/reject/pending、重复定位、已有 parent 冲突、Aura 488 条真实候选 |
| 验证方式 | 定向/全量 pytest、Aura 临时副本 `suggest`、正式文件 hash/产物存在性检查、治理检查、`detect_changes()` |
| 失败/回滚边界 | 建议只写 sidecar；应用失败不写 override；跳过脚本即可回到现有流程 |
| 当前阻塞项 | 无；阶段 2 只读演练完成，未对正式 Aura 生成 sidecar |
| 最新独立准入复核 | 通过；详见下方“最新独立准入复核” |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-19 |
| 阶段 | 阶段 2：真实 PDF 包只读演练 |
| 结论 | 通过：阶段 2 已完成 |
| 证据 | Aura 临时副本 488 条候选中 417 条已有 parent_key、71 条为空、0 条自动建议；正式 ingest hash 未变且未生成建议 sidecar；治理检查通过 |
| 复核者 | Codex |

## 阶段 2 Step 0 证据（2026-07-19）

- 输入：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/ingest_ready.csv` 的临时副本，不写入正式包。
- 可执行命令：`scripts/pdf-parent-context-review <临时包> suggest`。
- 临时副本基线：488 条候选，417 条已有 `parent_key`，71 条为空。
- 预期：只生成建议 sidecar；不改变临时副本 `ingest_ready.csv`；正式包不产生 `parent_context_suggestions.csv` 或报告。
- 实际：建议 0 条，人工审核 71 条；正式文件 SHA-256 为 `4dd62cb3d19cdbe12a072018f6216c370fe177cca37d36e434bfdad39acc6654`，正式包未生成建议文件。

## 阶段 2 实施证据（2026-07-19）

- 真实 Aura 临时副本运行成功：`existing=417`、`manual_review=71`，`suggested_parent_rows=0`。
- 当前 Aura 的 71 条空值记录均为单级章节或不适合结构性自动推断的内容，因此没有被机械填充；已有 417 条非空值未被覆盖。
- 正式 Aura `ingest_ready.csv` hash 保持不变，`data/parent_context_suggestions.csv` 和 `data/parent-context-review-suggestion-report.md` 均不存在。
- `plan-governance-cli check . --strict-readiness`、`git diff --check` 通过；不生成正式批次，不需要下游交付文档更新。

## 阶段 1 实施证据（2026-07-19）

- 新增 `scripts/pdf-parent-context-review`，支持 `suggest`/`apply`；建议阶段不修改 `ingest_ready.csv`，应用阶段只合并明确批准项到 `parent_context_overrides.csv`。
- 新增 `tests/test_pdf_parent_context_review.py`：二级路径建议、单级路径保留人工审核、自引用保护、非 ready 保护、approve/reject/pending 和现有 enrichment 传递共 4 条场景通过。
- 定向 parent_key 测试：10 passed；全量 pytest：366 passed，5 warnings。
- `plan-governance-cli check . --strict-readiness`、`git diff --check` 和项目级/用户级 skill 同步校验通过。
- GitNexus `detect_changes({scope: "all"})`：风险 LOW，受影响流程 0；新增脚本/测试为未入索引的新文件，跟踪文件仅涉及计划和阶段 8 使用说明。

本次只完成真实包临时副本演练；后续不自动对正式 PDF 包批量填充，须由审核者确认建议后再执行 `apply`。

## 完成条件

- `suggest` 幂等运行，输出稳定，且不改变 `ingest_ready.csv`。
- 只对结构明确且不自引用的空 `parent_key` 生成建议；不确定项可见但不自动批准。
- `apply` 仅处理明确 `approve`，并安全合并现有 override；未决定和拒绝项不影响既有流程。
- 现有 `pdf-enrich-parent-context`、`pdf-export-ingest` 的候选身份、审核状态、ready/skipped/not_ready 集合和批次数量不因建议脚本改变。
- 项目级与用户级 `pdf2md` skill 同步说明新审核步骤。
- 定向测试、全量测试、`plan-governance-cli check . --strict-readiness`、`git diff --check` 和提交前 `detect_changes()` 通过。

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-19 | Codex | 阶段 1：审核 sidecar 建议与确认 | 通过：达到实施标准 | Step 0 基线、sidecar 契约、fixture 矩阵和回滚边界已记录 |
| 2026-07-19 | Codex | 阶段 1 准入 | 通过：达到实施标准 | Step 0 基线、sidecar 契约、fixture 矩阵和回滚边界已记录 |
| 2026-07-19 | Codex | 阶段 1：审核 sidecar 建议与确认 | 通过：阶段 1 已完成 | 定向 10/10、全量 366 passed、治理检查通过；GitNexus 风险 LOW、受影响流程 0 |
| 2026-07-19 | Codex | 阶段 2：真实 PDF 包只读演练 | 通过：阶段 2 已完成 | Aura 临时副本 488/417/71/0 统计符合预期；正式包 hash 未变，未生成建议 sidecar |

## Test Coverage（测试覆盖率证据）

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`：366 passed，5 warnings。
- parent_key 审核建议与现有 enrichment 定向测试：10 passed。
- `plan-governance-cli check . --strict-readiness`：通过。
- `git diff --check` 和项目级/用户级 `pdf2md` skill 同步校验：通过。
