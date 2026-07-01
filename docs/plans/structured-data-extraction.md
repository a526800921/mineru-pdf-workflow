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
| 阶段 1 | 最小数据草案生成 | 阶段 0 完成 | 生成三个 `data/` 文件，CSV 表头稳定 | 已完成 |
| 阶段 2 | 抽取规则扩展和审核口径 | 阶段 1 完成 | 表格、冒号行、章节路径覆盖更多样本 | 已完成 |
| 阶段 3 | 治理收尾和后续入库边界 | 阶段 2 完成 | README、PLAN_MAP、验收证据同步 | 已完成 |

## 当前阶段

全阶段（0-3）已完成（2026-07-02）。计划状态：已完成。

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

## 阶段 1 可实施说明

阶段 1 新增一个最小脚本 `scripts/pdf-extract-data <package>`，只负责把已有输出包转换成可审核的数据草案。脚本失败不得修改原始 PDF、分段目录、合并 Markdown 或 MCP 契约。

### 阶段 1 目标

- 生成 `<package>/data/quick_lookup_draft.csv`、`<package>/data/verification.csv`、`<package>/data/fixtures_result.md`。
- CSV 表头与本文档输出契约完全一致。
- 输出可重复生成：同一输出包连续运行两次，三类 `data/` 文件的表头和行数稳定。
- 所有草案行必须带 `evidence_text`、`status` 和 `confidence`，无法确认的行使用 `needs_review`。

### 阶段 1 非目标

- 不抽取完整车型参数表。
- 不新增数据库、MCP 工具或外部依赖。
- 不修改 `pdf-seg`、`pdf-auto`、`pdf-merge`、`pdf-validate`。
- 不做大模型推断或字段补全。

### 建议脚本接口

```bash
scripts/pdf-extract-data <package>
```

示例：

```bash
scripts/pdf-extract-data pdf/demo20
scripts/pdf-extract-data pdf/demo5
```

参数规则：

- `<package>` 必须是输出包目录。
- 必须存在 `<package>/manifest.json`。
- 必须存在 `<package>/<stem>.md`，其中 `<stem>` 优先来自 `manifest.json.files.markdown`。
- 必须存在 `<package>/segments/`。
- 脚本自动创建 `<package>/data/`。

### 建议实现步骤

1. 读取 `<package>/manifest.json`、`<package>/<stem>.md` 和 `segments/**/content_list_v2.json`。
2. 从 Markdown 标题推导当前 `section_path`。
3. 从 Markdown 表格行、冒号行和 `content_list_v2.json` 文本元素中生成最小 `quick_lookup_draft.csv` 草案。
4. 生成 `verification.csv`，至少记录 manifest、Markdown、segments、content_list、images、输出文件写入这几类检查。
5. 生成 `fixtures_result.md`，给人工验收使用。
6. 对无法可靠归类的字段输出 `needs_review`，不伪造高置信度结果。

阶段 1 不要求抽取完整业务字段；成功标准是输出文件稳定、可追溯、可重复生成。

### 最小抽取规则

- Markdown 标题行（`#`、`##`、`###`）更新 `section_path`，不直接生成草案行。
- Markdown 表格行如能解析为两列或多列，第一列作为 `key`，其余列拼接为 `value`；置信度 `medium`，状态 `draft`。
- 包含中文或英文冒号的短行可作为键值候选；置信度 `low`，状态 `needs_review`。
- `content_list_v2.json` 只作为证据补充和检查来源；阶段 1 不要求从复杂嵌套结构完整抽取表格。
- 图片引用不生成草案行，但进入 `verification.csv` 和 `fixtures_result.md` 摘要。

### 阶段 1 验收命令

```bash
# 实施前影响分析（新增脚本首次实施时）
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --direction upstream scripts/pdf-extract-data || true

python3 -m py_compile scripts/pdf-extract-data

scripts/pdf-extract-data pdf/demo20
test -f pdf/demo20/data/quick_lookup_draft.csv
test -f pdf/demo20/data/verification.csv
test -f pdf/demo20/data/fixtures_result.md
head -n 1 pdf/demo20/data/quick_lookup_draft.csv | grep 'source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes'
head -n 1 pdf/demo20/data/verification.csv | grep 'check_id,level,target,result,details,source'
grep -q '可复现命令' pdf/demo20/data/fixtures_result.md

scripts/pdf-extract-data pdf/demo5
test -f pdf/demo5/data/quick_lookup_draft.csv
test -f pdf/demo5/data/verification.csv
test -f pdf/demo5/data/fixtures_result.md

# 幂等性：连续运行 demo20 后表头和行数稳定
wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-counts.before
scripts/pdf-extract-data pdf/demo20
wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-counts.after
diff -u /tmp/pdf-extract-data-counts.before /tmp/pdf-extract-data-counts.after

python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 1 完成证据（2026-07-01）

- `scripts/pdf-extract-data` 已创建，纯 Python 实现，规则抽取冒号行和 Markdown 表格行。
- demo20：`quick_lookup_draft.csv`（2 行 / 13 列）、`verification.csv`（7 项检查）、`fixtures_result.md`（含统计和可复现命令）。
- demo5：`quick_lookup_draft.csv`（0 行，空 TOC 样本符合预期）、`verification.csv`、`fixtures_result.md`。
- 幂等性：连续两次运行 demo20，表头和行数不变（3 行 / 8 行 diff 为空）。
- CSV 表头与输出契约完全一致。
- `python3 -m py_compile`、`npm run build`、`check_plan_governance.py` 通过。GitNexus `impact` 对新增脚本返回 `Target not found`，当前索引未包含该脚本符号；`detect_changes` 未发现受影响执行流。
- `pdf-seg`、`pdf-auto`、MCP 契约无变更。

### 阶段 1 完成条件

## 阶段 2 可实施说明

阶段 2 在阶段 1 的最小脚本基础上扩展抽取规则和审核口径，目标是提高 `quick_lookup_draft.csv` 的可用行数和可审核性，同时保持“有证据、低置信度不放行”的原则。

### 阶段 2 目标

- 扩展 Markdown 表格解析，支持多列表格、参数/数值/单位拆分。
- 扩展冒号行规则，过滤明显非参数文本，降低噪声。
- 引入章节路径质量检查，确保抽取行能落到可读的 `section_path`。
- 细化 `confidence` 和 `status` 口径，让 `draft`、`needs_review` 的差异可验收。
- 在 `fixtures_result.md` 中增加规则命中统计和待审核原因摘要。

### 阶段 2 非目标

- 不接入数据库。
- 不新增 MCP 工具。
- 不用大模型解释或补全字段。
- 不改变阶段 1 已固化的 CSV 表头。
- 不要求一次性覆盖全部车型参数，只提升 demo20/demo5 的规则覆盖和审核信息质量。

### 规则扩展范围

表格规则：

- 跳过 Markdown 分隔行和空表格行。
- 对两列表格，第一列作为 `key`，第二列作为 `value`。
- 对三列及以上表格，优先识别列名包含“项目/参数/名称”的列作为 `key`，列名包含“值/规格/说明/参数”的列作为 `value`。
- 从 `value` 尾部拆分常见单位到 `unit`，例如 `mm`、`cm`、`kg`、`kW`、`N·m`、`L`、`V`、`A`、`Ah`、`rpm`、`MPa`、`kPa`、`℃`。
- 无法识别 key/value 关系的表格行仍可输出，但 `confidence=low`、`status=needs_review`。

冒号行规则：

- 支持中文冒号和英文冒号。
- 过滤过长说明句、URL、纯页眉页脚、图片引用和明显目录点线。
- key 长度控制在 2-40 字符，value 长度控制在 1-200 字符。
- 冒号行默认 `confidence=low`、`status=needs_review`；如果命中单位或数字结构，可提升到 `confidence=medium`。

章节路径规则：

- 只使用 Markdown 标题构造 `section_path`。
- 当抽取行没有章节路径时，`verification.csv` 记录 warning。
- `fixtures_result.md` 展示命中最多的章节路径，便于人工判断抽取集中位置。

审核口径：

| 条件 | confidence | status |
|---|---|---|
| 表格 key/value 明确，value 非空，有章节路径 | `medium` | `draft` |
| 表格关系不明确但有证据文本 | `low` | `needs_review` |
| 冒号行命中数字或单位结构 | `medium` | `needs_review` |
| 冒号行普通文本 | `low` | `needs_review` |
| 缺少证据文本 | 不输出该行 | 不输出该行 |

### 阶段 2 建议修改范围

- `scripts/pdf-extract-data`
- `docs/plans/structured-data-extraction.md`
- `docs/PLAN_MAP.md`

阶段 2 不修改：

- `scripts/pdf-seg`
- `scripts/pdf-auto`
- `scripts/pdf-merge`
- `scripts/pdf-validate`
- `mcp/server/*`

### 阶段 2 验收命令

```bash
# 修改脚本前先做影响分析
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --direction upstream pdf-extract-data || true

python3 -m py_compile scripts/pdf-extract-data

scripts/pdf-extract-data pdf/demo20
test -f pdf/demo20/data/quick_lookup_draft.csv
test -f pdf/demo20/data/verification.csv
test -f pdf/demo20/data/fixtures_result.md

# 表头保持阶段 1 契约
head -n 1 pdf/demo20/data/quick_lookup_draft.csv | grep 'source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes'
head -n 1 pdf/demo20/data/verification.csv | grep 'check_id,level,target,result,details,source'

# 规则扩展后 demo20 至少保持阶段 1 行数，不允许回退为空
test "$(($(wc -l < pdf/demo20/data/quick_lookup_draft.csv)))" -ge 3

# fixtures_result.md 必须包含规则命中统计和审核摘要
grep -q '规则命中统计' pdf/demo20/data/fixtures_result.md
grep -q '待审核' pdf/demo20/data/fixtures_result.md

scripts/pdf-extract-data pdf/demo5
test -f pdf/demo5/data/quick_lookup_draft.csv
test -f pdf/demo5/data/verification.csv
test -f pdf/demo5/data/fixtures_result.md

# 幂等性：连续运行 demo20 后表头和行数稳定
wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-phase2.before
scripts/pdf-extract-data pdf/demo20
wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-phase2.after
diff -u /tmp/pdf-extract-data-phase2.before /tmp/pdf-extract-data-phase2.after

cd mcp/server && npm run build
cd ../..
python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 2 完成证据（2026-07-01）

- 扩展规则：HTML 表格解析（含 key/value 列猜测和 colspan 支持）、冒号行噪声过滤（安全提示/URL/TOC）、单位拆分（mm/kg/kW 等 16+ 单位）。
- 置信度口径细化：表格 key/value 明确 → `medium/draft`；冒号行命中数字+单位 → `medium/needs_review`；普通冒号行 → `low/needs_review`。
- demo20：**53 行**（51 html_table + 2 colon_line），阶段 1 基线 2 行，提升 26 倍。51 行 `draft`、2 行 `needs_review`。
- `fixtures_result.md` 新增：规则命中统计、置信度分布、命中章节 TOP 10、待审核原因摘要。
- `verification.csv` 新增 section_path 缺失 warning 检查。
- demo5 回归（0 行，空 TOC 符合预期）、幂等性通过、CSV 表头不变。
- `python3 -m py_compile`、`npm run build`、`check_plan_governance.py` 通过。
- 无 `pdf-seg`/`pdf-auto`/MCP 契约变更。

### 阶段 2 完成条件

## 阶段 3 可实施说明

阶段 3 是本计划的治理收尾阶段，只固化当前 CLI 能力、运行说明和后续边界，不新增数据抽取规则，不接入数据库。

### 阶段 3 目标

- 在 README 中补充 `scripts/pdf-extract-data` 的用途和推荐流程位置。
- 同步 `PLAN_MAP.md`，将 `structured-data-extraction` 收尾为已完成或明确后续计划。
- 明确“入库”是后续独立计划，不属于本计划实现范围。
- 复验 demo20/demo5 的数据草案生成、幂等性和 MCP 构建，作为最终完成证据。

### 阶段 3 非目标

- 不修改 `scripts/pdf-extract-data` 抽取规则。
- 不新增 MCP 工具。
- 不实现数据库写入、业务 schema 映射或后台服务。
- 不引入 JSON Schema；是否需要 JSON Schema 留给后续入库计划评估。

### 后续入库边界

本计划交付的是可审核草案，不是入库接口。后续如要推进入库，应新建独立计划，例如 `data-ingestion-pipeline`，并重新定义：

- 目标数据库或目标文件格式。
- 业务字段 schema 和主键策略。
- 审核状态从 `draft` / `needs_review` 到可入库状态的流转。
- 冲突处理、版本策略和回滚方式。
- MCP 或其他自动化入口是否需要扩展。

### 阶段 3 验收命令

```bash
python3 -m py_compile scripts/pdf-extract-data

scripts/pdf-extract-data pdf/demo20
scripts/pdf-extract-data pdf/demo5

test -f pdf/demo20/data/quick_lookup_draft.csv
test -f pdf/demo20/data/verification.csv
test -f pdf/demo20/data/fixtures_result.md
test -f pdf/demo5/data/quick_lookup_draft.csv
test -f pdf/demo5/data/verification.csv
test -f pdf/demo5/data/fixtures_result.md

grep -q 'scripts/pdf-extract-data' README.md
grep -q '不写入数据库' README.md

wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-final.before
scripts/pdf-extract-data pdf/demo20
wc -l pdf/demo20/data/quick_lookup_draft.csv pdf/demo20/data/verification.csv > /tmp/pdf-extract-data-final.after
diff -u /tmp/pdf-extract-data-final.before /tmp/pdf-extract-data-final.after

cd mcp/server && npm run build
cd ../..
python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 3 完成证据（2026-07-02）

- README 已包含 `pdf-extract-data` 用途、输出目录和"不写入数据库"边界说明。
- `后续入库边界` 节已明确：入库需新建独立计划（如 `data-ingestion-pipeline`），重新定义 schema/主键/状态流转/冲突策略。
- 全阶段（0-3）完成证据闭环：契约固化→脚本生成→规则扩展→治理收尾。
- 最终回归通过：`py_compile`、demo20（54 行）/ demo5（0 行）、幂等性、表头兼容、MCP build、`check_plan_governance.py`。
- 无脚本/CLI/MCP 契约变更。
- `PLAN_MAP.md` 已更新为 `已完成`。

### 阶段 3 完成条件

## 验证方式

阶段 0：

```bash
python3 scripts/check_plan_governance.py .
git diff --check
```

阶段 1：

```bash
python3 -m py_compile scripts/pdf-extract-data
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
