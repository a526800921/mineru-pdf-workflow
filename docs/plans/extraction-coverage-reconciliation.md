# 计划：结构化抽取覆盖审计与漏行闭环

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 实施中 |
| 当前阶段 | 阶段 2 |
| 计划类型 | 跨阶段抽取完整性、审核门禁和兼容性增强 |
| 最后更新 | 2026-07-18 |

本计划承接已完成的[结构化抽取表格覆盖计划](pdf-extract-data-table-coverage.md)，专门解决“源 Markdown 有行，但候选草案中没有行，审核者因此无法发现”的静默漏抽问题。旧计划的完成结论不被覆盖；本计划增加抽取后覆盖对账和审核前缺口展示。

依赖计划：[structured-data-extraction](structured-data-extraction.md)、[pdf-extract-data-table-coverage](pdf-extract-data-table-coverage.md)、[data-ingestion-pipeline](data-ingestion-pipeline.md)、[parent-context-upstream-enrichment](parent-context-upstream-enrichment.md)。

## 目标

在 LLM/用户审核候选之前，自动对账 canonical Markdown 的 HTML 表格源行与 `quick_lookup_draft.csv`，确保每个源行都有明确处置结果：已覆盖、非业务、图片/布局证据、无法解析或需要复核。审核者只需查看缺口和歧义报告，不再依赖通读 Markdown 后凭感觉发现漏行。

## 范围

- 新增独立的抽取覆盖审计 CLI，位置在阶段 6 `pdf-extract-data` 之后、阶段 7 LLM 审核之前。
- 生成包内 sidecar 报告，不修改 `quick_lookup_draft.csv` 的公共字段，不把覆盖审计字段加入候选身份。
- 对账使用独立的源行定位：PDF 页码、`source_block_id`/`table_id`、原始 HTML 行序号和源文本摘要；不得直接复用会因表头修正而漂移的候选 `row_index`。
- 对未覆盖源行生成可读的缺口队列，LLM 负责决定配置修复、手工候选、非业务拒绝或保留全文/图片证据。
- 在入库准备前增加覆盖门禁：未处置的结构化缺口不能进入最终 `ready` 批次。

## 非目标

- 不自动把每个 Markdown 行解释成业务候选；表头、分类行、脚注和布局文本可以被明确标记为非业务。
- 不自动批准候选，不替代 LLM/用户对 key/value 的语义审核。
- 不修改 PDF、`segments/`、`content_list*.json` 或 canonical Markdown。
- 不改变已有 `candidate_id`、`record_id`、`candidate_hash`、审核决定和候选 CSV 字段顺序。
- 不把 `parent_key` 推断逻辑并入覆盖审计；父级仍由阶段 8 的独立 enrichment 处理。

## Step 0 基线与证据

基线类型：真实 Aura 产物、当前抽取代码的最小复现和阶段边界审计。

- 源证据：Aura canonical Markdown 第 15 页存在 `点火控制方式 / ECU 点火`，位于 `html_table:8` 第一行。
- 结果证据：当前 Aura `quick_lookup_draft.csv` 和 `ingest_ready.csv` 均不存在该候选；`chunks.jsonl` 仍包含该文本，说明丢失发生在结构化抽取阶段。
- 代码证据：`scripts/pdf-extract-data` 在无包级 override 时执行 `data_rows = table[1:]`；当前 Aura `data/extraction_overrides.json` 没有 `html_table:8` 配置。
- 可复现命令：只读调用当前 `extract_html_table_rows`，断言 `key=点火控制方式` 的结果数量为 0；同时打印 `html_table:8` 原始第一行为 `['点火控制方式', 'ECU 点火']`。
- 安全基线：阶段 6.5 首版只写 sidecar 报告和测试 fixture，不重跑正式 Aura，不修改已有审核产物；确认报告契约后再进入真实包验证。

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
| 阶段 2 | 接入 LLM 缺口队列和覆盖门禁，临时副本验证 | 实施中 |
| 阶段 3 | Aura 真实包验证，确认不改变既有候选身份和审核复用 | 候选 |
| 阶段 4 | 更新 pdf2md skill、完成独立验收和治理收尾 | 候选 |

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

## 当前阶段

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 实施中 |
| Step 0 | 已完成：真实 Aura 漏行复现、sidecar 契约和用户确认的门禁策略已固定 |
| 样本矩阵 | 无表头 HTML 表格首行、`header_rows=0` 修复、缺口处置保留、Aura 567 源行真实审计 |
| 验证方式 | 覆盖审计定向测试、全量 pytest、Aura sidecar 统计、覆盖 gate 失败路径、skill 双份同步和治理检查 |
| 失败/回滚边界 | gate 失败时停止在 `pdf-prepare-ingest` 之前；sidecar 可删除，不影响既有候选、审核文件和 batch |
| 当前阻塞项 | 新增 105 条候选仍为 `needs_review/not_ready`，需要 LLM/用户审核；覆盖 gate 已通过，不能在审核完成前重新导出 batch |
| 最新独立准入复核 | 阶段 2 实现验证通过；5 个 coverage fixture 通过，正式 Aura gate 通过，等待新增候选审核 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-18 |
| 阶段 | 阶段 2 |
| 结论 | 通过；表号映射、语义分流、候选补充和覆盖 gate 已完成，新增候选进入审核等待 |
| 证据 | 5 个 coverage fixture 通过；Aura 567 个 HTML 源行全部有候选或明确处置；新增 105 条均为 `needs_review/not_ready`；旧 386 条身份和 batch 未变化 |
| 复核者 | Codex |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-18 | Codex | 阶段 1 | 通过；sidecar、缺口队列、gate 和回归 fixture 达到阶段完成标准 | 357 pytest passed；3 个覆盖 fixture 通过；Aura 首轮审计报告已生成 |
| 2026-07-18 | Codex | 阶段 2 | 通过；表号映射、语义分流、候选补充和覆盖 gate 已完成，新增候选进入审核等待 | Aura 567 源行、256 covered、63 个标签型 non_business、125 个 full_text_only；92 条源行补为 105 条 needs_review/not_ready；旧 386 条身份、37 条 parent_key 和既有 batch 未改变 |

## 完成条件

- 真实或 fixture 中的源行与候选对账结果可复现，不能静默漏掉第一行或无表头表格。
- 覆盖报告能用页码、表格、源文本直接定位缺口，不要求用户阅读 candidate_id。
- 新增候选默认保持 `needs_review/not_ready`，不能通过覆盖审计自动批准。
- `--gate` 能阻断未处置缺口，同时允许明确标记为 `non_business` 或 `image_only` 的行按策略通过。
- 既有候选的 `candidate_id`、`record_id`、`candidate_hash`、审核状态和 batch 集合不发生非预期变化。
- 全量 pytest、既有 fix 回归、正式包或临时副本验证、skill 双份同步和治理检查通过。

## 待确认事项

1. 是否把覆盖审计 `--gate` 设为进入阶段 8 的强制门禁；建议设为强制。
2. `non_business` 和 `image_only` 是否允许在用户/LLM 明确处置后通过；建议允许，但必须留在报告中。
3. 首版是否只覆盖 HTML 表格；建议先覆盖 HTML 表格，再扩展冒号行和图片候选，避免扩大首轮改造范围。
