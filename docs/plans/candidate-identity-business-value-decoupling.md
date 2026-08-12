# 计划：候选来源锚点稳定化与解析可观测性优化

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 已完成 |
| 当前阶段 | 阶段 3 |
| 计划类型 | 结构化候选身份、审核绑定与抽取可观测性优化 |
| 最后更新 | 2026-08-12 |
| 来源 | [150Sc 交付会话问题复盘](../issues/150sc-session-feedback.md) |

本计划只优化**后续新建解析/审核轮次**的稳定性。历史包已经完成解析和交付，保持冻结；本计划不迁移旧候选身份、审核决定、override、`ingest_ready.csv`、批次或 manifest，也不把历史包重新解释为 v2。

## 需求探索

### 已确认结论（2026-08-12）

- `ingest_ready.csv` 是由草案、审核输入、`manual_fixes.jsonl` 和 `parent_context_overrides.csv` 派生的可重建投影，不能作为人工直接编辑后的新事实源。
- 不新增通用“字段修订账本”、`review_status=superseded`、审核决定版本链、局部重抽 CLI 或自动合并重建产物。
- 已有 `manual_fixes.jsonl`、`review_decisions.jsonl`、`parent_context_overrides.csv` 分别继续承担内容修正、审核决定和父级补全职责；本计划不另造并行状态层。
- 历史 v1 包默认冻结且不迁移。v2 只用于后续新建解析轮次；若将来选择重做旧 PDF，应按新的完整审核轮次处理，不复用旧审核决定。
- “最终产物一致”指未触及缺陷的业务交付字段、`record_id`、审核放行结果和批次数量保持一致；`candidate_id`、`candidate_hash` 是审核追溯元数据，可在新 v2 包中变化。已确认的缺陷修复允许对受影响业务字段产生定向差异，并必须给出 fixture 与差异清单。
- `pair_groups` 的 LLM 批量批准不纳入本计划。它会改变审核安全策略，保留为未来独立小阶段；现行 `needs_review` 门禁不变。

### 方案取舍

选择“稳定来源锚点 + 最小版本边界”，而非历史迁移或新的修订系统：

1. 仅在新包写入 `manifest.data_contract.candidate_identity_version=2`；缺失该字段的历史包按 v1 处理，不被静默升级。
2. 将 v2 `candidate_id` 建立在 PDF 指纹与 canonical 原始来源位置上，业务语义字段不参与身份。
3. 仅修复已复现且高收益的同页 section 覆盖与 HTML 表号双轨问题；不新增局部重抽入口。

## 背景与 Step 0 证据

### 已复现问题

150Sc 会话表明：当前 `candidate_id` 把 `section_path`、`parent_key`、`key_role` 纳入 location；同页 section 修正或父级补全会改变候选身份，进而导致审核决定和父级 override 失配。`pair_groups` 还以 `row_index=原行.子行` 表示拆分，当前同源碰撞会追加内容摘要，使业务 key/value 重新进入身份。

当前实现在 `scripts/pdf-prepare-ingest` 中计算 `candidate_id`；`scripts/pdf-extract-data` 负责生成来源字段。HTML 表的 `table_id` 当前只对可抽取表递增，遇到单行表后与 canonical 原始表号错位；`build_page_section_map` 对同一页的多个 TOC 同级条目会以最后一项覆盖整页。

### 真实样本边界

- 只读样本：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150Sc/`。
- 该包的 `manifest.hash.sha256` 已记录源 PDF 指纹；包内审核、父级 override、ready 和 batch 均为历史完成产物，不作为本计划的写入目标。
- 详细问题记录只作为背景：[150Sc 交付会话问题复盘](../issues/150sc-session-feedback.md)。本计划是后续实施细节事实源。

## 目标

- 为新 v2 包提供只依赖来源位置的稳定 `candidate_id`，使 `section_path`、`parent_key`、`key_role` 与审核主身份解耦。
- 让 candidate 内容校验只覆盖需要审核的业务事实，避免纯上下文/父级修正无谓地使审核决定过期。
- 让 HTML 抽取、配置、覆盖审计使用同一套 canonical 原始表号，消除“源码表号/候选表号”双轨。
- 修复同页多个 TOC 子节互相覆盖导致的 section 归属错误。
- 对未修复缺陷的输入，保持新包业务交付结果与现有流程一致。

## 非目标

- 不迁移、重写或重新审核任何历史 v1 包。
- 不改变 `record_id` 算法、下游批次格式或数据库边界。
- 不新增审核决定版本链、`superseded` 审核状态、通用字段修订 sidecar、`force` 父级覆盖或局部重抽 CLI。
- 不放开 `pair_groups` 的 LLM 批量批准。
- 不修改 PDF、`segments/`、`content_list*.json` 或 canonical Markdown 原文。

## v2 候选身份契约（设计）

### 版本边界

- 新包在首次阶段 6 抽取时写入 `manifest.data_contract.candidate_identity_version=2`。
- 缺失该字段的包按 v1 读取；已存在审核/交付产物的历史包继续受重跑保护，不能因运行新脚本而被静默升级。
- `pdf-prepare-ingest` 必须按包声明的版本计算和校验身份；v1/v2 审核决定不得混用。

### 来源锚点

v2 的内部来源锚点为：

```text
source_anchor = source_pdf_sha256 + source_kind + raw_block_ordinal + raw_row_ordinal + pair_slot
candidate_id  = sha256("candidate-v2|" + source_anchor)
```

- `source_pdf_sha256` 来自 `manifest.hash.sha256`；缺失或不是有效 SHA-256 时，v2 不生成可审核候选。
- HTML 表的 `raw_block_ordinal` 是 canonical Markdown 中所有 `<table>` 的原始序号，包含单行/不可抽取表；`raw_row_ordinal` 是原始 `<tr>` 序号，不能受 `header_rows` 或过滤结果影响。
- Markdown 表使用其 canonical 原始表序号与行序号；冒号段落使用 canonical 行位置。
- `pair_slot` 只表示明确配置的拆分槽位；未拆分候选使用固定槽位。它属于来源位置，不是业务语义。
- 为保持既有 CSV 表头，本阶段优先复用并规范 `source_block_id`、`table_id`、`row_index` 的生成；不新增用户需要维护的来源字段。HTML 新包中 `source_block_id` 与 `table_id` 均使用同一 canonical 原始表号，`row_index` 表示原始行/拆分槽位。

`section_path`、`parent_key`、`key_role`、key/value/unit、evidence、页码、模型名、notes、置信度和状态均不得进入 `candidate_id`。页码继续用于取证与门禁，模型名继续是业务记录字段，但两者都不是来源身份输入。

### 审核内容 hash 与 record_id

```text
candidate_hash = sha256("candidate-review-v2|" + candidate_id + key + value + unit + evidence_text)
```

- `candidate_hash` 只保护需要审核的业务事实和证据；纯 section、parent、role、页码或备注变化不使它过期。
- v2 `review_decisions.jsonl` 仍保留 `record_id` 用于审计展示，但审核绑定以 `candidate_id + candidate_hash` 为准；当这两项匹配时，`record_id` 快照变化不得单独拒绝决定。实施前必须先将这一 v2 规则同步到 ADR 0003 和两份 `pdf2md` skill。
- `record_id` 保持现有算法和下游角色；本计划不使其成为稳定来源身份，也不为旧值建立迁移映射。
- 同一 v2 来源锚点出现多个候选时，禁止以 key/value 内容摘要追加后缀消歧；必须阻断并进入 `needs_review/not_ready`，由抽取配置或来源锚点修复解决。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 冻结 v2 契约、最小 fixture、版本边界和差异口径 | 本计划的需求探索已确认 | 只读基线、精确测试矩阵、独立复核 | 已完成 |
| 阶段 1 | 生成稳定原始来源锚点、candidate v2/hash v2 和碰撞阻断 | 阶段 0 独立准入通过 | 新包定向回归与业务输出不变量 | 已完成 |
| 阶段 2 | 修复同页 section 归属并统一 HTML 原始表号 | 阶段 1 完成，阶段 2 自身 Step 0 通过 | 定向 section/table fixture 与抽取覆盖审计 | 已完成 |
| 阶段 3 | 契约同步与独立验收 | 阶段 1、2 完成，阶段 3 自身 Step 0 通过 | 全量回归、skill/ADR、治理与反向引用 | 已完成 |

## 当前阶段

阶段 3：契约同步与独立验收已完成。ADR、项目级 `skills/pdf2md/SKILL.md`、用户级同步副本和治理文档已同步 v2 的版本边界、来源锚点、审核绑定、碰撞阻断、同页 section 和覆盖审计语义；本阶段未修改历史包、下游批次格式或 CLI 参数。

### 阶段证据

- `scripts/pdf-extract-data`
- `scripts/pdf-prepare-ingest`
- `scripts/pdf-audit-extraction-coverage`
- `tests/test_pdf_extract_data.py`
- `tests/test_pdf_prepare_ingest.py`
- `tests/test_pdf_audit_extraction_coverage.py`
- `tests/test_pdf_rebuild_protection.py`
- `docs/adr/0003-llm-orchestrated-dynamic-assistants.md`
- `skills/pdf2md/SKILL.md`

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| 阶段状态 | 已完成 |
| Step 0 | 阶段 1、2 已完成；阶段 3 已同步 ADR 0003 和两份 `pdf2md` skill，并完成逐字同步、反向检索和全量回归。 |
| 样本矩阵 | 见下方“阶段 3 样本/fixture 矩阵”；每项均定义命令、预期、失败判定和输出位置 |
| 验证方式 | 两份 skill `cmp`、ADR/skill 关键字反向检查、完整 pytest、`git diff --check`、GitNexus 变更检测和治理严格检查 |
| 失败/回滚边界 | 仅修改契约文档和治理记录；逐字同步、反向检查和回归均通过，未触发回滚。 |
| 当前阻塞项 | 无。 |
| 最新独立准入复核 | 通过：阶段 3 完成，计划达到已完成标准。 |

### 阶段 0 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| v2 忽略上下文字段 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k candidate_v2_context` | 改 `section_path`、`parent_key`、`key_role` 后 `candidate_id` 与 `candidate_hash` 不变 | 任一身份/hash 因上下文字段变化 | pytest 输出 |
| v2 区分真实来源槽位 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k candidate_v2_source_anchor` | 不同原始表/行/pair 槽位得到不同 ID | 不同来源 ID 相同，或业务值参与 ID | pytest 输出 |
| 同锚点碰撞阻断 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k candidate_v2_collision` | 无内容后缀；候选保持 `needs_review/not_ready` | 用 key/value 摘要生成新 ID 或静默 ready | pytest 输出 |
| 原始 HTML 表号 | `python3 -m pytest -q tests/test_pdf_extract_data.py tests/test_pdf_audit_extraction_coverage.py -k raw_table` | 单行表前后，抽取表号、配置和覆盖审计一致 | 再出现源码/候选表号错位 | pytest 输出 |
| 同页 section | `python3 -m pytest -q tests/test_pdf_extract_data.py -k same_page_section` | 同页兄弟节保留 canonical 标题行归属 | 后写 TOC 条目覆盖整页 | pytest 输出 |
| 新包业务交付回归 | `python3 -m pytest -q tests/test_pdf_extract_data.py tests/test_pdf_prepare_ingest.py tests/test_pdf_export_ingest.py` | 未触及缺陷的 fixture 业务字段、record_id、ready 与 batch 数量一致 | 业务字段/record_id/数量出现无说明变化 | pytest 输出 |
| 历史包冻结 | `python3 -m pytest -q tests/test_pdf_rebuild_protection.py` | 缺少 v2 标记且有审核产物的包不被重抽或升级 | v1 包被静默写为 v2 或覆盖产物 | pytest 输出 |

### 阶段 0 完成条件

- [ ] v2 来源锚点、candidate hash、v1/v2 版本选择和碰撞策略有最小可执行 fixture。
- [ ] 已冻结 v2 `record_id` 仅为审核展示快照、`candidate_id + candidate_hash` 为审核绑定的规则。
- [ ] 新包业务交付的一致性比较字段、允许的缺陷定向差异和输出位置已登记。
- [ ] 阶段 1 的影响分析目标、验证方式、失败边界和回滚策略已冻结。
- [ ] ADR 0003 与项目级/用户级 `pdf2md` skill 的待同步点已列明，且最新独立准入复核明确通过。

### 阶段 0 完成证据（2026-08-12）

- 已新增最小 fixture：prepare 的 v2 上下文稳定性、来源锚点区分、碰撞阻断、审核绑定和源 PDF hash 缺失；extract 的 canonical 段落行、pair 行、HTML 原始表号和同页 TOC；coverage 的 v2 原始表号；重跑保护的首次 v2 版本标记。
- 原实现运行上述新增选择器，分别得到 5、4、1、1 项失败，证明 fixture 不会把目标行为误判为已完成；既有 38 项定向回归仍全部通过。
- 阶段 1 实施范围、失败策略与不变量维持原计划：仅新包启用 v2；历史 v1 包不升级；没有来源 hash 或锚点碰撞时不生成 ready/batch。

### 阶段 1 完成证据（2026-08-12）

- 新包首次抽取写入 `manifest.data_contract.candidate_identity_version=2`；有审核/交付产物的历史包即使显式重建也不补写版本标记。
- v2 `candidate_id` 只使用源 PDF SHA-256、来源种类、原始块号、原始行号和 pair 槽位；`candidate_hash` 只绑定 candidate ID、key/value/unit/evidence。section、parent、role、页码或模型变化不再使 v2 审核决定失效；`record_id` 算法不变。
- 同一 v2 锚点不再加内容后缀，而是保留 `needs_review/not_ready` 并进入既有重复身份升级队列。
- 验证：`tests/test_pdf_prepare_ingest.py` 24/24，`tests/test_pdf_extract_data.py -k 'not same_page'` 10/10，`tests/test_pdf_rebuild_protection.py` 4/4，`tests/test_pdf_export_ingest.py` 3/3；语法编译和 `git diff --check` 通过。

### 阶段 2 完成证据（2026-08-12）

- 同一 `target_page` 有多个 TOC 条目时，页级 map 不再写该页；抽取器保留之前按 canonical Markdown 标题得到的 section 路径，而非让最后一个 TOC 条目覆盖整页。
- v2 覆盖审计直接使用 canonical HTML `table_id` 和原始 `<tr>` 行号；v1 继续保留“跳过单行表后重映射候选表号”的兼容规则。
- 验证：同页 fixture 1/1、覆盖审计 6/6、完整 `python3 -m pytest -q` 391/391 通过（仅有既有 PyMuPDF/Swig 弃用警告）。

### 阶段 3 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| skill 同步 | `cmp -s skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md` | 两份事实源逐字一致 | `cmp` 非零 | shell 退出码 |
| v2 契约反向检查 | `rg -n 'candidate-v2|candidate-review-v2|candidate_identity_version|source_anchor_collision' docs/adr/0003-llm-orchestrated-dynamic-assistants.md skills/pdf2md/SKILL.md` | ADR 与项目 skill 都明确 v2 版本边界、锚点和碰撞门禁 | 任一关键契约缺失 | rg 输出 |
| 旧规则清理 | `rg -n '内容摘要可唯一消歧|record_id 不匹配.*拒绝' docs/adr/0003-llm-orchestrated-dynamic-assistants.md skills/pdf2md/SKILL.md` | 不再把 v1 特例误述为 v2 当前规则 | 命中未限定为历史 v1 的旧规则 | rg 输出 |
| 完整实现回归 | `python3 -m pytest -q` | 391 项通过 | 任一失败 | pytest 输出 |

### 阶段 3 完成证据（2026-08-12）

- ADR 0003、项目级 skill 与用户级同步副本已写明：新包 v2、历史完成包保持 v1 且不迁移；来源锚点与审核 hash；`candidate_id + candidate_hash` 审核绑定；`source_anchor_collision` 的 `needs_review/not_ready` 阻断；同页 TOC 和 v2 覆盖审计的原始编号语义。
- `cmp -s skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md` 通过；关键 v2 契约检索通过，过时的无版本限定“内容摘要消歧”和“record_id 一律拒绝”表述均已清除。
- `python3 -m pytest -q` 通过：391 passed，5 个既有 PyMuPDF/Swig 弃用警告；`git diff --check` 通过。
- `plan-governance-cli check . --strict-readiness` 已通过：此前 `final-output-quality-gates` 的阶段 1 准入事实已存在，仅缺少可机器识别的追加式复核记录；该记录已独立补齐，不涉及解析实现或其实施范围。

### 阶段 2 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| 同页 sibling TOC | `python3 -m pytest -q tests/test_pdf_extract_data.py -k same_page` | 重复 `target_page` 不写入页级 TOC map，候选保留 canonical 标题行归属 | 后写条目覆盖整页 | pytest 输出 |
| v2 原始 HTML 表号 | `python3 -m pytest -q tests/test_pdf_audit_extraction_coverage.py -k v2` | `html_table:2`、原始 `<tr>` 行 2 直接覆盖，gate 通过 | 使用 v1 映射或误报缺口 | pytest 输出 |
| v1 覆盖审计兼容 | `python3 -m pytest -q tests/test_pdf_audit_extraction_coverage.py -k 'not v2'` | 既有跳过单行表映射仍生效 | 既有 v1 fixture 覆盖结论变化 | pytest 输出 |
| 抽取回归 | `python3 -m pytest -q tests/test_pdf_extract_data.py` | 除登记的同页失败外无回归；实施后全绿 | key/value/unit 或审核状态出现无登记变化 | pytest 输出 |

## 后续阶段范围

### 阶段 1：来源锚点与 v2 身份

预期修改范围：`scripts/pdf-extract-data`、`scripts/pdf-prepare-ingest`、相关定向测试。实施前必须分别对受改函数完成 GitNexus 上游影响分析；若风险为 HIGH/CRITICAL，先报告并停止等待确认。

- HTML、Markdown 表和段落生成稳定的 canonical 原始来源锚点。
- 新包写入 v2 版本标记；旧包缺失标记时保持 v1，绝不自动迁移。
- v2 不再通过内容摘要消歧；碰撞进入升级队列。
- 决策应用在 v2 中以 `candidate_id + candidate_hash` 绑定，record ID 快照不作为独立拒绝条件。

### 阶段 2：section 与表号可观测性

预期修改范围：`scripts/pdf-extract-data`、`scripts/pdf-audit-extraction-coverage`、相关定向测试。

- 同一物理页存在多个同级 TOC 条目时，不再用后一个条目覆盖整页；该页候选回退/保留 canonical 标题行归属。
- HTML 抽取配置、候选 `table_id` 和覆盖审计全部使用 canonical 原始表号；报告不再要求人工心算映射。
- 除已复现的 section/table ID 缺陷外，不改变业务候选的 key/value/unit、审核门禁或 batch 数量。

### 阶段 3：契约同步与独立验收

在实现结果通过后，才更新：`docs/adr/0003-llm-orchestrated-dynamic-assistants.md`、项目级 `skills/pdf2md/SKILL.md` 与 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。随后独立核对：

- v1 历史包未被写入；v2 fixture 没有混用 v1 决定。
- 新包业务交付字段与基线一致，唯一允许差异为 candidate v2 审核元数据和登记的缺陷修复项。
- `git diff --check`、定向/全量 pytest、`plan-governance-cli check . --strict-readiness`、两份 skill `cmp` 和反向引用检查全部通过。

## 影响模块或文件

- `scripts/pdf-extract-data`：原始来源锚点、HTML 表号、同页 section 归属。
- `scripts/pdf-prepare-ingest`：candidate v2/hash v2、版本选择、审核决定绑定与碰撞门禁。
- `scripts/pdf-audit-extraction-coverage`：统一原始表号后的覆盖对账。
- `tests/test_pdf_extract_data.py`：表号、同页 section、来源锚点 fixture。
- `tests/test_pdf_prepare_ingest.py`：v1/v2、上下文字段稳定性、碰撞与审核绑定 fixture。
- `tests/test_pdf_audit_extraction_coverage.py`：覆盖审计回归。
- `tests/test_pdf_export_ingest.py`：入库批次导出回归。
- `tests/test_pdf_rebuild_protection.py`：历史包保护回归。
- `docs/adr/0003-llm-orchestrated-dynamic-assistants.md`：阶段 3 才同步的 ADR 契约事实源。
- `skills/pdf2md/SKILL.md`：阶段 3 才同步的项目级 skill 事实源。
- `/Users/jafish/.claude/skills/pdf2md/SKILL.md`：阶段 3 才同步的用户级 skill 副本。

## 失败策略与回滚

- 阶段 1/2 只在 fixture 与临时新包验证；历史包和外部 150Sc 完成包不得写入。
- v2 源 PDF 指纹缺失、原始锚点不完整、碰撞或 v1/v2 混用时，停止在 `needs_review/not_ready`，不生成 ready/batch。
- 任意业务字段、record ID、审核放行数或批次数量发生未登记变化时，停止并回退本次代码/配置改动；不得以 candidate 元数据变化掩盖业务回归。
- 不实现局部重抽；后续若确有重复、量化的局部重建需求，另立计划并重新完成 Step 0。

## 验证方式

- `cmp -s skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md`
- `rg -n 'candidate-v2|candidate-review-v2|candidate_identity_version|source_anchor_collision' docs/adr/0003-llm-orchestrated-dynamic-assistants.md skills/pdf2md/SKILL.md`
- `python3 -m pytest -q`：391 passed。
- `git diff --check`。
- `plan-governance-cli check . --strict-readiness`：通过。

## 完成证据

- 阶段 0 的失败 fixture 与 v2/v1 边界证据见“阶段 0 完成证据（2026-08-12）”；阶段 1、2 的实现及定向回归证据见对应阶段完成证据。
- 阶段 3 已完成 ADR 与两份 skill 同步、反向检索、391 项全量 pytest 和 diff 校验；完整命令与输出摘要见“阶段 3 完成证据（2026-08-12）”和上方“验证方式”。
- 历史完成包未被写入；本次变更仅涉及新包解析、审核前准备、覆盖审计及其 fixture 和契约文档。

## 测试覆盖率

- 本次为脚本与 fixture 回归，未新增百分比覆盖率门槛；全量 `pytest` 覆盖 391 项测试，包含 candidate v2、历史 v1 重跑保护、HTML 原始表号、同页 TOC 和覆盖审计的定向 fixture，全部通过。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-12 |
| 阶段 | 阶段 3 |
| 结论 | 通过：阶段 3 完成，计划达到已完成标准 |
| 证据 | 独立核对 391 项 pytest、两份 skill 逐字同步、ADR/skill 关键契约和旧规则反向检索、`git diff --check`；严格治理检查已通过。 |
| 复核者 | Codex 完成验收复核 |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-08-12 | Codex | 阶段 0：来源锚点与 v2 契约冻结 | 未通过，保持设计中 | 用户确认历史包冻结、无迁移、业务交付一致性与首期范围收缩；治理严格检查已通过，现有实现仍缺 v2 fixture、版本边界和独立准入证据。 |
| 2026-08-12 | Codex 独立准入复核 | 阶段 0：来源锚点与 v2 契约冻结 | 通过，阶段 0 完成 | 11 个新增 fixture 在旧实现稳定失败，38 项既有定向基线通过；范围、非目标、版本边界、验证命令和回滚边界均冻结。 |
| 2026-08-12 | Codex 独立准入复核 | 阶段 1 | 通过：达到待实施标准 | 阶段 1 自身 Step 0、失败 fixture、验证方式、完成条件和安全边界均已核对；仅准许计划列出的脚本和测试改动。 |
| 2026-08-12 | Codex 实施记录 | 阶段 1 | 通过，阶段 1 完成 | v2 来源锚点、候选 hash、版本选择、审核绑定和碰撞门禁已经实现；24 项 prepare、10 项非同页 extract、4 项 rebuild 和 3 项 export 回归通过。 |
| 2026-08-12 | Codex 独立准入复核 | 阶段 2 | 通过：达到待实施标准 | 阶段 2 自身的同页 TOC 和 v2 覆盖审计失败 fixture 可复现，v1 兼容边界、测试命令和回滚策略已冻结。 |
| 2026-08-12 | Codex 实施记录 | 阶段 2 | 通过，阶段 2 完成 | 同页 TOC 回退与 v2 原始表号覆盖审计已实现；同页 1/1、coverage 6/6、全量 pytest 391/391 通过。 |
| 2026-08-12 | Codex 独立准入复核 | 阶段 3 | 通过：达到待实施标准 | ADR、项目级和用户级 skill 的待同步契约已定位；两份 skill 当前一致，文档修改范围、同步顺序、反向检查和完整回归已冻结。 |
| 2026-08-12 | Codex 完成验收复核 | 阶段 3 | 通过：阶段 3 完成，计划达到已完成标准 | ADR 与两份 skill 已同步；391 项 pytest、逐字同步、反向检索、diff 和严格治理检查均通过。 |

## 相关计划与证据

- [150Sc 交付会话问题复盘](../issues/150sc-session-feedback.md)
- [LLM-first 审核工作流加固](llm-first-review-workflow-hardening.md)
- [审核产物重跑保护](review-artifact-rebuild-safety.md)
- [抽取覆盖对账](extraction-coverage-reconciliation.md)
- [结构化数据抽取](structured-data-extraction.md)
- [结构化数据入库准备](data-ingestion-pipeline.md)
