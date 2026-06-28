# 计划：PDF 输出包目录结构

## 背景

现有流水线的输出分散在 `<PDF文件名>-output/segments`、`merged.md`、`review.md` 等路径下。后续 V2 图文浏览、数据抽取和入库草案需要一个稳定的 PDF 输出包目录，将原始 PDF、合并 Markdown、质量报告、分段结果、图片资源、manifest 和结构化数据草案放在同一车型目录中。

目标目录：

```text
pdf/
  春风 150AURA/
    春风 150AURA.pdf
    春风 150AURA.md
    review.md
    segments/
    images/
    manifest.json
    data/
      quick_lookup_draft.csv
      verification.csv
      fixtures_result.md
```

## 事实源职责

本文档是 `pdf-output-package-layout` 的实施细节事实源，记录输出包目录结构、迁移兼容策略、Step 0 证据、验证方式、完成条件、风险和回滚。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。自动化流水线总体契约以 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

- `/pdf2md <package>/<stem>.pdf` 以 PDF 所在目录作为输出包根目录，即 `package = dirname(pdf_path)`。
- `scripts/pdf-seg <package>/<stem>.pdf>` 默认生成 `<package>/segments/`。
- 输出包根目录包含原始 PDF、`images/`、`data/` 和 `manifest.json`。
- `scripts/pdf-merge <package>/segments` 默认输出 `<package>/<package名>.md`。
- `scripts/pdf-auto <pdf> <package>/segments` 默认输出 `<package>/<pdf_stem>.md` 和 `<package>/review.md`。
- `segments/` 内部继续兼容现有 `p0000-0000/` 分段格式。

## 非目标

- 不实现 `data/` 下 CSV/Markdown 草案的抽取逻辑。
- 不实现 V2 图文浏览。
- 不迁移历史输出目录。
- 不移除 `PDF_MERGE_OUTPUT` 和 `PDF_AUTO_MERGE_OUTPUT` 兼容环境变量。

## 不变量

- 原始输入 PDF 不被删除或修改。
- `segments/` 内部格式保持兼容，`pdf-validate` 不需要感知输出包。
- 自定义输出路径环境变量优先于默认路径。
- `manifest.json` 是辅助索引，不作为验证或合并的唯一事实源。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。

## 影响模块或文件

- `scripts/pdf-seg`
- `scripts/pdf-merge`
- `scripts/pdf-auto`
- `README.md`
- `mcp/README.md`
- `docs/PLAN_MAP.md`
- `docs/plans/automated-pdf-pipeline.md`

## 公共契约变化

输出包根目录规则：

| 输入 | 输出包根目录 | 说明 |
|---|---|---|
| `/pdf2md pdf/春风 150AURA/春风 150AURA.pdf` | `pdf/春风 150AURA/` | 其他产物与该 PDF 放在同一目录 |
| `/pdf2md /abs/pdf/春风 150AURA/春风 150AURA.pdf` | `/abs/pdf/春风 150AURA/` | 不再额外创建第二层 `春风 150AURA/` |

因此调用方应先把 PDF 放到目标车型目录中。`/pdf2md` 只在该目录内补齐解析产物。

默认输出包：

| 路径 | 含义 |
|---|---|
| `<package>/<stem>.pdf` | 原始 PDF |
| `<package>/<stem>.md` | 合并 Markdown，等价于旧 `merged.md` |
| `<package>/review.md` | 上游 PDF 解析质量报告 |
| `<package>/segments/` | MinerU 分段结果，内部格式兼容现有分段目录 |
| `<package>/images/` | 后续 V2 图文浏览资源目录 |
| `<package>/manifest.json` | 车型、版本、文件、来源、hash、解析状态 |
| `<package>/data/` | 从 Markdown 提取并准备入库的数据草案 |

`manifest.json` 初始字段：

```json
{
  "model": "春风 150AURA",
  "version": null,
  "source_pdf": "/abs/source/春风 150AURA.pdf",
  "files": {
    "pdf": "春风 150AURA.pdf",
    "markdown": "春风 150AURA.md",
    "review": "review.md",
    "segments": "segments",
    "images": "images",
    "data": "data"
  },
  "hash": {
    "sha256": "..."
  },
  "parse_status": "segmented|all_passed|needs_review|error"
}
```

## Step 0 证据

当前默认输出：

- `scripts/pdf-seg` 输出 `<PDF文件名>-output/segments/`。
- `scripts/pdf-merge` 在未设置 `PDF_MERGE_OUTPUT` 时输出分段目录同级的 `<stem>-merged.md`。
- `scripts/pdf-auto` 当前默认合并输出依赖 `segments_dir` 同级目录，review 输出为 `review.md`。
- MCP `run_pdf_auto` 以 `pdf_path` 和 `segments_dir` 为输入，返回 CLI JSON 中的合并 Markdown 和 review 路径。

GitNexus 影响分析：

- `runPdfAuto`：风险 LOW，1 个直接调用方 `main`，0 个受影响执行流。
- `validateInputs`：风险 LOW。
- `main`：风险 LOW。
- `scripts/pdf-auto` 文件层面：风险 LOW，图谱无上游符号调用；实际影响为 CLI/MCP 路径契约。

## 实施步骤

1. 更新 `/pdf2md` 或等价入口的输出包根目录推导：`package_dir="$(dirname "$pdf_path")"`。
2. 更新 `pdf-seg` 默认分段目录为 `<package>/segments/`，并生成或更新 `manifest.json`。
3. 更新 `pdf-merge` 对 `segments/` 包目录的默认合并路径。
4. 更新 `pdf-auto` 的默认合并路径、review 路径和 `manifest.json` 解析状态。
5. 更新 README、MCP 文档和自动化流水线计划。
6. 运行 shell 语法检查、TypeScript 编译、治理检查和 GitNexus `detect_changes()`。

## 验证方式

```bash
bash -n scripts/pdf-seg
bash -n scripts/pdf-merge
bash -n scripts/pdf-auto

cd mcp/server
npm run build

python3 scripts/check_plan_governance.py .
```

环境依赖验证：

```bash
/pdf2md pdf/春风\ 150AURA/春风\ 150AURA.pdf
```

完成后应存在：

```text
pdf/春风 150AURA/春风 150AURA.pdf
pdf/春风 150AURA/春风 150AURA.md
pdf/春风 150AURA/review.md
pdf/春风 150AURA/segments/
pdf/春风 150AURA/images/
pdf/春风 150AURA/data/
pdf/春风 150AURA/manifest.json
```

## 完成条件

- 新默认目录结构已由脚本生成。
- 旧的 `PDF_MERGE_OUTPUT` 和 `PDF_AUTO_MERGE_OUTPUT` 仍可覆盖默认输出路径。
- `segments/` 内部结构仍可被 `pdf-validate` 和 `pdf-merge` 读取。
- MCP 返回的 `merged_markdown` 和 `review_markdown` 指向新目录结构。
- 验证命令通过，计划治理检查通过。

## 风险和回滚

风险：

- 外部脚本如果依赖旧的 `<stem>-output/segments` 路径，需要改为读取 `<stem>/segments`。
- 输入 PDF 所在目录会被视为输出包根目录；如果用户传入散落 PDF，产物会写在该 PDF 当前目录中。
- `manifest.json` 字段未来可能需要补充版本、来源 URL 或业务车型 ID。

回滚：

- 可通过 `PDF_MERGE_OUTPUT` 和 `PDF_AUTO_MERGE_OUTPUT` 临时恢复合并输出位置。
- `pdf-validate` 仍只依赖传入的 `segments_dir`，不受包目录影响。
- 历史输出目录不迁移、不删除。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| `data/` 下草案文件由谁生成 | 后续数据抽取计划负责 | 否 | 候选 |
| `manifest.json` 的车型和版本字段是否需要外部配置 | 初期用 PDF stem 作为 model，version 为 null | 否 | 待确认 |
| 散落 PDF 是否自动创建车型目录 | 不自动创建；调用方先放入目标目录，`/pdf2md` 以 PDF 所在目录为包根 | 否 | 已确认 |
| 是否需要历史目录迁移脚本 | 暂不迁移，避免误动历史产物 | 否 | 已延后 |

## 关联 ADR、迁移、spec 或 issue

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [MCP 接入设计](../../mcp/README.md)
