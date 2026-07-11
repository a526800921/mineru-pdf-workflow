---
name: pdf2md
description: Use when the user wants to convert a PDF to Markdown, parse a PDF, extract structured data from a PDF output package, run the MinerU PDF workflow, or prepare/export reviewed PDF data. Triggers on PDF conversion, PDF-to-Markdown, MinerU parsing, .pdf paths, output package validation, pdf-auto, pdf-extract-data, pdf-prepare-ingest, or pdf-export-ingest.
---

# PDF to Markdown

本 skill 是 Claude Code 用户级 `pdf2md` skill 的项目事实源。

同步目标：

```text
/Users/jafish/.claude/skills/pdf2md/SKILL.md
```

同步方式：

```bash
mkdir -p /Users/jafish/.claude/skills/pdf2md
cp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md
```

涉及 PDF 解析流程、输出包结构、MCP `run_pdf_auto` 契约、ModelPad PDF 服务编排、结构化数据/入库导出流程的更新，必须先更新本文件，再同步到 Claude Code 用户级 skill。若当次无法同步，必须在相关计划的未决问题或风险中记录原因和补同步动作。

## 前置条件

- PDF 可放在任意路径；所有产物（segments、md、review、manifest、images、data）默认输出到 **PDF 所在目录**，无需将 PDF 复制到本项目。
- 脚本位于 `<project>/scripts/`，可通过绝对路径调用，也可将 `scripts/` 加入 `PATH`。
- MCP 工具 `run_pdf_auto` 封装了 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`，可直接使用。
- 如果 MCP 工具不可用，可直接运行同等 CLI 命令。
- ModelPad app/API 必须在线；默认 API 为 `http://127.0.0.1:9999`。

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
  doc.md                   ← 合并后的 Markdown
  review.md                ← 人工复核清单
  manifest.json            ← 解析状态元数据
  segments/                ← 分段解析产物（默认每页一段，可设 MINERU_SEGMENT_SIZE 覆盖）
    p0001-0001/
    p0002-0002/
    ...
  images/                  ← 提取的图片（预留）
  data/                    ← 结构化数据
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
```

也可以按主题组织到子目录，例如 `~/manuals/honda-cbr/pdf/xxx.pdf`——产物会出现在 `~/manuals/honda-cbr/pdf/` 下。

默认规则：

- `scripts/pdf-seg /path/to/doc.pdf` 输出到 `/path/to/segments/`。
- `scripts/pdf-auto /path/to/doc.pdf /path/to/segments` 默认合并到 `/path/to/doc.md`，人工复核清单为 `/path/to/review.md`。
- `pdf-seg` 和 `pdf-auto` 启动时会校验 `manifest.json` 中的 PDF hash、页数、单页分段配置和 MinerU 关键参数；发现旧格式、旧多页目录、缺页或配置不匹配时，会清理 `segments/` 并从头按当前配置重建。
- 启动清理只作用于 `segments/` 下的解析生成物；`pdf-rerun` 是定点修复入口，发现目录不匹配时应先重新执行全量 `pdf-seg`，不会静默删除整包。
- `scripts/pdf-extract-data /path/to` 写入 `<pdf_dir>/data/`。
- `scripts/pdf-prepare-ingest /path/to` 写入 `<pdf_dir>/data/ingest_ready.csv` 和 `conflicts.csv`。
- `scripts/pdf-export-ingest /path/to` 写入 `<pdf_dir>/data/ingest_batch.jsonl` 和 `ingest_manifest.json`。
- `scripts/pdf-eval-tables /path/to` 写入 `<pdf_dir>/data/table_accuracy.csv`（表格结构自检评测，只读评测产物；选段复用 pdf-merge 口径）。
- `scripts/pdf-eval-vlm /path/to` 写入 `<pdf_dir>/data/vlm_eval.jsonl`（VLM 图表理解描述，10 页抽样验证；渲染 DPI / API 端点通过环境变量配置）。
- `scripts/pdf-merge <segments_dir>` 合并分段 Markdown，输出带**段级锚点** `<!-- pages N-M -->` 和**逐页锚点** `<!-- page N -->` 的合并 md。回填旧包时直接重跑此命令。
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

已有 `segments/` 时可以跳过 `pdf-seg`，直接调用 `run_pdf_auto` 或 `scripts/pdf-auto`。

## 工具选择

| 情况 | 做法 |
|---|---|
| 只有 PDF，没有分段 | 先 `scripts/pdf-seg <pdf>` |
| 已有 `<package>/segments/` | 直接用 `run_pdf_auto` 或 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>` |
| 用户只要 Markdown | 跑到 `pdf-auto` 即可 |
| 用户要结构化草案 | 继续跑 `scripts/pdf-extract-data <package>` |
| 用户要入库候选 | 继续跑 `scripts/pdf-prepare-ingest <package>` |
| 用户要交付下游 | 继续跑 `scripts/pdf-export-ingest <package>` |
| 用户明确要快速结果 | 可降低 `PDF_VALIDATE_THRESHOLD`，例如 0.5-0.7 |
| 用户要高质量 | 默认阈值 0.82，`MINERU_RERUN_EFFORT=high` |

## run_pdf_auto 参数

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

`pdf-auto` / `run_pdf_auto`：

- `all_passed` / `passed`：验证通过，已合并 Markdown。
- `needs_review` / `needs_review`：已合并 Markdown，同时生成 `review.md`，需要人工复核。
- `error` / `failed`：脚本或输入错误。

常见产物：

- `merged_markdown`：合并后的 `<pdf所在目录>/<stem>.md`。
- `review_markdown`：人工复核清单 `<pdf所在目录>/review.md`。
- `rerun_segments`：真正执行 high 重跑的段。目录页、图片稀疏页、表格页通常进入 review_only，不做无效 high 重跑。

## 其他 MCP 工具

除 `run_pdf_auto` 外，流水线还提供若干只读查询和导出工具：

### read_page — 按页码读取 Markdown

```bash
scripts/pdf-read-page <package_dir> <page> [page_end]
# 或通过 MCP: read_page
```

返回合并 Markdown 中指定页的内容。合并 md 由 `<!-- pages N-M -->` 段级锚点和 `<!-- page N -->` 逐页锚点共同定位：

- **逐页锚点存在时**：`page_start==page_end==N`，精确到单页。
- **无逐页锚点时**：回退段级，`page_start`/`page_end` 反映段范围（向后兼容）。

### search_pdf_content — 关键词检索

```bash
scripts/pdf-search-content <package_dir> <query>
# 或通过 MCP: search_pdf_content
```

在合并 Markdown 和 `quick_lookup_draft.csv` 中搜索关键词，返回页码、章节、原文片段。

### export_chunks — 向量化前置导出

```bash
scripts/pdf-export-chunks <package_dir>
# 或通过 MCP: export_chunks
```

将合并 Markdown 预处理为 `data/chunks.jsonl`（纯文本块，按 `##` 切分、HTML 表格展开、图片替换、token 上限 384）。

## 结构化数据与入库准备

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

- 冲突 identity：`(model, section_path, page_start, source_block_id, table_id, parent_key, key)`
- `key_role=marker` 不参与冲突检测（符号占位符）
- `key_role=spec_value` 不参与冲突检测（规格值不是业务 key）
- `key_role=local_label` 必须有 `table_id` 或 `source_block_id` 才参与
- 跨上下文多值但缺少页段/块上下文的 key 标记为 `needs_review_context`
- `conflicts.csv` 新增上下文列：`page_start`、`source_block_id`、`table_id`、`parent_key`、`key_role_distribution`

生成入库候选和冲突报告：

```bash
scripts/pdf-prepare-ingest <pdf所在目录>
```

输出：

```text
data/ingest_ready.csv
data/conflicts.csv
```

人工审核覆盖文件可选：

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

## 页面类型与处理策略

| 页面类型 | 低覆盖率时 | 说明 |
|---|---|---|
| `text` | 可触发 high 重跑 | 文字页低覆盖通常是真实解析问题 |
| `toc` | review_only | 目录页常因 PDF 文本层重复导致覆盖率异常 |
| `image_or_sparse` | review_only | 图片或稀疏文本页不适合文字覆盖率重跑 |
| `table` | review_only | 表格结构差异不应触发文字 high 重跑 |
| `no_text_layer` | skip | PDF 无文本层，无法覆盖率验证 |

## 排障

| 症状 | 处理 |
|---|---|
| `segments_dir does not exist` | 先跑 `scripts/pdf-seg <pdf>` |
| ModelPad API 无响应 | 先启动 `/Users/jafish/Documents/work/ModelPad` app，并确认 `GET http://127.0.0.1:9999/api/health` 返回可用 |
| PDF 服务启动超时 | 检查 ModelPad 中 `pdf` 模型状态，必要时调大 `MODELPAD_PDF_START_TIMEOUT` |
| MCP 工具找不到 | 确认项目 `.mcp.json` 指向 `mcp/server/dist/index.js`，必要时在 `mcp/server` 执行 `npm run build` 并重启 Claude Code |
| `needs_review` 但用户要先看结果 | 可降低 `PDF_VALIDATE_THRESHOLD` 或手动运行 `scripts/pdf-merge <segments_dir>` |
| `review_overrides.csv` 报非法字段 | 只允许 `record_id,review_status,notes` |
| 没有导出批次记录 | 检查 `ingest_ready.csv` 中是否存在 `review_status=approved` 且 `ingest_status=ready` |
