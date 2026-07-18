# 计划：上游低影响 parent_key 补全

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 已完成 |
| 当前阶段 | 阶段 4 |
| 计划类型 | 上游输出契约、兼容性增强、入库批次交付 |
| 最后更新 | 2026-07-18 |

本计划替代已废弃计划 `semantic-parent-context-pipeline`。旧计划的抽取层改造和正式 Aura 重生成均不作为本计划实施依据；旧计划只保留回滚历史。

依赖背景：[结构化数据抽取](structured-data-extraction.md)、[结构化数据入库准备管线](data-ingestion-pipeline.md)；替代关系见旧计划的回滚记录。

## 目标

让上游每个可交付数据包都带有统一的 `parent_key`，下游直接消费，不再在下游临时补列或补语义。

## 核心决策

- 新增独立的上游 `parent_key` enrichment 阶段，位置在 `pdf-prepare-ingest` 之后、`pdf-export-ingest` 之前。
- `candidate_id`、`record_id`、`candidate_hash`、审核决定、审核状态和 ready 门禁均在 enrichment 前冻结；enrichment 不重新计算、不迁移审核身份。
- 仅补全 `ingest_ready.csv`，再由现有 `pdf-export-ingest` 原样传递到 `ingest_batch.jsonl`；不修改审核输入 `quick_lookup_draft.csv`，避免审核前后身份漂移。
- 现有非空 `parent_key` 默认保留；覆盖文件只能补空值，不能静默覆盖已有值。
- 父级不确定时留空并写入报告，不猜测、不按题号写规则；父级补全不改变 `review_status` 或 `ingest_status`，因此不会把未审核记录变成 ready。
- 下游仓库不在本计划范围内。

## 输入、输出和字段

包内可选输入：

```text
<package>/data/parent_context_overrides.csv
```

最小字段：

```text
candidate_id,parent_key,context_source,notes
```

优先使用唯一 `candidate_id` 定位；历史兼容场景可使用 `record_id,parent_key,context_source,notes`，但仅当该 `record_id` 在当前 `ingest_ready.csv` 中唯一。每行必须且只能填写一个定位字段。`context_source` 只记录来源类别，例如 `human_review`、`llm_review`、`package_override`；脚本不把来源类别当作业务批准依据。该来源信息只留在覆盖文件和报告中，不新增到入库记录，避免扩大公共 Schema。

阶段输出：

```text
<package>/data/ingest_ready.csv
<package>/data/ingest_batch.jsonl
<package>/data/ingest_manifest.json
<package>/data/parent-context-enrichment-report.md
```

`parent_key` 在 CSV 中放在业务 `key` 前面；JSONL 使用同名字段。manifest 继续记录 `ingest_ready.csv` 的输入 hash，报告记录补全数量、已有数量、空值数量、来源分布和异常。

## 处理规则

1. 读取 `ingest_ready.csv`，确认基础字段完整；历史重复 `record_id` 可以保留，不能作为候选覆盖的唯一定位。
2. 读取可选覆盖文件；优先按唯一 `candidate_id` 命中 ready 全集，兼容的 `record_id` 定位必须唯一；重复定位、空定位、空 `parent_key` 或未知字段均失败。
3. 对每行按“已有非空值优先，其次覆盖文件，最后为空”确定 `parent_key`。
4. 只允许更新 `parent_key`，不改变任何审核、状态、业务值和来源字段；上下文来源写入报告，不写入入库记录。
5. 原子写回 `ingest_ready.csv`，生成报告。
6. 调用现有 `pdf-export-ingest` 生成 JSONL 和 manifest；导出前仍执行原有页码和 ready 门禁。

## Step 0 基线与安全边界

基线类型：真实历史产物、当前脚本审计和回滚后的全量回归。

- 旧 Aura 正式产物已恢复，审核绑定和 348 条 batch 基线可复用。
- 250Sr 已验证 `parent_key` 是正常上游交付字段，现有产物中 `quick_lookup_draft.csv`、`ingest_ready.csv`、`ingest_batch.jsonl` 均有该字段。
- 当前 `compute_candidate_id` 将 `parent_key` 纳入来源位置；因此 enrichment 必须在 prepare 之后执行，否则会重演旧审核失配。
- 当前 `pdf-export-ingest` 会原样写出 `ingest_ready.csv` 行，说明不需要修改导出身份逻辑即可传递字段。
- 正式 Aura 试跑发现历史 `ingest_ready.csv` 缺少 `candidate_id/candidate_hash`，但历史 `ingest_batch.jsonl` 已有这两个字段；直接重导会丢失旧 batch 的候选交接字段。因此阶段 1 增加 legacy batch 字段保留边界：仅当当前 ready 缺少候选字段、旧 batch 有同 record_id 且稳定业务字段完全一致时才回填到新 JSONL；不回写 ready，不匹配则失败。
- 历史 Aura 重新生成时发现新版骨架有 5 组重复 `record_id`；无 `parent_context_overrides.csv` 时 enrichment 只做字段重排/保留，不因历史重复身份阻断产物重跑；阶段 4 改为优先使用唯一 `candidate_id`，只有兼容的 `record_id` 覆盖才要求 `record_id` 唯一，避免一条人工意见批量套用。
- 回滚边界：删除或停用 enrichment 输入/脚本即可回到现有 prepare/export 流程；不需要恢复审核文件或重算候选身份。

## Step 0 证据

真实 Aura 回滚基线、250Sr 对照包、Aura 正式重跑前备份、381 条历史审核迁移演练和 candidate_id 碰撞样本均已固定；正式包最终验证为 386 条候选、353 条 ready、33 条 skipped、0 条 not_ready。

## 验证方式

执行 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`、`bash tests/test-fix-validate.sh`、`plan-governance-cli check . --strict-readiness`，并检查正式 Aura 的 candidate 字段完整性、candidate_id 唯一性、batch 计数、manifest package/hash、skill 双份同步和回滚备份。

## 阶段路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| 阶段 0 | 冻结低影响边界、字段、覆盖文件和验证矩阵 | 已完成 |
| 阶段 1 | 新增审核后 enrichment 脚本和单元/集成测试 | 已完成 |
| 阶段 2 | 更新项目级与用户级 `pdf2md` skill，固化阶段 8/9 顺序 | 已完成 |
| 阶段 3 | 真实 150 Aura 正式重跑、审核复用和未迁移项交接 | 已完成 |
| 阶段 4 | 基于用户确认的结构化父级映射补全 Aura parent_key | 已完成 |

## 当前阶段

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已完成：旧 Aura 回滚基线、250Sr 字段基线、candidate_id 风险、临时副本演练和正式重跑前备份已固定 |
| 样本矩阵 | 新增/已有/空 parent_key、已有值冲突、无覆盖文件幂等运行、重复 record_id 无覆盖、重复 record_id 有覆盖、Aura 381 条审核迁移 |
| 验证方式 | enrichment/export 定向测试；Aura 正式包字段/状态/hash 检查；全仓 pytest；既有 fix 回归；skill 同步和治理检查 |
| 失败/回滚边界 | 覆盖文件异常或已有值冲突时原子失败；审核决定必须 candidate_id/candidate_hash 一对一，record_id 覆盖仍要求唯一；可恢复备份位于 Aura 包 `backup/candidate-disambiguation-20260718T214547` |
| 当前阻塞项 | 无；阶段 4 已按用户确认完成 parent_key 补全并验证批次传递 |
| 最新独立准入复核 | 通过；详见下方“最新独立准入复核”字段 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-18 |
| 阶段 | 阶段 4 |
| 结论 | 通过；用户确认的父级映射已写入上游 ready 和 batch，候选身份及审核状态无漂移 |
| 证据 | `data/parent-key-semantic-enrichment-report.md`；386 条 ready 中累计新增 30 条、原有 7 条、仍空 349 条；batch 353 条；备份 `backup/parent-key-enrichment-followup-20260718T220619` |
| 复核者 | Codex |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-18 | Codex | 阶段 1 | 通过，达到实施标准 | 新脚本隔离测试、临时包导出、全仓测试和既有修复回归通过；未写入正式 Aura |
| 2026-07-18 | Codex | 阶段 3 | 通过；正式重跑已完成，25 条身份不唯一记录按安全边界留待用户复核 | 备份 `backup/parent-context-rerun-20260718T211434`；正式 `ingest_ready.csv` 386 条、batch 324 条；381 条审核中安全迁移 356 条，25 条未迁移并写入 `data/parent-context-rerun-migration-report.md` |
| 2026-07-18 | Codex | 阶段 3 | 通过；用户确认审核和 candidate_id 消歧已写入，正式产物无 not_ready | 备份 `backup/candidate-disambiguation-20260718T214547`；用户确认新增 30 条决定（29 approved、1 rejected）；正式 batch 353 条，skipped 33 条，not_ready 0 条 |
| 2026-07-18 | Codex | 阶段 4 | 通过；用户确认的结构化父级映射已写入，达到完成标准 | `data/parent-key-semantic-enrichment-report.md`；累计新增发动机 9、传动 6、轮辋规格 1、电器装置 6、减震器 8；candidate_id/candidate_hash、审核状态、业务字段和 quick draft 未变；全量回归与批次校验通过 |

## 阶段 1 完成条件

- 脚本可重复运行；无覆盖文件时保留现有字段并生成零变更报告。
- 只补空 `parent_key`，已有非空值不被覆盖。
- `record_id`、`candidate_id`、`candidate_hash`、审核状态和 ready/skipped/not_ready 集合完全不变。
- 覆盖文件异常时非零退出且不破坏原 `ingest_ready.csv`。
- 导出 JSONL 保留 `parent_key`，manifest 的 batch 计数和原有门禁仍有效。
- 历史 ready 缺少候选字段时，导出 JSONL 保留旧 batch 的 `candidate_id/candidate_hash`；字段或稳定内容不一致时失败。
- 全量测试、治理检查、skill 双份同步和 `git diff --check` 通过。

## 阶段 1 实施证据（2026-07-18）

- 新增 `scripts/pdf-enrich-parent-context`，只在 `pdf-prepare-ingest` 之后更新 `ingest_ready.csv` 的 `parent_key`，并生成补全报告。
- 新增 `tests/test_pdf_enrich_parent_context.py`：补空、已有值冲突原子失败、无覆盖文件幂等三条路径通过。
- 250Sr 临时副本演练：182 条 `ingest_ready`，已有非空父级 67 条，补全 0 条，导出 179 条 batch；未修改正式包。
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`：345 passed, 5 warnings。
- `bash tests/test-fix-validate.sh`：通过 133，失败 0。
- `python3 -m py_compile scripts/pdf-enrich-parent-context scripts/pdf-prepare-ingest scripts/pdf-export-ingest`、`git diff --check`、两份 skill `cmp` 通过。
- 增加重复 `record_id` 边界测试：无覆盖文件保留历史重复行；有覆盖文件仍拒绝重复身份；enrichment/export 定向测试共 8 passed。

### 兼容性发现（2026-07-18）

- 正式包第一次试跑已回滚；备份恢复后 `ingest_ready.csv`、旧 batch、旧 manifest hash 均恢复原值。
- 试跑核对证明：ready 的 348 条候选身份未变，但直接重新导出会因历史 ready 缺列而丢失 batch 中的 `candidate_id/candidate_hash`；该路径未被保留，已作为阶段 1 的兼容性修复项。

## 阶段 3 正式 Aura 重跑证据（2026-07-18）

- 正式包已从用户回滚后的 `quick_lookup_draft.csv` 重新生成 `ingest_ready.csv`，没有重写 draft，也没有猜测新增 `parent_key`。
- 旧 `review_decisions.jsonl` 共 381 条；按新版候选身份安全迁移 356 条，旧审核文件和重跑前数据已备份到 `backup/parent-context-rerun-20260718T211434`。
- 正式 `data/ingest_ready.csv` 共 386 条，`candidate_id` 与 `candidate_hash` 填充率均为 100%；`parent_key` 非空 7 条，且位于 `key` 前；第 35 行已按第 36 行结构修正轮胎规格参数。
- 正式 `data/ingest_batch.jsonl` 共 353 条，全部为 ready，candidate 字段填充率 100%，无重复 `candidate_id`；`data/ingest_manifest.json` 的 package 已指向正式 Aura 目录，计数为 ready 353、skipped 33、not_ready 0。
- 审核迁移过程中发现的 25 条不确定记录没有静默放行，详见 `data/parent-context-rerun-migration-report.md`；逐条业务反查见 `data/parent-context-rerun-human-review.md`。
- 用户确认后，30 条审核决定已写入正式文件（29 条 approved、1 条 rejected）；扭矩表 10 条候选通过确定性内容摘要消歧，详见 Aura 包 `data/candidate-identity-disambiguation-report.md`。

## 当前阻塞项

无。阶段 4 已完成，正式包不存在 `not_ready`，下游可消费 353 条 ready batch。仍不确定的 `parent_key` 保持空值。

## 阶段 4 Step 0 证据与范围（2026-07-18）

- 用户已确认父级映射：发动机参数、轮胎规格、轮辋规格、电器装置、减震器。
- 当前 Aura 已有 7 条非空 `parent_key`；目标是只对确认映射下的空值补全，保留已有值。
- 覆盖定位使用唯一 `candidate_id`；由于 Aura 存在历史重复 `record_id`，不再以 `record_id` 作为默认覆盖定位。
- 非目标：不修改 `quick_lookup_draft.csv` 的候选身份、不重新审核、不改变 `review_status`/`ingest_status`，不修改下游仓库。

## 阶段 4 验证方式与完成条件

- 生成 `data/parent_context_overrides.csv`，逐条记录 `candidate_id,parent_key,context_source,notes`；旧包只有唯一 `record_id` 时保留兼容输入。
- 运行 `pdf-enrich-parent-context` 和 `pdf-export-ingest`；验证新增数量、已有值未变、candidate 字段/hash、审核状态、ready 计数和 batch parent_key 传递。
- 全量 pytest、fix 回归、治理检查和 skill 双份同步通过；正式包保留阶段 4 前备份。
- 完成条件：所有确认映射已写入 ready/batch，仍不确定的 parent_key 保持空值，且没有候选身份或审核状态漂移。

## 阶段 4 完成证据（2026-07-18）

- 已按用户确认生成 `data/parent_context_overrides.csv`，覆盖定位全部使用唯一 `candidate_id`。
- `pdf-enrich-parent-context`：本次追加总记录 386；已有非空 28；本轮补全 9；仍为空 349。
- 阶段 4 累计：原有非空 7；累计补全 30；最终非空 37。
- `pdf-export-ingest`：batch 353 条；parent_key 非空 37 条；manifest 为 ready 353、skipped 33、not_ready 0。
- candidate_id/candidate_hash、审核状态、业务 key/value/unit、来源定位字段和 `quick_lookup_draft.csv` 与阶段 4 前完全一致。
- 正式补全前备份：`backup/parent-key-enrichment-20260718T215811`；详细报告见 `data/parent-key-semantic-enrichment-report.md`。

## Test Coverage（测试覆盖率证据）

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`：354 passed，5 warnings。
- `bash tests/test-fix-validate.sh`：133/133 通过。
- `plan-governance-cli check . --strict-readiness`：通过。
- `git diff --check`、项目级/用户级 skill 同步校验和正式 Aura 字段/状态/hash 校验：通过。
