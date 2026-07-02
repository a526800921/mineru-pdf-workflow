# 计划：结构化数据入库准备管线

## 背景

`structured-data-extraction` 已在输出包 `<package>/data/` 下生成可审核草案：`quick_lookup_draft.csv`、`verification.csv` 和 `fixtures_result.md`。这些文件当前只承载人工复核和后续入库准备，不直接写入数据库。

本计划负责把“可审核草案”继续推进到“可入库候选”的边界设计：明确字段契约、主键策略、审核状态流转、冲突处理、回滚方式和后续实施阶段。阶段 0 只落地设计和门禁，不改代码、不接数据库。

## 事实源职责

本文档是 `data-ingestion-pipeline` 的实施细节事实源，记录入库准备边界、候选字段、状态枚举、主键策略、Step 0 证据、验证方式、完成条件、风险、回滚和未决问题。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。输出包目录结构以 [PDF 输出包目录结构计划](pdf-output-package-layout.md) 为准。结构化草案输出契约以 [输出包结构化数据抽取计划](structured-data-extraction.md) 为准。

## 目标

- 定义从 `quick_lookup_draft.csv` 到可入库候选记录的最小契约。
- 固定入库准备产物与原草案文件之间的追溯关系。
- 明确人工审核状态和入库状态的候选枚举。
- 明确 deterministic `record_id`、冲突检测和回滚边界。
- 为后续阶段生成 `ingest_ready.csv` 或等价产物提供可执行门禁。

## 非目标

- 阶段 0 不实现代码。
- 阶段 0 不写入业务数据库。
- 阶段 0 不新增 MCP 工具。
- 阶段 0 不修改 `scripts/pdf-extract-data`、`scripts/pdf-auto` 或输出包生成逻辑。
- 不承诺最终数据库选型，数据库、SQLite、JSONL 或 CSV 只作为后续候选。

## 不变量

- 原始草案文件不被入库准备流程就地修改。
- 没有人工审核通过的数据不得标记为可入库。
- 每条入库候选必须可追溯到源输出包、源 CSV 行和证据文本。
- 入库准备产物必须可重复生成；同一输入和同一审核状态下 `record_id` 稳定。
- 冲突、低置信度、缺证据或字段不完整的数据必须保留在不可入库状态。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。

## 影响模块或文件

阶段 0 只新增或更新文档：

- `docs/plans/data-ingestion-pipeline.md`
- `docs/PLAN_MAP.md`

后续实施代码时，候选范围为：

- 新增 `scripts/pdf-prepare-ingest` 或等价脚本。
- `README.md`：仅在脚本可用后补充使用方式。
- `<package>/data/ingest_ready.csv` 或等价入库候选产物。

阶段 0 不修改：

- `scripts/pdf-extract-data`
- `scripts/pdf-seg`
- `scripts/pdf-merge`
- `scripts/pdf-auto`
- `scripts/pdf-validate`
- `mcp/server/*`

## 候选输出契约

阶段 0 将入库准备产物定义为候选契约，后续阶段实施前仍可收敛字段名和状态枚举。默认候选文件为：

```text
<package>/data/
  ingest_ready.csv
```

### ingest_ready.csv

| 字段 | 含义 | 规则 |
|---|---|---|
| `record_id` | 稳定记录 ID | 由源包、源行哈希和关键业务字段生成 |
| `source_pdf` | 源 PDF 文件名 | 继承 `quick_lookup_draft.csv.source_pdf` |
| `model` | 车型或文档名 | 继承草案字段 |
| `section_path` | 章节路径 | 继承草案字段 |
| `key` | 字段名 | 继承草案字段，后续可做规范化 |
| `value` | 字段值 | 继承草案字段，后续可做类型校验 |
| `unit` | 单位 | 继承草案字段或人工修正 |
| `evidence_text` | 证据文本 | 必填，来自草案证据 |
| `confidence` | 抽取置信度 | 继承草案字段 |
| `review_status` | 人工审核状态 | `draft`、`needs_review`、`approved`、`rejected` |
| `ingest_status` | 入库状态 | `not_ready`、`ready`、`ingested`、`skipped` |
| `source_row_hash` | 源草案行哈希 | 用于追溯和幂等检测 |
| `created_at` | 生成时间 | 阶段 1 固定为空字符串；后续真实入库时再固定时间来源和时区策略 |
| `notes` | 备注 | 冲突、修正、跳过原因 |

### 状态语义

`review_status` 候选语义：

| 状态 | 含义 |
|---|---|
| `draft` | 草案行尚未人工复核 |
| `needs_review` | 需要人工确认或补证据 |
| `approved` | 已人工确认，可进入入库准备 |
| `rejected` | 明确拒绝，不进入入库 |

`ingest_status` 候选语义：

| 状态 | 含义 |
|---|---|
| `not_ready` | 不满足入库条件 |
| `ready` | 已通过审核和冲突检查，可被下游入库 |
| `ingested` | 已由下游系统确认入库 |
| `skipped` | 主动跳过，保留原因 |

### 主键策略候选

阶段 0 候选策略：

```text
record_id = sha256(source_pdf + model + section_path + key + value + unit + source_row_hash)
source_row_hash = sha256(quick_lookup_draft.csv 的规范化整行内容)
```

后续阶段需要验证该策略是否能处理同一字段多来源、多版本 PDF、人工修正后重算和业务字段重命名。

### 冲突处理候选

- 同一 `record_id` 重复出现时视为幂等重复。
- 同一 `model + section_path + key` 出现多个不同 `value` 时标记为冲突，`ingest_status=not_ready`。
- `evidence_text` 为空或 `review_status` 不是 `approved` 时不得进入 `ready`。
- `confidence=low` 的记录即使人工未拒绝，也必须先停留在 `needs_review` 或 `not_ready`。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化入库边界和候选契约 | `structured-data-extraction` 已完成 | 草案样本、字段契约、状态流转、完成条件明确 | 已完成 |
| 阶段 1 | 生成入库候选文件 | 阶段 0 完成 | 生成 `ingest_ready.csv`，记录 ID 稳定，源行可追溯 | 已完成 |
| 阶段 2 | 人工审核状态流转和冲突检查 | 阶段 1 完成 | 审核状态、冲突、跳过原因可复现 | 候选 |
| 阶段 3 | 实际入库接口或外部系统边界 | 阶段 2 完成 | 下游接口、回滚和幂等策略明确 | 候选 |

## 当前阶段

阶段 0-1 已完成（2026-07-02）。阶段 2（人工审核状态流转）候选。

## Step 0 证据

### 样本状态

2026-07-02 已完成 `structured-data-extraction` 全阶段验收，demo20 和 demo5 可作为入库准备边界样本：

- `pdf/demo20/data/quick_lookup_draft.csv`：54 行含表头。
- `pdf/demo20/data/verification.csv`：8 行含表头。
- `pdf/demo20/data/fixtures_result.md`：已生成摘要报告。
- `pdf/demo5/data/quick_lookup_draft.csv`、`verification.csv`、`fixtures_result.md`：空样本路径稳定。
- `README.md` 已说明 `scripts/pdf-extract-data` 用法，并明确不写入数据库。

### 可复现命令

```bash
scripts/pdf-extract-data pdf/demo20
scripts/pdf-extract-data pdf/demo5
wc -l pdf/demo20/data/quick_lookup_draft.csv
wc -l pdf/demo20/data/verification.csv
head -n 1 pdf/demo20/data/quick_lookup_draft.csv
```

### 当前缺口

- 尚无 `ingest_ready.csv` 或等价入库候选产物。
- 尚无正式入库状态流转脚本。
- 尚无业务数据库、SQLite、JSONL 或外部系统选型。
- 尚无跨 PDF 版本的主键冲突样本。

## 阶段 0 验收命令

```bash
test -f pdf/demo20/data/quick_lookup_draft.csv
test -f pdf/demo20/data/verification.csv
test -f pdf/demo20/data/fixtures_result.md
head -n 1 pdf/demo20/data/quick_lookup_draft.csv | grep 'source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes'
python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 0 完成证据（2026-07-02）

- 入库候选契约已固化：`ingest_ready.csv`（14 字段）、`review_status` 4 状态枚举、`ingest_status` 4 状态枚举。
- 主键策略候选：`record_id = sha256(source_pdf + model + section_path + key + value + unit + source_row_hash)`。
- 冲突处理候选：同 key 异值标记 `not_ready`、低置信度不得进 `ready`、非 approved 不得入库。
- demo20/demo5 草案样本可用（54 行/0 行），`structured-data-extraction` 全阶段已完成。
- 计划已进入 `PLAN_MAP.md`（设计中 → 待实施），依赖关系明确。
- 阶段 1 实施边界：新增 `scripts/pdf-prepare-ingest`，不改抽取脚本、不写数据库、不新增 MCP。

### 阶段 0 完成条件

- 本计划进入 `PLAN_MAP.md`，状态为 `待实施` 或后续状态。
- 入库边界、候选字段、状态枚举、主键策略、冲突处理和回滚策略已记录。
- 依赖 `structured-data-extraction` 和 `pdf-output-package-layout` 已在 `PLAN_MAP.md` 中明确。
- 阶段 1 实施边界清楚：新增入库准备产物生成脚本，不改抽取脚本、不写数据库、不新增 MCP。

## 阶段 1 可实施说明

阶段 1 新增一个最小脚本 `scripts/pdf-prepare-ingest <package>`，读取 `<package>/data/quick_lookup_draft.csv`，生成 `<package>/data/ingest_ready.csv`。实施前必须先复核阶段 0 契约，并按 GitNexus 规则做影响分析。

### 阶段 1 目标

- 生成 `ingest_ready.csv`。
- 以稳定算法生成 `record_id` 和 `source_row_hash`。
- 保留源草案行的可追溯字段。
- 对未审核、低置信度、冲突或缺证据记录输出 `not_ready`。

### 阶段 1 非目标

- 不写入数据库。
- 不修改 `quick_lookup_draft.csv`。
- 不新增 MCP 工具。
- 不做业务字段字典映射。

### 阶段 1 输入输出

输入：

```text
<package>/data/quick_lookup_draft.csv
```

输出：

```text
<package>/data/ingest_ready.csv
```

`ingest_ready.csv` 字段以本文档的候选输出契约为准。阶段 1 不引入独立 schema 文件，字段校验通过脚本内表头常量和验收命令完成。

### 阶段 1 生成规则

- `source_row_hash` 使用源草案行的规范化字段值计算，字段顺序沿用 `quick_lookup_draft.csv` 表头。
- `record_id` 使用阶段 0 候选主键策略生成，同一源行重复运行必须稳定。
- 草案 `status=draft` 默认映射为 `review_status=draft`、`ingest_status=not_ready`。
- 草案 `status=needs_review` 默认映射为 `review_status=needs_review`、`ingest_status=not_ready`。
- 草案 `status=rejected` 默认映射为 `review_status=rejected`、`ingest_status=skipped`。
- 阶段 1 不自动生成 `approved` 或 `ready`，避免未审核数据误入库。
- 阶段 1 的 `created_at` 固定为空字符串，避免重复生成时因运行时间变化破坏幂等。
- 缺少 `evidence_text`、`key` 或 `value` 的记录必须保持 `ingest_status=not_ready`，并在 `notes` 记录原因。
- 同一 `model + section_path + key` 出现多个不同 `value` 时必须标记冲突，相关记录保持 `not_ready`。
- 空草案输入也必须生成只有表头的 `ingest_ready.csv`。

### 阶段 1 验收命令

```bash
# 实施前影响分析（新增脚本）
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --direction upstream scripts/pdf-prepare-ingest || true

python3 -m py_compile scripts/pdf-prepare-ingest

scripts/pdf-prepare-ingest pdf/demo20
test -f pdf/demo20/data/ingest_ready.csv
head -n 1 pdf/demo20/data/ingest_ready.csv | grep 'record_id,source_pdf,model,section_path,key,value,unit,evidence_text,confidence,review_status,ingest_status,source_row_hash,created_at,notes'
test "$(wc -l < pdf/demo20/data/ingest_ready.csv | tr -d ' ')" -eq "$(wc -l < pdf/demo20/data/quick_lookup_draft.csv | tr -d ' ')"

scripts/pdf-prepare-ingest pdf/demo5
test -f pdf/demo5/data/ingest_ready.csv
test "$(wc -l < pdf/demo5/data/ingest_ready.csv | tr -d ' ')" -eq 1

cp pdf/demo20/data/ingest_ready.csv /tmp/demo20-ingest-ready.before
scripts/pdf-prepare-ingest pdf/demo20
cmp /tmp/demo20-ingest-ready.before pdf/demo20/data/ingest_ready.csv

python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 1 完成证据（2026-07-02）

- `scripts/pdf-prepare-ingest <package>` 已创建，读取 `quick_lookup_draft.csv` → 生成 `ingest_ready.csv`（14 字段）。
- `record_id`：`sha256(source_pdf|model|section_path|key|value|unit|source_row_hash)`（64-hex）。
- `source_row_hash`：`sha256(14 字段规范化行)`。
- 状态映射：`draft→draft/not_ready`、`needs_review→needs_review/not_ready`、`rejected→rejected/skipped`。
- 冲突检测：同 `model+section_path+key` 多值 → `not_ready`；缺证据/低置信度/非 approved → `not_ready`。
- demo20：53 行 → `ingest_ready.csv` 54 行（含表头），全部 `not_ready`。
- demo5：空草案 → 仅表头（1 行）。
- 幂等性：`cmp` 字节一致。`created_at` 固定为空字符串。
- 不写数据库、不修改原草案、不新增 MCP。`py_compile`/`check_plan_governance`/`npm build` 通过。

### 阶段 1 完成条件

## 风险

- `quick_lookup_draft.csv` 的草案质量不足，可能导致入库候选大量停留在 `not_ready`。
- 主键策略可能无法覆盖多版本 PDF 或人工修正后的稳定性要求。
- 审核状态和入库状态如果混用，会导致下游误入库。
- 数据库选型尚未确定，阶段 0 字段契约后续可能需要适配。
- 后续阶段若引入真实 `created_at`，必须先固定时间来源和时区策略，避免破坏幂等验证。

## 回滚

- 阶段 0 纯文档变更，可删除本计划或将状态标记为 `已废弃`。
- 后续生成的 `ingest_ready.csv` 只作为派生产物，可删除后从草案重新生成。
- 后续若接入外部系统，必须在阶段 3 前补充独立回滚和幂等策略。

## 未决问题

- 最终入库目标是业务数据库、SQLite、JSONL 还是继续使用 CSV。
- 是否需要独立 JSON Schema 或 CSV schema 文件做机器校验。
- `record_id` 是否应纳入 PDF hash、版本号或人工审核批次。
- 人工审核状态是否由 CSV 编辑、单独 review 文件或外部系统维护。
- 是否需要在 MCP 中暴露入库准备能力。
