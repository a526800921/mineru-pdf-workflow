# PDF 下游交付契约

## 1. 文档定位

本文档是 PDF 输出包交付给下游系统时的文件职责和消费边界说明。

- 适用范围：MinerU 解析、`pdf2md` 人/LLM 协作修复、结构化抽取和入库前数据准备完成后的输出包。
- 本项目边界：只准备和导出数据，不直接写入数据库。
- 事实源关系：字段和状态的详细实现以项目级 `skills/pdf2md/SKILL.md`、ADR 0003 和相关专项计划为准；本文档提供下游消费视图。

## 2. 下游交付分层

下游按用途选择对应文件，不要把过程草案当成最终接口。

| 用途 | 主要交付文件 | 消费者 | 是否必需 |
|---|---|---|---|
| 原文阅读、页码追溯 | `<stem>.md`、`manifest.json` | 文档检索、审核、结构化关联 | 必需 |
| 目录展示和页码跳转 | `toc.md`、`toc_tree.json` | 前端、目录导航、章节映射 | 按需；机器跳转必须使用 `toc_tree.json` |
| 向量化前准备 | `data/chunks.jsonl` | embedding/向量索引系统 | 需要向量化时必需 |
| 入库前批次 | `data/ingest_batch.jsonl`、`data/ingest_manifest.json` | 外部入库系统 | 需要结构化入库时必需 |
| 审核和异常追溯 | `review.md`、`data/conflicts.csv`、`data/review_decisions.jsonl`、`data/escalation_queue.jsonl` | 人工审核、审计、失败回收 | 建议随包保留 |

每个 PDF 输出包在本次流程的最后一个交付阶段都应生成：

```text
data/downstream_delivery.md
```

这是下游的首个阅读入口和交付导航，不是新的业务事实源。它必须根据当前包内实际文件、`manifest.json`、`ingest_manifest.json` 和 `chunks.jsonl` 汇总生成；任何文件变更、重新抽取或重新审核后都必须重新生成。

## 3. 推荐交付包

```text
<package>/
  <stem>.md                    # canonical Markdown，正文事实源
  toc.md                       # 无锚点目录展示视图
  toc_tree.json                # 机器权威目录结构
  review.md                    # 剩余异常和人工复核清单
  manifest.json                # 文件关系、hash、页码和解析状态

  data/
    extraction_overrides.json  # LLM/人工确认的包级抽取配置，可选
    chunks.jsonl               # 向量化前纯文本块，可选
    ingest_ready.csv           # 全量候选及审核/入库状态，不直接导入
    conflicts.csv              # 冲突报告
    review_decisions.jsonl     # LLM/用户审核决定及依据
    escalation_queue.jsonl     # 仍需用户确认的项目
    ingest_batch.jsonl         # 最终 ready 批次
    ingest_manifest.json       # 批次 hash、数量和交付状态
    review_overrides.csv       # 旧包兼容输入，可选
    manual_fixes.jsonl         # 人工修复事实源，可选但建议留档
    logical_tables.jsonl       # 由 manual_fixes 派生的可选视图
```

原始 `PDF`、`segments/`、`content_list*.json` 和 `images/` 可以随包留档，用于追溯和重新验证，但不是下游结构化导入接口。

## 4. 文件消费规则

### 4.1 canonical Markdown

- 主文档路径必须读取 `manifest.json.files.markdown`，不能通过目录遍历猜测。
- `<stem>.md` 保留 `<!-- pages N-M -->` 页锚点；按页读取、结构化抽取和证据定位都使用物理页码。
- `toc.md` 只用于人工阅读或前端展示，不能作为正文或 chunks 输入。

### 4.2 目录文件

- `toc.md`：无锚点的连续展示列表。
- `toc_tree.json`：机器权威目录；`target_page` 是正文物理页，`toc_page` 是目录所在物理页，`depth` 表示层级。
- 需要页码跳转、章节映射或结构化关联时读取 `toc_tree.json`，不要从 `toc.md` 重新解析页码。

### 4.3 chunks

- `data/chunks.jsonl` 每行一个 JSON chunk，包含 `id`、`content`、`page`、`section`、`token_count`。
- chunks 已完成 Markdown 清洗、HTML 表格展开、图片占位替换和 token 限制；下游直接使用 `content` 做 embedding。
- `page` 和 `section` 用于检索结果回链原文；回链正文时读取 canonical Markdown，不读取 `toc.md`。

### 4.4 入库前数据

- `data/ingest_ready.csv` 是候选和审核门禁产物，包含 ready、not_ready、skipped 等状态，不是直接导入文件。
- `data/ingest_batch.jsonl` 只包含 `review_status=approved` 且 `ingest_status=ready` 的记录，是外部入库系统的主要输入。
- `data/ingest_manifest.json` 用于校验批次身份、输入 hash、记录数量、冲突数量和“未写入数据库”状态。
- 下游必须校验 `ingest_manifest.json` 的 hash 和计数与实际 JSONL 一致；本项目不确认外部系统是否已经入库。

### 4.5 审核和配置

- `extraction_overrides.json`：LLM/用户确认的表格列语义和包级抽取策略；下游重现抽取时应保留并读取。
- `review_decisions.jsonl`：记录审核者、决策依据、候选身份、hash 和理由。
- `escalation_queue.jsonl`：记录仍需用户确认的歧义、冲突、证据缺失或身份不稳定项；未确认项不得自行变为 ready。
- `review_overrides.csv` 仅用于旧包兼容，不是新的审计事实源。

## 5. 交付前门禁

交付给下游前至少确认：

1. `manifest.json.files.markdown` 指向存在的 canonical Markdown，且不是 `toc.md`。
2. `toc_tree.json` 的页码契约已验证；需要结构化导出时 `page_numbering.status` 必须为 `verified`。
3. `review.md` 中仍需用户确认的项目已处理，或明确随包交付并阻止对应记录进入 ready。
4. `conflicts.csv`、`ingest_ready.csv`、`ingest_batch.jsonl` 的记录集合和状态一致。
5. `ingest_manifest.json` 的输入 hash、ready 数量和批次状态与实际文件一致。
6. 未执行数据库写入；外部系统完成入库后由其维护自己的回写状态。

## 6. downstream_delivery.md 契约

### 6.1 生成时机

- 当本次 PDF 请求的最后一个交付阶段完成后生成；只完成 Markdown 时也生成，但明确标记结构化数据或 chunks 尚未生成。
- 完成 `pdf-prepare-ingest` 或 `pdf-export-ingest` 后必须重新生成，以反映最新候选数量、批次 hash 和剩余升级项。
- 发生 Markdown 修复、目录修复、配置变更、重新抽取或审核决定变化后，旧入口文件视为过期，必须重新生成。

### 6.2 最低内容

入口文件至少包含：

1. 本包状态：`markdown_ready`、`review_required`、`ready_for_downstream` 或 `blocked`。
2. canonical Markdown、`manifest.json`、`toc.md`、`toc_tree.json`、`review.md` 的相对路径和用途。
3. `data/chunks.jsonl`、`data/ingest_ready.csv`、`data/ingest_batch.jsonl`、`data/ingest_manifest.json` 的存在状态和用途。
4. ready、skipped、not_ready、冲突和待用户确认项目数量（文件不存在时标记为 `not_generated`，不得猜测为 0）。
5. chunks 数量、页码范围和最大 token（chunks 未生成时标记为 `not_generated`）。
6. 入库批次 ID、输入 hash、ready 数量和“未写入数据库”说明（批次未生成时标记为 `not_generated`）。
7. 交付前门禁结果、剩余异常、推荐下游消费顺序和生成时间。

### 6.3 消费规则

- 下游首先读取 `data/downstream_delivery.md`，再按其中的实际路径读取资源。
- 入口文件只做导航和状态汇总；具体记录以 `manifest.json`、`ingest_manifest.json`、`ingest_batch.jsonl`、`chunks.jsonl` 和审核文件为准。
- 不把入口文件本身、`review.md`、`quick_lookup_draft.csv` 或 `verification.csv` 当作正文、embedding 或入库数据。
- 如果状态是 `review_required` 或 `blocked`，下游不得把未达门禁的候选当作最终数据；应根据入口文件列出的剩余异常回到 `review.md` 或审核队列。

## 7. 不应直接消费的文件

以下文件是过程、草案或评测产物，除非下游明确需要，不应作为最终接口：

- `quick_lookup_draft.csv`
- `verification.csv`
- `fixtures_result.md`
- `table_accuracy.csv`
- `vlm_eval.jsonl`
- `segments/**/content_list*.json`

下游如果需要这些文件，应按版本和用途显式登记消费者，不要从它们推导出与本契约冲突的字段或状态。
