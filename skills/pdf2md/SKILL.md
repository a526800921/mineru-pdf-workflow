---
name: pdf2md
description: Use when the user wants to convert a PDF to Markdown, parse a PDF, review or repair PDF conversion results, extract structured data from a PDF output package, run the MinerU PDF workflow, or prepare/export reviewed PDF data. Triggers on PDF conversion, PDF-to-Markdown, MinerU parsing, .pdf paths, output package validation, review.md, table repair, TOC repair, pdf-auto, pdf-extract-data, pdf-prepare-ingest, or pdf-export-ingest.
---

# PDF to Markdown

本 skill 是 Claude Code 用户级 `pdf2md` skill 的项目事实源。

下游文件职责和交付门禁见项目内 `docs/specs/pdf-downstream-delivery-contract.md`（PDF 下游交付契约）。每个 PDF 输出包在本次流程的最后一个交付阶段必须生成 `<package>/downstream_delivery.md` 作为下游首个阅读入口；下游系统再按该契约选择 `canonical Markdown`、`chunks.jsonl` 或 `ingest_batch.jsonl`，不要直接消费过程草案。

同步目标：

```text
/Users/jafish/.claude/skills/pdf2md/SKILL.md
```

同步方式：

```bash
mkdir -p /Users/jafish/.claude/skills/pdf2md
cp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md
```

涉及 PDF 解析流程、输出包结构、CLI JSON 契约、ModelPad PDF 服务编排、结构化数据/入库导出流程的更新，必须先更新本文件，再同步到 Claude Code 用户级 skill。若当次无法同步，必须在相关计划的未决问题或风险中记录原因和补同步动作。

## 前置条件

- PDF 可放在任意路径；所有产物（segments、md、review、manifest、images、data）默认输出到 **PDF 所在目录**，无需将 PDF 复制到本项目。
- 项目根目录必须先定位，再调用脚本：优先使用当前工作目录，或从当前目录向上查找同时包含 `scripts/pdf-auto` 和 `skills/pdf2md/SKILL.md` 的目录；也可使用 `git rev-parse --show-toplevel` 获取仓库根目录。定位成功后记为绝对路径 `<project>`，所有脚本都通过 `<project>/scripts/<command>` 调用，不假设用户级 skill 目录下存在项目脚本。
- 当前项目的通用脚本目录是 `<project>/scripts/`，公共库在 `<project>/scripts/lib/`；PDF 在项目外时，脚本仍使用项目根目录定位，产物仍写回 PDF 所在目录。
- 当前项目没有运行时通用 `templates/` 目录。`docs/reports/probe-template.md` 仅是报告探针模板；PDF 包级抽取配置使用 `<package>/data/extraction_overrides.json`，下游入口 `downstream_delivery.md` 根据实际产物动态生成，不从固定模板猜测文件状态或数量。
- 自动化 PDF 流程使用 `scripts/pdf-auto <pdf> <segments_dir>`；需要机器可读结果时设置 `PDF_AUTO_JSON=1`。
- ModelPad app/API 必须在线；默认 API 为 `http://127.0.0.1:9999`。
- 项目脚本使用的 MinerU CLI 与 ModelPad PDF 服务保持同版本；当前统一为 MinerU `3.4.4`。

## ModelPad PDF 服务

`pdf-seg`、`pdf-auto`、`pdf-rerun` 依赖 ModelPad 托管的 PDF 服务。脚本会通过 ModelPad API 查询 `pdf` 模型状态，只有模型 `status=running` 且返回了数字 `port` 时，才会把 `http://127.0.0.1:<port>` 作为 MinerU API 地址：

- 如果 PDF 服务已在运行，脚本只复用服务，结束时不停止它。
- 如果 PDF 服务未运行，脚本会通过 ModelPad API 启动 `pdf` 模型，等待 MinerU API 就绪，运行完成后只停止本次脚本启动的服务。
- 如果 ModelPad API 不可用或启动失败，脚本应失败并输出明确诊断。
- 不再通过扫描相邻本地端口推断 PDF 服务，避免其他 ModelPad 模型占用 9001/9002 等端口时被误判为 PDF 服务。

可选环境变量：

```bash
MODELPAD_API_BASE=http://127.0.0.1:9999
MODELPAD_PDF_MODEL_ID=40621169-461C-4018-974E-9FAC92A542E7
MODELPAD_PDF_START_TIMEOUT=120
```

## 输出包结构

所有产物默认输出到 **PDF 所在目录**。例如 PDF 位于 `/path/to/doc.pdf`：

```text
/path/to/
  doc.pdf                  ← 原始 PDF
  doc.md                   ← 合并后的 Markdown（含段级锚点 <!-- pages N-M -->）
  toc.md                   ← 目录展示视图（无锚点连续列表，供人工阅读/前端渲染）
  toc_tree.json            ← 机器权威目录结构（title/target_page/toc_page/depth，可选 printed_page）
  review.md                ← 人工复核清单
  manifest.json            ← 解析状态元数据（含 page_numbering 页码坐标系契约）
  downstream_delivery.md   ← 下游首个阅读入口（由最后交付阶段生成）
  segments/                ← 分段解析产物（默认每页一段，可设 MINERU_SEGMENT_SIZE 覆盖）
    p0001-0001/
    p0002-0002/
    ...
    pXXXX-XXXX-fallback/  ← 页级质量 fallback 候选，与原始页并存
  images/                  ← 提取的图片（预留）
  data/                    ← 结构化数据
    extraction_overrides.json ← LLM/人工确认的表格列语义和包级抽取策略配置（可选）
    quick_lookup_draft.csv
    verification.csv
    fixtures_result.md
    ingest_ready.csv
    conflicts.csv
    review_overrides.csv
    ingest_batch.jsonl
    ingest_manifest.json
    table_accuracy.csv       ← 表格结构自检评测（P4b，只读）
    vlm_eval.jsonl           ← VLM 图表理解描述（P4c，每页一行 JSON）
    manual_fixes.jsonl       ← pdf2md 人工协作阶段的修复事实源（可选）
    logical_tables.jsonl     ← manual_fixes.jsonl 的可选逻辑表格派生视图
```

也可以按主题组织到子目录，例如 `~/manuals/honda-cbr/pdf/xxx.pdf`——产物会出现在 `~/manuals/honda-cbr/pdf/` 下。

默认规则：

- `scripts/pdf-seg /path/to/doc.pdf` 输出到 `/path/to/segments/`。
- `scripts/pdf-auto /path/to/doc.pdf /path/to/segments` 默认合并到 `/path/to/doc.md`，人工复核清单为 `/path/to/review.md`。
- 单页质量异常先在 consistency check 后、`pdf-validate` 前检测；fallback 只重跑异常页，使用 `effort=high` 与 `--image-analysis false`，并保留原始页与 `-fallback` 候选。
- 表格字段遗漏检测使用 PDF 原生文字的 bbox/视觉行与 MinerU HTML 表格逻辑单元格做通用比对；发现 PDF 表格区域存在、HTML 缺失的字段时产生 `native_table_text_missing`，并记录 `missing_text`、`detector` 和指标。覆盖左列行标缺失和整表头/顶部列头丢失（HTML 首行全空且表头带内有原生文字时，`metrics.missing_scope=header_row`）两类。该规则不维护业务字段白名单；无法可靠定位表格区域、无文本层或结果不确定时进入 `review`，不自动覆盖原始结果。
- `manifest.json.page_fallback` 记录每页触发信号、原始/fallback 参数、质量指标、执行状态和 `selected`；合并按 selected 选择同源候选，不只替换 Markdown。
- `review.md` 除 pdf-validate 覆盖率类复核段外，还包含：
  - **页级质量复核段**：列出 `manifest.page_fallback` 中 `selected=review` 或 `fb_status=failed` 的页（含检测器、触发信号、缺失字段），使原生表格字段遗漏等页级质量问题在人工报告中可见；`selected=fallback` 的页已采纳，不列入。
  - **目录归属复核段**：列出无法唯一归属到物理目录页的 TOC 条目（`toc_repair.repair_merged` 写回的 `toc_unassigned`），附来源标注（大纲/原生文本）；大纲来源的指向页标注“大纲（页码可能不准）”。这些条目已从 `toc.md`、`toc_tree.json` 和合并目录块排除，需人工确认其物理目录页。
- `pdf-seg` 和 `pdf-auto` 启动时会校验 `manifest.json` 中的 PDF hash、页数、单页分段配置和 MinerU 关键参数；发现旧格式、旧多页目录、缺页或配置不匹配时，会清理 `segments/` 并从头按当前配置重建。
- 启动清理只作用于 `segments/` 下的解析生成物；`pdf-rerun` 是定点修复入口，发现目录不匹配时应先重新执行全量 `pdf-seg`，不会静默删除整包。
- `scripts/pdf-extract-data /path/to` 写入 `<pdf_dir>/data/`。
- `scripts/pdf-prepare-ingest /path/to` 写入 `<pdf_dir>/data/ingest_ready.csv` 和 `conflicts.csv`。
- `scripts/pdf-export-ingest /path/to` 写入 `<pdf_dir>/data/ingest_batch.jsonl` 和 `ingest_manifest.json`。
- 本次 PDF 流程的最后一步必须生成 `<pdf_dir>/downstream_delivery.md`。该文件是根据当前包实际产物生成的交付导航，汇总文件路径、状态、数量、hash、剩余异常和推荐消费顺序；它不是新的业务事实源。Markdown 修复、重新抽取、审核决定或入库批次变化后必须重新生成。
- 当现有 CLI 无法安全完成一个明确且有限的 PDF 特定操作时，LLM 可以先组合现有 CLI，再生成一次性或包级动态辅助脚本；运行前必须备份目标派生产物、记录 hash、先 dry-run、限制页锚点/record_id/文件范围，并在失败时整组回滚。动态脚本默认放在临时目录，不直接修改通用 `scripts/`。
- 用户入口继续是 `pdf2md` skill，项目执行层继续使用 CLI；当前不新增 MCP Server 或 MCP 兼容层。只有出现跨机器远程调用、队列、多客户端发现或权限隔离需求时，才重新评估 MCP。
- `scripts/pdf-eval-tables /path/to` 写入 `<pdf_dir>/data/table_accuracy.csv`（表格结构自检评测，只读评测产物；选段复用 pdf-merge 口径）。
- `scripts/pdf-eval-vlm /path/to` **可选**写入 `<pdf_dir>/data/vlm_eval.jsonl`（对 `image_or_sparse` 页做本地 VLM 视觉补充；标准模型固定为 `qwen3-vl-8b`，默认自动启停，设 `VLM_API_BASE` 可直连但仍需确认模型身份）。
- `scripts/pdf-merge <segments_dir>` 合并分段 Markdown，输出带**段级锚点** `<!-- pages N-M -->` 的合并 md。回填旧包时直接重跑此命令。
- `pdf2md` 的人工协作阶段位于 `pdf-auto` 完成之后、`pdf-extract-data` 之前；人工修复原地更新 canonical Markdown，并将修复状态、来源 hash、`manual_fixes.jsonl` hash 和当前 Markdown hash 同步写入 `manifest.json`。不生成 `*-fixed.md`。对于扫描结果为空的页，只允许在人工确认的 `rebuild_table`/`cross_page_table` 记录中使用 `allow_empty_page=true`，按页锚点写入新表格并保持幂等。
- `logical_tables.jsonl` 只有存在独立下游消费者时才生成，且必须由 `manual_fixes.jsonl` 派生，不能作为第二个事实源。
- 目录页由 `toc_repair` 按**物理目录页**归属：条目只归属于其 PDF 原生文本实际出现的物理目录页（完整行/词边界匹配，短标题不命中更长词，如“制动”不命中“前制动手柄”）；无法唯一归属时进入 `review`，不静默猜测。目录输出分三个用途，禁止下游混用：
  - `doc.md`：主文档，保留段级锚点 `<!-- pages N-M -->`，供按页读取、结构化抽取和 section 映射；其中嵌入的目录块展示印刷页码，页锚点仍使用物理页码；
  - `toc.md`：无锚点连续目录列表，供人工阅读和前端渲染；不含任何页级锚点，不重新解析或猜测页码；如果存在 `printed_page`，展示印刷页码，否则回退到物理页码；
  - `toc_tree.json`：机器权威目录结构，每条含 `title`、`target_page`（条目指向正文物理页）、`toc_page`（条目所在物理目录页）、`depth`，可选保留 `printed_page`（原始印刷页码）；`pdf-extract-data` 用 `target_page` 做 section 映射。
- 当 PDF 同时存在内置大纲、主目录和末尾字母索引时，`toc_repair` 按内置大纲顺序解决重复标题，选择覆盖最多大纲条目的主目录连续页，并补入相邻的“目录条目 + 正文”混合页；字母索引不覆盖成伪目录。合并级修复只替换实际目录页锚点块，不按目录首尾页连续覆盖中间正文页。
- 目录修复必须把 `doc.md`、`toc.md`、`toc_tree.json`、`review.md`（如复核结论变化）和 `manifest.json` 作为一个同步发布单元：`manifest.files.toc` 指向 `toc.md`，`manifest.files.toc_tree` 指向 `toc_tree.json`，并登记 `manifest.hash.toc_md_sha256` 与 `manifest.hash.toc_tree_json_sha256`。不得只改主 Markdown 或只改展示目录；原始 `segments/**/content_list*.json` 只读，不能作为人工修复目标。
- **页码坐标系契约**：`toc_tree.json` 的 `target_page` 必须统一为 PDF 物理页码（与 `<!-- pages N-M -->` 段锚点一致）。`manifest.json` 的 `page_numbering` 块记录映射关系：
  ```json
  {
    "page_numbering": {
      "physical_page_basis": "pdf_1_based",
      "mapping_type": "constant_offset|identity|piecewise|unknown",
      "status": "verified|proposed|needs_review",
      "printed_to_physical_offset": 8,
      "evidence": [{"printed_page": 1, "physical_page": 9, "source": "PDF page label"}]
    }
  }
  ```
  - `status=verified`：人工确认映射正确，下游可安全消费，记录可进入 `ready`/导出。
  - `status=proposed`：系统检测到映射但未经人工确认，视为不安全——下游警告、入库门禁阻断、导出拒绝。
  - `status=needs_review`：无法自动判断映射，`toc_tree.target_page` 可能为印刷页码——同 `proposed` 阻断。
  - 旧包缺少 `page_numbering` 块视为安全降级（同 `needs_review`），各消费者发出警告、阻断 ready/导出。
  - `toc_tree.json` 可选 `printed_page` 字段保留原始印刷页证据。
- **下游消费者安全门禁**：
  - `pdf-extract-data`：TOC section_map 使用前检查 `page_numbering`；未验证时 stderr 警告 + `verification.csv` 写入 `toc_section_path` warning，但仍构建 section_map（最佳信源）。
  - `pdf-prepare-ingest`：`compute_ingest_status()` 之后运行页码门禁；未验证时所有 `ready` 记录降级为 `not_ready`，notes 追加 `unverified_page_numbering` 标记。终态（skipped/superseded/suppressed）不受影响。
  - `pdf-export-ingest`：导出前最终门禁；`status != verified` 时 `sys.exit(1)` 拒绝导出，防止旧包已有 ready 记录绕过上游门禁。
  - `pdf-check-fixes`：校验 `page_numbering` 块 schema（必含字段、枚举值、offset 完整性、toc 文件 hash 一致性）。旧包缺失时不报 error。
- 不再使用旧的 `<pdf_stem>-output/`、`merged.md` 约定。

## 核心流程

```bash
# PDF 可以在任意路径，产物跟着 PDF 走
scripts/pdf-seg /path/to/doc.pdf
scripts/pdf-auto /path/to/doc.pdf /path/to/segments
scripts/pdf-extract-data /path/to
scripts/pdf-prepare-ingest /path/to
scripts/pdf-export-ingest /path/to
```

如果 `scripts/` 不在 `PATH` 中，使用绝对路径：

```bash
<project>/scripts/pdf-seg /path/to/doc.pdf
<project>/scripts/pdf-auto /path/to/doc.pdf /path/to/segments
```

已有 `segments/` 时可以跳过 `pdf-seg`，直接调用 `scripts/pdf-auto`。

## 自动处理与人工校对边界（当前冻结）

本项目不以“自动修复所有异常”为目标。当前交付边界是：

- 自动完成 TOC 处理、确定性的表格格式化，以及有页锚点、来源 hash 和命中次数保障的低风险表格处理；
- 自动发现大量空 `td`、异常列、缺失文字和结构警告，并写入 `review.md`/draft；
- 复杂表头、列语义、`rowspan/colspan`、跨页关系、扫描件空页和图片表格由人工逐项确认；空页表格可在人工确认后通过显式 `allow_empty_page=true` 的重建记录写回，但不得自动猜测；
- 人工确认或拒绝通过 `manual_fixes.jsonl` 和 manifest 留痕，再安全更新 canonical Markdown；
- 未确认或无法安全判断的内容保持 `needs_review`/`not_ready`，不得为了提高自动修复率而猜测；
- `pdf-table-repair` 不再生成 PDF words/bbox 到候选列的自动映射，也不按序猜测缺失文本位置；`pdf-table-fix` 提供缺失文本证据，列语义和落位由人工确认；
- `pdf-extract-data` 只提供通用 `rowspan/colspan` 网格展开和证据定位；复杂表格的列语义由 LLM/人工写入可选的 `data/extraction_overrides.json`，不得把某个车型或页码的列规则硬编码进脚本；`■/▲` 等维修标记应按配置保留在证据/备注中，不能未经确认成为业务 `key`；包级 `policies.numeric_key=skip` 可显式过滤图示编号等纯数字 key，默认策略仍为 `keep`；
- 已经格式化完成、没有实际 HTML 变化的 `pretty_print` 候选不会进入 apply 阶段；这类页面只保留人工审计证据；
- 只有最终 Markdown、目录产物、修复记录和 manifest 完成同步后，才重新运行 `pdf-extract-data` 与 `pdf-prepare-ingest`。

`content_list*.json` 和原始 segments 始终只读。`pdf2md` 人工协作阶段与 `pdf-table-repair` 负责提供人工校对证据、页级安全应用和产物同步，不继续扩展为全自动表格语义重建器。

## 工具选择

| 情况 | 做法 |
|---|---|
| 只有 PDF，没有分段 | 先 `scripts/pdf-seg <pdf>` |
| 已有 `<package>/segments/` | 直接用 `scripts/pdf-auto` 或 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>` |
| 用户只要 Markdown | 跑到 `pdf-auto` 即可 |
| 用户要结构化草案 | 继续跑 `scripts/pdf-extract-data <package>` |
| 用户要入库候选 | 继续跑 `scripts/pdf-prepare-ingest <package>` |
| 用户要交付下游 | 继续跑 `scripts/pdf-export-ingest <package>` |
| 用户明确要快速结果 | 可降低 `PDF_VALIDATE_THRESHOLD`，例如 0.5-0.7 |
| 用户要高质量 | 默认阈值 0.82，`MINERU_RERUN_EFFORT=high` |

## `pdf-auto` CLI 参数

必填：

- `pdf_path`：PDF 绝对路径。
- `segments_dir`：分段目录绝对路径，通常是 `<pdf所在目录>/segments`。

可选：

- `threshold`：覆盖率阈值，默认 0.82。
- `rerun_effort`：重跑精度，通常使用 `high`。
- `merge_output`：自定义合并输出路径；默认 `<pdf所在目录>/<stem>.md`。

CLI 回退：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
```

## 结果解读

`pdf-auto`：

- `all_passed` / `passed`：验证通过，已合并 Markdown。
- `needs_review` / `needs_review`：已合并 Markdown，同时生成 `review.md`，需要人工复核。
- `error` / `failed`：脚本或输入错误。

常见产物：

- `merged_markdown`：合并后的 `<pdf所在目录>/<stem>.md`。
- `review_markdown`：人工复核清单 `<pdf所在目录>/review.md`。
- `rerun_segments`：真正执行 high 重跑的段。目录页、图片稀疏页、表格页通常进入 review_only，不做无效 high 重跑。

## 其他 CLI 工具

流水线还提供若干只读查询和导出 CLI：

### read_page — 按页码读取 Markdown

```bash
scripts/pdf-read-page <package_dir> <page> [page_end]
```

返回合并 Markdown 中指定页的内容。合并 md 由 `<!-- pages N-M -->` 段级锚点和 `<!-- page N -->` 逐页锚点共同定位：

- **逐页锚点存在时**：`page_start==page_end==N`，精确到单页。
- **无逐页锚点时**：回退段级，`page_start`/`page_end` 反映段范围（向后兼容）。

### search_pdf_content — 关键词检索

```bash
scripts/pdf-search-content <package_dir> <query>
```

在合并 Markdown 和 `quick_lookup_draft.csv` 中搜索关键词，返回页码、章节、原文片段。

### export_chunks — 向量化前置导出

```bash
scripts/pdf-export-chunks <package_dir>
```

将合并 Markdown 预处理为 `data/chunks.jsonl`（纯文本块，按 `##` 切分、HTML 表格展开、图片替换、token 上限 384）。

chunks 导出只读取 `manifest.json.files.markdown` 指定的 canonical Markdown；`toc.md`、`review.md` 或目录遍历得到的其他 Markdown 不能作为输入。manifest 缺失、损坏、未配置 `files.markdown`、路径指向包外或目标不存在时，命令必须非零退出且不生成新的 `chunks.jsonl`，不得猜测或回退到其他 Markdown。该门禁只约束输入选择，既有切块字段、页锚点和 384 token 上限保持不变。

## 结构化数据与入库准备

### 人/LLM 协作定位（当前冻结）

`pdf-extract-data` 是 `pdf2md` 协作流程中的入库前数据准备工具，不是第二套自动修复入口，也不是把车型语义硬编码进脚本的项目。LLM 负责读取已确认的 canonical Markdown、PDF 证据、`review.md` 和当前配置，判断是否存在漏抽或列语义问题，并生成或更新包内 `data/extraction_overrides.json`；脚本只负责通用 HTML 网格展开、来源定位、候选生成和状态计算。

用户只需要确认 PDF 事实、表格关系、列语义和 LLM 无法分辨的候选。LLM 默认审核证据明确的候选：可用 `evidence_exact` 自动批准明确业务记录，可用 `rule_based_non_business` 自动拒绝明确的页脚、表头、脚注或残片；存在多种解释、来源冲突、证据缺失或候选身份不稳定时，才写入 `escalation_queue.jsonl` 请求用户确认。LLM 将全部决定写入 `review_decisions.jsonl`；`pdf-prepare-ingest` 读取该文件和旧 `review_overrides.csv`，执行状态门禁；用户不需要运行脚本或手工编辑 JSON。

具体 PDF 的列规则只能留在该输出包的 `extraction_overrides.json`，不能写入通用 `scripts/pdf-extract-data`。当前春风250Sr的表格闭环已完成；未来只有出现新的真实漏抽样本时，才新增 fixture 或推进通用能力，不以扩大自动化覆盖率作为默认目标。

阶段 3 的通用抽取增强规则：

- 冒号行先分类为 `business_candidate`、`non_business` 或 `ambiguous`；明确的 URL、电话、警告和脚注继续过滤，`ambiguous` 保留为 `needs_review` 候选并在 notes 中记录分类原因。
- 包内 `data/extraction_overrides.json` 可为一张表声明 `pair_groups`，每组使用 `key_column` 和 `value_columns` 指定独立 key/value；一行多组会拆成多条候选，`row_index` 使用 `原行.子行`，notes 保留 `pair_group` 来源。
- 未配置 `pair_groups` 时保持原有抽取行为；列越界或配置不完整时跳过该组，不由脚本猜列；pair_groups 候选默认 `needs_review`，不能绕过审核门禁。

生成结构化草案：

```bash
scripts/pdf-extract-data <pdf所在目录>
```

输出：

```text
data/quick_lookup_draft.csv    ← 结构化草案，含来源上下文
data/verification.csv
data/fixtures_result.md
```

`quick_lookup_draft.csv` 字段（加粗为 v2 新增上下文字段）：

| 字段 | 说明 |
|---|---|
| `source_pdf` | 来源 PDF 文件名 |
| `model` | 车型/文档标识 |
| `section_path` | 章节路径 |
| `key` | 抽取的属性名 |
| `value` | 抽取的属性值 |
| `unit` | 单位 |
| `page_start` | 来源 PDF 起始页 |
| `page_end` | 来源 PDF 结束页 |
| `evidence_text` | 证据文本片段 |
| `confidence` | 置信度（high/medium/low） |
| `status` | 状态（draft/needs_review） |
| `notes` | 备注（抽取规则标识） |
| **`source_block_id`** | 来源块序号（paragraph:N / md_table:N / html_table:N） |
| **`table_id`** | 所属表格 ID |
| **`row_index`** | 表格内行序号 |
| **`parent_key`** | 父级行/列标签 |
| **`key_role`** | key 分类（business_key / local_label / marker / spec_value / state_label） |

`key_role` 分类用于后续冲突判定：

| key_role | 含义 | 示例 |
|---|---|---|
| `business_key` | 业务属性 | 排量、最大功率 |
| `local_label` | 局部编号 | 2、3、10-16 |
| `marker` | 符号/占位符 | ■、▲、-、/ |
| `spec_value` | 规格值被误作 key | M8×30、M10×1.25 |
| `state_label` | 界面状态/标签 | 主界面、电话、菜单音乐 |

冲突判定规则（v2 上下文感知）：

- 冲突 identity：`(model, section_path, page_start, source_block_id, table_id, row_index, parent_key, key)`；同一表格中同一项目的多个保养间隔行由 `row_index` 区分
- `key_role=marker` 不参与冲突检测（符号占位符）
- `key_role=spec_value` 不参与冲突检测（规格值不是业务 key）
- `key_role=local_label` 必须有 `table_id` 或 `source_block_id` 才参与
- 跨上下文多值但缺少页段/块上下文的 key 标记为 `needs_review_context`
- `conflicts.csv` 新增上下文列：`page_start`、`source_block_id`、`table_id`、`row_index`、`parent_key`、`key_role_distribution`

生成入库候选和冲突报告：

```bash
scripts/pdf-prepare-ingest <pdf所在目录>
```

输出：

```text
data/ingest_ready.csv
data/conflicts.csv
data/review_decisions.jsonl  ← LLM/用户审核决定和决策依据
data/escalation_queue.jsonl  ← 仅保留需要用户确认的歧义、冲突和证据缺失项
```

兼容旧包的人工审核覆盖文件可选：

```csv
record_id,review_status,notes
<record_id>,approved,人工确认
```

保存为：

```text
<pdf所在目录>/data/review_overrides.csv
```

然后重新运行：

```bash
scripts/pdf-prepare-ingest <pdf所在目录>
```

新的富结构审核决定由 LLM 维护：

```json
{"candidate_id":"…","record_id":"…","review_status":"approved","review_actor":"llm","decision_basis":"evidence_exact","review_rule_version":"llm-review-v1","candidate_hash":"…","reason":"证据与候选一致","reviewed_at":""}
```

规则：

- `review_actor=llm` 只有 `decision_basis=evidence_exact` 可以批准，只有 `rule_based_non_business` 可以拒绝；
- `review_actor=user` 的批准/拒绝必须使用 `decision_basis=user_confirmed`；
- `candidate_hash` 不匹配、candidate_id 不唯一或 record_id 不匹配时，脚本拒绝应用决定；
- 旧 `review_overrides.csv` 继续兼容，但不补写虚假的 LLM/用户审计字段；它只允许按唯一 `record_id` 应用，重复 `record_id` 会拒绝执行并提示改用 `candidate_id`；
- `escalation_queue.jsonl` 会将重复 `record_id` 标记为 `duplicate_record_identity`，要求用户确认，不能由旧 CSV 静默批量批准；
- `ingest_ready.csv` 新增的 `candidate_id`、`review_actor`、`decision_basis`、`review_rule_version`、`candidate_hash`、`reviewed_at` 字段追加在旧字段之后，不改变旧列位置。

导出可交付批次：

```bash
scripts/pdf-export-ingest <pdf所在目录>
```

输出：

```text
data/ingest_batch.jsonl
data/ingest_manifest.json
```

重要边界：

- 当前流程不直连数据库。
- `pdf-export-ingest` 只导出 `review_status=approved` 且 `ingest_status=ready` 的记录。
- `ingest_manifest.json` 记录输入 hash、计数、状态和“未写入数据库”说明。
- 本项目不确认下游入库成功；外部系统回写 `ingested` 需另建计划。

## LLM/人工协作阶段（统一主入口）

`pdf2md` 是唯一用户入口。用户不需要记忆或执行脚本；LLM 负责读取产物、选择工具、维护配置、执行验证和汇报结果。原 `pdf2md-fix` 兼容 skill 已按阶段 5 用户批准废弃，不再提供第二个触发入口；历史计划中的名称仅保留为迁移记录和产物字段来源说明。

### 下游交付入口

每次流程结束后，LLM 必须先读取并生成/更新：

```text
<package>/downstream_delivery.md
```

生成内容必须来自当前包实际文件和 manifest，不得把不存在的文件或记录计数写成 0。该入口至少说明本包状态、canonical Markdown、目录文件、`chunks.jsonl`、`ingest_batch.jsonl`、`ingest_manifest.json`、审核队列、冲突数量和剩余异常。下游先读这个入口，再按其中路径消费资源。

### 统一顺序

```text
pdf-auto
  → 读取 manifest/review.md/canonical Markdown
  → 分类：自动处理 / 需要用户确认 / 需要动态辅助脚本 / 保留待复核
  → 按页锚点修复 TOC、表格、缺失文本和章节归属
  → 同步 manual_fixes.jsonl、manifest 和目录三件套
  → pdf-extract-data（必要时读取 extraction_overrides.json）
  → LLM 自动审核明确候选，生成 review_decisions.jsonl
  → 只把 escalation_queue.jsonl 中的歧义项交给用户确认
  → LLM 写入用户决定并重新运行入库前审核
  → pdf-prepare-ingest
  → pdf-export-ingest
  → 交付入库前数据包，不导入数据库
```

每轮操作前，LLM 必须先回答：发现了什么、依据哪一页或哪条记录、需要用户确认什么、确认后会更新哪些产物。

### 人工确认边界

LLM 默认处理证据明确的候选；用户只确认 PDF 中的事实和业务语义例外：

- 是否确实缺少文字、表头或表格行；
- 连续页面是否属于同一逻辑表格，以及表头/列语义是什么；
- TOC 条目应归属哪个物理目录页；
- 结构化候选的 key/value/unit/section_path 是否符合 PDF；
- 候选记录存在多种合理解释时应 `approved`、`rejected` 还是继续 `needs_review`。

LLM 不得把推断当成事实，不得批准缺证据/有冲突/身份不稳定的候选，不得把 VLM 输出直接作为最终事实。LLM 的明确决定必须保留候选 hash、规则版本和理由；用户确认采用以下格式：

```text
【需要确认】<确认项标题>
问题：<一个可判断的问题>
PDF 证据：第 <页码> 页；<原文/截图/表格范围>
当前候选：<Markdown、表格或结构化候选>
请确认：确认 / 修改为…… / 拒绝 / 保留待复核
确认后更新：<manual_fixes.jsonl | extraction_overrides.json | review_decisions.jsonl>
```

四类文件职责不能混用：`manual_fixes.jsonl` 记录内容/表格事实修复，`extraction_overrides.json` 记录表格列语义和包级抽取策略，`review_decisions.jsonl` 记录 LLM/用户审核决定及依据，`review_overrides.csv` 只作为旧包的结构化审核状态兼容输入。

### 动态辅助脚本边界

现有 CLI 不足时，LLM 按以下优先级处理：

```text
组合现有 CLI → 生成临时动态辅助脚本 → 同类问题重复后晋升通用 CLI
```

动态脚本运行前必须备份目标 Markdown、manifest、相关 JSON/CSV 和修复记录，记录 hash，先执行 dry-run，并限制到页锚点、record_id 或明确文件范围。只允许修改派生产物，禁止修改 PDF、原始 `segments/` 和 `content_list*.json`。失败时整组回滚，重复运行必须幂等；默认脚本保留在临时目录，不直接写入通用 `scripts/`。详细规则见项目内 `docs/adr/0003-llm-orchestrated-dynamic-assistants.md`（ADR 0003）。

统一事务包装器为 `scripts/pdf-run-helper`。LLM 先准备临时动态命令，再通过以下边界执行；用户不需要运行这条命令：

```bash
scripts/pdf-run-helper \
  --package <输出包> \
  --allow <包内派生文件相对路径> \
  --validate-command '["scripts/pdf-check-fixes", "<输出包>"]' \
  --log <包外摘要路径> \
  -- <动态命令及参数>
```

包装器会用 `PDF_HELPER_MODE=dry-run`、`PDF_HELPER_MODE=apply` 依次调用动态命令，再用 `PDF_HELPER_MODE=validate` 调用显式只读验证命令，并注入 `PDF_HELPER_PACKAGE`、`PDF_HELPER_ALLOWLIST`、`PDF_HELPER_RUN_ID`。dry-run 改变任意包内文件、apply 改变 allowlist 之外的文件、命令或验证失败、验证阶段发生写入时，整包恢复执行前快照；输出 JSON 摘要，记录命令、验证命令、各模式退出码、变更路径、前后清单 hash、结果和回滚状态。allowlist 只能包含派生产物文件，不能包含 PDF、`segments/`、`content_list*.json` 或目录，也不能包含 `review_overrides.csv`、`review_decisions.jsonl`、`escalation_queue.jsonl`、`ingest_ready.csv`、`conflicts.csv`、`ingest_batch.jsonl`、`ingest_manifest.json` 等审批/入库前门禁产物。动态脚本默认放临时目录；需要复用时由 LLM 登记命令、输入/输出、hash 和验证命令，重复问题先补 fixture 再晋升通用 CLI。

### LLM 交付摘要

执行后必须同时报告：输入包和 hash、执行的 CLI/动态脚本、备份情况、用户确认数量、产物前后变化、TOC/页锚点/manifest/表格/冲突/幂等验证、剩余异常和下一步。不能只报告“脚本执行成功”。

当前项目继续使用 `pdf2md skill + CLI 执行层 + 用户审批`，不新增 MCP Server 或 MCP 兼容层。只有跨机器远程调用、任务队列、多客户端发现或权限隔离成为明确需求时，才另立计划评估 MCP。

## 页面类型与处理策略

| 页面类型 | 低覆盖率时 | 说明 |
|---|---|---|
| `text` | 可触发 high 重跑 | 文字页低覆盖通常是真实解析问题 |
| `toc` | review_only | 目录页常因 PDF 文本层重复导致覆盖率异常 |
| `image_or_sparse` | review_only | 图片或稀疏文本页不适合文字覆盖率重跑 |
| `table` | review_only | 表格结构差异不应触发文字 high 重跑 |
| `no_text_layer` | skip | PDF 无文本层，无法覆盖率验证 |

### 本地 VLM（可选）

主解析、质量 fallback 和合并默认不会调用本地 VLM。完成 `pdf-auto` 后，如果页面主要是图片、扫描内容、图表或稀疏文本，且需要补充视觉摘要、图中关键文字或视觉元素描述，再手动执行：

```bash
scripts/pdf-eval-vlm /path/to/package
```

该命令固定使用 `qwen3-vl-8b`，通过 ModelPad API 自动管理生命周期。ModelPad 管理 API 固定为 `http://127.0.0.1:9999`，实际 VLM 服务端点固定为 `http://127.0.0.1:9005`。VLM 已运行时复用不停止；已停止时自动启动，执行完成后自动停止。也支持 `VLM_API_BASE=http://127.0.0.1:9005` 直连远端 VLM 端点（跳过 ModelPad 启停），但远端必须仍提供 `qwen3-vl-8b`。它只读取输出包并将每页结构化结果写入 `data/vlm_eval.jsonl`，不参与表格 `td` 异常修复，也不替代 MinerU 主解析。

## 排障

| 症状 | 处理 |
|---|---|
| `segments_dir does not exist` | 先跑 `scripts/pdf-seg <pdf>` |
| ModelPad API 无响应 | 先启动 `/Users/jafish/Documents/work/ModelPad` app，并确认 `GET http://127.0.0.1:9999/api/health` 返回可用 |
| PDF 服务启动超时 | 检查 ModelPad 中 `pdf` 模型状态，必要时调大 `MODELPAD_PDF_START_TIMEOUT` |
| `needs_review` 但用户要先看结果 | 可降低 `PDF_VALIDATE_THRESHOLD` 或手动运行 `scripts/pdf-merge <segments_dir>` |
| `review_overrides.csv` 报非法字段 | 只允许 `record_id,review_status,notes` |
| 旧 CSV 的 `record_id` 对应多条候选 | 脚本拒绝静默批量应用；查看 `escalation_queue.jsonl`，由 LLM 生成按 `candidate_id` 绑定的决定 |
| 没有导出批次记录 | 检查 `ingest_ready.csv` 中是否存在 `review_status=approved` 且 `ingest_status=ready` |
