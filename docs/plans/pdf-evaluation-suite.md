# 计划：PDF 评测套件（P4）

## 背景

`pdf-workflow-enhancement-roadmap` 的 P4 阶段对标豆包四层架构的"生产评测"层。原 P4 把三件事捆为一个粗粒度候选阶段：表格解析精度评测、TOC 条目级验证、多模态 VLM 图表理解。2026-07-08 的 Step 0 侦察表明三者可实施性差异极大：TOC 条目级验证设计已就绪且零依赖，表格结构自检指标无需人工标注即可实施，而多模态 VLM 需要选型与外部环境评估。

据此将 P4 拆分为可独立验收的子阶段，本计划为 P4 的实施细节事实源。

## 事实源职责

本文档是 P4（评测套件）的实施细节事实源，记录字段方案、Schema、Step 0 证据、验证方式、完成条件、风险和未决问题。

计划状态、依赖、替代/合并/废弃关系、推荐顺序和当前阻塞项以 [PLAN_MAP](../PLAN_MAP.md) 为准。阶段顺序摘要以 [pdf-workflow-enhancement-roadmap](pdf-workflow-enhancement-roadmap.md#阶段路线图) 为准。

TOC 条目级验证的字段方案（`toc_entries` / `toc_stats` Schema、抽取正则、设计决策）事实源为 [覆盖率验证口径优化计划#后续增强候选](coverage-validation-optimization.md#后续增强候选)，本文档不复制，只记录 P4a 的实施决策与门禁。

## 目标

- 补齐生产评测层：TOC 条目级验证（P4a）+ 表格结构自检评测（P4b）。
- 各子阶段产出可独立验收、只读、不改现有页面决策的评测增量。
- 完成多模态 VLM 图表理解（P4c）的本地模型调用、结构化输出和抽样验收。

## 范围

- **P4a（已完成）**：目录页在 `pdf-validate` 输出中新增条目级验证字段，`review.md` 逐条目报告缺失。
- **P4b（已完成）**：对 `content_list.json`（v1）的 table 元素做结构自检，产出 `<package>/data/table_accuracy.csv`。
- **P4c（已完成）**：对 `image_or_sparse` 页调用本地 VLM（qwen3-vl-8b，MLX 8bit）产出结构化描述，写入 `data/vlm_eval.jsonl`。10 页均匀抽样全部通过。

## 非目标

- 不改变 MinerU 解析引擎或表格 HTML 抽取本身。
- 不改变 `pdf-validate` 现有 `status` / `rerunnable` 页面决策（评测只新增字段与产物）。
- P4b 不做 TEDS / 单元格 F1 等需要人工标注 ground truth 的精度评测（用户决策：走结构自检指标）。
- 不新增 Python 依赖（纯规则 + 标准库 `html.parser` / 现有 `_strip_html`）。
- P4c 不在本轮承诺 VLM 环境搭建或 API 成本。

## 不变量

- 现有 CLI 脚本签名和 JSON 输出契约不变；评测字段为新增，向后兼容。
- 原始 PDF、分段结果、合并 Markdown、`chunks.jsonl` 不被评测工具修改（只读）。
- `run_pdf_auto` 及现有 8+1 个 MCP 工具契约不变；评测工具作为新增。
- 同一事实只定义一次：P4a 字段方案链接 coverage 计划，P4b 字段方案在本文档定义。

## 影响模块或文件

P4a（TOC 条目级验证）：

- `scripts/pdf-validate`：`detect_page_type` 已识别 `toc` 页；新增条目抽取与 `toc_entries` / `toc_stats` 字段。
- `scripts/lib/review_report.py`：`review.md` 生成逐条目缺失报告。

P4b（表格结构自检评测，已完成）：

- `scripts/pdf-eval-tables`（已建）：读取输出包 `content_list.json`（v1）的 table 元素，产出 `data/table_accuracy.csv`；选段复用 pdf-merge 段名正则口径。
- `scripts/lib/table_eval.py`（已建）：HTML 表格结构解析（含 rowspan/colspan 网格展开）、选段口径、section 段级定位与自检指标计算。
- `tests/test_table_eval.py`（已建）：15 个零依赖单测覆盖解析/选段/section 三组纯逻辑。
- MCP `eval_tables`：未实现（决定 CLI-only，见未决问题）。

P4c（已完成）：`scripts/pdf-eval-vlm`（新建，`fitz` 整页渲染 `image_or_sparse` 页 + 调 ModelPad 托管的 qwen3-vl-8b 8bit 量化 VLM → `data/vlm_eval.jsonl`）。

## 公共契约变化

- P4a：`pdf-validate` JSON 中 `toc` 页新增 `toc_entries` / `toc_stats` 字段（字段语义链接 coverage 计划）。
- P4b：新增产物 `<package>/data/table_accuracy.csv`（Schema 见下）。CLI-only，未新增 MCP 工具（`tools/list` 维持 9）。
- P4c：新增产物 `<package>/data/vlm_eval.jsonl`（8 字段 Schema 见 P4c 输出契约）。CLI-only，未新增 MCP 工具（`tools/list` 维持 9）。

## P4a：TOC 条目级验证（已完成）

### 字段方案

`toc_entries` / `toc_stats` Schema、`TOC_ENTRY_RE` 抽取正则、字段语义详见 [覆盖率验证口径优化计划#toc_entries-json-扩展](coverage-validation-optimization.md#后续增强候选)。本文档不复制。

### 实施决策（本计划固定）

| 决策 | 选择 | 依据 |
|---|---|---|
| 条目级验证是否改变页面决策 | 仅用于 `review.md` 展示，不影响 `review_only` vs `rerun` | coverage 计划推荐"初期仅展示"，保持不变量 |
| 修复策略 | 补全模式（仅补丢失条目，不替换全页） | coverage 计划推荐，更安全 |
| 跨行 TOC 条目 | 先单行 `TOC_ENTRY_RE`，再合并相邻行 | coverage 计划 p0001 实测 ~80% 单行可匹配 |

### Step 0 证据

- coverage 计划 p0001 实测：约 18 个目录条目，2 条完全丢失（"前言"、"后制动手柄"），`TOC_ENTRY_RE` 对约 80% 条目有效（coverage-validation-optimization.md:176-224）。
- `scripts/pdf-validate` 已有 `_TOC_PATTERN`、`detect_page_type` 返回 `toc`，条目抽取可在既有 toc 分支内实现。

### 验证方式

```bash
PDF_VALIDATE_JSON=1 scripts/pdf-validate "pdf/春风 150AURA/春风 150AURA.pdf" "pdf/春风 150AURA/segments" > /tmp/p4a.json
python3 -c "
import json
r = json.load(open('/tmp/p4a.json'))
toc_pages = [s for seg in r['segments'] for s in seg.get('pages', []) if s.get('page_type') == 'toc']
assert toc_pages, 'no toc page'
p = toc_pages[0]
assert 'toc_entries' in p and 'toc_stats' in p, 'missing toc fields'
st = p['toc_stats']
assert st['total'] == st['found'] + st['missing'] + st['partial'], 'toc_stats 不自洽'
print('P4a: toc_entries/toc_stats 字段完整且自洽')
"
```

### 完成条件

- [x] `toc` 页 JSON 含 `toc_entries[]`（`title` / `page_ref` / `found` / `match_text`）和 `toc_stats`（`total` / `found` / `missing` / `partial`）。→ 春风 150AURA 7 个 toc 页、121 条目字段全完整。
- [x] `toc_stats.total == found + missing + partial`，计数自洽。→ 结构性保证 + 全量 7 页 + 定向单测均自洽。
- [x] `review.md` 对 toc 页逐条目列出缺失标题，而非仅"整页覆盖率低"。→ 7 目录页逐条目，第 3 页缺失表列出 `LCD 仪表（根据配置）`。
- [x] 不改变现有 `status` / `rerunnable` 判定（对照 P4a 前后 `page_type_summary` 一致）。→ A/B 剥离 toc 字段后新旧 JSON 逐字节一致。
- [x] `python3 scripts/check_plan_governance.py .` 通过。

### 验收记录（2026-07-08）

**结论：P4a 达到"已完成"标准，5 条完成条件全部达标。**

代码改动（未提交）：`scripts/pdf-validate`（+102，`extract_toc_entries` / `_extract_toc_candidates` + toc 页字段注入）、`scripts/lib/review_report.py`（+45，`_append_toc_entry_details`）。

严格验收证据：

- **A/B 金标准回归**：`git stash` 两个代码文件跑旧版，剥离 `toc_entries`/`toc_stats` 后新旧 pdf-validate JSON（春风 150AURA 24 段）**逐字节完全一致** → P4a 为纯增量、零副作用，`status`/`decision`/`rerunnable`/`coverage`/`page_type_summary` 全不变。
- **退出码排雷**：`exit=1` 确认为 pdf-validate "有 suspicious 段即 `SystemExit(1)`"（行 560）的既有契约，旧版同样 exit=1，非 P4a 回归。
- **真实样本覆盖**：7 个 toc 页共 121 条目，found=120 / missing=0 / partial=1，全部自洽。
- **分支补盲**：真实样本 missing=0，构造定向单测（用脚本内真实函数）强制触发 **missing / found / partial 三分支 + 跨行标题-页码配对**，`total=3=1+1+1` 自洽通过。
- **`found` 精确口径**：`found` = 目录条目标题（归一化后）是否出现在**该 toc 页自身**的 MinerU Markdown 输出中，即"目录页解析完整性"，而非"正文章节真实存在"。这是对 [coverage 计划字段语义](coverage-validation-optimization.md#后续增强候选)"是否在 MinerU 输出中找到"的实现细化。

skill 同步：P4a 仅扩展 `pdf-validate` 字段与 `review.md`（人工兜底清单），不涉及 PDF 解析流程、输出包结构、`run_pdf_auto` 契约或入库导出流程，**无需同步 `pdf2md` skill**。

## P4b：表格结构自检评测（已完成）

### 设计原理

用户决策：不做需要人工标注的 TEDS，改用**结构自检指标**——从表格 HTML 自身结构推断解析健全性，零 ground truth、零成本。列数不一致、HTML 解析失败等信号能定位大多数破损表格。

### 数据源

`<package>/segments/<pXXXX-YYYY>/<model>/hybrid_auto/<model>_content_list.json`（v1，扁平 content 项列表）中 `type == "table"` 元素的 **`table_body`** 字段（原始 HTML 字符串）。

- 春风 150AURA 全样本核实：v1 有 **115 个 table 元素，104 含 `table_body`**（另 11 空表 → `parse_status="empty"`）。
- **必须用 v1**：v2 虽也有 115 个 table 元素，但只带 `content`（纯文本）、无 `table_body`/HTML 结构，无法做结构自检；`pdf-validate`/coverage 用 v2 做逐页文本覆盖率，P4b 用 v1 做表格 HTML 结构，两者按目的分工，非口径漂移。
- **选段口径（实现决策）**：复用 pdf-merge 段名正则 `^p(\d{4,})-(\d{4,})$`，只取有效段，排除 `p0185-0191-rerun` 等遗留/临时目录与 `.DS_Store`。全扫所有子目录会把已被覆盖的旧段与 rerun 目录重复计数（实测 121 表），merge 口径为 115。
- 全局页码 = 段目录名起始页 + `page_idx`（`page_idx` 为**段内相对 0-based**，每段页数由 `segment_size` 决定，默认 10）。
- 解析用标准库 `html.parser`：单元格文本经 parser 的 data 事件天然与标签分离（`convert_charrefs=True` 自动解码实体），判空无需再过 `_strip_html`。

### 输出契约

`<package>/data/table_accuracy.csv`，每行一个表格：

| 字段 | 类型 | 说明 |
|---|---|---|
| `table_id` | string | 唯一标识，格式 `p<全局页码>_t<页内表序>`，如 `p0018_t01` |
| `page` | int | 全局页码（1-based）= 段起始页 + `page_idx` |
| `section` | string | 所属 `##` 标题（从合并 Markdown 按页锚点就近定位，可用 `table_caption` 辅助，缺省空串） |
| `row_count` | int | `<tr>` 行数 |
| `col_count` | int | 列数（取各行 `<td>`/`<th>` 计数含 colspan 展开后的最大值） |
| `cell_count` | int | 单元格总数 |
| `empty_cell_count` | int | 文本为空的单元格数 |
| `empty_cell_ratio` | float | `empty_cell_count / cell_count`，保留 3 位小数 |
| `merged_cell_count` | int | 含 `rowspan` 或 `colspan` 属性的单元格数 |
| `col_consistent` | bool | 各行展开后列数是否一致（解析健全性核心信号） |
| `parse_status` | string | `ok` / `malformed`（HTML 解析异常或列数不一致）/ `empty`（无单元格） |

### CLI-to-MCP 映射

| MCP 工具 | CLI 后端 | 说明 |
|---|---|---|
| `eval_tables`（可选） | `scripts/pdf-eval-tables`（需新建） | 产出 `data/table_accuracy.csv` |

### Step 0 证据

2026-07-08 全样本核实（纠正初版把数据源误写为 `content_list_v2` 的 `html` 字段——表格 HTML 实际在 **v1 的 `table_body`** 字段；v2 的 table 元素只有纯文本 `content`，无法用）：

- `content_list.json`（v1）table 元素 **115 个，104 含 `table_body`**，分布在 18 个段（参数/规格页密集；p0025-0032 等纯文本段为 0，不能以单段以偏概全）。
- table 元素字段：`type`、`table_body`(html)、`page_idx`(段内 0-based)、`table_caption`、`table_footnote`、`bbox`；html 含 `rowspan`/`colspan`。
- `content_list_v2.json` 虽也有 115 table，但其 table 元素只有 `content`（纯文本）、无 `table_body`/HTML；`pdf-validate`/coverage 用 v2 做逐页文本覆盖率（见 [coverage-analysis.md#方案-b提升-content_list-口径为主要观测来源](../coverage-analysis.md)），P4b 需要表格 HTML 结构，只能用 v1。
- 合并 Markdown `<table>` = 104，与 v1 含 `table_body` 的 104 一致（同源）。
- `pdf-validate` 的 `_strip_html` 可复用做单元格文本清洗。

### 验证方式

```bash
scripts/pdf-eval-tables "pdf/春风 150AURA"
python3 -c "
import csv
rows = list(csv.DictReader(open('pdf/春风 150AURA/data/table_accuracy.csv')))
assert len(rows) == 115, f'table 元素数应为 115: {len(rows)}'  # 104 含 table_body + 11 empty
cols = {'table_id','page','section','row_count','col_count','cell_count',
        'empty_cell_count','empty_cell_ratio','merged_cell_count','col_consistent','parse_status'}
assert cols <= set(rows[0].keys()), f'字段缺失: {cols - set(rows[0].keys())}'
empty = [r for r in rows if r['parse_status'] == 'empty']
bad = [r for r in rows if r['parse_status'] == 'malformed']
assert len(empty) == 11, f'空表数应为 11: {len(empty)}'
print(f'P4b: {len(rows)} 表格, {len(bad)} 结构异常, {len(empty)} 空表, 字段完整')
"

cd mcp/server && npm run build   # 若实现 MCP eval_tables
python3 scripts/check_plan_governance.py .
```

### 完成条件

- [x] `data/table_accuracy.csv` 产出，每行一个表格，含全部 11 个字段。→ 春风 150AURA 115 行、11 字段完整。
- [x] 表格数量与 `content_list.json` table 元素数一致（春风 150AURA：115，其中 104 含 `table_body`、11 记 `empty`）。→ merge 口径 115/104/11 逐项吻合。
- [x] `col_consistent` / `parse_status` 能标出列数不一致或解析失败的表格。→ 15 单测 + 负样本包端到端标出 malformed（col_consistent=False）/empty。
- [x] 非法输入（不存在目录、无 content_list）返回明确 error，不产出半成品 CSV。→ 三类非法输入均 exit=1 + 明确 error，未产 CSV。
- [—] 若实现 MCP `eval_tables`：TypeScript 编译通过，`tools/list` 返回 10 个工具。→ 决定 CLI-only，未实现，不适用。
- [x] `python3 scripts/check_plan_governance.py .` 通过。
- [x] 同步 `mcp/README.md`（若新增工具）与项目级 `skills/pdf2md/SKILL.md`（新增 `data/table_accuracy.csv` 产物说明）及用户级 skill。→ 未新增 MCP 工具，`mcp/README.md` 无需改；项目级 + 用户级 skill 已同步。

### 验收记录（P4b，2026-07-08）

**结论：P4b 达到"已完成"标准，功能性完成条件全部达标（MCP 封装按决策不实现）。**

代码新增（未提交）：`scripts/lib/table_eval.py`（`parse_table_html` 网格解析 + `parse_segment_name` 选段口径 + `build_section_index`/`section_for_page` + `eval_package_tables` 编排）、`scripts/pdf-eval-tables`（bash wrapper + JSON 模式）、`tests/test_table_eval.py`（15 单测）。

严格验收证据：

- **TDD 全绿**：15 个零依赖单测（`python3 tests/test_table_eval.py`）覆盖规整/colspan/rowspan 占位/列不一致/空表/空单元格率/th/真实告警表 + 选段口径（rerun 排除）+ section 段级定位三分支。rowspan 网格占位由 red→green 驱动而出。
- **真实样本吻合**：春风 150AURA 产出 115 行、104 ok、11 empty、0 malformed，与计划 Step 0（merge 口径 115/104/11）逐项吻合。
- **选段口径根因闭环**：全扫所有段子目录得 121 表（`p0185-0191` 与遗留 `p0185-0191-rerun` 重复计数），复用 pdf-merge 段名正则后得 115。pdf-rerun 标准流程原地 `rm -rf` 覆盖原段、不产 `-rerun` 目录，该目录为手动实验残留。
- **网格逻辑真实核对**：最复杂的 rowspan+colspan 混合表（p14 62×3 merged=60、p140 17×6 merged=10）逐行展开列数正确、consistent=True，证明 malformed=0 是真实数据质量而非漏标；21 个含合并单元格的表全部未误报。
- **破损信号端到端**：构造负样本包（列不一致表 + 空表 + rerun 脏段），CSV 正确标出 malformed（col_consistent=False）与 empty，rerun 段被排除（3 行而非 4）。
- **非法输入门禁**：不存在目录 / 无 segments / 有段无 content_list 三类均 exit=1 + 明确 error，均不产出半成品 CSV。

section 精度：段级近似（合并 md 每段锚点内首个 `##`），已知不精确到页内、缺省空串——见未决问题。

skill 同步：P4b 新增 `data/table_accuracy.csv` 产物，属输出包结构变更，已同步项目级 `skills/pdf2md/SKILL.md` 与用户级 skill。

## P4c：多模态 VLM 图表理解（已完成）

### 设计原理

对 `image_or_sparse` 页调用本地 VLM（qwen3-vl-8b，MLX 8bit 量化）产出结构化视觉描述。零新增依赖：`fitz`（已有）、`openai`（已有）。

### 架构

```
scripts/pdf-eval-vlm          ← bash 封装壳（arg 校验 + JSON 模式 + heredoc）
scripts/lib/vlm_eval.py       ← Python 库（页分类/渲染/API/校验/输出编排）
tests/test_vlm_eval.py        ← 单测（67 全局用例，零网络）
```

### 实施决策（本计划固定）

| 决策 | 选择 | 依据 |
|---|---|---|
| 页分类来源 | 自包含重检测（content_list_v2.json + fitz 文本量） | 不依赖 pdf-validate 先行运行；复刻 `detect_page_type` 中 image_or_sparse 判定逻辑（含 image 类型元素 或 PDF token < 15） |
| 整页渲染 | `fitz` `page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))` | 复用现有 fitz，零新增依赖；DPI 默认 200，环境变量 `VLM_DPI` 可调 |
| VLM 端点 | `POST http://127.0.0.1:9005/v1`（OpenAI 兼容） | ModelPad 托管的 qwen3-vl-8b（MLX 8bit；Apple M5 Pro 推理峰值 ~11 GB、~32.5 token/s） |
| JSON 产出 | `response_format={"type":"json_object"}` + 严格 Schema 校验 | Step 0 已验证：system prompt + response_format 双约束下解析成功率 100%；解析失败标记 `parse_status:"failed"`，无自动修复 |
| 字段名标准化 | `_normalize_vlm_fields`：移除 `.` 前缀 + visual_elements 内 `text` → `description` | MLX 8bit 量化模型偶发在字段名加 `.` 前缀（`.page_summary` 而非 `page_summary`），元素内使用 `text` 而非 `description` |
| 输出范围 | 全量检测但验收仅需 10 页抽样 | 108 页 image_or_sparse 全检测，端到端验证用 10 页均匀抽样（与 Step 0 口径一致） |

### 输出契约

`<package>/data/vlm_eval.jsonl`，每页一行 JSON：

| 字段 | 类型 | 说明 |
|---|---|---|
| `page` | int | PDF 页码（1-based） |
| `page_summary` | string/null | 页面整体视觉内容摘要；失败时为 null |
| `visual_elements` | list[object] | 视觉元素列表，每项含 `type`（元素类型）和 `description`（元素描述） |
| `key_text` | list[string] | 页面关键文本片段 |
| `confidence` | float/null | 模型置信度（0-1），失败时为 null |
| `section` | string | 所属 `##` 标题（从合并 Markdown 定位），缺省空串 |
| `parse_status` | string | `ok`（JSON 有效 + Schema 校验通过）/ `failed`（API 异常或 Schema 校验失败） |
| `error` | string | 失败原因（仅 `parse_status="failed"` 时出现） |

### 影响模块或文件

- `scripts/pdf-eval-vlm`（新建）：bash 封装壳，`pdf-eval-tables` 模式严格对齐
- `scripts/lib/vlm_eval.py`（新建）：Python 库，含全部编排逻辑
- `tests/test_vlm_eval.py`（新建）：67 全局单测覆盖页分类/渲染/API(mock)/校验/输出

### 完成条件

- [x] `data/vlm_eval.jsonl` 产出，每行含全部 8 个字段。→ Step 0 + 验收均通过。
- [x] 10 页混合抽样 JSON 解析成功率 100%。→ 10/10 OK，`page_summary`/`visual_elements`/`key_text`/`confidence` 全字段齐全。
- [x] 页面描述内容可追溯（人工抽样封面/提示页/规格页/仪表/制动等）。→ 10 页描述均与页面内容吻合。
- [x] 非法输入返回明确错误。→ 不存在的包目录 / 缺 segments / 缺 PDF 均 exit=1 + 明确 error。
- [x] 67 全局单测通过（零网络 mock）。→ `python3 -m unittest discover tests/` OK。
- [x] `python3 scripts/check_plan_governance.py .` 通过。

## 依赖关系

- P4a 依赖 [coverage-validation-optimization](coverage-validation-optimization.md)（TOC 条目字段设计事实源）、`pdf-validate` toc 页识别。
- P4b 依赖 [pdf-output-package-layout](pdf-output-package-layout.md)（产物写入 `<package>/data/`）、`content_list.json` table 元素 `table_body` 字段。
- P4a/P4b 均依赖 [automated-pdf-pipeline](automated-pdf-pipeline.md) CLI 契约与春风 150AURA 输出包样本。
- 上游阶段 [pdf-workflow-enhancement-roadmap](pdf-workflow-enhancement-roadmap.md) P3b 已完成。

## 风险和回滚

风险：

- P4a 条目抽取对跨行 TOC 漏匹配，可能低估 `found` 数；缓解：先单行后合并，`match_text` 保留可人工复核。
- P4b `col_count` 在复杂 `rowspan`/`colspan` 嵌套下可能偏差；结构自检为启发式，非精确精度，`col_consistent` 仅作破损信号。
- 新增 MCP `eval_tables` 增加 server 启动开销；影响可忽略。

回滚：

- P4a 字段为新增，移除字段即回滚，不影响 `status` 判定。
- P4b 产物 `table_accuracy.csv` 独立于其他 `data/` 产物，删除即回滚。
- 各子阶段产物独立，可单独回滚。

## Step 0 证据

见 P4a、P4b 各自「Step 0 证据」小节。汇总基线（2026-07-08 侦察）：

- 春风 150AURA：191 页、104 个 HTML 表格、174 个图片引用、288 个 `##` 标题。
- `content_list.json`（v1）table 元素带 `table_body`（115 个，104 含 HTML）；`content_list_v2.json` 的 table 元素仅 `content` 纯文本、无 HTML，故 P4b 只能用 v1。
- `pdf-validate` 已有 `detect_page_type`（text/toc/table/image_or_sparse/no_text_layer）、`_strip_html`、`_TOC_PATTERN`、`list_content_types`，三项子能力均有可复用基础设施。
- TOC 条目字段方案已在 coverage 计划完整定义。

### P4c Step 0 侦察记录（2026-07-10）

基线命令：

```bash
PDF_VALIDATE_JSON=1 scripts/pdf-validate \
  "pdf/春风 150AURA/春风 150AURA.pdf" \
  "pdf/春风 150AURA/segments" > /tmp/p4c-baseline.json
```

结果：命令按现有验证门槛返回 `exit=1`，但仍输出合法 JSON；页面分类统计为 `text=24`、`toc=7`、`table=63`、`image_or_sparse=97`，总计 191 页。`exit=1` 属现有覆盖率门槛结果，不代表 JSON 生成失败，后续 P4c 只消费页面分类字段。

本机环境只读盘点：Apple M5 Pro、64 GB 内存；Python 已有 `fitz 1.24.14`、`torch 2.12.1`、`transformers 5.12.1`、`openai 2.44.0`；未发现 `ollama`、`vllm`、`llamafile` 或 LM Studio CLI。ModelPad `http://127.0.0.1:9999` 已配置 `qwen3-vl-8b`（Qwen3-VL-8B-Instruct，MLX，端口 9005），启动后 `/health` 返回 `healthy`，实际加载 `Qwen3-VL-8B-Instruct-8bit`。结论是：整页渲染和本地 VLM 推理运行时均已具备，模型可进入候选评测，但不能据此直接进入正式实施。

单页探针：对春风 150AURA 第 12 页（`image_or_sparse`）以 144 DPI 临时渲染整页 PNG，通过 `POST http://127.0.0.1:9005/chat/completions` 调用。模型正确识别“阅读用户说明书/遵照所有指示和警告”、一氧化碳警告框、三角警告图标和印刷页码 11；输出置信度 0.98，推理峰值内存约 10.99 GB，生成速度约 32.5 token/s。当前发现一个验收阻塞：模型返回内容开头多出一个 `{`，导致约定 JSON 不是合法 JSON；正式实施前必须增加 JSON 解析/修复策略或调整提示词并固化回归样本。

同页复测：增加 system 级 JSON-only 约束，并传入 `response_format={"type":"json_object"}` 后，模型输出通过 `json.loads` 解析；内容仍正确识别警告标题、警告框、一氧化碳风险和页码 11。由此确定 P4c 的首选策略为“API JSON mode + 严格 Schema 校验”，解析失败进入 `needs_review`，不使用无界的自动修复作为默认放行条件。

10 页混合抽样（页面 12、41、53、73、87、100、111、145、158、185）全部通过 JSON 解析和 Schema 校验（10/10）；覆盖警告页、表格页、操作示意图、仪表截图、设置截图和维护表。缩略图人审未发现模型摘要与页面主要内容明显冲突，满足进入“待实施”的 Step 0 门槛。完整结果保存在临时文件 `/tmp/p4c-10page-results.json`，不作为项目产物提交。

P4c 首版视觉描述契约（拟进入设计阶段）：

```json
{
  "page_summary": "string",
  "visual_elements": [{"type": "string", "description": "string"}],
  "key_text": ["string"],
  "confidence": 0.0
}
```

首版验收门槛：JSON 解析成功率 100%；必填字段齐全且类型正确；`confidence` 在 0–1；人工抽样页面的主题/主要视觉元素/关键文字均可追溯，明显幻觉或无法确认内容必须标为 `unknown` 或进入 `needs_review`。在至少 10 页混合抽样通过前，P4c 不进入“待实施”。

Step 0 结论：页面基线、模型运行时选型（ModelPad qwen3-vl-8b 8bit）、Schema 和抽样门槛均已固定，后续实施与验收已完成。

### 验收记录（P4c，2026-07-10）

**结论：P4c 达到”已完成”标准，5 条完成条件全部达标。**

代码新增：`scripts/pdf-eval-vlm`（bash wrapper + heredoc）、`scripts/lib/vlm_eval.py`（Python 库）；VLM 专项 38 个测试，项目全量 67 个测试。

严格验收证据：

- **文档指定的 10 页抽样全部通过**：第 1 页（封面）、33（后视图示意图）、47（下电操作表）、58（行车记录仪）、81（仪表菜单）、92（自动下电设置）、105（通讯录）、116（时间设置）、150（发动机保养）、165（制动系统）——逐页调用结果 JSON 解析 10/10、Schema 校验 10/10。当前分类中第 1/58/92 页分别为 `toc`/`text`/`text`，其余 7 页为 `image_or_sparse`；这 3 页保留为文档指定的混合抽样，不冒充 `image_or_sparse`。人审确认页面摘要与内容吻合，无明显幻觉。
- **字段标准化有效性**：MLX 8bit 模型输出的 `.page_summary` 等带点号字段经 `_normalize_vlm_fields` 正确标准化；`visual_elements` 内 `text` 字段映射为 `description`。验证：标准化后 Schema 校验通过率 100%。
- **system prompt 依赖**：无 system prompt（无 JSON-only 约束）时模型返回 `{“”:””}`；增加 `”你是一个 PDF 页面描述助手。只输出合法 JSON”` 后全部正常。已在 `build_vlm_messages` 固定默认 system prompt。
- **PDF 路径分辨率**：`eval_vlm_package` 先尝试 `<package>/<name>.pdf`（包内），回退 `<parent>/<name>.pdf`（包旁），再回退 manifest.json。春风样本在包内布局下通过。
- **67 个项目测试全绿，其中 38 个 VLM 专项测试**：覆盖页分类三分支（image/normal/sparse）、Schema 校验（有效/缺失/类型错误/范围/None/非 dict/子元素缺失）、字段标准化（点号前缀/text→description）、消息构建（含/无 system prompt）、API mock（成功/异常/非 JSON）、段名解析（有效/rerun/DS_Store）、section 索引、JSONL 写入、fitz 渲染。
- **非法输入门禁**：不存在目录 / 缺 segments / 缺 PDF 均 exit=1 + 明确 error，不产生半成品 JSONL。
- **零新增依赖**：`fitz`/`openai` 均为项目已有。已确认 `openai 2.44.0` 兼容。

skill 同步：P4c 新增 `data/vlm_eval.jsonl` 产物，属输出包结构变更，已同步项目级 `skills/pdf2md/SKILL.md` 与用户级 skill。

## 验证方式

见 P4a、P4b 各自「验证方式」小节。总门禁：

```bash
python3 scripts/check_plan_governance.py .
```

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| P4b 是否实现 MCP `eval_tables` | CLI 优先；工具数达阈值再评估封装 | 否 | 已决：CLI-only，本轮不实现（未新增工具，`tools/list` 维持 9） |
| P4b `section` 定位精度 | 从合并 Markdown 按页锚点就近取最近 `##`，缺省空串 | 否 | 已实现为段级近似（段锚点内首个 `##`），页内精度待增强 |
| P4c 本地 VLM 选型与验收基准 | 已完成 Step 0：模型、Schema、JSON mode、10 页混合抽样和人审门槛均已固定 | 否 | 已完成，可进入待实施 |
| P4b 产物需同步 `pdf2md` skill | 实施 P4b 时新增 `data/table_accuracy.csv` 产物说明到项目级 + 用户级 skill | 否 | 已同步（项目级 + 用户级） |
| P4a `partial` 中文字符级判定偏宽（命中率≥0.5 易高估 partial/低估 missing） | 未来收紧为词级或连续子串匹配；当前样本仅 1 例、影响极小 | 否 | 已记录（P4a 验收观察） |
| P4a `found` 语义边界易被误读为"正文章节存在" | 已在验收记录明确口径为"该页目录解析完整性"；如扩展需在字段文档注明 | 否 | 已记录 |
| P4a `extract_toc_entries` 无持久化单测（靠验收临时单测覆盖 missing 分支） | 建议补 `tests/` 回归单测固化三分支与跨行合并 | 否 | 后续 enhancement |

## 关联 ADR、迁移、spec 或 issue

- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [pdf-workflow-enhancement-roadmap](pdf-workflow-enhancement-roadmap.md) — P4 上游路线图与阶段顺序事实源
- [覆盖率验证口径优化计划](coverage-validation-optimization.md#后续增强候选) — P4a TOC 条目字段方案事实源
- [MCP 接入设计](../../mcp/README.md) — P4b 可选 `eval_tables` 工具契约

## Test Coverage（测试覆盖率证据）

这是 2026-07-15 的仓库级回归基线：`python -m pytest -q` 为 `312 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`。该证据用于确认当前仓库回归状态，不冒充本历史计划的行覆盖率百分比。
