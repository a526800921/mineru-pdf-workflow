# 计划：LLM 优先审核与 PDF 入库前流程硬化

## 计划状态

- 状态：实施中
- 当前阶段：阶段 2：稳定候选身份和 override 兼容
- 最后更新：2026-07-16

本文档是 `llm-first-review-workflow-hardening` 的实施细节事实源。计划状态、当前阶段、依赖、推荐顺序、阻塞项和证据入口以 [PLAN_MAP](../PLAN_MAP.md) 为准。

本计划是对已完成 [LLM/人工协作入口迁移](llm-human-collaboration-migration.md) 的后续硬化，不重新打开旧计划的历史完成结论。旧计划记录迁移到统一 `pdf2md` 入口的事实；本计划处理真实运行后发现的审核自动化、候选身份、通用抽取和 chunks 导出问题。

## 背景与问题

本次春风 150 Aura 手册的真实协作已经验证：用户不需要逐条审核 `ingest_ready.csv`，LLM 可以完成绝大多数证据明确的候选审核，用户只需要处理真正无法从 PDF、Markdown 和表格结构中分辨的项目。

阶段 0 基线中的代码和 skill 曾以“所有待审核候选都由用户确认”为默认边界，导致协作效率低于实际能力。本阶段已开始收敛该边界；同时，本次运行暴露出以下通用问题：

1. `pdf-export-chunks` 通过目录遍历选择 Markdown，可能误读 `toc.md`，而不是 manifest 指定的主 Markdown；
2. 冒号抽取器会把时间、URL、邮箱、脚注和说明句误识别成候选；
3. 一行包含多组 key/value 的表格只能依赖临时动态脚本拆分；
4. `record_id` 无法稳定区分重复来源，审核覆盖可能误作用于多行；
5. `review_overrides.csv` 缺少审核者、决策依据、规则版本和候选 hash，无法完整审计 LLM 与用户的协作决策。

## 目标

- 将审核策略调整为“LLM 默认处理明确候选，用户只处理升级项”。
- 保留入库前门禁：缺 key/value/evidence、存在冲突、来源不稳定或语义不确定的记录不得进入 `ready`。
- 增加稳定的候选身份，使重抽取、动态拆分和重复来源不会造成审核误绑定。
- 增加结构化审核决策和升级队列，区分 LLM 决策与用户决策。
- 将时间/URL/邮箱/脚注等冒号误切分处理抽象为通用规则。
- 增加配置驱动的多组 key/value 表格展开能力。
- 使 chunks 始终从 manifest 指定的 canonical Markdown 导出，并对误读 TOC 做回归保护。
- 继续由 `pdf2md` skill 作为唯一用户入口，保持 CLI-only，不新增 MCP Server。
- 保持项目边界在入库前数据准备，不执行数据库导入。

## 非目标

- 不修改原始 PDF、原始 `segments/` 或 `content_list*.json`。
- 不在通用脚本中写入品牌名、PDF 文件名、固定页码或单个手册的业务字段。
- 不让 Python 自动猜测无法由证据确定的表格业务语义。
- 不提供“全部 approve”或绕过升级队列的快捷路径。
- 不直接把 LLM 的判断写成用户确认；审核记录必须区分 `llm` 和 `user`。
- 不重新引入 MCP Server 或 MCP 兼容层。
- 不在本计划中执行数据库导入。
- 不改写已完成计划作为新事实源；新契约只写入本计划及后续同步的正式 skill/ADR/migration 文档。

## 相关事实源与关系

- [LLM/人工协作入口迁移](llm-human-collaboration-migration.md)：已完成的入口迁移和动态脚本安全边界。
- [结构化数据入库准备管线](data-ingestion-pipeline.md)：当前 `ingest_ready.csv`、状态和入库前交付边界。
- [结构化抽取覆盖](pdf-extract-data-table-coverage.md)：抽取字段和当前候选生成流程。
- [ADR 0003：LLM 编排与受控动态辅助脚本](../adr/0003-llm-orchestrated-dynamic-assistants.md)：当前 CLI-only 和动态脚本原则。
- [PDF 工作流与 LLM 协作复盘](../reports/pdf-workflow-llm-review-2026-07-15.md)：本计划的真实运行证据和问题清单。

ADR 0003 已在 2026-07-16 追加审核契约增量修订，明确 LLM 自动审核的信任边界和升级条件；后续阶段只允许在本计划和 ADR 的新契约上继续演进。

## 协作信任边界

| 决策者 | 可自动完成 | 必须升级给用户 |
|---|---|---|
| LLM | 证据完整且 key/value 一致的批准；明确页脚、表头、脚注、HTML 残片等非业务候选的拒绝；生成审核理由和升级队列 | 多种合理解释、跨页/合并单元格语义不确定、来源冲突、证据缺失、候选身份重复或不稳定、高风险参数列义不确定 |
| Python/CLI | 抽取、hash、身份生成、状态门禁、冲突检测、导出、回滚和校验 | 不判断 PDF 特定业务语义，不自动改变审核决定 |
| 用户 | 对升级项确认 PDF 事实、表格关系、列语义和最终候选状态 | 不需要执行脚本、手工编辑 CSV 或维护 hash/manifest |

LLM 自动批准的最低条件：

- key、value 与完整 evidence 一致；
- 来源页码、表格/段落、行列或子行定位明确；
- 无未解决冲突；
- 无缺失字段、数字 key、明显错列或歧义冒号；
- candidate identity 唯一且可追溯；
- 决策依据可以归入已登记的规则类别。

LLM 自动拒绝的最低条件：

- 明确是页脚、地址、电话、邮箱或企业元数据；
- 明确是表头、分类行、脚注符号解释或 HTML 残片；
- 明确只有页码、单位、数字或无业务意义的标记。

无法满足上述条件时，候选进入 `escalation_queue`，不得静默批准或删除。

## 目标数据契约

### 审核决策

建议新增富结构审计产物：

```text
<package>/data/review_decisions.jsonl
```

每条至少包含：

| 字段 | 规则 |
|---|---|
| `candidate_id` | 稳定定位单个候选来源，优先审核绑定字段 |
| `record_id` | 保留现有内容身份，供兼容和下游追溯 |
| `review_status` | `approved`、`rejected`、`needs_review` |
| `review_actor` | `llm` 或 `user` |
| `decision_basis` | 如 `evidence_exact`、`rule_based_non_business`、`user_confirmed`、`ambiguous` |
| `review_rule_version` | 本次使用的审核规则版本 |
| `candidate_hash` | 防止候选内容变化后静默复用决定 |
| `reason` | 面向审计和升级展示的简短理由 |
| `reviewed_at` | ISO 8601 时间；不可用时保留空值但必须明确原因 |

`review_overrides.csv` 保留为 `pdf-prepare-ingest` 的兼容输入；本阶段采用 `review_decisions.jsonl` 作为富结构审核事实源，不扩展旧 CSV 表头，也不由脚本反向生成旧 CSV。

### 升级队列

```text
<package>/data/escalation_queue.jsonl
```

每条至少包含：`candidate_id`、`record_id`、`page_start`、`page_end`、`evidence_text`、`current_candidate`、`ambiguity_type`、`llm_options`、`recommended_action`。

用户每次只需处理升级队列。用户确认后，由 LLM 将决定追加写入 `review_decisions.jsonl`；旧包仍可继续使用 `review_overrides.csv`，两者状态冲突时脚本拒绝运行。

### 候选身份

新增 `candidate_id`，不立即替换现有 `record_id`：

```text
candidate_id = hash(source_pdf_hash + source_block_id + table_id + row_index + pair_index + page_start + page_end)
```

实际字段组合以阶段 2 的兼容测试为准，但必须满足：

- 同一来源位置重抽取后可稳定绑定；
- 同一内容出现在不同来源位置时可区分；
- 双 key/value 拆分后的每个子候选有独立身份；
- 无法唯一确定身份时进入升级队列，而不是按 `record_id` 静默批量应用。

## 阶段路线图

| 阶段 | 目标 | 主要产物 | 状态 |
|---|---|---|---|
| 阶段 0：审核契约与候选身份冻结 | 冻结审核策略、数据契约和真实基线 | 本计划、基线命令、准入证据 | 已完成 |
| 阶段 1：审核决策与升级队列 | 审核决策与升级队列 | `review_decisions.jsonl`、`escalation_queue.jsonl`、兼容映射 | 已完成 |
| 阶段 2：稳定候选身份和 override 兼容 | 稳定候选身份和 override 兼容 | `candidate_id`、重复身份门禁、迁移/回滚说明 | 已完成 |
| 阶段 3 | 通用抽取增强 | 冒号分类、`pair_groups`、子行来源 | 设计中 |
| 阶段 4 | canonical Markdown chunks 导出修复 | manifest 主文档选择、回归 fixture | 设计中 |
| 阶段 5 | skill、ADR、用户级 skill 同步和真实 PDF 验收 | 更新后的协作入口和验收证据 | 设计中 |

## 当前阶段

阶段 0、阶段 1 和阶段 2 已完成。阶段 3 尚未启动；本次验收闭环的当前阶段指针仍为阶段 2：稳定候选身份和 override 兼容。

### 阶段 2 准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已冻结保留现有 candidate-v1 兼容算法、增加重复 `record_id`/`candidate_id` 阻断、仅允许唯一身份应用旧 CSV，以及不在本阶段迁移历史 ID 的安全边界 |
| 样本矩阵 | 重复 `record_id` 旧 CSV fixture、唯一 `record_id` 兼容 fixture、重复 `candidate_id` 富结构决定 fixture、同一来源重跑稳定性 fixture；每项有命令、预期结果、失败判定和输出位置 |
| 验证方式 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py`、`bash tests/test-fix-validate.sh`、全量 pytest、治理严格检查和 GitNexus 变更范围检查 |
| 失败/回滚边界 | 重复身份一律非零退出并保持旧产物不变；不改变历史 candidate-v1 算法和既有 CSV 字段顺序；失败时删除本次生成产物并从草案重建 |
| 当前阻塞项 | 无阶段 2 阻塞；candidate-v2 跨版本迁移和真实 PDF 重跑保留到后续真实样本验收，不在本阶段静默迁移旧决定 |
| 最新独立准入复核 | 2026-07-16，阶段 2，结论“通过：达到待实施标准”，复核者 Codex；证据为重复身份最小复现、兼容边界和回滚矩阵 |

### 阶段 2 当前目标

- 防止旧 `review_overrides.csv` 通过重复 `record_id` 静默批量修改多条来源不同的记录；
- 防止富结构 `review_decisions.jsonl` 通过重复 `candidate_id` 批量应用；
- 在不破坏 candidate-v1 和旧 CSV 的前提下，证明同一来源重跑的 candidate identity 稳定；
- 为后续 candidate-v2 跨版本迁移保留明确的阻断和回滚边界。

### 阶段 2 Step 0：身份唯一性与兼容安全基线

状态：已完成，达到实施标准。

#### Step 0 证据

基线类型：最小失败 fixture + 真实 Aura 重复 `record_id` 风险快照 + 现有审核兼容回归。

当前实现已经具备 candidate-v1 和 `candidate_hash`，但旧 `review_overrides.csv` 仍按 `record_id` 应用；当一个 `record_id` 对应多个候选时，旧逻辑会同时修改这些候选。阶段 2 先修复这个高风险边界，不直接改变历史 candidate-v1 的计算方式，避免已有富结构决定整体失效。

冻结规则：

- `review_decisions.jsonl` 继续以唯一 `candidate_id` 为主键；重复 candidate_id 一律拒绝；
- 旧 `review_overrides.csv` 只允许按 `record_id` 命中唯一一行；命中多行时非零退出，并提示改用 `review_decisions.jsonl`；
- candidate-v1 计算公式保持不变，先验证同一输入重跑稳定；candidate-v2 需要另建迁移 fixture，不在本阶段静默替换；
- 任何身份阻断都不能生成新的 ready 产物，旧产物由调用方按包级备份恢复；
- 不把重复内容简单视为幂等，因为来源位置可能不同。

#### Step 0 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| 重复 `record_id` + 旧 CSV | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k duplicate_record_override` | 非零退出，提示使用 candidate_id，行状态不被静默批量修改 | 重复来源均被 approved 或输出半成品 | pytest 输出、临时包 |
| 唯一 `record_id` + 旧 CSV | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k legacy_override` | 旧格式正常应用 | 兼容输入失败或旧字段位置变化 | pytest 输出 |
| 重复 `candidate_id` + 富结构决定 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k duplicate_candidate_identity` | 非零退出，保持拒绝批量应用 | 多行被同一决定修改 | pytest 输出 |
| 同一来源重跑 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k candidate_identity_stable` | candidate-v1 和 candidate_hash 稳定 | 相同输入 ID 漂移 | pytest 输出 |
| 既有兼容回归 | `bash tests/test-fix-validate.sh` | 133/133 通过 | fix_data、旧 CSV 或导出门禁回归 | shell 输出 |

#### 阶段 2 Step 0 验证方式

- 先执行重复 `record_id` 最小失败 fixture，确认旧逻辑的风险可被测试捕获；
- 实施后验证重复覆盖在应用前失败，且不写 `ingest_ready.csv`/`conflicts.csv`；
- 验证唯一旧覆盖和富结构 candidate 决定不受影响；
- 验证同一行两次生成的 candidate-v1、candidate_hash 完全一致；
- 运行全量 pytest、修复回归、治理严格检查和 `git diff --check`。

#### 阶段 2 Step 0 完成条件

- 重复 `record_id` 不再允许旧 CSV 静默批量应用；
- 重复 `candidate_id` 和未知 candidate identity 均被阻断；
- candidate-v1 兼容行为和旧 CSV 唯一路径有回归证据；
- 失败不会产生半成品 ready 结果；
- 最新独立准入复核明确达到“待实施”标准。

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-16 |
| 阶段 | 阶段 2：稳定候选身份和 override 兼容 |
| 结论 | 通过：达到待实施标准 |
| 证据 | 已冻结重复 `record_id` 阻断、唯一旧 CSV 兼容、重复 `candidate_id` 阻断、candidate-v1 不迁移和失败回滚边界；最小 fixture 矩阵已登记。 |
| 复核者 | Codex |

### 阶段 2 实施证据（2026-07-16）

本阶段已完成通用脚本和 fixture 实施，整体计划状态仍保持 `实施中`，后续阶段不因本阶段完成自动进入实施：

- `apply_overrides` 先建立 `record_id` 到候选行的映射；旧 CSV 命中 0 条或多条时均非零退出，重复命中明确提示改用 `review_decisions.jsonl` 的 `candidate_id`，且在任何行状态修改前失败。
- `build_escalation_queue` 对重复 `record_id` 追加 `duplicate_record_identity`，设置 `requires_user=true` 和 `recommended_action=user_confirm`；不自动改变审核或入库状态。
- candidate-v1、candidate hash、record_id 计算方式未改变；新增同一来源重跑稳定性和重复 record_id 旧覆盖阻断测试。
- 项目级 `skills/pdf2md/SKILL.md`、用户级 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 和 ADR 0003 已同步旧 CSV 唯一身份规则。
- 验证结果：阶段 2 定向 fixture 6 passed；`tests/test_pdf_prepare_ingest.py` 15 passed；全量 pytest 330 passed；`bash tests/test-fix-validate.sh` 133/133；`plan-governance-cli check . --strict-readiness` 通过；`git diff --check` 和两份 skill `cmp` 通过。
- 未重跑真实 PDF 包，未修改原始 PDF、segments、Markdown、审核产物或数据库。

### 阶段 2 独立验收（2026-07-16）

结论：通过，阶段 2 完成。

独立核对结果：

- 重复 `record_id` 的旧 CSV 覆盖在任何状态写入前失败，并提示改用 `candidate_id`；既有 `ingest_ready.csv` 哨兵内容保持不变，`conflicts.csv` 不产生半成品。
- 重复 `candidate_id` 的富结构 JSONL、未知 `candidate_id`、过期 hash 和 record_id 不匹配均有阻断路径；重复身份同时会进入需要用户确认的升级队列。
- 唯一旧 CSV 覆盖仍能应用，candidate-v1、candidate_hash、record_id 在同一来源重跑时保持稳定，旧字段顺序未变化。
- 独立命令结果：阶段 2 定向 fixture 6 passed；`tests/test_pdf_prepare_ingest.py` 15 passed；全量 pytest 330 passed；`bash tests/test-fix-validate.sh` 133/133；严格治理检查、diff 检查和 skill 同步检查通过。
- 变更范围复核：GitNexus 未发现 HIGH/CRITICAL；无扩展名 `scripts/pdf-prepare-ingest` 内部函数未被索引，以源码调用点和上述回归替代影响证据；工作区既有 TOC/统计文件改动未纳入本阶段行为判断。
- 安全边界确认：未重跑真实 PDF 包，未修改原始 PDF、segments、Markdown、审核产物或数据库。

复核者：独立验收复核（Codex）。

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-16 | Codex | 阶段 2：稳定候选身份和 override 兼容 | 通过：达到待实施标准 | 重复身份阻断、旧 CSV 唯一兼容、candidate-v1 稳定和回滚边界已冻结 |
| 2026-07-16 | 独立验收复核 | 阶段 2：稳定候选身份和 override 兼容 | 通过：达到待实施标准 | 独立验收确认阶段完成；6 项阶段 2 定向 fixture、15 项入库准备测试、330 项全量 pytest、133/133 修复回归、严格治理检查、skill 同步和未写真实 PDF/数据库证据 |

## 阶段 1 实施与验收记录

阶段 1 已完成自己的 Step 0、实施和独立验收；其历史细节保留如下。

### 阶段 0 完成记录：目标

冻结本计划的审核边界、兼容策略、样本基线、验证命令、失败/回滚边界，确保阶段 1 可以独立实施。

### 阶段 0 完成记录：范围

- 记录真实 Aura 包的最终结果和 chunks 误读问题；
- 明确 LLM 自动批准、自动拒绝和必须升级的条件；
- 明确 `candidate_id` 与现有 `record_id` 的兼容方向；
- 明确 `review_decisions.jsonl` 与 `review_overrides.csv` 的关系；
- 建立阶段 1-5 的实施顺序和依赖。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 实施中 |
| Step 0 | 阶段 1 已冻结 JSONL 审核决策、兼容 CSV、LLM/用户决策边界、候选 hash 校验和升级队列生成规则 |
| 样本矩阵 | 最小 JSONL 审核 fixture、旧 `review_overrides.csv` 兼容 fixture、过期 hash/非法 actor/冲突决定 fixture、动态 helper 门禁 fixture；每项均有命令、预期结果、失败判定和输出位置 |
| 验证方式 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py tests/test_pdf_run_helper.py`、`bash tests/test-fix-validate.sh`、真实包只读检查、治理严格检查 |
| 失败/回滚边界 | 新决策格式校验失败时拒绝生成 ready；保留旧 CSV 兼容入口；按包备份和重建 `ingest_ready.csv`/`conflicts.csv`，不接触原始 PDF/segments/数据库 |
| 当前阻塞项 | 无阶段 1 阻塞；阶段 2 的 candidate identity 进一步稳定化、阶段 3 抽取增强和阶段 4 chunks 修复尚未启动 |
| 最新独立准入复核 | 2026-07-16，阶段 1，结论“通过：达到待实施标准”，复核者 Codex；证据为阶段 1 Step 0、契约 fixture 和治理检查 |

### 阶段 0 完成记录：非目标

- 不修改 `scripts/`；
- 不修改 `skills/pdf2md/SKILL.md`；
- 不修改外部 PDF 包；
- 不更改现有审核状态或 `ingest_ready.csv`；
- 不标记任何既有阶段为已完成。

### 阶段 0 Step 0 证据（历史基线）

基线类型：真实运行快照 + 失败回归复现 + 现有测试缺口盘点。

本次 Aura 包实际结果：

- `ingest_ready.csv`：386 行；
- `ready / approved`：353；
- `skipped / rejected`：33；
- `not_ready`：0；
- 冲突：0；
- 数字 key：0；
- 空 key/value/evidence：0；
- 正确 canonical Markdown chunks：365；
- 页码覆盖：1-191；
- chunks 超过 384 token：0。

已复现的通用缺陷：标准 `pdf-export-chunks` 误选 `toc.md`，仅生成 6 个 chunks；直接对 manifest 指定的主 Markdown 执行相同分块逻辑可生成 365 个 chunks。因此问题位于 canonical Markdown 选择，而非分块算法本身。

已确认的候选风险：当前真实包存在 5 个重复 `record_id`；现有 `review_overrides.csv` 仅按 `record_id` 绑定，无法保证不同来源行不会被同一覆盖项同时作用。

### 阶段 0 样本/fixture 矩阵（历史基线）

| 样本/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| Aura 入库前基线 | `python3 - <<'PY'` 读取外部包 `data/ingest_ready.csv`，统计状态、空字段、数字 key、重复 ID | 得到 386/353/33/0、无空字段、无数字 key，并显式报告重复 ID | 统计无法重现，或出现 ready 空字段/数字 key | 外部包 `data/` |
| Aura 主文档分块基线 | `scripts/pdf-export-chunks /Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura` | 修复前可复现误选 TOC；直接使用 manifest 主文档可得 365 chunks | 两种路径无法区分，或主文档 chunks 不覆盖 1-191 页 | 外部包 `data/chunks.jsonl` |
| 当前抽取测试 | `python3 -m pytest -q tests/test_pdf_extract_data.py` | 当前抽取契约通过 | 现有测试失败且无法归因于计划内变更 | pytest 输出 |
| 当前 chunks 测试 | `rg -n "pdf-export-chunks|chunk_markdown|manifest.files.manual|toc.md" scripts tests` | 找到主文档选择实现和现有测试缺口 | 无法定位 canonical 选择逻辑或缺少可测试入口 | 命令输出 |
| 治理反向引用 | `rg -n "llm-first-review-workflow-hardening|review_decisions|escalation_queue|candidate_id|不自动批准|用户确认" docs skills scripts tests` | 新旧边界均可区分，无旧草案重新成为事实源 | 同一字段/状态在多个文档中出现冲突定义 | 命令输出 |

### 阶段 0 验证方式（历史基线）

- 检查本计划是否具备目标、范围、非目标、Step 0、样本矩阵、验证方式、失败/回滚边界和当前阻塞项；
- 检查 `PLAN_MAP.md` 是否同步计划状态、阶段、依赖、推荐顺序和证据链接；
- 运行 `plan-governance-cli check . --strict-readiness`；
- 运行 `git diff --check`；
- 不修改任何业务代码和外部 PDF 产物。

### 阶段 0 完成条件（历史基线）

- 新计划已登记，状态与当前阶段一致；
- LLM-first 审核边界、用户升级边界和 CLI 门禁边界没有歧义；
- `review_decisions.jsonl`、`escalation_queue.jsonl`、`candidate_id` 的兼容方向已记录；
- 真实包基线和 chunks 误读问题有可复现证据；
- 阶段 1 有明确输入、输出、失败策略和回滚边界；
- 最新独立准入复核明确达到“待实施”标准。

### 阶段 0 失败/回滚边界（历史基线）

- 本阶段只修改治理文档；失败时只需恢复本次文档变更，不接触代码、外部 PDF 包和审核产物；
- 如果兼容策略无法在不误绑定历史审核的前提下确定，阶段 1 保持 `设计中`，不得进入实现；
- 如果新策略与现有 ADR/计划冲突，先追加 ADR/迁移说明，再实施代码；
- 后续任何实际产物迁移都必须保留原 CSV、原 manifest 和备份 hash，支持按包回滚。

### 阶段 0 独立准入复核（2026-07-16，历史记录）

结论：通过，达到 `待实施` 标准。

复核依据：已核对当前 `PLAN_MAP.md`、`llm-human-collaboration-migration`、`data-ingestion-pipeline`、`pdf-extract-data-table-coverage`、ADR 0003 以及本次真实运行报告；当前阶段只修改文档，目标/非目标、真实基线、样本矩阵、验证命令、失败/回滚边界和后续阶段依赖均明确。阶段 1-5 不因阶段 0 的准入自动视为完成或待实施。

复核者：Codex（基于仓库内容、真实包运行证据和治理检查的独立准入复核）。

### 阶段 0 最新独立准入复核（历史记录）

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-16 |
| 阶段 | 阶段 0：审核契约与候选身份冻结 |
| 结论 | 通过：达到 `待实施` 标准 |
| 证据 | 已核对本计划、`PLAN_MAP.md`、相关已完成计划、ADR 0003 和 2026-07-15 真实运行报告；目标/非目标、Step 0 基线、样本矩阵、验证方式、失败/回滚边界和阶段依赖均已明确。 |
| 复核者 | Codex |

## 阶段 0 独立复核记录（历史记录）

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-16 | Codex | 阶段 0：审核契约与候选身份冻结 | 通过：达到 `待实施` 标准 | 本计划 Step 0、样本矩阵、治理检查和真实运行报告 |

## 阶段 1 详细实施记录（历史记录）

阶段 1 已完成自己的 Step 0、实施和独立验收；以下内容为历史实施细节。

### 阶段 1 Step 0：审核决策契约与兼容基线

状态：已完成，达到实施标准。

#### Step 0 证据

基线类型：公共审核契约迁移 + 真实包状态快照 + 最小兼容 fixture。

本阶段冻结以下实现前提：

- `review_decisions.jsonl` 作为新审核决策的富结构输入和审计事实源；
- `review_overrides.csv` 保持 `record_id,review_status,notes` 兼容输入，不要求旧包立即迁移；
- `candidate_id` 和 `candidate_hash` 写入 `ingest_ready.csv` 的新增末尾字段，旧字段顺序保持不变；
- LLM 自动批准只接受 `decision_basis=evidence_exact`；LLM 自动拒绝只接受 `decision_basis=rule_based_non_business`；用户决策要求 `decision_basis=user_confirmed`；
- 决策目标必须唯一匹配当前候选，`candidate_hash` 不匹配或 record_id 不匹配时拒绝运行；
- `escalation_queue.jsonl` 由 `pdf-prepare-ingest` 重新生成，只包含待用户确认的歧义、冲突、证据缺失和候选身份不稳定项；
- 动态 helper 不得直接修改 `review_decisions.jsonl`、`escalation_queue.jsonl` 或既有审核/入库门禁产物。

#### Step 0 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| LLM 明确批准 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k llm_approved` | 生成 approved/ready，审计字段完整，升级队列为空 | 缺 hash、错误 basis 或缺证据仍进入 ready | pytest 输出、临时包 `data/` |
| LLM 明确拒绝 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k llm_rejected` | 生成 rejected/skipped，保留 reason，不进入 ready | 非业务候选被导出或证据被删除 | pytest 输出、临时包 `data/` |
| LLM 歧义升级 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k escalation` | 生成 needs_review/not_ready 和 `escalation_queue.jsonl` | 歧义候选静默批准或升级队列缺证据 | pytest 输出、临时包 `data/` |
| 旧 CSV 兼容 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k legacy_override` | 旧格式仍能应用，新增审计字段为空且不改变旧列位置 | 旧包失败或字段顺序漂移 | pytest 输出、临时包 `data/` |
| 过期候选 hash | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k stale_hash` | 非零退出，不生成新的 ready 结果 | 过期决定被静默接受 | pytest 输出 |
| 动态 helper 审核门禁 | `python3 -m pytest -q tests/test_pdf_run_helper.py -k gate` | `review_decisions.jsonl` 和升级队列不能被 allowlist 授权 | 动态脚本可直接写审核决定或升级队列 | pytest 输出 |
| 既有回归 | `bash tests/test-fix-validate.sh` | 既有 record_id 位置、fix_data、CSV 兼容测试通过 | 既有修正/回滚/导出门禁失败 | shell 输出 |

#### 阶段 1 Step 0 验证方式

- 先用临时包验证富结构审核决定、兼容 CSV、hash 校验、唯一候选匹配和升级队列；
- 核对新增字段追加在 `ingest_ready.csv` 末尾，现有下游按列位置读取的脚本不变；
- 验证 LLM 不能使用错误决策依据绕过 ready 门禁；
- 验证动态 helper 不能直接写审核决定、升级队列、review override 或入库产物；
- 运行 `plan-governance-cli check . --strict-readiness` 和 `git diff --check`。

#### 阶段 1 Step 0 完成条件

- 审核决策 Schema、actor/basis 枚举、candidate hash 校验和 CSV 兼容行为已固定；
- LLM 明确批准/拒绝、歧义升级、过期决定、重复目标和旧 CSV 均有可执行 fixture；
- 旧 `record_id`、CSV 字段顺序和数据库导入边界不变；
- `escalation_queue.jsonl` 可让用户只看到真正需要确认的项目；
- 最新独立准入复核明确达到“待实施”标准。

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-16 |
| 阶段 | 阶段 1：审核决策与升级队列 |
| 结论 | 通过：达到待实施标准 |
| 证据 | 已冻结 JSONL/CSV 兼容契约、actor/basis 门禁、candidate hash 校验、升级队列和动态 helper 保护范围；样本矩阵包含明确批准、明确拒绝、歧义升级、旧 CSV、过期 hash 和既有回归命令。 |
| 复核者 | Codex |

### 阶段 1 实施证据（2026-07-16）

- `scripts/pdf-prepare-ingest` 已支持 `review_decisions.jsonl`：校验 JSONL 字段、LLM/用户 actor、decision basis、candidate_id、record_id 和 candidate_hash；不满足契约时非零退出。
- `ingest_ready.csv` 在保留既有字段顺序的前提下追加 `candidate_id`、`review_actor`、`decision_basis`、`review_rule_version`、`candidate_hash`、`reviewed_at`。
- 已生成 `data/escalation_queue.jsonl`，区分 LLM 待审核项和必须用户确认的歧义/冲突/证据缺失/身份不稳定项。
- `scripts/pdf-run-helper` 已禁止动态命令授权 `review_decisions.jsonl` 和 `escalation_queue.jsonl`。
- 项目级和用户级 `pdf2md` skill 已同步，ADR 0003 已追加审核契约增量修订；两份 skill `cmp` 一致。
- `python3 -m pytest -q`：325 passed；阶段 1 相关测试和既有 helper 测试：21 passed；`bash tests/test-fix-validate.sh`：133/133；`plan-governance-cli check . --strict-readiness`：通过；`git diff --check`：通过。
- 未运行真实 Aura 包写入流程，未修改原始 PDF、segments、Markdown 或数据库；阶段 1 的代码和契约实现已完成，独立验收结论记录在本计划末尾，计划仍保留实施中以等待后续阶段。

### 阶段 1 独立验收（2026-07-16）

结论：通过，阶段 1 的实现和协作契约满足完成条件；计划继续保持 `实施中`，等待阶段 2 单独完成 Step 0 和准入复核。

验收证据：

- `python3 -m pytest -q`：325 passed，只有既有第三方 DeprecationWarning；
- `bash tests/test-fix-validate.sh`：133/133；
- `plan-governance-cli check . --strict-readiness`：通过；
- `git diff --check`：通过；
- `cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md`：通过；
- 反向引用检查确认新契约、旧 CSV 兼容边界和历史背景表述已区分；
- 未发现真实 PDF 包、原始证据或数据库写入；
- GitNexus 变更检测未报告 HIGH/CRITICAL 风险。由于目标脚本是无扩展名可执行文件，其函数未被 GitNexus 建模，脚本影响面以现有回归和源码调用边界复核替代。

## 阶段 1 独立复核记录（历史记录）

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-16 | Codex | 阶段 0：审核契约与候选身份冻结 | 通过：达到 `待实施` 标准 | 本计划 Step 0、样本矩阵、治理检查和真实运行报告 |
| 2026-07-16 | Codex | 阶段 1：审核决策与升级队列 | 通过：达到待实施标准 | JSONL/CSV 兼容契约、审核门禁、升级队列和动态 helper 保护范围已冻结 |
| 2026-07-16 | 独立验收复核 | 阶段 1：审核决策与升级队列 | 通过：达到待实施标准 | 实现和协作契约满足完成条件；阶段 2 未启动；325 pytest、133/133 修复回归、治理严格检查、skill 同步、反向引用和未写真实 PDF/数据库证据 |

### 目标

- 让 LLM 能够对明确候选自动批准或自动拒绝；
- 只把真正歧义项写入 `escalation_queue.jsonl`；
- 保存全部审核决策及其依据；
- 保持现有 `review_overrides.csv` 兼容，避免一次性破坏旧包。

### 初步实现范围

- `scripts/pdf-prepare-ingest` 的输入适配或新增决策投影脚本；
- 审核产物 Schema 和 fixture；
- `review_status` 与 `ingest_status` 的门禁测试；
- 项目级 `skills/pdf2md/SKILL.md` 的协作契约更新；
- 更新 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`；
- ADR 0003 的增量修订或新增 ADR。

### 阶段 1 不允许的行为

- LLM 以低置信度或缺证据候选直接批准；
- 动态辅助脚本直接修改审核门禁产物；
- 通过 `record_id` 对重复身份静默批量批准；
- 把用户未处理的升级项写入 `ready`。

## 阶段 2-5 的准入提示

后续阶段的 Step 0、样本矩阵和完成条件必须在进入各阶段前分别补齐。阶段 2 已完成自己的 Step 0 和独立准入复核，当前正在实施；阶段 3-5 仍保持 `设计中`。任何公共字段或状态变化都要先同步本计划、`PLAN_MAP.md`、相关 ADR/migration 和两份 `pdf2md` skill。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| LLM 误批准模糊候选 | 明确自动批准条件；未知原因一律升级；保留证据和决策理由 | 恢复旧的用户确认门禁，重新生成 `ingest_ready.csv` |
| 新决策格式破坏旧 CSV | 先保留旧 CSV，新增 JSONL 投影层和双格式 fixture | 停用 JSONL 投影，继续使用旧 `review_overrides.csv` |
| candidate_id 迁移误绑定旧审核 | 要求 source hash、重复身份检查和迁移报告；重复时阻断 | 删除迁移映射，使用原草案重建审核状态 |
| 冒号规则误删业务记录 | 只降低自动批准资格，不直接删除证据；增加最小回归 fixture | 回退解析分类规则，重新生成草案 |
| pair_groups 配置错列 | 保留原 HTML、列号和预览 diff；失败不生成 approved 候选 | 删除包级配置，回退默认抽取 |
| chunks 再次误读 TOC | manifest 主文档硬门禁和回归测试 | 回退 chunks，不影响 Markdown 和 ingest 数据 |
| skill 与实现不同步 | 项目级 skill 先改，再同步用户级 skill，记录 hash | 恢复两份旧 skill，暂停新审核策略 |

## 验证方式（计划级）

阶段实施时按当前阶段追加命令和证据，至少包括：

```bash
python3 -m pytest -q tests/test_pdf_extract_data.py
python3 -m pytest -q tests/test_pdf_prepare_ingest.py
python3 -m pytest -q tests/test_pdf_run_helper.py
scripts/pdf-check-fixes <package>
scripts/pdf-prepare-ingest <package>
scripts/pdf-export-chunks <package>
plan-governance-cli check . --strict-readiness
git diff --check
```

真实包验收必须同时检查：

- LLM 自动决策数、用户升级数和未决升级数；
- ready 记录字段完整、无冲突、无数字 key；
- 每条 ready 可追溯到 candidate identity 和 evidence；
- 重跑前后决策绑定稳定；
- chunks 使用 manifest 主 Markdown，覆盖完整页码且不包含目录专属内容；
- 不执行数据库导入。

## 当前阻塞项

无阶段 2 阻塞项。

当前边界：candidate-v1 计算方式保持不变；candidate-v2 跨版本迁移、真实 PDF 重跑和后续抽取增强不属于阶段 2，必须在后续阶段单独补齐 Step 0 和准入复核。

## 后续独立复核记录

后续每个阶段追加独立准入或验收记录，不覆盖本节历史记录。`PLAN_MAP.md` 只链接最新有效结论。
