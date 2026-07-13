# 计划：pdf-extract-data 表格覆盖与审核候选补全

## 计划状态

- 状态：候选
- 当前阶段：阶段 0：漏抽覆盖矩阵与审核边界冻结
- 最后更新：2026-07-12

本文档是 `pdf-extract-data` 表格覆盖修复的事实源。它承接已完成的 [structured-data-extraction](structured-data-extraction.md)、[data-ingestion-pipeline](data-ingestion-pipeline.md) 和 [pdf2md-fix 人工复核与内容修复工作流](pdf2md-fix-manual-workflow.md)，不重新打开 `pdf-merge` 的格式化契约，也不把抽取草案直接当成最终事实。

## 背景与 Step 0 证据

外部复盘报告 `/Users/jafish/Documents/work/motofind/docs/reports/pdf-extract-data-250sr-summary.md` 显示：表格人工修复已经完成，但 `pdf-extract-data` 只抽取了部分高价值表格，右手把、仪表指示灯、仪表调节、发动机转速、仪表专用开关、导航界面、日常检查和部分保养表没有进入结构化草案。

当前实现的可复核根因：

- HTML 表格抽取依赖较窄的 `key_markers`/`val_markers`，对“功能、操作、内容、状态、按键”等业务表头覆盖不足；
- 只取首行做表头，双层 `rowspan/colspan` 表头会与数据行错位；
- 没有安全的两列简表候选路径，因此非冒号、无标准关键词的操作表完全漏抽；
- 抽取结果中的 `needs_review` 和冲突不能直接批量 approve；当前入库契约要求人工审核、证据完整且无冲突后才能进入 `ready`。

Step 0 必须把外部报告中的 250Sr 页码映射到当前项目真实输出包，并建立“Markdown 表格总数 → 可抽取表格 → 已生成草案行 → needs_review/冲突 → ready”的覆盖矩阵。外部报告的行数不能直接作为当前仓库完成证据。

## 目标

- 提高高价值业务表格进入 `quick_lookup_draft.csv` 的覆盖率。
- 支持多层表头、`rowspan/colspan` 和两列简表的候选抽取，同时保留来源表格、页码和原文证据。
- 对无法确定 key/value 语义的表格生成 `needs_review` 候选，而不是静默丢弃或自动猜测。
- 保持 `record_id` 可追溯、`pdf-prepare-ingest` 的审核门禁和 `ready` 放行规则不变。
- 让人工可以从漏抽表格清单进入 `pdf-table-audit`/`pdf-table-repair`，再回到结构化抽取验收。

## 非目标

- 不批量生成 `approved`、`ready` 或入库结论。
- 不把所有两列表格无条件解释为 key/value；导航布局图、纯视觉标注和不稳定图文关系可以只保留全文/图片证据。
- 不修改 canonical Markdown、原始 segments 或 PDF；表格内容修复继续走页级人工修复契约。
- 不通过增加关键词掩盖 `rowspan/colspan` 网格错位问题。
- 不改变 `ingest_ready.csv`、`review_overrides.csv` 和 `pdf-export-ingest` 的公共状态语义。
- 不将 `manual_fixes.jsonl` 直接转换为已审核结构化事实；它只能提供来源和修复证据。

## 影响模块或文件

- `scripts/pdf-extract-data`：表头网格、列语义候选、两列简表候选和漏抽报告。
- `scripts/pdf-prepare-ingest`：只做兼容性验证；除非 Step 0 证明状态门禁需要修改，否则不改变审核流转。
- `scripts/pdf-check-fixes`：验证抽取候选的来源字段或 manifest 派生产物登记，具体是否扩展由 Step 0 决定。
- `scripts/pdf-table-fix`、`scripts/pdf-table-repair`：提供异常页、修复表格和来源证据，不承担结构化放行。
- `tests/`：新增多层表头、两列简表、无关键词表头、歧义表格和漏抽覆盖回归。
- `skills/pdf2md-fix/SKILL.md`：补充“抽取覆盖缺口 → 候选 → 人工审核”的入口说明；只有公共契约变化时才同步用户级 skill。
- `docs/PLAN_MAP.md`：登记状态、依赖和验收证据。

## 抽取候选契约（设计中）

新增或补全的草案行必须保留：

- `source_block_id`、`table_id`、`row_index`、`page_start`、`page_end`；
- `evidence_text` 和原始表头/单元格来源；
- `extraction_method`：`html_table_header`、`html_table_two_col_candidate`、`colon_line` 或其他明确方法；
- `confidence`、`status` 和 `needs_review_reason`；
- 当表头含 `rowspan/colspan` 时，保留展开前后的表头网格摘要，便于人工校对。

规则：

- 语义明确的表格可生成 `confidence=medium` 的草案，但仍遵守现有审核状态契约；
- 两列简表和新增关键词命中只能生成候选，默认 `status=needs_review`，不能自动变成 `approved`；
- 表头网格无法稳定展开、key/value 多解或存在图片列歧义时，必须生成漏抽/待复核原因；
- 只有 `review_overrides.csv` 明确批准、证据完整且无未解决冲突，`pdf-prepare-ingest` 才能输出 `ready`。

## 分阶段计划

### 阶段 0：漏抽覆盖矩阵与审核边界冻结

状态：设计中。

1. 在当前项目的春风、demo20、demo60 临时副本上统计 HTML 表格总数、已抽取表格、漏抽表格和抽取状态。
2. 将漏抽表格分为：高价值结构化候选、需要人工确认的候选、仅全文/图片证据三类。
3. 复现三类根因：关键词不命中、双层表头错位、两列简表无入口。
4. 冻结新增候选字段、`needs_review_reason` 和不自动 approve 的门禁。

准入条件：有可运行的覆盖矩阵和三个最小失败 fixture；能证明现有 `ready` 门禁没有被绕过。

### 阶段 1：表头网格与列语义候选

1. 先实现 `rowspan/colspan` 表头网格展开，禁止用第一行直接代表复杂表头。
2. 扩展业务表头词典，但关键词只作为候选信号，不作为最终语义证明。
3. 对两列简表生成 `key/value` 候选，并明确标记 `needs_review`；不适用于明显布局图或纯视觉表格。
4. 输出未覆盖表格原因，避免“没有草案行”与“表格无业务价值”混为一谈。
5. 保持原有字段和 `record_id` 稳定，增加来源字段时验证旧消费者兼容。

完成条件：p34、p40、p44、p47/p48、p55/p56、p73、p77 和 p86–p93 等代表性表格能够生成可审计候选或明确漏抽原因，且无静默列错位。

### 阶段 2：人工审核与入库门禁兼容

1. 为新增候选生成 `needs_review` 草案，不自动写 `review_overrides.csv`。
2. 人工确认文字时可使用固定 `qwen3-vl-8b` 生成证据，但 VLM不决定表格列结构或业务语义。
3. 运行 `pdf-prepare-ingest` 验证未审核候选保持 `not_ready`，只有明确批准且无冲突的记录才进入 `ready`。
4. 验证 `record_id`、冲突检测、导出和下游字段兼容。

完成条件：新增候选能走完“抽取 → 人工确认 → review override → ready/不放行”闭环，且没有批量 approve 捷径。

### 阶段 3：真实样本覆盖回填

1. 在临时副本回填春风250Sr报告中的高价值漏抽表格。
2. 复核 demo20/demo60 的跨页表格、8192候选和图片/布局表格，区分结构化候选与全文证据。
3. 统计覆盖率、needs_review 比例、冲突比例、误报和人工耗时。

完成条件：高价值漏抽表格的候选覆盖率有可复现提升，且所有新增行均有页码、表格、原文和审核状态。

### 阶段 4：独立验收

- 覆盖矩阵与真实草案行数可复现；
- 多层表头、两列简表、无关键词表头和布局图均有明确结果；
- 新增候选默认不进入 `ready`，审核后状态流转正确；
- `pdf-check-fixes`、`pdf-prepare-ingest`、`pdf-export-ingest` 和现有下游测试无回归；
- 全量 pytest、相关 shell 回归、治理和 drift 检查通过。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 扩充关键词引入错误 key/value | 关键词只生成候选，默认 `needs_review` | 删除新增草案，从 canonical Markdown 重建 |
| colspan 表头展开错位 | 保存表头网格和原始 HTML，增加逐格回归 | 标记漏抽，不生成结构化行 |
| 两列布局图被当作业务表 | 加入布局图/图片列警告，保留全文证据 | 拒绝候选，保留原始表格 |
| 漏抽补全后误入 ready | `pdf-prepare-ingest` 保持 approved/证据/冲突三重门禁 | 清除 review override，重新生成 not_ready |
| record_id 因字段补全变化 | 保留 source_row_hash 和旧映射，变更显式记录 | 保留旧记录，生成新候选，不静默覆盖 |

## 验证方式

```bash
python3 scripts/pdf-extract-data <package>
python3 scripts/pdf-prepare-ingest <package>
python3 scripts/pdf-check-fixes <package>
pytest -q
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```
