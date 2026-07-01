# 计划：输出包结构化数据抽取

## 背景

`pdf-output-package-layout` 已将 PDF 输出包稳定为 `<package>/`，并预留 `data/` 目录用于入库草案。当前流水线已经能生成原始 PDF、合并 Markdown、分段结果、图片、`manifest.json` 和质量报告，但 `data/` 下的结构化草案仍为空。

本计划负责把已稳定的输出包继续推进到“可人工校验、可后续入库”的数据层，先产出保守的草案文件，不直接写数据库。

## 事实源职责

本文档是 `structured-data-extraction` 的实施细节事实源，记录数据抽取范围、输出文件契约、字段定义、Step 0 证据、验证方式、完成条件、风险和回滚。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。输出包目录结构以 [PDF 输出包目录结构计划](pdf-output-package-layout.md) 为准。解析质量判定以 [覆盖率验证口径优化计划](coverage-validation-optimization.md) 为准。

## 目标

- 在 `<package>/data/` 下生成第一版结构化草案文件。
- 将合并 Markdown、`content_list_v2.json` 和 `manifest.json` 中的可观察信息转换为可审核行数据。
- 每条抽取结果保留来源证据：页码、章节路径、原文片段或来源文件。
- 先支持人工审核和后续入库准备，不直接对接数据库。

## 非目标

- 不实现业务数据库写入。
- 不新增 MCP 工具，第一版仍通过 CLI 或脚本产物完成验收。
- 不用大模型推断缺失字段；第一版只做规则抽取和证据保留。
- 不修改 MinerU 解析引擎、覆盖率判定或 `pdf-auto` JSON 契约。
- 不承诺一次性覆盖所有车型字段；第一版优先固定文件格式和质量门禁。

## 不变量

- 原始 PDF、分段结果、合并 Markdown 不被修改。
- `data/` 产物可重复生成，同一输入下文件名和列名稳定。
- 草案字段必须能追溯到输出包内文件，不生成无证据的业务结论。
- 低置信度、冲突或无法归类的数据进入待审核状态，不自动放行。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。

## 影响模块或文件

第一阶段预计只新增或更新文档。后续实施代码时，候选范围为：

- 新增 `scripts/pdf-extract-data` 或等价脚本。
- `README.md`：仅在脚本可用后补充使用方式。
- `docs/PLAN_MAP.md`
- `docs/plans/pdf-output-package-layout.md`
- `docs/plans/structured-data-extraction.md`

第一版不修改：

- `scripts/pdf-seg`
- `scripts/pdf-merge`
- `scripts/pdf-auto`
- `scripts/pdf-validate`
- `mcp/server/*`

## 输出契约

第一版输出目录固定为：

```text
<package>/data/
  quick_lookup_draft.csv
  verification.csv
  fixtures_result.md
```

### quick_lookup_draft.csv

用于承载可后续入库或人工整理的键值型草案。

| 字段 | 含义 | 规则 |
|---|---|---|
| `source_pdf` | 源 PDF 文件名 | 来自 `manifest.json.files.pdf` 或实际 PDF 文件名 |
| `model` | 车型或文档名 | 初期使用 `manifest.json.model` |
| `section_path` | 章节路径 | 从 Markdown 标题层级推导，无法推导则为空 |
| `key` | 草案字段名 | 从表格、冒号行或规则命中的标题生成 |
| `value` | 草案字段值 | 原文提取，不做大模型改写 |
| `unit` | 单位 | 可从值尾部解析；无法确定则为空 |
| `page_start` | 起始页 | 来自分段名或 `content_list_v2.json` 页序 |
| `page_end` | 结束页 | 单页段与 `page_start` 相同 |
| `evidence_text` | 证据文本 | 原文片段，便于人工复核 |
| `confidence` | 置信度 | `high`、`medium`、`low` |
| `status` | 审核状态 | `draft`、`needs_review`、`rejected` |
| `notes` | 备注 | 记录冲突、缺失或规则来源 |

### verification.csv

用于记录抽取质量和输出包一致性检查。

| 字段 | 含义 |
|---|---|
| `check_id` | 检查项编号 |
| `level` | `error`、`warning`、`info` |
| `target` | 检查对象 |
| `result` | `passed`、`failed`、`needs_review` |
| `details` | 细节说明 |
| `source` | 来源文件或命令 |

### fixtures_result.md

用于给人工验收看的摘要报告，至少包含：

- 输入输出包路径。
- 抽取行数、待审核行数、错误数。
- 命中的章节和表格概览。
- `verification.csv` 的 error/warning 摘要。
- 可复现命令。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化 Step 0 样本和输出契约 | demo20 输出包可用 | 真实样本结构、字段契约、验收命令明确 | 已完成 |
| 阶段 1 | 最小数据草案生成 | 阶段 0 完成 | 生成三个 `data/` 文件，CSV 表头稳定 | 候选 |
| 阶段 2 | 抽取规则扩展和审核口径 | 阶段 1 完成 | 表格、冒号行、章节路径覆盖更多样本 | 候选 |
| 阶段 3 | 治理收尾和后续入库边界 | 阶段 2 完成 | README、PLAN_MAP、验收证据同步 | 候选 |

## 当前阶段

当前阶段为阶段 0 已完成（2026-07-01）。阶段 1（最小数据草案生成）候选实施中。

## Step 0 证据

### 样本状态

2026-07-01 已用 demo20 生成真实输出包：

- 样本 PDF：`pdf/demo20/demo20.pdf`
- 合并 Markdown：`pdf/demo20/demo20.md`
- 输出包 manifest：`pdf/demo20/manifest.json`
- 分段目录：`pdf/demo20/segments/`
- 图片目录：`pdf/demo20/images/`
- `content_list_v2.json`：20 个，每页 1 个分段。
- 图片验收：13 张图片，合并 Markdown 3 个图片引用，连续两次 `pdf-auto` 后无漂移。

真实 `content_list_v2.json` 结构已确认：

- 文件顶层是页数组。
- 每页是元素数组。
- 元素基础字段为 `type`、`content`、`bbox`。
- demo20 已观察到元素类型：`table`、`page_number`、`title`、`paragraph`、`image`、`page_header`。

### 可复现命令

```bash
scripts/pdf-seg pdf/demo20/demo20.pdf
PDF_VALIDATE_THRESHOLD=0.4 scripts/pdf-auto pdf/demo20/demo20.pdf pdf/demo20/segments

find pdf/demo20/segments -name '*content_list_v2.json' | wc -l
find pdf/demo20/images -type f | wc -l
grep -oE '!\[[^]]*\]\([^)]+\)' pdf/demo20/demo20.md | wc -l
```

### 当前缺口

- `data/` 目录已由输出包流程创建，但没有草案文件生成逻辑。
- 尚无正式字段 schema 或 CSV 表头测试。
- 尚无脚本负责从 Markdown / `content_list_v2.json` 汇总结构化草案。

### 阶段 0 完成证据（2026-07-01）

- 输出契约已固化：`quick_lookup_draft.csv`（13 列 + 3 置信度 + 3 状态枚举）、`verification.csv`（6 列）、`fixtures_result.md`（6 项最低内容）。
- demo20 样本基线已确认：20 个 `content_list_v2.json`、13 张图片、合并 Markdown + manifest 可用。
- `data/` 目录已由 `pdf-seg` 自动创建，但草案生成逻辑待阶段 1 实现。
- 计划已加入 `PLAN_MAP.md`，状态 `设计中`。
- `pdf-output-package-layout.md` 的 `data/` 未决项已指向本计划。
- 阶段 1 实施边界清楚：新增脚本，不修改现有解析/验证/MCP 契约。

## 阶段 0 验收命令

```bash
test -f pdf/demo20/demo20.md
test -f pdf/demo20/manifest.json
test -d pdf/demo20/segments
test -d pdf/demo20/images
test "$(find pdf/demo20/segments -name '*content_list_v2.json' | wc -l | tr -d ' ')" -ge 20
test "$(find pdf/demo20/images -type f | wc -l | tr -d ' ')" -ge 1
python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

## 阶段 0 完成条件

- 本计划进入 `PLAN_MAP.md`，状态为 `设计中` 或后续状态。
- 输出契约、字段表头、状态枚举和样本基线已记录。
- `pdf-output-package-layout.md` 的 `data/` 未决项已指向本计划。
- 阶段 1 的实施边界清楚：新增数据抽取脚本，不修改现有解析/验证/MCP 契约。

## 阶段 1 候选实施方向

阶段 1 可以新增一个最小脚本，例如 `scripts/pdf-extract-data <package>`：

1. 读取 `<package>/manifest.json`、`<package>/<stem>.md` 和 `segments/**/content_list_v2.json`。
2. 生成稳定表头的 `data/quick_lookup_draft.csv`。
3. 生成 `data/verification.csv`，记录输入文件存在性、行数、图片引用、content_list 数量等检查。
4. 生成 `data/fixtures_result.md`，给人工验收使用。
5. 对无法可靠抽取的字段输出 `needs_review`，不伪造高置信度结果。

阶段 1 不要求抽取完整业务字段；成功标准是输出文件稳定、可追溯、可重复生成。

## 验证方式

阶段 0：

```bash
python3 scripts/check_plan_governance.py .
git diff --check
```

阶段 1 候选：

```bash
bash -n scripts/pdf-extract-data
scripts/pdf-extract-data pdf/demo20
test -f pdf/demo20/data/quick_lookup_draft.csv
test -f pdf/demo20/data/verification.csv
test -f pdf/demo20/data/fixtures_result.md
head -n 1 pdf/demo20/data/quick_lookup_draft.csv | grep 'source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes'
head -n 1 pdf/demo20/data/verification.csv | grep 'check_id,level,target,result,details,source'
python3 scripts/check_plan_governance.py .
```

## 完成条件

全计划完成时：

- `data/` 下三类草案文件可由命令稳定生成。
- demo20 和 demo5 至少各有一次验收记录。
- 输出文件字段契约和状态语义已同步到治理文档。
- 不破坏现有 `pdf-seg`、`pdf-auto`、MCP `run_pdf_auto` 契约。
- GitNexus `detect_changes` 风险可接受，治理检查通过。

## 风险和回滚

风险：

- MinerU `content_list_v2.json` 结构可能随版本变化。
- Markdown 中的表格、图片和标题层级可能不稳定，第一版抽取结果需要人工审核。
- 规则抽取容易产生看似结构化但不可入库的低质量数据，因此必须保留 `status` 和 `evidence_text`。

回滚：

- 删除或忽略 `<package>/data/*.csv`、`<package>/data/*.md` 即可回滚数据草案，不影响解析产物。
- 第一版不修改现有解析、验证、合并和 MCP 代码，失败时不影响主流水线。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 第一版是否只输出 CSV | 是，先用 CSV 固定表头和人工审核流程 | 否 | 已确认 |
| 是否需要 JSON Schema | 阶段 1 可先用 CSV 表头检查；阶段 2 再评估 JSON Schema | 否 | 候选 |
| 是否纳入 MCP 工具 | 第一版不纳入，等 CLI 契约稳定后再评估 | 否 | 候选 |
| 是否抽取完整车型参数表 | 第一版不承诺完整业务覆盖，只保证可追溯草案 | 否 | 已确认 |

## 关联 ADR、迁移、spec 或 issue

- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)
