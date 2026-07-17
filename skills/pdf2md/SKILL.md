---
name: pdf2md
description: Use when the user wants to convert a PDF to Markdown, parse a PDF, review or repair PDF conversion results, extract structured data from a PDF output package, run the MinerU PDF workflow, or prepare/export reviewed PDF data. Triggers on PDF conversion, PDF-to-Markdown, MinerU parsing, .pdf paths, output package validation, review.md, table repair, TOC repair, pdf-auto, pdf-extract-data, pdf-prepare-ingest, or pdf-export-ingest.
---

# PDF to Markdown

本 skill 是项目级 PDF 工作流事实源，用户只需与 `pdf2md` 协作；项目执行层使用 CLI，不新增 MCP Server 或兼容层。

同步目标：`/Users/jafish/.claude/skills/pdf2md/SKILL.md`。涉及本文件契约时，先更新项目级文件，再同步用户级文件；无法同步时不得宣称完成，并在计划风险中记录原因。

## 使用规则

- 严格按阶段 0～9 推进。每阶段先完成“完成条件/门禁”，再进入下一阶段；不得仅因产物已存在就跳过校验。
- 每轮先说明：发现了什么、证据在哪一页/条记录、需要谁确认、确认后更新哪些产物。
- 用户确认 PDF 事实、表格关系、列语义和歧义候选；LLM 读取产物、编排 CLI、维护包内配置、执行验证和汇报。
- PDF、`segments/`、`content_list*.json` 始终只读。只允许修改输出包内派生产物。
- 产物默认写入 PDF 所在目录；不复制 PDF，不使用旧的 `<stem>-output/` 或 `merged.md` 约定。
- 当前边界是入库前准备，不直连数据库；CLI-only，不维护 MCP 工具兼容层。

## 交付等级

用户没有指定更高目标时，在达到目标等级后停止：

| 目标 | 必须完成的阶段 | 最终主要产物 |
|---|---:|---|
| Markdown | 0～3 | `<stem>.md`、`manifest.json`、`review.md` |
| 复核后的 Markdown | 0～5 | canonical Markdown、TOC 三件套、修复记录、manifest |
| 结构化草案 | 0～6 | `data/quick_lookup_draft.csv`、`verification.csv` |
| 入库候选 | 0～8 | `data/ingest_ready.csv`、`conflicts.csv` |
| 最终下游交付 | 0～9 | `downstream_delivery.md`、可选 chunks/入库批次 |

---

## 阶段 0：确认任务和工作区

### 目标与进入条件

确认 PDF、项目根目录、输出包目录和交付等级。此阶段不运行解析 CLI。

### 本阶段 tool

文件读取、路径校验和 hash 工具；不运行解析 CLI。

### 操作与 tool

1. 读取用户目标，选择交付等级。
2. 定位 `<project>`：优先使用 `PDF2MD_PROJECT_ROOT`；否则从当前目录向上查找同时包含 `scripts/pdf-auto` 和本文件的目录；再校验登记路径 `/Users/jafish/Documents/work/mineru-pdf-workflow`。`git rev-parse --show-toplevel` 只能作为候选，不能单独作为项目根目录。
3. 确认 PDF 是绝对路径且可读；将 `<package>` 固定为 PDF 所在目录。
4. 记录输入 PDF hash、绝对路径和本轮交付目标。

所有脚本通过 `<project>/scripts/<command>` 调用，不假设用户级 skill 目录有项目脚本。

### 产物、门禁与失败处理

- 成功：`<project>`、`<pdf>`、`<package>` 和交付等级明确。
- 失败：停止并报告缺失路径；不得在错误仓库创建或改写公共 `pdf-*` 脚本。
- 只有 G0 通过，才能进入阶段 1。

---

## 阶段 1：准备 ModelPad 和 MinerU 解析环境

### 目标与操作顺序

确认 PDF 服务可用，再创建或复用分段产物。

1. 检查 ModelPad API，默认 `http://127.0.0.1:9999`。
2. 查询 `pdf` 模型；只有 `status=running` 且返回数字 `port` 时，才使用 `http://127.0.0.1:<port>` 作为 MinerU API 地址。
3. 服务未运行时，由脚本通过 ModelPad 启动 `pdf` 模型，等待就绪；脚本结束只停止本次启动的服务。已运行服务只复用，不停止。
4. ModelPad API 不可用或启动失败时，失败并输出诊断；不得扫描相邻端口猜测 PDF 服务。
5. 没有有效 `<package>/segments/` 时运行：

   ```bash
   <project>/scripts/pdf-seg <pdf>
   ```

### tool 和配置

- `pdf-seg`、`pdf-auto`、`pdf-rerun` 使用 ModelPad 托管的 PDF 服务。
- MinerU CLI 与服务保持同版本，当前统一为 MinerU `3.4.4`。
- 可选变量：`MODELPAD_API_BASE`、`MODELPAD_PDF_MODEL_ID`、`MODELPAD_PDF_START_TIMEOUT`。
- 机器调用设置 `PDF_AUTO_JSON=1`，不改变文件输出契约。

### 产物、门禁与失败处理

- `pdf-seg` 默认写入 `<package>/segments/`，并建立 PDF hash、页数、分段配置和关键参数基线。
- 旧格式、旧多页目录、缺页或配置不匹配时，脚本只清理 `segments/` 下的解析生成物并按当前配置重建。
- G1 要求服务可用、输入基线可建立；未通过时停止，不进入阶段 2。
- 人工确认：本阶段不需要业务确认；服务、版本或输入基线异常时停止。

---

## 阶段 2：自动解析和基础 Markdown

### 目标与操作顺序

生成 canonical Markdown、目录产物、manifest 和自动复核报告。

### 本阶段 tool

`pdf-auto`；如缺少有效 segments，先使用阶段 1 的 `pdf-seg`。机器调用设置 `PDF_AUTO_JSON=1`。

已有有效 `segments/` 时可跳过阶段 1 的 `pdf-seg`，直接运行：

```bash
<project>/scripts/pdf-auto <pdf> <package>/segments
```

需要机器可读摘要时使用：

```bash
PDF_AUTO_JSON=1 <project>/scripts/pdf-auto <pdf> <package>/segments
```

`pdf-auto` 完成段合并、TOC 处理、覆盖率检查、页级质量 fallback 判定和 review 生成。可选参数为 `threshold`、`rerun_effort`、`merge_output`；默认覆盖率阈值为 `0.82`，高质量场景通常使用 `MINERU_RERUN_EFFORT=high`。

### 默认输出包

```text
<package>/
  <pdf>.pdf                 # 原始输入，只读
  <stem>.md                 # canonical Markdown，含页面/段锚点
  toc.md                    # 无锚点展示目录
  toc_tree.json             # 机器权威目录结构
  review.md                 # 自动复核和待确认事项
  manifest.json             # 状态、hash、页码和文件关系
  segments/                 # 分页解析候选，含可选 -fallback 页
  images/                   # 预留图片产物
  data/                     # 阶段 6～8 生成的结构化产物
```

默认规则：`pdf-auto` 合并到 `<package>/<stem>.md`；人工复核清单为 `<package>/review.md`。`manifest.files.markdown` 是 canonical Markdown 的唯一机器入口。

### 结果解读和门禁

- `all_passed/passed`：验证通过并已合并。
- `needs_review`：已合并但必须读取 `review.md`；不得把它当作失败或自动批准。
- `error/failed`：脚本或输入错误，停止后续阶段。
- G1 通过后才进入阶段 3；G2 不通过不得进行结构化抽取。
- 人工确认：本阶段不批准复杂表格语义；所有异常留给阶段 3 分类。

---

## 阶段 3：质量分类、按页取证和 fallback

### 目标与操作顺序

先读取 `manifest.json`、`review.md` 和 canonical Markdown，再按页分类异常，不要直接修改结果。

1. 对每个异常页记录页面类型、触发信号、原始/fallback 参数、质量指标、执行状态和 `selected`。
2. 将页面分类为 `text`、`toc`、`image_or_sparse`、`table` 或 `no_text_layer`。
3. `text` 页低覆盖率才考虑 high 重跑；目录、表格、图片/稀疏页通常 `review_only`；无文本层跳过文字覆盖率验证。
4. 需要补充视觉证据时，最后才按需运行 VLM；VLM 输出只作证据，不作最终表格事实。

### tool

- `pdf-read-page <package> <page> [page_end]`：优先用逐页锚点精确读取，缺失时回退段级锚点。
- `pdf-search-content <package> <query>`：在 canonical Markdown 和 `quick_lookup_draft.csv` 中检索页码、章节和片段。
- `pdf-rerun`：只定点重跑异常页；目录不匹配时先全量 `pdf-seg`，不静默删除整包。
- `pdf-validate`：覆盖率和结构校验由 `pdf-auto` 编排；只把校验结果作为证据，不把低覆盖率直接解释为文字解析失败。
- `pdf-eval-tables <package>`：只读生成 `data/table_accuracy.csv`。
- `pdf-eval-vlm <package>`：可选生成 `data/vlm_eval.jsonl`，固定 `qwen3-vl-8b`；默认由 ModelPad 管理服务生命周期。

### 自动 fallback 和 review 规则

- fallback 只重跑异常页，通常使用 `effort=high` 和 `--image-analysis false`，原始页和 `-fallback` 候选并存。
- `manifest.page_fallback` 记录触发信号、参数、指标、状态和 `selected`；合并按 `selected` 选择同源候选，不只替换 Markdown。
- 原生 PDF 表格文字与 MinerU HTML 逻辑单元格不一致时产生 `native_table_text_missing`，记录 `missing_text`、`detector` 和指标；无法可靠定位、无文本层或不确定时进入 review，不覆盖原始结果。
- `review.md` 必须暴露 `selected=review`、`fb_status=failed` 的页级质量问题，以及无法唯一归属物理目录页的 `toc_unassigned` 条目；`selected=fallback` 已采纳，不列为待复核。

### 门禁

每个异常页必须有分类、证据和下一步。需要用户确认的项目按以下格式提交：

```text
【需要确认】<标题>
问题：<一个可判断的问题>
PDF 证据：第 <页码> 页；<原文/截图/表格范围>
当前候选：<Markdown、表格或结构化候选>
请确认：确认 / 修改为…… / 拒绝 / 保留待复核
确认后更新：<manual_fixes.jsonl | extraction_overrides.json | review_decisions.jsonl>
```

### 产物

`manifest.json` 中的页级质量状态、`review.md` 的质量/目录复核段，以及可选的 fallback、表格评测和 VLM 证据。

G2 通过后，才能进入阶段 4；如果用户只要未经人工修复的 Markdown，阶段 3 完成后生成交付入口并停止。

---

## 阶段 4：人工/LLM 修复内容和表格事实

### 目标与边界

修复 TOC、表格、缺失文字和章节归属，并保留可审计事实。LLM 先组合现有 CLI，再考虑一次性动态辅助脚本。

自动处理只限于有页锚点、来源 hash、预期命中次数和低风险确定性规则的内容。复杂表头、列语义、`rowspan/colspan`、跨页关系、扫描空页和图片表格必须逐项人工确认；不得为了提高自动修复率猜测。

### tool 和文件职责

- `pdf-table-repair`：生成候选、证据和局部修复范围。
- `pdf-table-fix`：提供缺失文字、原生 PDF 和 HTML 表格证据；不自动猜缺失文字落位。
- `pdf-run-helper`：动态脚本的统一事务包装器。
- `manual_fixes.jsonl`：内容/表格事实修复记录。
- `data/extraction_overrides.json`：列语义和包级抽取策略，不能与修复记录混用。
- `logical_tables.jsonl`：可选的 `manual_fixes.jsonl` 派生视图；只有存在独立下游消费者时生成，不能成为第二个事实源。

`content_list*.json`、原始 segments 和 PDF 不可修改。canonical Markdown 原地更新，不生成 `*-fixed.md`。空扫描页只有在人工确认的 `rebuild_table/cross_page_table` 记录中可使用 `allow_empty_page=true`，并按页锚点幂等写入。

### 动态辅助脚本安全边界

只对明确、有限、可验证且现有 CLI 无法安全完成的操作生成临时脚本。脚本默认放临时目录，不直接写入通用 `scripts/`。

```bash
<project>/scripts/pdf-run-helper \
  --package <package> \
  --allow <package-relative-derived-file> \
  --validate-command '["<project>/scripts/pdf-check-fixes", "<package>"]' \
  --log <outside-package-summary> \
  -- <dynamic-command>
```

执行必须具备：全组备份和 hash、`dry-run`、allowlist、页锚点/record_id/来源 hash 或等价定位、幂等、apply 后只读验证和整组回滚。dry-run 有写入、apply 越权、验证失败或验证阶段写入时恢复快照。

allowlist 只能包含包内派生产物；禁止授权 PDF、segments、`content_list*.json`、目录以及 `review_decisions.jsonl`、`escalation_queue.jsonl`、`review_overrides.csv`、`ingest_ready.csv`、`conflicts.csv`、`ingest_batch.jsonl`、`ingest_manifest.json` 等审核/入库门禁产物。

### 门禁

用户确认项必须已经明确列出，未确认或无法安全判断的内容保持 `needs_review/not_ready`。阶段 4 不直接生成结构化字段修正，结构化语义进入阶段 6/7。进入阶段 5 前必须有修复记录、来源 hash 和回滚结果。

### 产物

`manual_fixes.jsonl`、更新后的 canonical 修复候选和 `pdf-run-helper` 事务摘要；如有独立消费者，才生成由修复记录派生的 `logical_tables.jsonl`。

---

## 阶段 5：同步 canonical Markdown、TOC 和 manifest

### 目标与操作顺序

将 Markdown、目录、修复记录和 manifest 作为一个同步发布单元。

1. 修复后运行 `pdf-merge <package>/segments` 或按页回填 canonical Markdown。
2. 同步 `<stem>.md`、`toc.md`、`toc_tree.json`、`review.md`（结论变化时）、`manual_fixes.jsonl` 和 `manifest.json`。
3. 登记 `manifest.files.toc`、`manifest.files.toc_tree` 及 TOC hash；不得只修改主 Markdown 或只修改展示目录。
4. 运行 `pdf-check-fixes <package>`，再用 `pdf-read-page` 复核锚点和目录归属。

### 本阶段 tool

`pdf-merge`、`pdf-check-fixes`、`pdf-read-page`；这些工具只验证和同步派生产物，不修改原始 segments。

### 产物

`<stem>.md`、`toc.md`、`toc_tree.json`、`review.md`、`manual_fixes.jsonl` 和 `manifest.json` 的同步发布单元。

### 目录和页码契约

- `doc.md`/`<stem>.md`：正文事实源，保留 `<!-- pages N-M -->` 和逐页锚点；锚点使用 PDF 物理页码。
- `toc.md`：无锚点连续展示列表，只用于人工阅读/前端渲染；展示印刷页码但不重新猜测页码。
- `toc_tree.json`：机器权威目录；每条含 `title`、`target_page`、`toc_page`、`depth`，可选 `printed_page`。`target_page` 必须是正文物理页码，结构化抽取用它做 section 映射。
- 目录只按条目原生文本实际出现的物理目录页归属；短标题不能命中更长词；无法唯一归属时进入 review，不静默猜测。内置大纲只用于解决重复标题，不把字母索引当伪目录。

`manifest.page_numbering` 至少记录：`physical_page_basis=pdf_1_based`、`mapping_type`、`status`、必要的 offset 和 evidence。`status=verified` 才安全；`proposed`、`needs_review` 或旧包缺失该块都阻断 ready/导出。

### 门禁和失败处理

`pdf-check-fixes` 校验 page_numbering schema、枚举、offset 完整性、`manifest.files.toc`/`toc_tree`、TOC hash 和修复记录。失败时不得进入阶段 6；原始 segments 和 `content_list*.json` 仍保持只读。

### 人工确认

无法唯一归属的 TOC 条目和 `page_numbering.status != verified` 的页码映射必须由用户确认；确认前不得进入 ready/导出。

---

## 阶段 6：从 canonical Markdown 生成结构化候选

### 目标与 tool

只有阶段 5 的 Markdown、TOC、修复记录和 manifest 通过后，才运行：

```bash
<project>/scripts/pdf-extract-data <package>
```

脚本只做通用 HTML 网格展开、来源定位、候选生成和状态计算；LLM/人工负责业务列语义。具体 PDF 的列规则只能写入 `<package>/data/extraction_overrides.json`，不能硬编码到通用脚本。

### 人工确认

复杂表格的列语义、业务 key/value/unit 和多种合理解释留给阶段 7；本阶段只生成候选，不批准业务事实。

### 抽取规则和产物

生成：`data/quick_lookup_draft.csv`、`verification.csv`、`fixtures_result.md`。候选至少保留来源 PDF、model、section_path、key/value/unit、page_start/page_end、evidence_text、confidence、status、notes，以及 `source_block_id`、`table_id`、`row_index`、`parent_key`、`key_role`。

支持包内 `pair_groups` 配置；每组用 `key_column` 和 `value_columns` 指定独立 key/value，一行多组拆成子行，默认 `needs_review`，列越界或配置不完整时跳过，不猜列。

冒号行先分类为 `business_candidate`、`non_business` 或 `ambiguous`；明确 URL、电话、警告和脚注过滤，`ambiguous` 保留为待审核候选。`■/▲` 等标记应按配置进入证据/备注，不得未经确认成为业务 key；`policies.numeric_key=skip` 只在包级配置中显式启用。

`key_role=marker/spec_value` 不参与冲突检测；`local_label` 必须有表格或块上下文；冲突 identity 使用 model、section、页段、块、表格、行、父 key 和 key。上下文不足的候选标记 `needs_review_context`。

### 产物

`data/quick_lookup_draft.csv`、`verification.csv`、`fixtures_result.md`，以及需要时的 `extraction_overrides.json`。

### 门禁

禁止使用 `toc.md`、`review.md` 或目录遍历得到的 Markdown 作为 canonical 输入。页码未验证时抽取可以生成最佳信源草案并警告，但不得让下游 ready/导出绕过页码门禁。

---

## 阶段 7：LLM 审核和用户升级

### 目标与审核顺序

LLM 默认审核证据明确的候选；用户只处理真正歧义项。

### 本阶段 tool

LLM 读取 canonical Markdown、PDF 证据和阶段 6 候选；维护 `review_decisions.jsonl`、`escalation_queue.jsonl`，不让通用脚本猜测或自动批准业务语义。

1. 读取 canonical Markdown、PDF 证据、`review.md`、抽取配置和候选。
2. 明确 key/value/evidence 一致、来源唯一、无冲突的业务候选，写入 `review_decisions.jsonl` 批准。
3. 明确页脚、表头、脚注、HTML 残片、地址、电话、邮箱或无业务意义标记，写入决定并拒绝。
4. 多种合理解释、跨页/合并单元格语义不确定、冲突、证据缺失、候选身份重复或不稳定时，写入 `escalation_queue.jsonl`，交给用户确认。

LLM 只有 `decision_basis=evidence_exact` 才能批准，只有 `rule_based_non_business` 才能拒绝；用户决定使用 `user_confirmed`。不得把 VLM 输出直接作为最终事实。

### 审核文件和身份

`review_decisions.jsonl` 每条至少含 `candidate_id`、`record_id`、`review_status`、`review_actor`、`decision_basis`、`review_rule_version`、`candidate_hash`、`reason`、`reviewed_at`。

`escalation_queue.jsonl` 至少含候选身份、页段、证据、当前候选、歧义类型、选项和推荐动作。用户确认后由 LLM 写入正式决定；用户不需要运行脚本或手工维护 hash。

候选身份应能区分来源位置和拆分子候选；默认可由 `source_pdf_hash + source_block_id + table_id + row_index + pair_index + page_start + page_end` 生成稳定 hash。候选 hash 变化、candidate_id 不唯一或 record_id 不匹配时拒绝应用决定。旧 `review_overrides.csv` 只兼容唯一 `record_id`，不补写虚假的审核审计字段；重复 record_id 必须升级到 candidate_id。

### 产物

`review_decisions.jsonl`、`escalation_queue.jsonl`，以及兼容旧包的 `review_overrides.csv`（仅作为输入，不是新的审计事实源）。

### 门禁

未处理的升级项、冲突、证据缺失或身份不稳定项保持 `needs_review/not_ready`。只有审核决定完整、候选 hash 一致且用户确认项已处理，才能进入阶段 8。

---

## 阶段 8：入库准备和批次导出

### 目标与 tool

先计算入库状态，再执行最终导出；不直连数据库。

```bash
<project>/scripts/pdf-prepare-ingest <package>
<project>/scripts/pdf-export-ingest <package>
```

`pdf-prepare-ingest` 写入 `data/ingest_ready.csv`、`conflicts.csv`，读取 `review_decisions.jsonl` 和兼容的 `review_overrides.csv`。`pdf-export-ingest` 写入 `data/ingest_batch.jsonl`、`ingest_manifest.json`。

### 两道门禁

- `pdf-prepare-ingest` 在状态计算后执行页码门禁；未验证页码时 ready 降级为 `not_ready`，终态 `skipped/superseded/suppressed` 不受影响。
- `pdf-export-ingest` 执行最终门禁；`page_numbering.status != verified` 时非零退出，防止旧包中的 ready 记录绕过上游门禁。
- 只导出 `review_status=approved` 且 `ingest_status=ready` 的记录。
- `ingest_manifest.json` 必须记录输入 hash、数量、状态和“未写入数据库”说明；下游入库成功由外部系统负责。

### 产物

`data/ingest_ready.csv`、`conflicts.csv`、`ingest_batch.jsonl` 和 `ingest_manifest.json`。本阶段不写入数据库。

### 门禁失败处理

存在未确认升级项、冲突、未验证页码、hash 不一致或候选身份错误时停止，不生成或不交付最终批次。修复 Markdown、TOC、抽取配置或审核决定后，按阶段 5 → 6 → 7 → 8 顺序重跑。

### 人工确认

阶段 8 不新增业务判断；只消费阶段 7 已确认的审核决定。任何状态异常都回到对应阶段处理。

---

## 阶段 9：下游交付和可选 chunks

### 目标与 tool

需要向量化时运行：

```bash
<project>/scripts/pdf-export-chunks <package>
```

它只读取 `manifest.json.files.markdown` 指定的 canonical Markdown；不得选择 `toc.md`、`review.md` 或目录遍历结果。manifest 缺失、损坏、缺少 `files.markdown`、路径越界或目标不存在时必须非零退出，且不生成新的 chunks。既有字段、页锚点、HTML 表格展开、图片替换和 384 token 上限保持不变。

### 最后生成交付入口

每次本轮流程的最后一个交付阶段必须生成或更新 `<package>/downstream_delivery.md`。它是下游首个阅读入口，不是新的业务事实源。内容必须来自当前实际文件和 manifest，至少标明：

- 包状态：`markdown_ready`、`review_required`、`ready_for_downstream` 或 `blocked`；
- canonical Markdown、manifest、TOC、review、chunks 和入库批次的实际路径/状态；
- ready、skipped、not_ready、冲突和升级项目数量；未生成文件写 `not_generated`，不得猜成 0；
- chunks 数量、页码范围、最大 token；批次 ID、输入 hash、ready 数量和未写入数据库说明；
- 交付门禁、剩余异常、生成时间和推荐消费顺序。

Markdown、TOC、修复记录、抽取配置、审核决定或入库批次发生变化后，旧入口视为过期，必须重新生成。

### 下游消费边界

- 正文/追溯：canonical Markdown + manifest。
- 目录导航：`toc_tree.json`；不要从 `toc.md` 重新解析页码。
- 向量化：`data/chunks.jsonl`，每行含 `id`、`content`、`page`、`section`、`token_count`，默认上限 384 token。
- 入库前批次：`data/ingest_batch.jsonl` + `ingest_manifest.json`。
- `quick_lookup_draft.csv`、`verification.csv`、`fixtures_result.md`、`table_accuracy.csv`、`vlm_eval.jsonl` 和原始 segments 是过程/评测产物，除非消费者明确登记，不作为最终接口。

---

## 全局排障索引

| 症状 | 停在哪个阶段 | 处理 |
|---|---:|---|
| `segments_dir does not exist` | 1/2 | 先运行 `pdf-seg <pdf>`，再运行 `pdf-auto` |
| ModelPad API 无响应 | 1 | 启动 ModelPad app，确认 health API；不要猜端口 |
| PDF 服务启动超时 | 1 | 检查 `pdf` 模型状态，必要时调整 `MODELPAD_PDF_START_TIMEOUT` |
| `needs_review` 但先要结果 | 3 | 可降低 `PDF_VALIDATE_THRESHOLD` 或手动 `pdf-merge`，但必须保留 review 状态 |
| TOC 或 page_numbering 校验失败 | 5 | 修复目录三件套和 manifest 后，从阶段 5 重新进入后续流程 |
| 没有导出批次 | 8 | 检查 approved + ready、冲突、升级队列和 page_numbering=verified |
| chunks 内容疑似是目录 | 9 | 检查 `manifest.files.markdown`；修正后删除/重生成 chunks，不改切块算法 |

用户入口继续是 `pdf2md` skill，项目执行层继续使用 CLI；只有跨机器远程调用、队列、多客户端发现或权限隔离成为明确需求时，才另立计划评估 MCP。
