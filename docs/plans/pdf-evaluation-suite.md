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
- 为多模态 VLM 图表理解（P4c）保留候选边界与 Step 0 待办。

## 范围

- **P4a（已完成）**：目录页在 `pdf-validate` 输出中新增条目级验证字段，`review.md` 逐条目报告缺失。
- **P4b（待实施）**：对 `content_list_v2.json` 的 table 元素做结构自检，产出 `<package>/data/table_accuracy.csv`。
- **P4c（候选）**：对 `image_or_sparse` 页调本地 VLM 产出结构化描述。仅记录边界与阻塞，不进首批。

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

P4b（表格结构自检评测）：

- `scripts/pdf-eval-tables`（需新建）：读取输出包 `content_list_v2.json`，产出 `data/table_accuracy.csv`。
- `scripts/lib/table_eval.py`（需新建）：HTML 表格结构解析与自检指标计算。
- MCP `eval_tables`（可选）：`mcp/server/src/index.ts` 注册，`runScript` 调用 CLI。

P4c（候选）：`scripts/pdf-eval-vlm`（未建）、本地 VLM 后端（未定）。

## 公共契约变化

- P4a：`pdf-validate` JSON 中 `toc` 页新增 `toc_entries` / `toc_stats` 字段（字段语义链接 coverage 计划）。
- P4b：新增产物 `<package>/data/table_accuracy.csv`（Schema 见下）。若实现 MCP `eval_tables`，`tools/list` 由 9 增至 10。
- P4c：无（候选）。

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

## P4b：表格结构自检评测（待实施）

### 设计原理

用户决策：不做需要人工标注的 TEDS，改用**结构自检指标**——从表格 HTML 自身结构推断解析健全性，零 ground truth、零成本。列数不一致、HTML 解析失败等信号能定位大多数破损表格。

### 数据源

`<package>/segments/<pXXXX>/<model>/hybrid_auto/<model>_content_list_v2.json` 中 `type == "table"` 元素的 `html` 字段（原始 HTML 字符串，已由 Step 0 核实存在）。解析复用标准库 `html.parser`，文本清洗复用 `pdf-validate` 的 `_strip_html`。

### 输出契约

`<package>/data/table_accuracy.csv`，每行一个表格：

| 字段 | 类型 | 说明 |
|---|---|---|
| `table_id` | string | 唯一标识，格式 `p<页码>_t<表序>`，如 `p0025_t01` |
| `page` | int | 表格所在页码（1-based） |
| `section` | string | 所属 `##` 标题（从合并 Markdown 就近定位，缺省空串） |
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

- 春风 150AURA 合并 Markdown 含 **104 个 HTML 表格**、0 个 Markdown 管道表（`grep -c '<table'` = 104）。
- `content_list_v2.json` 路径与 table 元素 `html` 字段已核实存在（`segments/p0025-0032/.../hybrid_auto/*_content_list_v2.json`）。
- `pdf-validate` 已有 `_strip_html`、`list_content_types`（识别 `table` 元素），可直接复用。

### 验证方式

```bash
scripts/pdf-eval-tables "pdf/春风 150AURA"
python3 -c "
import csv
rows = list(csv.DictReader(open('pdf/春风 150AURA/data/table_accuracy.csv')))
assert len(rows) >= 100, f'表格数偏少: {len(rows)}'
cols = {'table_id','page','section','row_count','col_count','cell_count',
        'empty_cell_count','empty_cell_ratio','merged_cell_count','col_consistent','parse_status'}
assert cols <= set(rows[0].keys()), f'字段缺失: {cols - set(rows[0].keys())}'
bad = [r for r in rows if r['parse_status'] == 'malformed']
print(f'P4b: {len(rows)} 表格, {len(bad)} 结构异常, 字段完整')
"

cd mcp/server && npm run build   # 若实现 MCP eval_tables
python3 scripts/check_plan_governance.py .
```

### 完成条件

- [ ] `data/table_accuracy.csv` 产出，每行一个表格，含全部 11 个字段。
- [ ] 表格数量与合并 Markdown `<table>` 数量一致（春风 150AURA：104）。
- [ ] `col_consistent` / `parse_status` 能标出列数不一致或解析失败的表格。
- [ ] 非法输入（不存在目录、无 content_list）返回明确 error，不产出半成品 CSV。
- [ ] 若实现 MCP `eval_tables`：TypeScript 编译通过，`tools/list` 返回 10 个工具。
- [ ] `python3 scripts/check_plan_governance.py .` 通过。
- [ ] 同步 `mcp/README.md`（若新增工具）与项目级 `skills/pdf2md/SKILL.md`（新增 `data/table_accuracy.csv` 产物说明）及用户级 skill。

## P4c：多模态 VLM 图表理解（候选）

### 边界

对 `image_or_sparse` 页调用**本地 VLM 模型**（用户选型倾向）产出结构化视觉描述，补充图表密集页的语义。

### 阻塞与 Step 0 待办

| 项 | 状态 |
|---|---|
| 本地 VLM 选型与显存/环境评估 | 未做（MinerU `vlm-engine` vs 独立 VLM） |
| `image_or_sparse` 页数量基线统计 | 未做（需跑 `PDF_VALIDATE_JSON=1` 汇总 `page_type_summary`） |
| 描述质量验收基准 | 未定（无 ground truth 时如何验收） |

P4c 保持 `候选`，上述阻塞项在其进入"设计中"前必须先解决。

## 依赖关系

- P4a 依赖 [coverage-validation-optimization](coverage-validation-optimization.md)（TOC 条目字段设计事实源）、`pdf-validate` toc 页识别。
- P4b 依赖 [pdf-output-package-layout](pdf-output-package-layout.md)（产物写入 `<package>/data/`）、`content_list_v2.json` table 元素 html 字段。
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
- `content_list_v2.json` 存在且 table 元素带 `html` 字段。
- `pdf-validate` 已有 `detect_page_type`（text/toc/table/image_or_sparse/no_text_layer）、`_strip_html`、`_TOC_PATTERN`、`list_content_types`，三项子能力均有可复用基础设施。
- TOC 条目字段方案已在 coverage 计划完整定义。

## 验证方式

见 P4a、P4b 各自「验证方式」小节。总门禁：

```bash
python3 scripts/check_plan_governance.py .
```

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| P4b 是否实现 MCP `eval_tables` | CLI 优先；工具数达阈值再评估封装 | 否 | 待实施时决定 |
| P4b `section` 定位精度 | 从合并 Markdown 按页锚点就近取最近 `##`，缺省空串 | 否 | 已记录 |
| P4c 本地 VLM 选型与验收基准 | 进入设计中前先做 Step 0 待办 | 否（P4c 候选） | 已延后 |
| P4b 产物需同步 `pdf2md` skill | 实施 P4b 时新增 `data/table_accuracy.csv` 产物说明到项目级 + 用户级 skill | 否 | 补同步动作已登记 |
| P4a `partial` 中文字符级判定偏宽（命中率≥0.5 易高估 partial/低估 missing） | 未来收紧为词级或连续子串匹配；当前样本仅 1 例、影响极小 | 否 | 已记录（P4a 验收观察） |
| P4a `found` 语义边界易被误读为"正文章节存在" | 已在验收记录明确口径为"该页目录解析完整性"；如扩展需在字段文档注明 | 否 | 已记录 |
| P4a `extract_toc_entries` 无持久化单测（靠验收临时单测覆盖 missing 分支） | 建议补 `tests/` 回归单测固化三分支与跨行合并 | 否 | 后续 enhancement |

## 关联 ADR、迁移、spec 或 issue

- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [pdf-workflow-enhancement-roadmap](pdf-workflow-enhancement-roadmap.md) — P4 上游路线图与阶段顺序事实源
- [覆盖率验证口径优化计划](coverage-validation-optimization.md#后续增强候选) — P4a TOC 条目字段方案事实源
- [MCP 接入设计](../../mcp/README.md) — P4b 可选 `eval_tables` 工具契约
