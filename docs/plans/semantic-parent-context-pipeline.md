# 计划：结构化父级上下文统一处理与语义增强

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 已废弃 |
| 当前阶段 | 回滚完成：不启用 parent_key 字段改造 |
| 计划类型 | 上游字段契约、结构化抽取、入库传递和批次导出迭代 |
| 最后更新 | 2026-07-18 |

计划状态、依赖、推荐顺序、阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。原结构化草案契约见 [输出包结构化数据抽取计划](structured-data-extraction.md)，原入库准备契约见 [结构化数据入库准备管线](data-ingestion-pipeline.md)。顺序入口和阶段组织分别受 [pdf2md 顺序工作流](pdf2md-skill-sequential-workflow.md) 与 [pdf2md 阶段中心化重组](pdf2md-skill-phase-centric-reorganization.md) 约束。

## Step 0 Evidence

基线类型：真实下游反馈、当前流水线代码审计和已产生的春风 150 Aura 修复产物。当前外部产物证明目标结果可达到，但尚未证明从 canonical Markdown 重跑即可稳定产生该结果，因此本计划先冻结字段契约和可复现样本，再实施代码改动。

### 已确认的实际问题

- `scripts/pdf-extract-data` 已声明 `parent_key`，但当前只覆盖部分 `rowspan`、分组行和首列回退场景；冒号行和 Markdown 表格路径基本为空。
- `scripts/pdf-prepare-ingest`、`scripts/pdf-export-ingest` 已能传递 `parent_key`，但流水线没有对结构上明确的父级缺失建立统一门禁和审计输出。
- 下游 `/Users/jafish/Documents/work/motorcycle-manual-app/scripts/adapt_upstream_package.py` 已将 `parent_key` 映射为内部 `part_name`，但 `semantic_entries` 文本尚未拼接该父级。
- 下游阶段 2.1 计划当前使用 `context_path` 作为候选公共字段；本计划冻结后，`parent_key` 是上游唯一公共字段，`context_path` 不进入本轮 upstream CSV/JSONL 契约。

### 真实产物证据

外部修复产物位于：

`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/`

报告：`parent-context-fix-report.md`。

该报告记录了 343 条 `parent_key` 变化，包含“型式 → 发动机”和“整数排量 → 发动机”，最终 348 条 ready 记录的 `parent_key` 非空，且父级值均可回指 canonical Markdown。该产物是目标样本和回归基线，不是本计划实施完成证据。

### 当前代码基线

| 位置 | 当前观察 | 计划要求 |
|---|---|---|
| `scripts/pdf-extract-data` | HTML 表格只对部分 `rowspan`/分组行推导父级；显式“部位”父级列和 `colspan` 顶部类别不统一 | 建立通用表格网格和父级来源优先级 |
| `scripts/pdf-prepare-ingest` | 已保留字段并参与冲突 identity | 保持 identity 和 `record_id` 兼容，同时补充缺失父级审计 |
| `scripts/pdf-export-ingest` | 通常保留 CSV 字段 | 增加 batch/manifest 字段保真验证 |
| 下游 `adapt_upstream_package.py` | `part_name` 可接收父级，但 semantic 文本不包含它 | 本计划只交付稳定的 `parent_key`，下游自行适配 |

## 字段与语义决策

本迭代由本项目决定字段，不沿用下游计划中的 `context_path` 命名。

### 公共字段

只保留现有 `parent_key` 作为上游公共字段，不新增 `context_path`、`parent_path` 或题目专用字段。

`parent_key` 的含义是“当前记录在 canonical Markdown 表格或结构中的直接父级”，例如：

- `型式` → `发动机`
- `整数排量` → `发动机`
- `轮胎规格` 下的 `后轮` → `轮胎规格`
- 故障表中的 `不能启动` → 该表明确的直接“部位”父级

字段不承载 Q 编号、查询文本、审核别名或完整目录路径；完整章节路径继续由既有 `section_path`/来源字段承担。

### 父级来源优先级

实施时按以下顺序取值，并记录来源类型：

1. canonical Markdown/HTML 表格中的显式父级列或父级单元格；
2. `rowspan` 覆盖的父级单元格；
3. 同表明确的 `colspan` 分类行或表头分组；
4. 包内 `extraction_overrides.json` 声明的列语义映射，包括 `parent_column`、`parent_header` 和明确续表用的 `initial_parent_key`；
5. 无法可靠确定时留空并标记 `needs_review_context`，不得猜测或按 Q ID 补值。

`extraction_overrides.json` 只描述具体 PDF 的列语义，不改变公共字段名，也不把车型或题目规则硬编码进通用脚本。

### 下游语义文本

下游适配器生成语义文本时统一使用：

`parent_key + label + 已审核 aliases + value + unit`

父级上下文是同一条结构化记录的文本组成部分；本计划只冻结该交接契约，不修改下游 semantic 适配器、tag 向量、`record_id`、结构化 key/value/unit、来源锚点或数据库 Schema。`part_name` 只作为下游内部兼容映射，不升级为上游公共契约。

### 空值与门禁

不是所有记录都必然有父级。对没有可验证直接父级的记录，允许 `parent_key` 为空，但必须由规则明确其属于“无需父级”还是“需要人工复核”；结构上明确存在父级而字段为空时，不得进入无告警的 ready/batch。缺失记录、来源、原因和统计必须写入报告或验证产物。

## 目标

- 把 `parent_key` 从“部分抽取能力”提升为从 canonical Markdown 到 JSONL 的可复现流水线字段。
- 通用支持 `colspan` 分类行、`rowspan` 父级、显式父级列和包内列映射，不写 Q002/Q062 等问题专用分支。
- 保持 `record_id`、`source_row_hash`、记录数量、来源锚点和现有入库门禁稳定；对已有空父级审核决定提供 candidate_id 兼容别名。
- 向下游交付可追溯的父级上下文，使其可以自行将 `parent_key` 纳入 semantic 文本；本计划不改变 App 查询协议。
- 让结构化父级缺失可被审计、复核和安全回滚。

## 非目标

- 不修改 PDF、segments 或 canonical Markdown 内容。
- 不增加数据库 Schema、tag 向量、查询 API 或题库字段。
- 不为单个问题、查询文本、车型键名或当前样本写硬编码补丁。
- 不直接写入生产数据库或替换正式向量库；本次只允许在用户确认后更新正式 Aura 的上游文件产物，不修改下游仓库。
- 不把 `parent_key` 扩展成完整 `context_path`；目录路径和父级字段保持不同职责。

## 不变量

- 每个非空 `parent_key` 必须能回指 canonical Markdown 的表格结构或明确的包内映射，并保留来源类型。
- `parent_key` 只能增强上下文，不能覆盖业务 `key`、`value`、`unit` 或来源事实。
- 上游字段在 draft → ready → batch → manifest 中保真传递；`record_id` 和 `source_row_hash` 不因增加父级而变化，旧空父级 candidate_id 通过兼容别名继续可用。
- 未审核、冲突、证据缺失或父级来源不明的记录继续保持 `not_ready/needs_review`。
- 代码改动前必须进行 GitNexus 影响分析；代码完成后必须运行 `detect_changes()`。
- 更新 PDF 解析、结构化数据或入库导出契约时，先更新项目级 `skills/pdf2md/SKILL.md`，再同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 冻结 `parent_key` 契约、样本矩阵、缺失语义和回滚边界 | 已有真实反馈、代码审计和目标产物 | 文档、命令、预期结果和失败判定齐全 | 已完成 |
| 阶段 1：通用父级抽取 | 在抽取层通用推导直接父级 | 阶段 0 达到 `待实施`，完成符号影响分析 | HTML/Markdown fixture、150 Aura 重跑和来源审计 | 已完成 |
| 阶段 2 | 固化入库传递、缺失父级门禁和产物保真 | 阶段 1 通过 | draft/ready/batch/manifest 字段、hash、数量和状态回归 | 已完成 |
| 阶段 3 | 上游交接说明与下游边界确认（不实施下游代码） | 阶段 2 通过 | 字段说明、来源审计和不修改下游仓库的范围检查 | 不在本计划范围 |
| 阶段 4：上游全量验收、skill 同步和治理收尾 | 上游全量验收、skill 同步和治理收尾 | 阶段 1-2 通过 | Q002/Q062、真实 Aura 临时重跑、全仓回归和独立验收 | 已完成 |
| 阶段 4 追加项：正式 Aura 上游产物重生成 | 在用户确认后为正式 Aura 包补充续表配置，备份并重生成上游数据产物 | 用户明确确认；正式包现有文件只读盘点完成 | 配置、备份、抽取、审核应用、ready 门禁、batch/manifest、报告和回滚核对 | 已完成 |

## 当前阶段

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 状态 | 已完成 |
| Step 0 | 阶段 0 已完成；阶段 1/2 已完成实现，正式 Aura 追加项已完成用户确认、文件盘点、迁移审计和产物验收 |
| 准入状态 | 已完成 |
| 样本矩阵 | `colspan` 分类行、`rowspan` 父级、显式父级列、缺失父级、draft/ready/batch/manifest 传递和春风 150 Aura 真实报告 |
| 验证方式 | 先新增隔离 fixture 回归，再运行抽取/入库测试、真实样本重跑和治理检查 |
| 失败/回滚边界 | 先创建带时间戳的正式文件备份；父级错位、来源缺失、字段丢失、身份变化或门禁绕过时停止并恢复备份 |
| 当前阻塞项 | 无；GitNexus 未收录无扩展名 CLI 函数，已改用调用审计和回归补足影响证据 |
| 最新独立准入复核 | 日期=2026-07-18；阶段=阶段 4 追加项：正式 Aura 上游产物重生成；结论=通过、阶段完成；证据=正式 378 行 draft、266 条 batch、目标父级、列顺序、manifest 正式路径、产物 hash、备份和报告验收；复核者=Codex（独立验收） |

## 阶段 0：字段契约与基线冻结

### Step 0 样本矩阵

| 样本 | 输入/基线 | 可执行验证 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|---|
| 直接分类父级 | 含 `发动机` `colspan` 表头的 canonical Markdown | `scripts/pdf-extract-data <package>` | `型式`、`整数排量` 得到 `发动机` | 结构明确但为空，或写入题目专用规则 | 临时 package `data/quick_lookup_draft.csv` |
| 行/列父级 | 含 `rowspan` 和显式“部位”列的表格 | 同上 | 每条子记录得到直接父级，来源可审计 | 父级错位、跨行串值或无来源 | 临时 package `data/fixtures_result.md` |
| 无法判定 | 父级结构缺损或存在多个合理解释 | 同上 | 空值 + `needs_review_context` | 静默猜值或无报告放行 | 临时 package `data/parent-context-report.md` |
| 全链路传递 | 既有 draft 与审核决定 | `scripts/pdf-prepare-ingest <package>`；`scripts/pdf-export-ingest <package>` | CSV/JSONL/manifest 字段一致，record_id 集合不变 | 丢字段、变 hash、ready 越过门禁 | 临时 package `data/` |
| 真实目标样本 | 外部 150 Aura 修复报告及 JSONL | 只读 hash/字段/来源复核；实施后再从 canonical 重跑 | Q002/Q062 父级为 `发动机`，其余父级可追溯 | 只能靠一次性产物补丁得到结果 | `/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/parent-context-fix-report.md` |

### 阶段 0 完成条件

- [x] `parent_key` 是唯一上游父级公共字段；`context_path` 明确列为本轮非目标。
- [x] 直接父级、来源优先级、空值语义和 `needs_review_context` 门禁已冻结。
- [x] fixture 矩阵包含 `colspan`、`rowspan`、显式父级列、缺失父级和全链路传递。
- [x] 已写明代码影响分析、skill 同步、回滚和下游协调的执行顺序。
- [x] 准入复核确认本阶段达到 `待实施` 标准；该结论只代表阶段 1 实施准入，不代表最终验收。

### 阶段 0 完成证据（2026-07-18）

- 基线回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_pdf_extract_data.py tests/test_pdf_prepare_ingest.py`，结果为 `22 passed`。
- `colspan` 探针：三列“发动机”分类表中，当前 `型式`、`整数排量` 的 `parent_key` 均为空，证明阶段 1 需要补齐短表分类行。
- 显式父级列探针：含“部位 / 故障 / 原因”的表中，当前记录把“燃油系统”当作业务 key，`parent_key` 为空，证明需要显式父级列映射。
- 真实目标产物报告记录 343 条 `parent_key` 变化、348 条最终 ready 记录且空父级为 0；三件产物 hash 已核对：JSONL `54402ad3ad170457fe35b6f189b87d2e9a3741a6c799dbf6c36f38be5f244f50`、CSV `00dad4a5353d82fea06c7fc4a6ddc91fdf4a6f70d1596af4ac1c764a6acd4163`、manifest `740bc84c592f78dab4e31096a55cc2b2fecd844ed76c3e1176110b7c8db09418`。
- GitNexus 影响分析已执行；当前索引未收录无扩展名 CLI 脚本中的函数，目标函数均返回 `UNKNOWN / 0 callers`，未出现 HIGH/CRITICAL；后续以调用点审计、现有回归和新增 fixture 补足影响证据。
- 阶段准入结论：通过，进入阶段 1；复核者：Codex（实施准入复核，非最终业务验收）。

## 阶段 1：通用父级抽取

实施范围：`scripts/pdf-extract-data`、相关测试、必要的包内 `extraction_overrides.json`。先对将修改的函数执行 GitNexus upstream impact；若风险为 HIGH/CRITICAL，暂停并向用户报告。

重点工作：

1. 将 HTML 表格正规化为带 rowspan/colspan 展开的网格，保留单元格来源和列位置。
2. 识别显式父级列、rowspan 父级、colspan 分类行，并按契约优先级生成直接 `parent_key`。
3. 让 Markdown 表格路径与 HTML 表格路径使用同一字段语义；无可靠父级时输出审计状态，不猜测。
4. 增加 fixture 和真实样本回归；续表只能通过明确的包级 `initial_parent_key` 配置，不写入 Q002/Q062/Q097 等题目 ID 分支。

### 阶段 1 完成证据（2026-07-18）

- `scripts/pdf-extract-data` 已支持小型 `colspan` 分类行、展开后的 `rowspan` 父级、自动/配置显式父级列、Markdown 显式父级列和续表 `initial_parent_key`。
- 新增抽取回归覆盖上述来源和缺失语义；阶段 1/2 相关测试合计 `32 passed`。
- 项目级与用户级 `pdf2md` skill 已同步，并记录 `parent_key` 来源优先级、`initial_parent_key` 限定和 `context_path` 非目标。
- GitNexus 影响分析已在各待改符号前执行；由于无扩展名 CLI 未被索引，结果为 `UNKNOWN / 0 callers`，未出现 HIGH/CRITICAL。

## 阶段 2：入库传递与门禁

实施范围：`scripts/pdf-prepare-ingest`、`scripts/pdf-export-ingest`、相关测试和项目级 skill 契约。

- 验证 `parent_key` 在 draft → ready → batch → manifest 中保真。
- 保持 `record_id`、`source_row_hash` 和审核兼容策略；父级补全时通过旧空父级 candidate_id 别名兼容已有审核决定，若出现多候选命中必须拒绝。
- 对“结构明确但父级为空”生成 `needs_review_context`，不让 ready 或导出静默通过。
- 将父级覆盖率、空值分类、来源断裂和不可解析样本写入报告。
- 更新并同步两份 `pdf2md` skill；不新增 MCP 或数据库写入路径。

### 阶段 2 完成证据（2026-07-18）

- `pdf-prepare-ingest` 对抽取层明确标记的 `needs_review_context` 增加 ready 门禁；即使审核决定为 approved 也保持 `not_ready`。
- 已保留 `parent_key` 从 draft 到 ready、batch 的字段传递；旧的空父级 candidate_id 可通过兼容别名应用，重复命中仍拒绝。
- 最小全链路 fixture：`extract → prepare → export` 通过；真实 Aura 临时副本使用 `html_table:8` 的 `initial_parent_key=发动机` 配置，抽取 378 行，Q002/Q062 临时批准后 2 条 ready、2 条 batch，均保留 `parent_key=发动机`。
- 真实 Aura 正式数据目录未被写入；验证只在临时 package 完成。

## 阶段 3：上游交接边界（下游自理）

本阶段不修改 `/Users/jafish/Documents/work/motorcycle-manual-app`，只向其交付字段语义和来源约束。

- 上游交付 `parent_key` 的字段、来源、空值和兼容说明；下游可将其派生为内部路径或 `part_name`。
- 本计划不修改下游 semantic 文本、数据库、向量、题库或静态正式产物。

## 阶段 4：验收与治理收尾

### 验证方式

至少执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_pdf_extract_data.py tests/test_pdf_prepare_ingest.py tests/test_pdf_export_ingest.py tests/test_parent_context_pipeline.py
python3 -m py_compile scripts/pdf-extract-data scripts/pdf-prepare-ingest scripts/pdf-export-ingest
plan-governance-cli check . --strict-readiness
```

正式 Aura 重生成先备份现有上游文件，再更新包级配置并按既有审核文件重跑；不修改 PDF、segments、canonical Markdown、下游仓库或数据库。验收需同时检查：

- Q002 `整数排量` 和 Q062 `型式` 的 `parent_key=发动机`；
- 真实抽取候选的父级来源和缺失分类；
- draft/ready/batch/manifest 的字段、数量、`record_id` 集合、来源引用和门禁状态；
- batch JSONL 中保留 `parent_key`，且不存在未交付的上下文门禁绕过；
- `git diff --check`、GitNexus `detect_changes()` 和两份 skill 内容一致。

### 阶段 4 完成证据（2026-07-18）

- 全仓回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`，结果为 `352 passed, 5 warnings`。
- 既有修复回归：`bash tests/test-fix-validate.sh`，结果为 `通过: 133，失败: 0`。
- 结构化脚本语法检查、`git diff --check`、两份 `pdf2md` skill `cmp` 和 `plan-governance-cli check . --strict-readiness` 全部通过。
- GitNexus `detect_changes({scope:"unstaged"})` 返回 `risk_level=low`、`affected_count=0`；由于无扩展名 CLI 未被索引，变化检测未映射到脚本函数，但阶段前影响分析、调用点审计和回归已补足证据。
- 真实 Aura 临时验证：使用包级 `html_table:8.initial_parent_key=发动机`，Q002/Q062 得到 `parent_key=发动机`，prepare 产生 2 条 ready，export 产生 2 条 batch；正式 Aura 数据目录和下游仓库均未修改。

### 阶段 4 追加项：正式 Aura 上游产物重生成

执行边界：只更新 `/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/` 下的 `extraction_overrides.json`、结构化抽取结果、审核应用结果、入库前 batch、manifest 和父级修复报告；不修改下游仓库。

执行顺序：

1. 备份现有目标文件并核对备份 hash；
2. 在 `extraction_overrides.json` 增加 `html_table:8` 的无表头续表声明 `header_rows=0` 和 `initial_parent_key="发动机"`，不得改变原有 key/value 抽取；
3. 重跑抽取，检查记录数量、Q002/Q062 父级和来源审计；
4. 兼容旧审核输入：将 `review_actor=human` 归一为当前契约的 `user`，不改变审核状态、候选身份或审核理由；
5. 处理已失效的旧 `review_overrides.csv` 分类行记录：保留原文件备份，不让不存在的旧 `record_id` 阻断新抽取；
6. 仅迁移按 `table_id + key + value + unit` 唯一匹配的旧审核决定；不迁移歧义、缺失或内容改变的决定；
7. 应用安全迁移后的审核决定，运行 ready 门禁并检查父级缺失；
8. 导出 batch/manifest 和 `parent-context-fix-report.md`；
9. 若数量、身份、来源或门禁不符合预期，停止并恢复备份。

### 阶段 4 追加项完成证据（2026-07-18）

- 正式 Aura 配置已增加 html_table:8 的无表头续表声明 header_rows=0、initial_parent_key=发动机；未改变该表原有 key/value 抽取形态。
- 正式抽取：quick_lookup_draft.csv 378 行；parent_key 非空 166 行；型式、整数排量均为 发动机。
- 正式 CSV 列顺序：quick_lookup_draft.csv 和 ingest_ready.csv 均为 parent_key 位于业务 key 前。
- 审核迁移：旧 review_overrides.csv 与 review_decisions.jsonl 均按 table_id + key + value + unit 唯一匹配迁移；旧 human actor 已按审核依据归一；用户确认型式后，最终 266 条 ready、103 条 not_ready、9 条 skipped、0 组冲突。
- 正式 batch：266 条；型式、整数排量均进入 batch 且保留 parent_key=发动机；manifest 的 package 指向正式 Aura 路径。
- 报告：/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/parent-context-fix-report.md；原始文件备份位于 /tmp/motofind-150aura-parent-context-backup.WCML7n。
- 产物 hash：draft bb690ab2eb73b0738da964d2ff32b8c1d4996eedb11b7a426007234272bfbdde；ready 93431332a085817612be54273674922dd196b50ac5247cae7bf09a68f582bdc6；batch 386d2720cd5dcf3ddd218e8b4cfdf5c3738adb27b74a8da23c1b52df5cedf888；manifest 2233c9b95827e0ffa514dfb1531cb28615f72905992ea58140676dbb4b8b944f。
- 最终回归：全仓 pytest 354 passed、5 warnings；既有修复回归 133 passed、0 failed；严格治理检查、git diff --check、两份 skill cmp 和 GitNexus detect_changes 均通过，变化风险 low。

### 失败策略与回滚

- 抽取来源不明、父级错位、字段丢失、record_id 集合变化或 ready 门禁绕过：停止交付，不替换正式产物。
- 只在临时 package/数据库中重跑；回滚为删除临时产物或恢复实施前快照，不回写 PDF、Markdown、数据库或正式 JSONL。
- 下游若选择 `context_path`，由下游自行记录派生关系；上游不同时维护两套公共字段。

## 测试覆盖率

- 单元与流水线 fixture：`tests/test_pdf_extract_data.py`、`tests/test_pdf_prepare_ingest.py`、`tests/test_pdf_export_ingest.py`、`tests/test_parent_context_pipeline.py`，阶段相关结果 `32 passed`。
- 全仓回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`，`352 passed, 5 warnings`。
- 既有修复回归：`bash tests/test-fix-validate.sh`，`133 passed, 0 failed`。
- 语法与契约：三个上游脚本 `py_compile` 通过；项目级/用户级 `pdf2md` skill `cmp` 一致；`git diff --check` 和 `plan-governance-cli check . --strict-readiness` 通过。
- 最终追加回归：全仓 pytest `354 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `通过: 133，失败: 0`；CSV 列顺序和历史审核 actor 兼容测试已覆盖。
- 真实样本覆盖：Aura 临时副本抽取 378 行；Q002/Q062 各有 `parent_key=发动机`，临时审核后 2 条 ready、2 条 batch；正式数据和下游仓库未写入。

## 回滚记录（2026-07-18）

用户决定停止本计划，原因是新增 `parent_key` 后候选身份与历史审核绑定发生耦合，旧版已审核产物无法稳定复用，改造收益不足以抵消对后续产物稳定性的影响。

已执行：

- 撤销上游 `parent_key` 抽取、传递、门禁和相关测试改动；
- 恢复项目级与用户级 `pdf2md` skill 到改造前版本；
- 恢复正式 Aura `data/` 到改造前的审核、ready、batch 和 manifest 产物；
- 不修改下游仓库、PDF、segments、canonical Markdown 或数据库；
- 当前 parent_key 改造产物保留在 `/tmp/motofind-150aura-parent-rollback-current.3DeFBV`，原始回滚备份保留在 `/tmp/motofind-150aura-parent-context-backup.WCML7n`。

回滚后的正式 Aura 以原有审核绑定和批次为准，不再继续迁移 parent_key 审核。

## 阶段 4.1：正式 Aura 父级独立审核与确定性补全（已废弃）

### 目标、范围与非目标

本阶段处理正式 Aura 重生成后发现的父级字段独立审核问题。范围仅限上游正式包的 `parent_key` 证据核对、抽取配置/通用规则的确定性修正，以及由此派生的上游审核与入库前产物。非目标是修改下游适配、语义文本、数据库或任何 PDF/canonical Markdown 原文。

### Step 0 证据（2026-07-18）

- 正式 `data/ingest_ready.csv` 有 266 条 ready；与旧版 approved 候选按 `table_id + key + value + unit` 对齐后，只有 44 条父级完全一致，149 条新版父级为空，73 条父级变化。
- canonical Markdown 已直接确认三类确定性问题：`html_table:7` 的“性能”分类行被 3 行表头配置吞掉；`html_table:9` 是“底盘”续表；`html_table:8` 的“后轮”两行由 `rowspan` 分别继承“轮胎规格”和“轮辋规格”，但 override 路径未应用 rowspan。
- 现行规则要求：父级必须来自 canonical 表格结构或明确包级配置；旧审核状态不能替代新版 `parent_key` 审核；无法可靠确定的记录保持空值并进入审计/待复核。

### 当前阶段准入

- 准入状态：待实施
- 样本矩阵：`html_table:7` 参数表分类行、`html_table:8` 参数续表与 rowspan、`html_table:9` 参数续表；命令为正式包的 `scripts/pdf-extract-data`、`scripts/pdf-prepare-ingest`、`scripts/pdf-export-ingest` 全链路重跑；预期为三类父级分别为“性能”“轮胎规格/轮辋规格”“底盘”，失败判定为父级为空、业务 key/value/unit 改变、候选身份无法安全迁移或 ready 绕过门禁；输出位于正式包 `data/`。
- 验证方式：对比 canonical Markdown、旧/新候选 identity、父级来源 notes、ready/batch/manifest 数量和 record_id 集合，并运行项目回归、治理检查和变化检测。
- 失败/回滚边界：只写包内派生产物和本计划文档；正式包先保留现有备份；任何 key/value/unit、来源锚点或重复候选身份变化都停止自动迁移，保留 `not_ready`。
- 当前阻塞项：章节标题是否作为无分类行表格的 `parent_key` 尚未确定，不在本阶段擅自补齐。
- 最新独立准入复核：2026-07-18，Codex；结论为达到 `待实施` 标准，三类结构性证据已固定，章节标题语义列为明确未决项。

### 实施步骤

1. 修正通用 HTML 表格路径，使 `auto_no_header` override 仍应用 canonical 的 rowspan 父级映射。
2. 修正正式包 `html_table:7` 的表头行配置，补回“性能”分类行；为明确续表 `html_table:9` 配置 `initial_parent_key=底盘`。
3. 在不迁移歧义审核的前提下重生成 draft、prepare、export 和报告；旧审核只按候选 identity 迁移，父级变化继续单独审计。
4. 对章节标题语义保持待复核，不把旧版章节父级静默写回新版。

### 完成条件与验证命令

- `html_table:7` 的四条性能记录均为 `parent_key=性能`；`html_table:8` 的轮胎/轮辋 rowspan 子记录分别得到正确父级；`html_table:9` 首行得到 `parent_key=底盘`。
- 未改变业务 key/value/unit、来源页、候选 identity 规则；无法安全匹配的审核仍为 `not_ready`。
- `ingest_ready.csv`、`ingest_batch.jsonl`、`ingest_manifest.json` 的数量、record_id 集合和状态门禁一致。
- 运行 `pytest -q`、`bash tests/test-fix-validate.sh`、`plan-governance-cli check . --strict-readiness`、`git diff --check`，并对 GitNexus 执行 `detect_changes`。

### 回滚

使用正式 Aura 包现有 `/tmp/motofind-150aura-parent-context-backup.WCML7n` 备份恢复包内数据；代码和配置变更通过版本控制回退。下游仓库不作任何修改。

## 完成条件

- 从 canonical Markdown 重跑即可稳定生成符合契约的 `parent_key`，不依赖一次性 JSONL 补丁。
- `parent_key` 在抽取、准备和 batch JSONL 中可追溯且不丢失；manifest 保留对应输入 hash、数量和状态，结构明确的缺失会阻断或显式降级。
- Q002/Q062 均能得到 `发动机`，上游 batch JSONL 保留该父级；无题目专用硬编码。
- `record_id`、结构化字段、来源和入库门禁保持兼容，旧空父级审核决定可通过 candidate_id 兼容别名应用。
- 项目级和用户级 `pdf2md` skill 已同步；上游计划明确下游自理，不修改下游仓库。
- 独立验收基于当前仓库、可复现命令和反向引用确认完成，随后将计划状态更新为 `已完成`。

## 后续边界（不阻塞本计划完成）

1. 正式 Aura 已完成保守重生成；仍有 103 条 not_ready，后续审核由数据包维护方决定，不阻塞本计划的上游安全交付。
2. 正式包历史审核输入含 `review_actor=human`、旧候选身份和已失效分类行 `record_id`；需用兼容归一/安全迁移处理，不删除原始备份。
3. 临时续表配置若改变既有 key/value 或候选数量，必须停止并先修正配置能力。
4. 审核映射审计：381 条旧审核决定中 274 条唯一继承、5 条歧义、93 条无对应新候选、9 条旧记录缺失；83 条原 approved 决定不自动继承，保持未 ready。
5. 下游 `semantic_entries` 的文本分隔符和 aliases 由下游自行决定；本计划不扩展题库专用别名。
6. 用户级 skill 的同步写入位于本项目之外；阶段 4 执行时若权限或工作区不可用，必须记录阻塞和补同步动作。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-18 |
| 阶段 | 阶段 4 追加项：正式 Aura 上游产物重生成 |
| 结论 | 通过：阶段完成 |
| 证据 | 正式 378 行 draft、266 条 batch、目标父级、CSV 列顺序、manifest 正式路径、产物 hash、备份和报告验收；后续 103 条保持 not_ready |
| 复核者 | Codex |

## 相关计划与证据

- [结构化数据冲突误报与上下文主键修正](conflict-context-ingestion-fix.md)
- [pdf2md 顺序工作流](pdf2md-skill-sequential-workflow.md)
- [pdf2md 阶段中心化重组](pdf2md-skill-phase-centric-reorganization.md)
- [输出包结构化数据抽取](structured-data-extraction.md)
- [结构化数据入库准备管线](data-ingestion-pipeline.md)
- [ADR 0002：CLI-only 工作流](../adr/0002-cli-only-workflow.md)
- [ADR 0003：LLM 编排与受控动态辅助脚本](../adr/0003-llm-orchestrated-dynamic-assistants.md)
- 下游计划：`/Users/jafish/Documents/work/motorcycle-manual-app/docs/plans/search-query-regression-library.md`
- 外部真实样本报告：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura/data/parent-context-fix-report.md`

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-18 | Codex | 阶段 0：字段契约与基线冻结 | 通过：达到待实施标准 | 22 项基线回归、两个隔离失败探针、真实产物 hash、字段契约和回滚边界 |
| 2026-07-18 | Codex | 阶段 1：通用父级抽取 | 通过：阶段完成 | 32 项阶段 1/2 回归、HTML/Markdown 父级来源覆盖、续表配置和两份 skill 同步 |
| 2026-07-18 | Codex | 阶段 2：入库传递与门禁 | 通过：阶段完成 | `needs_review_context` 门禁、candidate_id 兼容别名、临时 Aura 2 条 ready/2 条 batch 验证 |
| 2026-07-18 | Codex | 阶段 4：上游全量验收、skill 同步和治理收尾 | 通过：计划完成 | 352 项 pytest、133 项既有修复回归、真实 Aura 临时全链路、两份 skill 同步、治理检查和变化检测 |
| 2026-07-18 | Codex | 阶段 4 追加项：正式 Aura 上游产物重生成 | 通过：阶段完成 | 正式 378 行 draft、266 条 batch、型式/整数排量父级、CSV 列顺序、审核迁移、备份、报告和 manifest 验收；最终 354 项 pytest、133 项修复回归 |

### 2026-07-18：阶段 4 追加项，正式 Aura 上游产物重生成

- 结论：用户已确认正式 Aura 上游文件写入；先备份，再执行配置补充和产物重生成。
- 准入证据：正式包文件已完成只读盘点；当前配置缺少 `html_table:8.initial_parent_key`，审核输入还暴露出旧 `human` actor、旧候选身份和已失效分类行 `record_id`，已纳入兼容处理；临时配置改变 key/value 的探针已停止；审核映射审计已完成。
- 回滚边界：恢复本次执行前的带时间戳备份；不修改下游仓库、PDF、segments、canonical Markdown 或数据库。
- 复核者：Codex（实施前执行记录）。

### 2026-07-18：阶段 0，准入通过

- 结论：阶段 0 达到 `待实施` 标准，阶段 1 可开始；最终字段实现和下游变更仍未验收。
- 证据：22 项上游回归通过、两个隔离失败探针、真实修复产物 hash、阶段样本矩阵和 GitNexus 影响分析记录。
- 未决：阶段 1 需确定通用表格网格实现与包内显式父级列配置；阶段 2 才处理流水线门禁。
- 复核者：Codex（实施准入复核，非最终业务验收）。

### 2026-07-18：阶段 1，已完成

- 结论：阶段 1 完成，进入阶段 2。
- 证据：抽取来源回归、32 项阶段 1/2 测试、真实 Aura 临时抽取和两份 skill 同步。
- 阶段：阶段 1：通用父级抽取。
- 复核者：Codex（实施准入复核，非最终业务验收）。

### 2026-07-18：阶段 2，已完成

- 结论：阶段 2 完成，进入阶段 4 上游验收。
- 证据：`needs_review_context` ready 门禁、旧 candidate_id 兼容、最小全链路 32 项测试和真实 Aura 临时 prepare/export。
- 阶段：阶段 2：入库传递与门禁。
- 复核者：Codex（实施准入复核，非最终业务验收）。

### 2026-07-18：阶段 4，已完成

- 结论：阶段 4 完成；本计划闭环。
- 证据：全仓 352 项 pytest、133 项既有修复回归、临时 Aura 全链路、skill 同步、治理严格检查和 GitNexus 变化检测。
- 阶段：阶段 4：上游全量验收、skill 同步和治理收尾。
- 复核者：Codex（实施准入复核，非最终业务验收）。
