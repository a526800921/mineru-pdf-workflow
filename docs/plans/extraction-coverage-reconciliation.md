# 计划：结构化抽取覆盖审计与漏行闭环

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 已完成 |
| 当前阶段 | 阶段 4：更新 pdf2md skill、完成独立验收和治理收尾 |
| 计划类型 | 跨阶段抽取完整性、审核门禁和兼容性增强 |
| 最后更新 | 2026-07-19 |

本计划承接已完成的[结构化抽取表格覆盖计划](pdf-extract-data-table-coverage.md)，专门解决“源 Markdown 有行，但候选草案中没有行，审核者因此无法发现”的静默漏抽问题。旧计划的完成结论不被覆盖；本计划增加抽取后覆盖对账和审核前缺口展示。

依赖计划：[structured-data-extraction](structured-data-extraction.md)、[pdf-extract-data-table-coverage](pdf-extract-data-table-coverage.md)、[data-ingestion-pipeline](data-ingestion-pipeline.md)、[parent-context-upstream-enrichment](parent-context-upstream-enrichment.md)。

## 目标

在 LLM/用户审核候选之前，自动对账 canonical Markdown 的 HTML 表格源行与 `quick_lookup_draft.csv`，确保每个源行都有明确处置结果：已覆盖、非业务、图片/布局证据、无法解析或需要复核。审核者只需查看缺口和歧义报告，不再依赖通读 Markdown 后凭感觉发现漏行。

## 范围

- 新增独立的抽取覆盖审计 CLI，位置在阶段 6 `pdf-extract-data` 之后、阶段 7 LLM 审核之前。
- 生成包内 sidecar 报告，不修改 `quick_lookup_draft.csv` 的公共字段，不把覆盖审计字段加入候选身份。
- 对账使用独立的源行定位：PDF 页码、`source_block_id`/`table_id`、原始 HTML 行序号和源文本摘要；不得直接复用会因表头修正而漂移的候选 `row_index`。
- 对未覆盖源行生成可读的缺口队列，LLM 负责决定配置修复、手工候选、非业务拒绝或保留全文/图片证据。
- coverage supplement 候选必须从 canonical Markdown 的物理页和 `toc_tree.json` 反查层级 `section_path`；不得依赖合并后不存在于 `segments/` 的表号或 source block ID 推断章节。
- coverage supplement 候选缺少 `section_path`、`page_start` 或 `page_end` 时，必须在阶段 8 前阻断为 `not_ready`；补充候选必须能回指覆盖 sidecar 的源表行和候选行号。
- 在入库准备前增加覆盖门禁：未处置的结构化缺口不能进入最终 `ready` 批次。

## 非目标

- 不自动把每个 Markdown 行解释成业务候选；表头、分类行、脚注和布局文本可以被明确标记为非业务。
- 不自动批准候选，不替代 LLM/用户对 key/value 的语义审核。
- 不修改 PDF、`segments/`、`content_list*.json` 或 canonical Markdown。
- 不改变已有 `candidate_id`、`record_id`、`candidate_hash`、审核决定和候选 CSV 字段顺序。
- 不把 `parent_key` 推断逻辑并入覆盖审计；父级仍由阶段 8 的独立 enrichment 处理。

## 方案决策：小影响面混合处理（2026-07-19）

- 采用“自动发现与补全、人工/LLM 审核确认”的边界，不追求 coverage supplement 的全自动批准。
- 自动化范围限定为：覆盖缺口发现、物理页 + TOC 上下文补全、基于已确认表格配置生成候选草案、`needs_review/not_ready` 初始化、覆盖 gate 和身份校验。
- 语义判断、重复页面是否保留独立来源、key/value 拆分和最终批准继续留在阶段 7。
- 不修改现有候选 CSV Schema、审核决定契约、阶段 6 主抽取逻辑或数据库接口；后续若自动生成补充草案，也必须是可选的派生产物，并默认不能进入 `ready`。
- 本次 Aura 的 3 条 p46/p47 缺口作为审核阶段补充候选处理，不将一次性数据修复扩大为全流程重构。

## Step 0 证据

基线类型：真实 Aura 产物、当前抽取代码的最小复现和阶段边界审计。

- 源证据：Aura canonical Markdown 第 15 页存在 `点火控制方式 / ECU 点火`，位于 `html_table:8` 第一行。
- 结果证据：当前 Aura `quick_lookup_draft.csv` 和 `ingest_ready.csv` 均不存在该候选；`chunks.jsonl` 仍包含该文本，说明丢失发生在结构化抽取阶段。
- 代码证据：`scripts/pdf-extract-data` 在无包级 override 时执行 `data_rows = table[1:]`；当前 Aura `data/extraction_overrides.json` 没有 `html_table:8` 配置。
- 可复现命令：只读调用当前 `extract_html_table_rows`，断言 `key=点火控制方式` 的结果数量为 0；同时打印 `html_table:8` 原始第一行为 `['点火控制方式', 'ECU 点火']`。
- 安全基线：阶段 6.5 首版只写 sidecar 报告和测试 fixture，不重跑正式 Aura，不修改已有审核产物；确认报告契约后再进入真实包验证。

## 验证方式

- 覆盖审计：`scripts/pdf-enrich-coverage-context --check <package>` 和 `scripts/pdf-audit-extraction-coverage --gate <package>`；预期上下文缺失 0、未解决缺口 0。
- 入库闭环：`scripts/pdf-prepare-ingest <package>`、`scripts/pdf-enrich-parent-context <package>`、`scripts/pdf-export-ingest <package>`；预期候选身份、非 parent 字段、审核状态和 batch 集合不发生非预期变化。
- 固定回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`、`bash tests/test-fix-validate.sh`；预期分别 366 passed、133 passed/0 failed。
- 正式包边界：先备份 Aura `data/`，重生成只做可回放测试，测试 data 移入备份目录后从原备份恢复，逐文件比较恢复结果。
- 治理与契约：项目级/用户级 skill `cmp`、`plan-governance-cli check . --strict-readiness`、`--stale-days 10`、`git diff --check`。
- 失败判定：coverage gate 非零、candidate ID 集合变化、非 parent 字段变化、状态/batch 数量变化、恢复文件差异或任一固定回归失败。

## 方案与 sidecar 契约

建议新增命令：

```bash
scripts/pdf-audit-extraction-coverage <package>
scripts/pdf-audit-extraction-coverage <package> --gate
```

默认生成：

```text
<package>/data/extraction_coverage.csv
<package>/data/extraction-coverage-report.md
<package>/data/extraction_gap_queue.jsonl
```

覆盖记录最少包含：

```text
source_pdf,source_block_id,table_id,source_row_index,
page_start,page_end,source_text,candidate_count,
coverage_status,disposition,action,notes
```

`coverage_status` 采用固定枚举：

- `covered`：已有一个或多个结构化候选。
- `missing_candidate`：源行看起来具有结构化价值，但没有候选。
- `non_business`：表头、分类行、脚注等，明确不进入结构化入库。
- `unparseable`：表格结构或列语义无法安全展开。
- `image_only`：只有图片/布局证据，暂不生成结构化候选。
- `needs_review`：需要 LLM/用户判断。

覆盖审计必须区分“没有候选”和“确认不需要候选”。只有所有源行均有最终处置，且不存在未处理的 `missing_candidate`、`unparseable` 或 `needs_review`，`--gate` 才通过。

## 阶段路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| 阶段 0 | 固定真实漏行基线、sidecar 字段、枚举和样本矩阵 | 已完成 |
| 阶段 1 | 新增覆盖审计 CLI、报告和最小回归 fixture | 已完成 |
| 阶段 2：coverage supplement 上下文传递修复 | 接入 LLM 缺口队列和覆盖门禁，并修复补充候选的章节上下文传递 | 已完成 |
| 阶段 3 | Aura 真实包验证，确认不改变既有候选身份和审核复用 | 已完成 |
| 阶段 4：更新 pdf2md skill、完成独立验收和治理收尾 | 更新 pdf2md skill、完成独立验收和治理收尾 | 已完成 |

## 阶段 0 准入条件

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已完成：Aura p15 漏行可复现，缺口位于阶段 6，当前 ready 门禁未被绕过 |
| 样本矩阵 | 无表头 HTML 表格首行、带 `<thead>` 的普通表格、多层表头/`colspan`、分类行、图片/布局表格、已有候选与缺失候选混合表格 |
| 验证方式 | 覆盖审计定向测试；Aura 临时副本对账；现有 pytest、fix 回归、prepare/export 门禁和治理检查 |
| 失败/回滚边界 | sidecar 生成失败时不修改候选和审核文件；覆盖门禁失败时停止在入库准备前；删除 sidecar/命令即可回到现有抽取流程 |
| 当前阻塞项 | Aura 首轮对账曾报告 300 条缺口；修正抽取器跳过单行表造成的表号错位并完成语义分流后，92 条真实业务源行已补为 105 条 `needs_review` 候选；等待审核，不阻塞覆盖 gate |
| 最新独立准入复核 | 通过；阶段 1 sidecar、缺口队列、`--gate` 和回归 fixture 已完成 |

## 阶段 1 完成证据（2026-07-18）

- 新增 `scripts/pdf-audit-extraction-coverage`，只读取 canonical Markdown、包级抽取配置和 `quick_lookup_draft.csv`，生成覆盖 CSV、Markdown 摘要和 JSONL 缺口队列。
- 覆盖定位使用 HTML 原始行号，不复用会受表头修正影响的候选 `row_index`；不增加候选字段，不计算或修改 candidate identity。
- 新增 3 个 fixture：无表头首行漏抽、`header_rows=0` 修复后覆盖、缺口处置保留并通过 gate。
- `tests/test_pdf_audit_extraction_coverage.py`：3 passed；全量 pytest：357 passed，5 warnings；`git diff --check` 和 py_compile 通过。
- Aura 只读式首轮审计：567 个 HTML 源行，200 covered、67 non_business、300 missing_candidate；p15 `html_table:8` 第 1 行“点火控制方式 | ECU 点火”被准确列入缺口。
- 修正审计与抽取器之间的表号映射：抽取器跳过单行 HTML 表后，后续候选 `table_id` 会前移；新增回归 fixture 验证原始表号到候选表号的映射，避免把已覆盖行误报为缺口。
- 正式 Aura 的既有 `quick_lookup_draft.csv`、`ingest_ready.csv`、审核文件和 batch 未被覆盖审计修改；sidecar 仅作为过程证据和后续门禁输入。

## 阶段 2 当前进展（2026-07-18）

- 修正映射并完成语义分流后重新审计 Aura：567 个 HTML 源行，256 covered、63 个标签型 `non_business`、125 个说明型 `full_text_only`，92 条真实业务源行进入补候选流程。
- 临时副本完整展开 p15、p36–38、p41、p43/46、p64–77 和 p187–188 业务表；92 条源行生成 105 条候选，多组并列表行按 `pair_groups` 拆分，全部置为 `needs_review`。
- 正式包追加 105 条候选后，`quick_lookup_draft.csv` 由 386 行变为 491 行；原有 386 行保持不变，`ingest_ready.csv` 新增 105 条 `needs_review/not_ready`。
- 覆盖 `--gate` 已通过；正式 `ingest_batch.jsonl` 和 `ingest_manifest.json` 未变化，未把新增未审核候选交付下游；旧候选身份、审核状态、内容和 37 条 parent_key 全部保持一致。

## 阶段 2 修复子阶段：coverage supplement 上下文传递（2026-07-19）

### Step 0 基线与证据

基线类型：真实 Aura 已交付包快照 + 最小失败断言 + 物理页/TOC 反查证据。

- `quick_lookup_draft.csv` 共 485 条，其中 104 条带 `coverage_supplement`；5 条的 `section_path` 为空，但 `page_start/page_end` 已存在，页码为 66、67、76、77。
- 这 5 条已全部进入 `ingest_ready.csv` 和 `ingest_batch.jsonl`，均为 `approved/ready`；因此缺陷从候选草案穿透到最终批次，而不是 `downstream_delivery.md` 单独丢字段。
- `toc_tree.json` 可唯一反查上下文：66 为 `LCD仪表（根据配置） / 仪表指示灯`，67 为 `LCD仪表（根据配置） / 信息显示`，76/77 为 `TFT仪表（根据配置） / 仪表指示灯`。
- 合并后的 canonical 表号为 38、39、45、46，但 `segments/` 中不存在这些合并后表号；因此 source block/table ID 不能作为章节解析输入。
- 可复现失败命令：对 Aura `quick_lookup_draft.csv` 过滤 `notes` 含 `coverage_supplement` 且 `section_path` 为空，必须得到 5 条；修复后必须得到 0 条。

### 当前阶段目标

- 增加确定性的 coverage context 解析命令，按物理页和层级 TOC 补齐补充候选的 `section_path`，并保留可审计的旧/新候选身份映射。
- 在 `pdf-prepare-ingest` 增加补充候选上下文门禁，缺少章节或页段时不得进入 `ready`。
- 修复 Aura 5 条记录，重新计算受影响的 `record_id`、`candidate_id`、`candidate_hash`，迁移对应审核决定并重新导出入库批次。

### 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| TOC 层级解析 | `python3 -m pytest -q tests/test_coverage_context.py` | 66/67/76/77 得到预期章节；未知页返回阻断结果 | 章节为空、兄弟章节串接错误或按 source block ID 猜测 | pytest 输出 |
| 补充候选上下文门禁 | `python3 -m pytest -q tests/test_pdf_prepare_ingest.py -k coverage_context` | 缺上下文的 supplement 不能 ready；完整字段可正常 ready | 空 `section_path` 进入 ready 或普通候选被误阻断 | pytest 输出 |
| Aura 失败回归 | `python3 - <<'PY'` 读取 Aura 草案并断言 5 条缺失 | 修复前红、修复后 0 条 | 仍有缺失或修改非目标候选 | 命令输出 |
| Aura 修复后批次 | `scripts/pdf-prepare-ingest <package>`、`scripts/pdf-enrich-parent-context <package>`、`scripts/pdf-export-ingest <package>` | 5 条新身份均有章节、审核决定和批次记录，ready 数量保持 452 | 旧决定误应用、candidate hash 不匹配、批次漏行或重复 | package/data |

### 验证方式、失败与回滚边界

- 先在合成 fixture 上验证 resolver、身份迁移和 ready 门禁，再处理正式 Aura 包。
- 只修改输出包内派生产物和项目 CLI/测试/治理文档；PDF、`segments/`、`content_list*.json`、canonical Markdown 保持只读。
- 章节修复会改变受影响记录的 `record_id`、`candidate_id` 和 `candidate_hash`；旧审核决定不得静默复用，必须通过稳定源位置生成旧/新映射并保留迁移报告。
- 任一候选身份、审核 hash、批次数量或来源位置校验失败，恢复执行前的草案、审核、入库和批次文件，不交付新批次。

### 当前阶段准入复核

| 字段 | 内容 |
|---|---|
| 准入状态 | 待实施 |
| Step 0 | 已完成：Aura 5 条空 `section_path` 记录、TOC 反查结果、合并表号与 segments 边界均已复现 |
| 样本矩阵 | resolver、ready 门禁、Aura 5 条回归、身份迁移和批次重导 |
| 验证方式 | 定向 pytest、Aura 只读失败断言、prepare/enrich/export、全量 pytest、治理检查、`detect_changes()` |
| 失败/回滚边界 | 只触及派生产物；身份迁移失败整组恢复，不改 PDF、segments、canonical Markdown 或数据库 |
| 当前阻塞项 | 无；5 条上下文和 3 条第 46–47 页业务源行均已处理并完成用户确认，455 条 approved/ready 已重新导出 |
| 最新独立准入复核 | 2026-07-19，阶段 2 上下文传递修复，结论“通过：达到待实施标准”，复核者 Codex；证据为上述 Aura 快照、最小失败断言和回滚边界 |

### 实施中追加证据（2026-07-19）

- `pdf-enrich-coverage-context --apply` 已将 Aura 5 条空 `section_path` 补为物理页对应的层级 TOC 路径。
- 5 条受影响候选的 `candidate_id`、`record_id`、`candidate_hash` 已通过稳定来源位置迁移；3 条对应的 `parent_context_overrides.csv` 身份也已同步迁移。
- 重新运行 `pdf-audit-extraction-coverage --gate` 暴露 3 条独立缺口：`html_table:23` 第 3/4 行（p46）和 `html_table:25` 第 3 行（p47）。复核确认三行均为真实业务操作，且同文本的前页候选不能替代当前页来源身份；已按 coverage supplement 补齐当前页候选并重跑 gate，通过后重新导出 452 条既有 ready 批次。

## 当前阶段

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已完成：Aura 漏行、coverage supplement 上下文、身份迁移、coverage gate 和正式包可回放备份边界均已固定 |
| 样本矩阵 | HTML 首行漏抽、表号映射、TOC 上下文、补充候选门禁、Aura 5 条修复、3 条业务补充、正式包备份/重生成/恢复 |
| 验证方式 | 定向 pytest、全量 pytest、133 项固定回归、Aura coverage check/gate、prepare/enrich/export、备份逐文件恢复、skill 双份同步、治理检查 |
| 失败/回滚边界 | gate 或身份校验失败时不交付；正式 parent_key 先备份，测试生成的 data 移入备份，恢复后逐文件比对；PDF、segments、canonical Markdown 和数据库未修改 |
| 当前阻塞项 | 无；正式调整 parent_key 已按用户确认作为业务基线保留，重生成结果仅作为可回放测试并已清理出正式 data/ |
| 最新独立准入复核 | 通过；阶段 4 已完成，计划关闭 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-19 |
| 阶段 | 阶段 4：更新 pdf2md skill、完成独立验收和治理收尾 |
| 结论 | 通过：阶段 4 已完成，计划关闭 |
| 证据 | 全量 pytest 366 passed；固定回归 133/133；Aura coverage context 0 缺失、gate 0 未解决缺口；正式包重生成测试候选 ID/非 parent 字段/状态/batch 无差异，备份恢复逐文件 0 差异；两份 skill 和严格治理检查通过 |
| 复核者 | Codex |

## 独立验收发现（2026-07-19，未通过）

- 复核范围：Aura 临时副本执行 `pdf-enrich-coverage-context --check`、`pdf-audit-extraction-coverage --gate`、`pdf-prepare-ingest`、`pdf-enrich-parent-context`、`pdf-export-ingest`。
- 通过项：coverage context 缺失 0 条；覆盖审计 567 源行、348 covered、未解决缺口 0；临时包 488 行、455 ready、33 skipped、0 not_ready、batch 455；候选 ID 唯一。
- 未通过项：临时重建后的 ready `parent_key` 为 104 条，正式 batch 为 394 条；当前 `parent_context_overrides.csv` 仅 104 条，正式 `ingest_ready.csv` 另有 315 条非空 parent_key 无法由当前 draft/override 重建。
- 结论：阶段 2 的 coverage supplement 上下文修复本身有效，但本计划暂不能完成独立验收；需要单独明确这 315 条 parent_key 的事实源或回放策略，不得在本计划中猜测补齐。

## 可回放验证证据（2026-07-19）

- 备份目录：`/Users/jafish/Documents/work/motofind/春风_150_Aura/backup/parent-key-replay-20260719T155439`。
- 正式基线：`ingest_ready.csv` 488 行、全量 417 条 parent_key、ready 455 条、ready parent_key 394 条、batch 455 条；`ingest_ready.csv` SHA-256 为 `4dd62cb3d19cdbe12a072018f6216c370fe177cca37d36e434bfdad39acc6654`。
- 测试链路：`pdf-enrich-coverage-context --check`、`pdf-audit-extraction-coverage --gate`、`pdf-prepare-ingest`、`pdf-enrich-parent-context`、`pdf-export-ingest` 全部通过。
- 测试结果：重生成后 488 行、455 ready、33 skipped、0 not_ready、batch 455；candidate_id 缺失 0、新增 0、非 `parent_key` 字段差异 0；测试 parent_key 为 104 条，符合当前 draft/override 可重建范围。
- 恢复结果：测试 `data/` 已移入 `backup/.../generated-data` 留档；原始备份恢复后缺失文件 0、额外文件 0、内容差异 0，正式 `ingest_ready.csv` SHA-256 恢复为 `4dd62cb3d19cdbe12a072018f6216c370fe177cca37d36e434bfdad39acc6654`。
- 结论：正式已调整 parent_key 作为当前业务基线保留；重生成结果仅用于验证，不进入正式交付。

## 阶段 3/4 完成证据（2026-07-19）

- 阶段 3 Aura 正式包可回放验证完成：coverage check、coverage gate、prepare、enrich、export 全部成功；重生成的 488 条候选与正式基线 candidate_id 集合一致，非 `parent_key` 字段差异 0，状态为 455 ready/33 skipped/0 not_ready，batch 455。
- 阶段 4 skill 与治理收尾完成：项目级/用户级 `pdf2md` skill 一致；`plan-governance-cli check . --strict-readiness`、`--stale-days 10`、`git diff --check` 通过。
- 全量验证：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` 为 366 passed；`bash tests/test-fix-validate.sh` 为 133 passed、0 failed。
- 计划范围边界：正式已调整的 parent_key 不从本次 draft/override 重新猜测；其业务基线已备份并恢复，不影响本计划对 coverage context、覆盖 gate、候选身份和批次状态的验收。

### 用户确认的可回放验证边界（2026-07-19）

- 用户确认正式 Aura 当前 `ingest_ready.csv` 中的 `parent_key` 已经过业务调整，应作为本轮对比基线保留。
- 本轮重生成只用于验证 coverage context、覆盖 gate、prepare/enrich/export 的可执行性和批次状态，不把重生成结果直接视为正式交付。
- 执行前备份正式包 `data/`；测试结束后将测试生成的 `data/` 移入备份目录留档，再从原始备份恢复正式 `data/`，并逐文件核对恢复结果。
- 该验证不授权修改 PDF、segments、canonical Markdown、审核决定或下游仓库；测试产物不得替代已确认的正式 parent_key。

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-18 | Codex | 阶段 1 | 通过；sidecar、缺口队列、gate 和回归 fixture 达到阶段完成标准 | 357 pytest passed；3 个覆盖 fixture 通过；Aura 首轮审计报告已生成 |
| 2026-07-18 | Codex | 阶段 2 | 通过；表号映射、语义分流、候选补充和覆盖 gate 已完成，新增候选进入审核等待 | Aura 567 源行、256 covered、63 个标签型 non_business、125 个 full_text_only；92 条源行补为 105 条 needs_review/not_ready；旧 386 条身份、37 条 parent_key 和既有 batch 未改变 |
| 2026-07-19 | Codex | 阶段 2：coverage supplement 上下文传递修复 | 通过：达到待实施标准；实施后 3 条业务缺口已补候选、完成用户确认并通过 gate | Step 0、TOC 反查和回滚边界齐备；363 pytest passed、133 项固定回归通过；Aura coverage context 0 缺失，coverage gate 0 未解决缺口，455 条 ready batch 已重导 |
| 2026-07-19 | Codex | 阶段 4：更新 pdf2md skill、完成独立验收和治理收尾 | 通过：阶段 4 已完成，计划关闭 | 全量 366 passed；固定回归 133/133；Aura 可回放 e2e、逐文件恢复、skill 同步和严格治理检查通过 |

## 完成条件

- 真实或 fixture 中的源行与候选对账结果可复现，不能静默漏掉第一行或无表头表格。
- 覆盖报告能用页码、表格、源文本直接定位缺口，不要求用户阅读 candidate_id。
- 新增候选默认保持 `needs_review/not_ready`，不能通过覆盖审计自动批准。
- coverage supplement 候选必须具有非空 `section_path`、`page_start`、`page_end`，且能通过 sidecar 源表行和候选行号回溯。
- 覆盖审计重新运行后发现的其他未处置缺口不能借上下文修复绕过；必须回到阶段 7 处理并重新通过 `--gate`。
- `--gate` 能阻断未处置缺口，同时允许明确标记为 `non_business` 或 `image_only` 的行按策略通过。
- 既有候选的 `candidate_id`、`record_id`、`candidate_hash`、审核状态和 batch 集合不发生非预期变化。
- 全量 pytest、既有 fix 回归、正式包或临时副本验证、skill 双份同步和治理检查通过。

## 待确认事项

1. 是否把覆盖审计 `--gate` 设为进入阶段 8 的强制门禁；已采用强制门禁。
2. `non_business` 和 `image_only` 是否允许在用户/LLM 明确处置后通过；建议允许，但必须留在报告中。
3. 首版是否只覆盖 HTML 表格；建议先覆盖 HTML 表格，再扩展冒号行和图片候选，避免扩大首轮改造范围。
4. 是否完全自动批准 coverage supplement；不采用。维持小影响面混合模式，自动生成草案但保留阶段 7 人工/LLM 确认。

## Test Coverage（测试覆盖率证据）

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`：366 passed，5 warnings。
- `bash tests/test-fix-validate.sh`：133 passed，0 failed。
- Aura 正式包可回放测试：coverage context 0 缺失、coverage gate 0 未解决缺口、488 行、455 ready、33 skipped、0 not_ready、batch 455；candidate ID 缺失/新增 0，非 parent 字段差异 0。
- 正式 data 恢复：缺失文件 0、额外文件 0、内容差异 0，`ingest_ready.csv` SHA-256 恢复为 `4dd62cb3d19cdbe12a072018f6216c370fe177cca37d36e434bfdad39acc6654`。
- `plan-governance-cli check . --strict-readiness`、`--stale-days 10`、`git diff --check` 和 skill 双份同步校验：通过。
