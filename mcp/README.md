# MCP 接入设计

本目录用于后续把 MinerU PDF 工作流接入 Claude Code。

> 治理说明：本文档保留 MCP 设计和运行手册。计划状态、阶段证据、依赖、阻塞项和推荐顺序以 [PLAN_MAP](../docs/PLAN_MAP.md) 为准；字段方案、完成条件和验证结果以 [自动化 PDF 解析流水线计划](../docs/plans/automated-pdf-pipeline.md) 为准。

## 接入策略

优先实现一个本地 MCP server，封装项目内脚本，而不是让 Claude Code 直接拼接复杂 shell 命令。

推荐分两步：

1. 先让 CLI 输出稳定的机器可读 JSON。
2. 再实现 MCP server，把 JSON 作为工具返回值。

## 工具契约

### `run_pdf_auto`（第一版，保留向后兼容）

自动化 PDF 解析流水线（分段解析→验证→可疑段重跑→再验证→合并→人工兜底清单）。

输入：

```json
{
  "pdf_path": "/abs/path/pdf/春风-150AURA/春风-150AURA.pdf",
  "segments_dir": "/abs/path/pdf/春风-150AURA/segments",
  "threshold": 0.82,
  "rerun_effort": "high",
  "merge_output": "/abs/path/pdf/春风-150AURA/春风-150AURA.md"
}
```

字段说明：

- `pdf_path`：必填，绝对路径，必须指向存在的 `.pdf` 文件。PDF 所在目录即输出包根目录。
- `segments_dir`：必填，绝对路径，必须指向已存在的分段目录（如 `<package>/segments/`）。
- `threshold`：可选，映射到 `PDF_VALIDATE_THRESHOLD`。
- `rerun_effort`：可选，映射到 `MINERU_RERUN_EFFORT`。
- `merge_output`：可选，映射到 `PDF_AUTO_MERGE_OUTPUT`，默认输出到 `<package>/<stem>.md`。

输出：

```json
{
  "status": "passed",
  "exit_code": 0,
  "merged_markdown": "/abs/path/pdf/春风-150AURA/春风-150AURA.md",
  "review_markdown": null,
  "stdout": "...",
  "stderr": "..."
}
```

`status` 取值：

- `passed`：`pdf-auto` 退出码为 0，合并完成且无人工兜底项。
- `needs_review`：`pdf-auto` 退出码为 2，合并完成但生成人工兜底清单。
- `failed`：`pdf-auto` 退出码为 1 或调用前校验失败。

失败模式：

- PDF 不存在或不是 `.pdf` 文件。
- 分段目录不存在，或缺少 `pXXXX-YYYY` 分段目录。
- `scripts/pdf-auto` 返回脚本错误。
- `scripts/pdf-auto` 输出无法映射到预期合并文件或 review 文件。

## CLI JSON 决策

`scripts/pdf-auto` 已实现可选 JSON summary：

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
```

CLI JSON 输出结构：

```json
{
  "status": "all_passed",
  "exit_code": 0,
  "merged_markdown": "/abs/path/pdf/春风-150AURA/春风-150AURA.md",
  "review_markdown": null,
  "rerun_segments": ["p0000-0019"]
}
```

JSON 模式应保留现有退出码语义：

- `0`：全部通过，合并完成。
- `1`：脚本自身错误。
- `2`：合并完成，但有段需要人工兜底。

CLI `status` 当前取值：

- `all_passed`：`pdf-auto` 退出码为 0，合并完成且无人工兜底项。
- `merged_with_issues`：`pdf-auto` 退出码为 2，合并完成但生成人工兜底清单。
- `error`：`pdf-auto` 退出码为 1，或调用前校验失败。

MCP server 第一版必须读取 stdout JSON 判断状态；stderr 只作为诊断日志返回或记录，不能依赖中文日志解析决定工具状态。MCP 对外返回可以把 CLI 状态映射为 `passed`、`needs_review`、`failed`。

## 阶段 6 验收与运行手册

阶段 6 已完成。验收范围、完成条件和验证结果以 [自动化 PDF 解析流水线计划](../docs/plans/automated-pdf-pipeline.md#阶段-6-完成证据) 为准；计划状态和证据索引以 [PLAN_MAP](../docs/PLAN_MAP.md) 为准。

下方只保留 MCP 运行手册和排障信息。

## 拆分式工具（P2 已实现）

以下 5 个拆分工具在 P2 阶段实现，每个工具对应一个独立 CLI 脚本。`run_pdf_auto` 保持不变。

### `parse_pdf_segmented`

封装 `scripts/pdf-seg`（`PDF_SEG_JSON=1`）。

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segment_size": 10,
  "backend": "hybrid-engine",
  "effort": "medium",
  "method": "auto",
  "lang": "ch"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pdf_path` | string | 是 | 绝对路径，指向 .pdf 文件 |
| `segment_size` | number | 否 | 每段页数，默认 10 |
| `backend` | enum | 否 | hybrid-engine / vlm-engine / pipeline，默认 hybrid-engine |
| `effort` | enum | 否 | medium / high，默认 medium |
| `method` | enum | 否 | auto / txt / ocr，默认 auto |
| `lang` | string | 否 | 文档语言，默认 ch |

输出：

```json
{
  "status": "completed",
  "exit_code": 0,
  "segments_dir": "/abs/path/pdf/demo/segments",
  "manifest_path": "/abs/path/pdf/demo/manifest.json",
  "total_pages": 40,
  "segment_size": 10,
  "segments": [
    { "name": "p0001-0010", "start_page": 1, "end_page": 10, "status": "done" }
  ]
}
```

失败模式：PDF 不存在、不是 .pdf 文件、MinerU 退出码非 0。

### `validate_segments`

封装 `scripts/pdf-validate`（`PDF_VALIDATE_JSON=1`）。

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segments_dir": "/abs/path/pdf/demo/segments",
  "threshold": 0.82
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pdf_path` | string | 是 | 绝对路径，指向原始 .pdf 文件 |
| `segments_dir` | string | 是 | 绝对路径，指向分段目录 |
| `threshold` | number | 否 | 覆盖率阈值（0-1），默认 0.82 |

输出：

```json
{
  "status": "has_issues",
  "exit_code": 1,
  "passed": false,
  "threshold": 0.82,
  "segments": [
    {
      "name": "p0001-0008",
      "start_page": 1,
      "end_page": 8,
      "coverage": 0.77,
      "status": "suspicious",
      "decision": "rerun",
      "rerunnable": true,
      "missing_tokens": [["车", 19], ["置", 19]],
      "markdown_path": "/path/to/segments/p0001-0008/demo.md",
      "pages": [...]
    }
  ]
}
```

segment status 取值：`passed` / `suspicious` / `skipped` / `failed`。

### `rerun_segments`

封装 `scripts/pdf-rerun`（`PDF_RERUN_JSON=1`）。页码使用 1-based（与 PDF 页码一致）。

输入：

```json
{
  "pdf_path": "/path/to/manual.pdf",
  "segments_dir": "/abs/path/pdf/demo/segments",
  "pages": [27, 29, 30],
  "effort": "high"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pdf_path` | string | 是 | 绝对路径，指向原始 .pdf 文件 |
| `segments_dir` | string | 是 | 绝对路径，指向分段目录 |
| `pages` | number[] | 是 | 需要重跑的 PDF 页码列表（1-based） |
| `effort` | enum | 否 | high / medium / low，默认 high |

输出：

```json
{
  "status": "completed",
  "exit_code": 0,
  "rerun_count": 3,
  "merged_markdown": "/abs/path/pdf/demo/demo.md",
  "segments": [
    { "name": "p0025-0032", "start_page": 25, "end_page": 32, "status": "done" }
  ]
}
```

segment status 取值：`done` / `failed` / `no_markdown` / `skipped`。

### `merge_segments`

封装 `scripts/pdf-merge`。

输入：

```json
{
  "segments_dir": "/abs/path/pdf/demo/segments",
  "merge_output": "/abs/path/pdf/demo/demo.md"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `segments_dir` | string | 是 | 绝对路径，指向分段目录 |
| `merge_output` | string | 否 | 自定义输出路径，默认自动推导 |

输出：

```json
{
  "status": "completed",
  "exit_code": 0,
  "merged_markdown": "/abs/path/pdf/demo/demo.md"
}
```

失败模式：分段目录不存在、分段缺少 Markdown、图片文件名冲突。

### `create_review_report`

封装 `scripts/pdf-review`（`scripts/lib/review_report.py`）。

输入：

```json
{
  "validate_json": "/tmp/validate.json",
  "review_output": "/abs/path/pdf/demo/review.md",
  "threshold": 0.82,
  "pdf_path": "/abs/path/pdf/demo/demo.pdf",
  "segments_dir": "/abs/path/pdf/demo/segments",
  "rerun_failures": "p0001-0008 p0040-0048"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `validate_json` | string | 是 | pdf-validate 的 JSON 报告路径 |
| `review_output` | string | 是 | 输出 review.md 路径 |
| `threshold` | number | 是 | 覆盖率阈值（与验证时一致） |
| `pdf_path` | string | 是 | 原始 PDF 路径 |
| `segments_dir` | string | 是 | 分段目录路径 |
| `rerun_failures` | string | 否 | 空格分隔的重跑失败分段名 |

输出：

```json
{
  "status": "completed",
  "exit_code": 0,
  "review_markdown": "/abs/path/pdf/demo/review.md"
}
```

### `read_page`（P3a 新增）

封装 `scripts/pdf-read-page`（`PDF_READ_PAGE_JSON=1`）。按 PDF 页码读取合并 Markdown 中对应段的文本。

输入：

```json
{
  "package_dir": "/abs/path/pdf/春风 150AURA",
  "page": 14,
  "page_end": 16
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_dir` | string | 是 | 输出包根目录（含 `<stem>.md` 和 `segments/`）的绝对路径 |
| `page` | number | 是 | PDF 页码（1-based），定位到包含该页的 `<!-- pages N-M -->` 段 |
| `page_end` | number | 否 | 结束页码，指定后返回连续多段的 Markdown |

输出：

```json
{
  "status": "completed",
  "page": 14,
  "page_start": 9,
  "page_end": 16,
  "section_path": "150 AURA 使用说明书 / 序列号",
  "segment_count": 1,
  "markdown": "## 序列号\n\n| 项目 | 规格 |\n| ..."
}
```

失败模式：输出包目录不存在、合并 Markdown 不存在且无分段目录、页码超出范围。

### `search_pdf_content`（P3a 新增）

封装 `scripts/pdf-search-content`（`PDF_SEARCH_CONTENT_JSON=1`）。对合并 Markdown + `quick_lookup_draft.csv` 做关键词匹配（AND 逻辑）。

输入：

```json
{
  "package_dir": "/abs/path/pdf/春风 150AURA",
  "query": "最大净功率",
  "max_results": 10,
  "source": "all"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_dir` | string | 是 | 输出包根目录的绝对路径 |
| `query` | string | 是 | 搜索关键词（支持空格分隔的多个词，AND 匹配） |
| `max_results` | number | 否 | 最大返回数，默认 10 |
| `source` | enum | 否 | `all` / `markdown` / `csv`，默认 `all` |

输出：

```json
{
  "status": "completed",
  "query": "最大净功率",
  "total_matches": 2,
  "results": [
    {
      "source": "csv",
      "key": "最大净功率",
      "value": "11.8 Kw / 8500",
      "unit": "rpm",
      "page_start": 14,
      "page_end": 14,
      "section_path": "150 AURA 使用说明书 / 序列号",
      "evidence_text": "最大净功率: 11.8 Kw / 8500 rpm",
      "confidence": "medium"
    },
    {
      "source": "markdown",
      "page_start": 9,
      "page_end": 16,
      "section_path": "150 AURA 使用说明书 / 序列号",
      "snippet": "最大净功率 11.8 Kw / 8500 rpm..."
    }
  ]
}
```

失败模式：输出包目录不存在、query 为空。

### `export_chunks`（P3b 新增）

封装 `scripts/pdf-export-chunks`（`PDF_EXPORT_CHUNKS_JSON=1`）。将合并 Markdown 预处理为 chunks.jsonl，供下游向量化。

输入：

```json
{
  "package_dir": "/abs/path/pdf/春风 150AURA",
  "output_path": "/abs/path/pdf/春风 150AURA/data/chunks.jsonl"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_dir` | string | 是 | 输出包根目录的绝对路径 |
| `output_path` | string | 否 | 自定义输出路径，默认 `<package>/data/chunks.jsonl` |

输出：

```json
{
  "status": "completed",
  "chunk_count": 335,
  "output_path": "/abs/path/pdf/春风 150AURA/data/chunks.jsonl"
}
```

chunks.jsonl 每行格式：

```json
{"id": "春风 150AURA@seq_003", "content": "序列号...", "page": "12-14", "section": "序列号", "token_count": 42}
```

预处理步骤：## 标题切分 → HTML 表格展开 → 图片占位符替换 → Markdown 清洗 → token 上限裁剪（≤384）。

## Claude Code 配置

MCP server 已实现，在 Claude Code 中添加：

```json
{
  "mcpServers": {
    "mineru-pdf-workflow": {
      "command": "node",
      "args": [
        "/Users/jafish/Documents/work/mineru-pdf-workflow/mcp/server/dist/index.js"
      ]
    }
  }
}
```

## 运行手册

### 安装与构建

```bash
cd mcp/server
npm install
npm run build          # 产物在 dist/index.js
```

开发模式（免构建）：

```bash
npm run dev            # tsx watch src/index.ts
```

### Claude Code 配置

项目根 `.mcp.json` 已配置。也可手动添加到 `~/.claude/mcp.json`：

```json
{
  "mcpServers": {
    "mineru-pdf-workflow": {
      "command": "node",
      "args": ["/Users/jafish/Documents/work/mineru-pdf-workflow/mcp/server/dist/index.js"]
    }
  }
}
```

### 本地验证

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

### 工具调用

在 Claude Code 中直接描述任务即可，模型会自动选择合适的参数。例如：

> 用 run_pdf_auto 处理 pdf/春风 150AURA/春风 150AURA.pdf，分段目录是 pdf/春风 150AURA/segments，阈值 0.82，重跑精度 high

### 返回状态

| MCP status | CLI status | exit_code | 含义 |
|---|---|---|---|
| `passed` | `all_passed` | 0 | 全部段验证通过，合并完成 |
| `needs_review` | `merged_with_issues` | 2 | 合并完成，有段需人工复核 |
| `failed` | `error` 或调用失败 | 1 | 脚本错误或输入校验失败 |

### 端到端验证证据（阶段 6）

详见 [自动化 PDF 解析流水线计划的阶段 6 完成证据](../docs/plans/automated-pdf-pipeline.md#阶段-6-完成证据)。

### 排障清单

| 症状 | 可能原因 | 排查步骤 |
|---|---|---|
| MCP server 不启动 | Node.js 版本过低 | `node -v`，需要 ≥18 |
| `tools/list` 不显示全部 6 个工具 | SDK 版本不匹配 | `npm ls @modelcontextprotocol/sdk` |
| 工具返回 `failed`: pdf_path does not exist | 路径不对 | 确认 PDF 路径是绝对路径，文件存在 |
| 工具返回 `failed`: segments_dir does not exist | 分段目录未生成 | 先运行 `parse_pdf_segmented` 生成分段，输出到 `<package>/segments/` |
| `parse_pdf_segmented` 耗时长 | segment_size 太小或 PDF 大 | 增大 `segment_size`（默认 10） |
| `rerun_segments` 后仍是 needs_review | PDF 本身文本层质量差 | 降低 `threshold` 或人工复核，属正常行为 |
| `Subprocess error: Command failed` | mineru 不在 PATH | 确认终端能直接运行 `mineru` |
| `merge_segments` 报图片冲突 | 不同分段图片同名但内容不同 | 检查分段 images/ 目录，手动处理冲突 |

## 实现前置条件

- ✅ `scripts/pdf-validate` 已支持 JSON 输出（`PDF_VALIDATE_JSON=1`）。
- ✅ `scripts/pdf-auto` 已实现 `PDF_AUTO_JSON=1` JSON summary。
- ✅ `scripts/pdf-seg` 已实现 `PDF_SEG_JSON=1` JSON 输出（P2 Step 1）。
- ✅ `scripts/pdf-rerun` 已实现 `PDF_RERUN_JSON=1` JSON 输出（P2 Step 2）。
- ✅ `scripts/pdf-review` + `scripts/lib/review_report.py` 已创建（P2 Step 0）。
- ✅ P2 5 个拆分工具已实现并注册（共 6 个工具：1 旧 + 5 新）。
- ✅ `scripts/pdf-read-page` 已实现（P3a Step 1）。
- ✅ `scripts/pdf-search-content` 已实现（P3a Step 2）。
- ✅ P3a 2 个检索工具已实现并注册（共 8 个工具：6 旧 + `read_page` + `search_pdf_content`）。
- ✅ `scripts/lib/chunk_utils.py` + `scripts/pdf-export-chunks` 已实现（P3b）。
- ✅ P3b `export_chunks` 已实现并注册（共 9 个工具）。

## 安全边界

- MCP server 只允许访问用户显式传入的本地 PDF 和对应输出目录。
- 所有工具通过 `spawn` 调用仓库内固定脚本：`scripts/pdf-auto`、`scripts/pdf-seg`、`scripts/pdf-validate`、`scripts/pdf-rerun`、`scripts/pdf-merge`、`scripts/pdf-review`。
- 只接受绝对路径。
- 不删除原始 PDF。
- 重跑只覆盖对应分段输出，不改其他分段。
- 任何人工修订文件应输出为新文件，不覆盖 MinerU 原始结果。
