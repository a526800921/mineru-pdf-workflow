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

- 在项目根目录 `/Users/jafish/Documents/work/mineru-pdf-workflow` 执行命令。
- PDF 应放在目标输出包目录内，例如 `pdf/demo20/demo20.pdf`。
- ModelPad app/API 必须在线；默认 API 为 `http://127.0.0.1:9786`。
- 第一版 MCP 工具为 `run_pdf_auto`，封装 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`。
- 如果 MCP 工具不可用，可直接运行同等 CLI 命令。

## ModelPad PDF 服务

`pdf-seg`、`pdf-auto`、`pdf-rerun` 依赖 ModelPad 托管的 PDF 服务。脚本会先探测 `MINERU_API_BASE_PORT`（默认 `9000`）起始的 3 个端口：

- 如果 PDF 服务已在运行，脚本只复用服务，结束时不停止它。
- 如果 PDF 服务未运行，脚本会通过 ModelPad API 启动 `pdf` 模型，等待 MinerU API 就绪，运行完成后只停止本次脚本启动的服务。
- 如果 ModelPad API 不可用或启动失败，脚本应失败并输出明确诊断。

可选环境变量：

```bash
MODELPAD_API_BASE=http://127.0.0.1:9786
MODELPAD_PDF_MODEL_ID=40621169-461C-4018-974E-9FAC92A542E7
MODELPAD_PDF_START_TIMEOUT=120
MINERU_API_BASE_PORT=9000
```

## 输出包结构

推荐结构：

```text
pdf/<package>/
  <stem>.pdf
  <stem>.md
  review.md
  manifest.json
  segments/
  images/
  data/
    quick_lookup_draft.csv
    verification.csv
    fixtures_result.md
    ingest_ready.csv
    conflicts.csv
    review_overrides.csv
    ingest_batch.jsonl
    ingest_manifest.json
```

默认规则：

- `scripts/pdf-seg <package>/<stem>.pdf` 输出到 `<package>/segments/`。
- `scripts/pdf-auto <pdf> <package>/segments` 默认合并到 `<package>/<stem>.md`，人工复核清单为 `<package>/review.md`。
- `scripts/pdf-extract-data <package>` 写入 `<package>/data/`。
- `scripts/pdf-prepare-ingest <package>` 写入 `ingest_ready.csv` 和 `conflicts.csv`。
- `scripts/pdf-export-ingest <package>` 写入 `ingest_batch.jsonl` 和 `ingest_manifest.json`。
- 不再使用旧的 `<pdf_stem>-output/`、`merged.md` 约定。

## 核心流程

```bash
cd /Users/jafish/Documents/work/mineru-pdf-workflow

scripts/pdf-seg pdf/demo20/demo20.pdf
scripts/pdf-auto pdf/demo20/demo20.pdf pdf/demo20/segments
scripts/pdf-extract-data pdf/demo20
scripts/pdf-prepare-ingest pdf/demo20
scripts/pdf-export-ingest pdf/demo20
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

- `pdf_path`：PDF 绝对路径，必须位于输出包目录。
- `segments_dir`：分段目录绝对路径，通常是 `<package>/segments`。

可选：

- `threshold`：覆盖率阈值，默认 0.82。
- `rerun_effort`：重跑精度，通常使用 `high`。
- `merge_output`：自定义合并输出路径；默认 `<package>/<stem>.md`。

CLI 回退：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <package>/segments
```

## 结果解读

`pdf-auto` / `run_pdf_auto`：

- `all_passed` / `passed`：验证通过，已合并 Markdown。
- `merged_with_issues` / `needs_review`：生成 `review.md`，需要人工复核。
- `error` / `failed`：脚本或输入错误。

常见产物：

- `merged_markdown`：合并后的 `<package>/<stem>.md`。
- `review_markdown`：人工复核清单 `<package>/review.md`。
- `rerun_segments`：真正执行 high 重跑的段。目录页、图片稀疏页、表格页通常进入 review_only，不做无效 high 重跑。

## 结构化数据与入库准备

生成结构化草案：

```bash
scripts/pdf-extract-data <package>
```

输出：

```text
data/quick_lookup_draft.csv
data/verification.csv
data/fixtures_result.md
```

生成入库候选和冲突报告：

```bash
scripts/pdf-prepare-ingest <package>
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
<package>/data/review_overrides.csv
```

然后重新运行：

```bash
scripts/pdf-prepare-ingest <package>
```

导出可交付批次：

```bash
scripts/pdf-export-ingest <package>
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
| ModelPad API 无响应 | 先启动 `/Users/jafish/Documents/work/ModelPad` app，并确认 `GET http://127.0.0.1:9786/api/health` 返回可用 |
| PDF 服务启动超时 | 检查 ModelPad 中 `pdf` 模型状态，必要时调大 `MODELPAD_PDF_START_TIMEOUT` |
| MCP 工具找不到 | 确认项目 `.mcp.json` 指向 `mcp/server/dist/index.js`，必要时在 `mcp/server` 执行 `npm run build` 并重启 Claude Code |
| `needs_review` 但用户要先看结果 | 可降低 `PDF_VALIDATE_THRESHOLD` 或手动运行 `scripts/pdf-merge <segments_dir>` |
| `review_overrides.csv` 报非法字段 | 只允许 `record_id,review_status,notes` |
| 没有导出批次记录 | 检查 `ingest_ready.csv` 中是否存在 `review_status=approved` 且 `ingest_status=ready` |
