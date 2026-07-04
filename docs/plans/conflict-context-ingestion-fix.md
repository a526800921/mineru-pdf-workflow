# 计划：结构化数据冲突误报与上下文主键修正

## 背景

真实样本 `pdf/春风 150AURA` 在执行结构化数据与入库准备流程后产生 35 组冲突，导致 390 条记录全部停留在 `ingest_status=not_ready`。人工对照最终 Markdown 与 PDF 原文页后确认，这些冲突基本不是同一事实互相矛盾，而是当前抽取和入库准备流程缺少页面、表格、父级行/列等上下文，把局部编号、符号、规格或状态标签误当成全局唯一 key。

本计划修正 `structured-data-extraction` 与 `data-ingestion-pipeline` 已完成阶段中的一个真实样本偏差：原候选规则“同一 `model + section_path + key` 多值即冲突”对手册类 PDF 表格过于粗糙。

## 事实源职责

本文档是 `conflict-context-ingestion-fix` 的实施细节事实源，记录冲突误报样本、字段与主键方案、阶段门禁、验证方式、完成条件、风险和回滚。

计划状态、依赖、推荐顺序、阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。原结构化草案契约见 [输出包结构化数据抽取计划](structured-data-extraction.md)。原入库准备契约见 [结构化数据入库准备管线](data-ingestion-pipeline.md)。

## 目标

- 修复真实样本中局部编号、符号、规格、状态标签造成的冲突误报。
- 补齐 `quick_lookup_draft.csv` 的来源上下文，至少包含可复现的页段或页面范围。
- 为表格记录增加可用于冲突判定的上下文维度，例如表格序号、表格标题、父级行/列标签或行号。
- 调整 `conflicts.csv` 的判定口径，使“同一上下文中的同一业务 key 多值”才进入未解决冲突。
- 保持 `review_overrides.csv`、`ingest_ready.csv`、`pdf-export-ingest` 的保守放行语义：没有人工审核通过的数据仍不得导出。

## 非目标

- 不直接写入数据库。
- 不修改原始 PDF、最终 Markdown、segments 或图片产物。
- 不用大模型推断缺失业务字段。
- 不一次性解决所有表格语义建模问题；本计划优先解决会阻塞入库准备的误报。
- 不把所有冲突自动忽略；真正同上下文异值仍必须保留为未解决冲突。

## 不变量

- 每条候选记录必须能追溯到源 PDF、最终 Markdown 片段和抽取规则。
- 未审核记录不得进入 `ready`。
- 冲突判定必须可重复、可解释、可由 CSV 产物复核。
- 符号或占位符不能单独作为全局冲突 key。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。
- 涉及结构化数据或入库导出流程的契约更新时，必须先更新项目级 `skills/pdf2md/SKILL.md`，再同步到 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`；若无法同步，必须在本文档风险或未决问题中记录。

## Step 0 证据

### 真实样本

- 输出包：`pdf/春风 150AURA`
- PDF：`pdf/春风 150AURA/春风 150AURA.pdf`
- 最终 Markdown：`pdf/春风 150AURA/春风 150AURA.md`
- 草案：`pdf/春风 150AURA/data/quick_lookup_draft.csv`
- 入库候选：`pdf/春风 150AURA/data/ingest_ready.csv`
- 冲突报告：`pdf/春风 150AURA/data/conflicts.csv`
- 人工问题报告：`pdf/春风 150AURA/data/conflict_false_positive_report.md`

### 已观察基线

2026-07-04 对真实样本执行只读核查：

- `quick_lookup_draft.csv`：390 行。
- `page_start` / `page_end`：390 行均为空。
- `ingest_ready.csv`：390 行，`ready=0`、`not_ready=390`。
- `conflicts.csv`：35 组冲突，冲突成员合计 120 条。
- 最终 Markdown 含页段注释，例如 `<!-- pages 65-72 -->`，可作为第一版页段定位来源。
- PDF 原文页已抽样核对：车辆视图、车辆上/下电、LCD/TFT 仪表、磨合期保养表、轮胎规格、智能车联终端、整车关键件扭矩表。

### 误报类型

| 类型 | 示例 | 原因 | 期望处理 |
|---|---|---|---|
| 局部数字编号 | `2`、`3`、`10`-`16` | 不同图片或配置图复用编号 | 加入图片/表格/页段上下文，不按全局 key 冲突 |
| 符号和占位符 | `■`、`▲`、`-`、`/` | 表格标记或非标准件占位 | 不作为冲突主 key；保留为属性或标记 |
| 表格父级上下文缺失 | `后轮` | 轮胎规格、轮辋规格、胎压、磨耗深度共用子项 | 父级行/列参与 identity |
| 规格列误作主 key | `M8×30`、`M8×25` | 螺栓规格不是唯一业务对象 | 位置列应作为主 key，规格为属性 |
| 状态/界面标签复用 | `主界面`、`电话`、`菜单音乐` | 不同按钮或动作下复用状态名 | 菜单按钮/动作上下文参与 identity |

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化误报基线和修正规则 | 真实样本可读，冲突样本已人工核对 | 文档、Step 0 证据、验收命令明确 | 已完成 |
| 阶段 1 | 补齐来源页段与表格上下文字段 | 阶段 0 完成，实施前影响分析完成 | `quick_lookup_draft.csv` 有稳定上下文字段 | 已完成 |
| 阶段 2 | 调整冲突判定与误报过滤 | 阶段 1 完成 | `conflicts.csv` 不再拦截已知误报类型 | 候选 |
| 阶段 3 | 回归验证、skill 同步和治理收尾 | 阶段 2 完成 | 春风样本、demo20/demo5、导出边界均通过 | 候选 |

## 当前阶段

阶段 1 已完成。下一步为阶段 2：调整冲突判定与误报过滤。

### 阶段 1 完成证据（2026-07-04）

- `scripts/pdf-extract-data` 已添加 `parse_page_comments`、`get_page_range`、`classify_key_role` 辅助函数，从 `<!-- pages 65-72 -->` 注释提取页段范围。
- `extract_colon_rows`、`extract_html_table_rows`、`extract_md_table_rows` 三个抽取函数均已接受 `page_map` 和 `counters` 参数，写入 `source_block_id`、`table_id`、`row_index`、`parent_key`、`key_role` 五个新字段。
- 春风样本重新抽取后 `quick_lookup_draft.csv` 仍为 390 行。
- `page_start/page_end` 从全部为空变为 390/390 有值（覆盖率 100%）。
- `key_role` 分类验证通过：`business_key` 260、`marker` 54、`local_label` 52、`spec_value` 16、`state_label` 8。
- `source_block_id` 分布：`html_table` 249、`paragraph` 141。
- `read_markdown` 修复了 `markdown: null` 时的 TypeError（demo20/demo5 处于 segmented 状态无合并 markdown，非本次回归）。
- 项目级 `pdf2md` skill 已更新 `quick_lookup_draft.csv` 字段说明和 `key_role` 枚举，已同步到用户级 skill。
- 治理检查通过：`python3 scripts/check_plan_governance.py .`，`git diff --check` 无空白问题。
- GitNexus 影响分析：三个目标函数均为脚本内部函数，无外部调用者，风险 LOW。

## 阶段 0 完成条件

- 本计划进入 `docs/PLAN_MAP.md`。
- 已记录真实样本、误报类型、候选字段方案和验证命令。
- `data-ingestion-pipeline` 中已链接本后续修正计划，避免旧冲突策略被误用为最终口径。
- 当前阶段不要求修改脚本。

### 阶段 0 完成证据（2026-07-04）

- `docs/plans/conflict-context-ingestion-fix.md` 已记录真实样本、误报类型、字段方案、冲突 identity 候选和验收门槛。
- `docs/PLAN_MAP.md` 已加入计划索引、推荐顺序、依赖关系、当前阻塞项和阶段 0 证据链接。
- `docs/plans/data-ingestion-pipeline.md` 已增加后续修正计划链接，说明原三元组冲突规则不再作为最终放行口径。
- 治理检查已通过：`python3 scripts/check_plan_governance.py .`。
- 空白检查已通过：`git diff --check`。

## 阶段 1 方案：来源上下文补齐

候选字段先以向后兼容方式新增到 `quick_lookup_draft.csv`，不得删除既有字段：

| 字段 | 来源 | 用途 |
|---|---|---|
| `page_start` | Markdown 页段注释或 segments 目录名 | 区分跨页复用 key |
| `page_end` | Markdown 页段注释或 segments 目录名 | 保留页段范围 |
| `source_block_id` | Markdown 中表格/段落顺序 | 区分同页多个表格或段落 |
| `table_id` | HTML/Markdown 表格顺序 | 表格记录上下文 |
| `row_index` | 表格内数据行序号 | 稳定定位表格行 |
| `parent_key` | rowspan/分组行/左侧父级列 | 还原“轮胎规格 → 后轮”等父子关系 |
| `key_role` | `business_key`、`local_label`、`marker`、`spec_value`、`state_label` | 指导冲突检测 |

阶段 1 不强制一次性完全还原复杂 `rowspan`，但必须至少让春风样本中的已知误报类型可被分类。

### 阶段 1 实施范围

阶段 1 只修改抽取层，目标是让草案行携带足够上下文；不修改冲突判定、不生成 ready、不改导出逻辑。

允许修改：

- `scripts/pdf-extract-data`
- `skills/pdf2md/SKILL.md`
- `/Users/jafish/.claude/skills/pdf2md/SKILL.md`（由项目级 skill 同步覆盖）
- `docs/plans/conflict-context-ingestion-fix.md`
- `docs/PLAN_MAP.md`

阶段 1 不修改：

- `scripts/pdf-prepare-ingest`
- `scripts/pdf-export-ingest`
- `scripts/pdf-auto`
- `scripts/pdf-merge`
- `scripts/pdf-validate`
- `mcp/server/*`

### 阶段 1 实施前门禁

修改脚本前必须运行并记录 GitNexus 影响分析：

```bash
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --target extract_colon_rows --direction upstream
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --target extract_html_table_rows --direction upstream
node .gitnexus/run.cjs impact --repo mineru-pdf-workflow --target extract_md_table_rows --direction upstream
```

如果任一影响分析返回 HIGH 或 CRITICAL，必须先向用户报告影响范围，再继续实施。

### 阶段 1 具体改动

1. 在 `scripts/pdf-extract-data` 中解析最终 Markdown 的页段注释：
   - 识别形如 `<!-- pages 65-72 -->` 的注释。
   - 为每个 Markdown 行号建立当前 `page_start/page_end`。
   - 若行号在第一个页段注释前，页码留空并在 `notes` 记录 `missing_page_context`。
2. 给 Markdown 扫描建立稳定块序号：
   - 普通冒号行使用 `source_block_id=paragraph:<n>`。
   - Markdown 表格使用 `source_block_id=md_table:<n>` 和 `table_id=md_table:<n>`。
   - HTML 表格使用 `source_block_id=html_table:<n>` 和 `table_id=html_table:<n>`。
3. 扩展 `quick_lookup_draft.csv` 字段，保留原字段顺序并追加：
   - `source_block_id`
   - `table_id`
   - `row_index`
   - `parent_key`
   - `key_role`
4. 为 `compute_source_row_hash` 的后续兼容做准备：
   - 阶段 1 只生成草案，不修改 `record_id`。
   - 阶段 2 再决定 `pdf-prepare-ingest` 是否把新增字段纳入 `source_row_hash`。
5. 给 `key_role` 增加最小分类：
   - `marker`：`■`、`▲`、`-`、`/`、空白占位类 key。
   - `local_label`：纯数字 key，例如车辆视图或仪表编号。
   - `spec_value`：螺栓/螺母规格模式，例如 `M8`、`M8×30`、`M10×1.25`。
   - `state_label`：菜单/通话/电话/音乐等界面状态标签。
   - `business_key`：默认值。
6. 对简单父级行/列做保守补齐：
   - HTML/Markdown 表格中首列或左侧分组字段可明确表示父级时，写入 `parent_key`。
   - 无法可靠判断时留空，不做猜测。
7. 更新项目级 `skills/pdf2md/SKILL.md`：
   - 说明 `quick_lookup_draft.csv` 新增上下文字段。
   - 说明这些字段用于后续冲突判定和人工复核。
8. 同步用户级 skill：
   - `mkdir -p /Users/jafish/.claude/skills/pdf2md`
   - `cp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md`

### 阶段 1 验收命令

```bash
python3 -m py_compile scripts/pdf-extract-data

scripts/pdf-extract-data "pdf/春风 150AURA"

python3 - <<'PY'
import csv
rows=list(csv.DictReader(open("pdf/春风 150AURA/data/quick_lookup_draft.csv", newline="", encoding="utf-8-sig")))
fields=rows[0].keys() if rows else []
required=["source_block_id","table_id","row_index","parent_key","key_role"]
missing=[f for f in required if f not in fields]
assert not missing, missing
assert len(rows) == 390, len(rows)
assert sum(1 for r in rows if r.get("page_start")) > 0
assert any(r.get("key_role") == "marker" for r in rows)
assert any(r.get("key_role") == "local_label" for r in rows)
assert any(r.get("key_role") == "spec_value" for r in rows)
print("rows", len(rows))
print("page_context_rows", sum(1 for r in rows if r.get("page_start")))
print("new_fields", required)
PY

scripts/pdf-extract-data pdf/demo20
scripts/pdf-extract-data pdf/demo5

python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 1 完成条件

- 春风样本重新抽取后，`quick_lookup_draft.csv` 仍为 390 行，新增上下文字段存在。
- 春风样本至少部分记录有 `page_start/page_end`，不再全部为空。
- 已知误报类型能被 `key_role` 初步分类：`marker`、`local_label`、`spec_value` 至少各有样本。
- demo20/demo5 的结构化抽取不失败。
- 项目级 `pdf2md` skill 已更新并同步到用户级 skill。
- 治理文档记录阶段 1 完成证据，`PLAN_MAP.md` 同步状态。

## 阶段 2 方案：冲突判定收敛

候选 identity：

```text
conflict_identity = (
  model,
  section_path,
  page_start,
  source_block_id,
  table_id,
  parent_key,
  key
)
```

候选过滤规则：

- `key_role=marker`：不参与冲突检测，例如 `■`、`▲`、`-`、`/`。
- `key_role=local_label`：必须带 `table_id` 或 `source_block_id` 后才能参与冲突检测。
- `key_role=spec_value`：规格本身不作为主 key，优先使用表格中的位置/项目列作为 `key`。
- 缺少上下文且出现多值时，不直接放行；标记为 `needs_review_context`，避免误把真冲突吞掉。
- `conflicts.csv` 继续输出未解决冲突，但 `notes` 必须说明冲突依据使用了哪些上下文字段。

## 阶段 3 验证方式

必须覆盖真实样本和既有样本：

```bash
python3 -m py_compile scripts/pdf-extract-data scripts/pdf-prepare-ingest scripts/pdf-export-ingest

scripts/pdf-extract-data "pdf/春风 150AURA"
scripts/pdf-prepare-ingest "pdf/春风 150AURA"

python3 - <<'PY'
import csv
from collections import Counter
rows=list(csv.DictReader(open("pdf/春风 150AURA/data/quick_lookup_draft.csv", newline="", encoding="utf-8-sig")))
conf=list(csv.DictReader(open("pdf/春风 150AURA/data/conflicts.csv", newline="", encoding="utf-8-sig")))
print("rows", len(rows))
print("blank_pages", sum(1 for r in rows if not r.get("page_start")))
print("conflicts", len(conf))
print("keys", Counter(c["key"] for c in conf).most_common(10))
PY

scripts/pdf-extract-data pdf/demo20
scripts/pdf-prepare-ingest pdf/demo20
scripts/pdf-export-ingest pdf/demo20

scripts/pdf-extract-data pdf/demo5
scripts/pdf-prepare-ingest pdf/demo5
scripts/pdf-export-ingest pdf/demo5

python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

验收门槛：

- 春风样本 `page_start` 不再全部为空。
- 春风样本中已知 35 组误报不得继续全部作为未解决冲突阻塞。
- `■`、`▲`、`-`、`/` 不得单独作为冲突 key。
- `后轮`、`M8×30`、车辆视图数字编号、仪表菜单状态标签应通过上下文区分。
- demo20/demo5 原有流程不回退，空样本仍只生成表头或空批次。

## 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| Markdown 页段只能给范围，不能精确到 PDF 单页 | 仍可能同页段内复用 key | 使用 `source_block_id`、`table_id`、`row_index` 继续区分 |
| HTML 表格 `rowspan/colspan` 还原不完整 | `parent_key` 可能缺失 | 第一版允许 `needs_review_context`，不强行 ready |
| 冲突过滤过宽 | 真冲突被忽略 | 对缺上下文多值保守标记待复核 |
| 新增字段影响旧审核覆盖 | `record_id` 可能变化 | 记录迁移说明；必要时保留旧 ID 或提供重算脚本 |
| skill 同步遗漏 | 用户级流程说明漂移 | 阶段 3 必须同步项目级和用户级 `pdf2md` skill |

## 回滚

- 代码层回滚到原 `pdf-extract-data` / `pdf-prepare-ingest` 行为。
- 已生成的数据产物可通过重新运行旧脚本覆盖。
- 如新增字段导致下游不兼容，先保留字段但让 `pdf-export-ingest` 继续只导出现有字段，再另建迁移计划。

## 未决问题

- 是否需要为 `quick_lookup_draft.csv` 引入显式 schema 文件，而不是只靠脚本内字段常量。
- `record_id` 是否应纳入新增上下文字段；若纳入，需要定义旧 `review_overrides.csv` 的迁移策略。
- `conflicts.csv` 是否需要新增 `conflict_type`、`identity_fields`、`excluded_reason` 字段。
- 第一版是否允许自动生成“误报解除报告”，用于人工批量审核。
