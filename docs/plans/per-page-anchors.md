# 计划：逐页锚点（合并 Markdown 页级定位）

## 背景

当前 `pdf-merge` 按分段（默认 8 页/段）合并 Markdown，只在每段前插入段级锚点 `<!-- pages N-M -->`。因此合并 md 只能区分到「段」（8 页一块），无法区分具体是第几页；`read_page` 输入单页也只能返回整段，结构化数据 `page_start/page_end` 也只能定位到段级（再靠 `refine_page_numbers` 用 PyMuPDF 文本搜索做启发式单页收窄）。

用户目标：合并 md 里能**逐页区分**——每一页有独立锚点，`read_page` 能真正按单页返回，结构化数据精确到单页。

关键事实（本会话 Step 0 实测）：MinerU 每段除 md 外还输出 `content_list.json`，其中每个内容块都带 `page_idx`（段内 0-based 页号）。合并 md 本就是这份清单渲染而来，只是丢弃了页号。据此可在合并阶段恢复逐页边界，**无需 `segment_size=1` 重新解析**。

## 事实源职责

本文档是 `per-page-anchors` 的实施细节事实源：目标、范围、字段/锚点契约、阶段划分、Step 0 证据、验证方式、完成条件、风险、回滚、未决问题。

计划状态、依赖、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。输出包结构和 `read_page` 对外契约的现状描述以 [`skills/pdf2md/SKILL.md`](../../skills/pdf2md/SKILL.md) 为准，本计划各阶段实施时必须先同步该 skill。

## 目标

- 合并 md 在保留段级锚点 `<!-- pages N-M -->` 的前提下，新增逐页锚点 `<!-- page N -->`（绝对 PDF 页码，与段级锚点同坐标系）。
- 新解析的输出包自动带逐页锚点；已生成的旧包可用现有 `segments/` 回填（不重新解析）。
- `read_page` 升级为真正按单页返回；无逐页锚点时回退段级（向后兼容）。
- 结构化数据 `page_start/page_end` 复用逐页锚点精确到单页。

## 范围

- `scripts/pdf-merge`：逐页锚点生成（方案 A′ + X，见下）。
- 回填入口：对现有 `segments/` 重跑新版 `pdf-merge`。
- `scripts/pdf-read-page`（及 MCP `read_page` 封装）：单页锚点解析。
- `scripts/pdf-extract-data`：逐页锚点优先，`refine_page_numbers` 降为 fallback。

## 非目标

- 不改 MinerU 解析引擎，不改 `segment_size`（仍默认 8 页/段）。
- 不重新解析 PDF；逐页信息全部来自已有 `content_list.json`。
- 不修改合并 md 的**正文内容**（A′ 只插注释行，不重建内容）。
- 不改 TOC 段的 md（保留 `toc_repair` 成果）。

## 方案：A′（原生 md 不动 + 首/尾块近似锚定）+ X（段内锚点连续）

对每个分段，读同目录 `*_content_list.json`：

1. 用 `page_idx` 把块**按页分组**，段起始物理页由目录名 `pXXXX-YYYY` 得到，绝对页 = 段起始页 + `page_idx`。
2. 对每一页，取**首块指纹**（定位锚点位置）与**尾块指纹**（校验该页完整存在于原生 md）：
   - `text`/`header`/`footer`/`aside_text`/`page_number` → 文本去空白前缀；
   - `table` → `table_body` 去空白前缀；
   - `image` → `img_path`。
3. 在**原生 md**上用「去空白映射 + 前向单调游标」定位指纹：**首、尾任一可靠命中**即在首块位置（回退到行首）前插 `<!-- page N -->`。
4. 边界处理（方案 X，保证段内锚点连续、宁缺毋误）：
   - 段内**个别页**首尾都失配 → 用相邻两个可靠锚点之间的位置补 `<!-- page N -->`，`manifest.json` 记该页为「近似定位」；
   - 某页在 `content_list` 里无任何内容块（纯空白页）→ 仍按顺序补空的 `<!-- page N -->`（锚点严格连续）；
   - 段内**多数页**失配 → **整段回退**，只保留段级锚点 `<!-- pages N-M -->`，`manifest.json` 记 warning。整段回退是**按失配率触发的通用兜底，不预设 TOC 段**：`toc_repair` 差异为字符级、非整段替换，A′ 不重建内容，故 TOC 段实测仍逐页命中（见 Step 0）。

段级锚点始终保留（叠加），现有 `read_page`/`extract-data` 的 `<!-- pages N-M -->` 正则不受影响。

### 为什么是 A′ 而不是重建（A）或纯对齐（B）

- **纯重建 A**（从 `content_list` 重渲染 md）：页边界精确，但会用「修复前的原始清单」覆盖「后处理过的 md」——丢失 `toc_repair` 成果（LCD→CD 类差异），且需逐一逆向 MinerU 渲染规则（`image.content` 的 `<details>`、图注顺序等）。
- **纯对齐 B**（贪心前向游标 + 页首单块）：跨页表格前缀重复导致误配并污染后续页（实测 p0009-0016：7/8 且 page15 误配、page16 丢失）。
- **A′**：输出仍是原生 md（后处理全保留、零内容风险），用 `page_idx` 分组保证「每组=一页」，首尾**双指纹**比单块贪心鲁棒，首尾皆失配即回退。A′ 下 `image.content`/图注顺序/OCR 单字符差异**都不产生内容差异**（不重建内容），只可能影响「指纹能否命中」，命中不了就回退兜底。

## 公共契约变化

| 契约 | 变化 | 兼容性 |
|---|---|---|
| 合并 md 格式 | 段级锚点后新增逐页锚点 `<!-- page N -->`（HTML 注释行） | 向后兼容：注释不影响渲染；按 `##` 切分的 chunk 不受影响；段级锚点保留 |
| `read_page` 输出 | 命中逐页锚点时 `page_start==page_end==page`；无逐页锚点回退段级（现状行为） | 向后兼容：字段不变，仅粒度变细 |
| `extract-data` `page_start`/`page_end` | 复用逐页锚点后精确到单页 | 行为迁移：需现状快照做对比基线 |

## 影响模块或文件

- `scripts/pdf-merge`（阶段 1）
- 回填入口（阶段 2，复用 `pdf-merge`，视需要加薄封装或文档化命令）
- `scripts/pdf-read-page`、`mcp/server/src/index.ts` 的 `read_page`（阶段 3）
- `scripts/pdf-extract-data` 的 `parse_page_comments`/`get_page_range`/`refine_page_numbers`（阶段 4）
- 每阶段同步 `skills/pdf2md/SKILL.md`（及用户级副本）

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 0 | 设计与 Step 0 证据固化 | 有完整输出包样本（春风 150AURA） | 本会话实测数据固化为可复现脚本/记录 | 已完成 |
| 1 | `pdf-merge` 逐页锚点（A′ + X） | 阶段 0 完成、用户批准实施 | 春风包合并 md 每正文段逐页锚点连续，失配段回退段级，manifest 记 warning | 已完成 |
| 2 | 回填旧包 | 阶段 1 完成 | 对现有 `segments/` 重跑 merge，锚点正确、正文内容与旧 md 一致 | 已完成 |
| 3 | `read_page` 单页 | 阶段 1 完成 | 输入单页返回该页 md；无逐页锚点段回退段级 | 已完成 |
| 4 | 结构化数据逐页 | 阶段 1、3 完成 | `page_start==page_end` 精确到单页；与 `refine_page_numbers` 现状对比无回归 | 已完成 |

## Step 0 证据（本会话，2026-07-08）

样本：`pdf/春风 150AURA`（191 页，25 个 `content_list.json`）。

- **现状**：`pdf-merge:92-96` 仅插段级 `<!-- pages N-M -->`；合并 md 共 24 段锚点（`pages 1-8` … `pages 185-191`）。
- **数据可用性**：`content_list.json` 每块带 `page_idx`；字段含 `text_level`（标题层级）、`table_body`、`img_path`；每页有 `page_number` 块（印刷页码）。
- **全包 type 分布**：text 1205 / page_number 195 / image 175 / table 121 / header 4 / aside_text 2 / footer 1。
- **路线 B 实测**（p0009-0016）：页首单块 + 贪心游标 = 7/8，page15 因跨页表格误配、page16 丢失。
- **路线 A 重建保真实测**（全包，丢弃 header/footer/aside_text/page_number）：22/25 段逐字零差异；共 10 行差异集中在 3 段。
- **差异根因**：`p0001-0008` LCD/CD 系 `toc_repair` 只改 md 不改 `content_list`（`content_list` 为修复前）；`p0161-0168` 图注顺序；`p0185-0191-rerun` `image.content` 的 `<details>` 渲染遗漏。
- **后处理边界**：`toc_repair.py:191` 是唯一「只改 md 不改 content_list」的后处理，仅作用于 TOC 段；rerun 段 md 与 `content_list` 配套一致，不失配。
- **A′ 命中率实测（2026-07-08，阶段 0 收尾）**：首尾双指纹（块文本 / `table_body` / `img_path` 去空白前 40 字符）+ 前向单调游标。正文段 p0009-0016 **8/8**（page15/16 首块失配、尾块命中——正是双指纹优于路线 B 单块 7/8 之处）；TOC 段 p0001-0008 **8/8**（`toc_repair` 字符级差异未落在指纹前缀，A′ 不重建故不受影响）。**修正原假设**：整段回退按失配率触发，TOC 段不预设回退。

## 验证方式

阶段 1（示例）：

```bash
scripts/pdf-merge "pdf/春风 150AURA/segments"
python3 - <<'PY'
import re
md = open('pdf/春风 150AURA/春风 150AURA.md', encoding='utf-8').read()
seg = re.findall(r'<!-- pages (\d+)-(\d+) -->', md)
page = [int(m) for m in re.findall(r'<!-- page (\d+) -->', md)]
print('段级锚点数:', len(seg), '逐页锚点数:', len(page))
# 正文段内逐页锚点应连续（TOC/回退段除外，由 manifest warning 标注）
print('逐页锚点范围:', min(page), '-', max(page))
PY
```

阶段 3：`read_page <pkg> N` 单页返回（page_start==page_end==N）；无逐页锚点段回退段级（page_start/end 为段级范围）；越界返回 error。

阶段 4：在春风 150AURA 样本上运行 `scripts/pdf-extract-data`，保存修改前后的 `data/quick_lookup_draft.csv`。除 `page_start`、`page_end` 及由页码驱动的 `section_path` 外，记录集合、表头、其余字段和状态语义必须无回归；CSV 整体哈希允许因上述预期字段变化而改变。

验收口径：

- 记录所在 Markdown 行之后的首个 `<!-- page N -->` 前锚点即为可靠逐页锚点；命中时必须输出 `page_start == page_end == N`。
- 没有逐页锚点、行号无法可靠定位或所属段仅有 `<!-- pages A-B -->` 时，才允许调用 `refine_page_numbers`；其输出可保留段级或 PDF 文本搜索得到的页码。
- 春风样本的行数必须保持 390，表头保持现有 17 列；以 `(source_block_id, table_id, row_index, parent_key, key, value)` 比对记录集合和状态语义。
- 必须有最小回归样例覆盖：重复 key、重复段落、重复表格值各一例，证明三者都按实际遍历位置绑定到对应逐页锚点。

阶段 4 实施决策（2026-07-10）：

1. **逐页锚点优先**：结构化记录命中 `<!-- page N -->` 时直接采用该页；只有没有可靠逐页锚点时，才调用 `refine_page_numbers` 作为 fallback。不得让 PDF 文本搜索覆盖已命中的逐页锚点。
2. **单页语义固定**：`page_start/page_end` 表示结构化记录所在 Markdown 行的逐页锚点页。命中逐页锚点时必须满足 `page_start == page_end`；`evidence_text` 可能包含跨页内容，但不改变该页码语义。未来如需表达证据覆盖范围，另增字段，不复用 `page_end`。
3. **重复行定位必须稳定**：实施时不得使用全文 `find()` 或“第一处 key/单元格匹配”推断行号。抽取器必须沿实际行/表格遍历位置传递行号，使重复 key、重复段落和重复表格值绑定到其真实逐页锚点；无法可靠定位时走既有 fallback。

治理检查：`python3 scripts/check_plan_governance.py .`

## 阶段 1 验收记录（2026-07-08）

`scripts/lib/page_anchors.py`（新建，A′+X 核心）+ `scripts/pdf-merge`（集成）+ `tests/test_page_anchors.py`（10 单测）。独立 subagent 对抗性验收：**有条件通过**。

自测 + 独立复核达标：
- **10 单测全绿**：首块 exact / 尾块 tail / 多数失配回退 / 空白页顺序补 / 正文零改动 / 绝对页码 + 真实段 p0009-0016 8/8。
- **春风端到端**（临时输出，未覆盖原包）：191 逐页锚点，1-191 连续无缺无重；段级锚点 24 保留；strip 逐页锚点后与原 md 逐字节一致。
- **manifest**：`total_anchors=191`、7 段 warning、0 整段回退。
- **影响**：`impact` / `detect_changes` LOW、affected_processes 空，向后兼容叠加。
- 独立验收另确认：跨页相同前缀未误配、191 锚点全在行首无破行、pdf-merge 集成（argv/import/v1 选择/段级保留）正确。

独立验收发现（放行前待处理）：
- **M-1（中，待修）**：近似页（miss/tail）用 `last_off` 补位，与**前一可靠页**锚点同 offset 堆叠 → 前一可靠页 read region 塌空。实测 9 对（前页 14/20/65/71/75/127/129/187/189 读空），且这些可靠页未进 manifest warning，会误导阶段 3 `read_page`/阶段 4 `extract-data`。修复：近似页锚点放**下一个**可靠锚点处 + 受连累页写 manifest。
- **M-2（中，待修）**：`page_idx` 不与段声明页范围 `pXXXX-YYYY` 交叉校验，越界/尾部缺口静默（春风规整未触发）。加段范围校验 + warning。
- **L-3（低）**：段缺 `content_list.json` → 整段逐页锚点缺失且不记 warning。
- **L-4（低）**：`strip_page_anchors` 正则自校验，源 md 若本含 `<!-- page N -->` 会误判（当前样本 0 行不触发）。

### 修复复验（2026-07-08）

**M-1 / M-2 已修，独立 subagent 复验确认；复验发现的粘行回归也已修。阶段 1 放行。**

- **M-1 修**：近似页（tail/miss/blank）改放「下一个 exact 锚点」处（段尾放段末），近似页诚实读空、前一可靠页 read region 保全。独立复验：9 个受连累可靠页（14/20/65/71/75/127/129/187/189）read region 全部非空且内容正确归位，空 region 严格 ⊆ 近似页集合。
- **M-2 修**：`seg_end` 段范围校验——越界 `page_idx` 记 `page_idx_out_of_range` 不溢出、尾部缺口补 blank 不静默；独立负样本验证通过。
- **粘行回归修**（复验发现的新缺陷）：`next_exact=len` + `pdf-merge` `.strip()` 去尾换行 → 段尾锚点粘正文行尾（3 处）。修法：`pdf-merge` 段 text 补尾换行使段末锚点落行首。端到端复验：**0 粘行**、strip 后与现有 md 逐字节一致（零改动不回归）、191 连续、M-1 不回归。
- **14 单测全绿**（新增 read region 不被偷 / 越界 / 尾部缺口 / 锚点独立行 4 个用例）。
- L-3 / L-4 / 整段全 tail 段未修，延后（见未决问题）。

## 完成条件

- [x] 阶段 1：正文段逐页锚点连续且落点正确；近似段记 warning；正文内容零改动。→ 191 锚点连续、零改动、0 粘行、M-1/M-2/粘行已修并独立复验、14 单测（见修复复验）。
- [x] 阶段 2：旧包回填后正文内容与旧 md 一致，逐页锚点正确。→ 4 包回填验证（见阶段 2 验收记录）。
- [x] 阶段 3：`read_page` 单页返回；无逐页锚点段回退段级；MCP 编译通过。→ 春风 150AURA 单页 page_start==page_end（57→57、1→1、191→191）；范围 57-60 四页拼接；越界返回 error；MCP tsc 编译通过（见阶段 3 验收记录）。
- [x] 阶段 4：`page_start==page_end` 精确到单页；对比现状无回归。→ 春风 150AURA 390 行全部单页（跨页 64→0），非页码字段零回归；demo20 55 行全部单页；demo60 147 行全部单页；demo5 0 行（空 TOC 符合预期）；幂等性通过。独立验收发现跨段锚点继承缺陷（M-5），已修复并回归验证通过（见阶段 4 验收记录及修复复验）。
- [~] 每阶段同步 `skills/pdf2md/SKILL.md` 及用户级副本。→ 阶段 1 `pdf-merge` 已能生成逐页锚点，但现有包未回填、`read_page` 未消费，合并 md 格式 skill 描述推迟到阶段 2 回填后统一更新（补同步动作已登记）。
- [x] `detect_changes()` 仅影响预期符号；治理检查通过。→ detect_changes LOW、affected_processes 空；治理检查通过。

## 阶段 2 验收记录（2026-07-09）

**回填 4 个旧包**（demo5/春风 150AURA/demo20/demo60），全部通过验证：

- **demo5**（5 页，5 段）：5 个逐页锚点，3 段有 `tail_page` warning（单页段首块失配但尾块命中，符合预期）。
- **春风 150AURA**（191 页，24 段）：191 个逐页锚点，7 段有 warning（`miss_page`/`tail_page`），与阶段 1 一致。
- **demo20**（20 页，2 段）：20 个逐页锚点，1 段有 warning（`tail_page:15, miss_page:16`）。
- **demo60**（60 页，8 段）：60 个逐页锚点，2 段有 warning。

**正文一致性**：`strip_page_anchors` 后与备份的旧 md **逐字节一致**（demo5 4612 字符、春风 150AURA 96626 字符）。

**锚点连续性**：4 包逐页锚点均连续无缺无重（1-5、1-191、1-20、1-60）。

**manifest 更新**：4 包 `manifest.json` 均写入 `page_anchors` 字段（`total_anchors`、`segments_with_warnings`、`warnings`）。

**图片处理**：demo20 收集 13 张新图片，demo60 收集 76 张新图片，春风 150AURA 跳过 314 张幂等图片。

**回填命令**（文档化）：

```bash
scripts/pdf-merge <package>/segments
```

无需新增脚本，直接复用新版 `pdf-merge`。旧包 md 如有手改，回填前需备份（已自动备份至 `<package>/.backup_stage2/`）。

## 阶段 3 验收记录（2026-07-10）

**`scripts/pdf-read-page` 升级为逐页锚点感知**，2 个新公共函数 + 三路选择逻辑，无新增依赖。

端到端验收（春风 150AURA 191 页输出包）：

| 测试 | 结果 |
|---|---|
| 单页 57 | `page_start=57, page_end=57` ✅ |
| 首页 1 | `page_start=1, page_end=1` ✅ |
| 末页 191 | `page_start=191, page_end=191` ✅ |
| 范围 57-60 | `page_start=57, page_end=60, segment_count=4` ✅ |
| demo60 首页 1 | `page_start=1, page_end=1` ✅ |
| 越界 999 | `status=error` ✅ |
| MCP `tsc` 编译 | 通过 ✅ |
| MCP 工具描述 | 已同步逐页锚点说明 ✅ |

**向后兼容验证**：无逐页锚点时 `page_anchors` 为空列表 → 走 `_extract_pieces_with_seg_anchors`（原段级逻辑），字段不变量不变。

**`read_page` 粒度提示**决策：回退段级时 `page_start!=page_end` 自然表达「非单页粒度」，无需新增字段。⇒ 对应未决问题已关闭。

skill 同步：`read_page` 输出粒度变细，属公共契约变更，需同步 `skills/pdf2md/SKILL.md` 及用户级副本（见完成条件）。

## 阶段 4 验收记录（2026-07-10）

**`scripts/pdf-extract-data` 全流程改造**：`parse_page_comments` 增设 `per_page_map` 逐页锚点解析；`get_page_range` 优先 `per_page_map`（命中时 `page_start==page_end==N`）；三条抽取器行号定位全部从全文 `find()` 改为实际遍历/HTML 块偏移；`refine_page_numbers` 变为仅对无逐页锚点的行做兜底过滤。

修改范围（`scripts/pdf-extract-data`）：

- `parse_page_comments`：新增 `PAGE_ANCHOR_RE` 正则，返回 `(page_map, per_page_map)`
- `get_page_range`：逐页锚点优先（命中时第三返回值为 `True`），回退段级
- `extract_colon_rows`：行号从 `md_text.find()` 改为逐行枚举
- `extract_html_table_rows`：新增 `_get_html_table_row_lines` 辅助函数，按 `<table>` 块位置 + `<tr>` 偏移计算实际行号
- `extract_md_table_rows`：适配 3-tuple 返回值
- `main`：`_has_per_page_anchor` 标记追踪，仅对非逐页锚点行调用 `refine_page_numbers`

端到端验收（春风 150AURA 191 页输出包）：

| 检查项 | 结果 |
|---|---|
| 行数 | 390（与基线一致）✅ |
| 列数 | 17（表头不变）✅ |
| 单页范围 | 390/390（跨页 64→0）✅ |
| 非页码字段无变化 | 390/390 行 ✅ |
| 重复 key 正确绑定不同页 | 48 组重复 key，均按实际位置分布 ✅ |
| 同一 block 无跨页错位 | 0 例 ✅ |
| refine_page_numbers 仅兜底 | 仅未命中逐页锚点的行触发 ✅ |
| 幂等性 | 连续两次运行一致 ✅ |
| 治理检查 | 通过 ✅ |

其他包回归：

- **demo20**（20 页）：55 行全部单页（页码范围 9-14），架构一致 ✅
- **demo60**（60 页）：147 行全部单页（页码范围 9-60），架构一致 ✅
- **demo5**（5 页）：0 行（空 TOC 样本，符合预期）✅

**Page 14 vs page 9 精度对比**：旧 `refine_page_numbers` 将 CF150T-32 等规格赋值到 page 9（因前言中提及 "CF150T-32 / CF150T-32A"），新逐页锚点正确归入 page 14（规格表所在页）。逐页锚点基于正文流定位，比 PDF 文本搜索更可靠。

最小回归样例覆盖：

- **重复 key**：验证 `后轮`（6 行分属 3 个不同页）、`NFC`（4 行分属 4 个不同页）均按实际遍历位置绑定正确 ✅
- **重复段落**：`extract_colon_rows` 的行号从 `find()` 改为枚举，重复冒号行不再误匹配 ✅
- **重复表格值**：`extract_html_table_rows` 的行号从全文搜索改为 HTML 块跟踪，重复单元格值绑定到对应逐页锚点 ✅

### 阶段 4 修复复验（2026-07-10）

独立对抗性验收发现 **M-5（中，已修）**：跨段逐页锚点继承。

**缺陷**：输出包前段有逐页锚点、后段只有段级锚点时，`get_page_range()` 错误沿用前段最后一个逐页锚点。例如内容在段 `<!-- pages 9-16 -->` 但返回 `('8', '8', True)`，违反 fallback 契约。

**根因**：`get_page_range` 搜索 `per_page_map` 时全局扫描，未检查段级锚点 `<!-- pages N-M -->` 作为作用域边界。逐页锚点从前段"泄漏"到后段。

**修复**：`get_page_range` 找到最佳逐页锚点后，检查该锚点与 `line_no` 之间是否存在段级锚点。若存在，则该逐页锚点属上一段，对当前行无效 → 回退段级。段级锚点即作用域边界。

**验证**：混合锚点 MD 样本（前段有逐页锚点、后段无）——前段返回 `(page, page, True)`，后段返回 `(seg_start, seg_end, False)`，全部正确。春风 150AURA 390 行页码均在段范围内，0 超段。

**回归**：demo20/demo60/demo5 一律通过，非页码字段零回归。

## 阶段 4 Step 0 门禁（2026-07-10）

阶段 4 已推进为**待实施**，实施目标和三项实施决策见上方“阶段 4 实施决策”。

现状回归基线（春风 150AURA 输出包）：

- `data/quick_lookup_draft.csv` 共 390 条记录，表头保持现有 17 列。
- 当前结果为 326 条单页范围、64 条跨页范围、0 条空页范围，页码范围为 2–191。
- 基线文件 SHA-256：`c7140903cb19fdcf9338c5307f25646701eca83f7f065f7678583c4fe5481ce0`。
- 阶段 4 的基线用于比较记录集合和非页码字段，不要求 CSV 哈希不变：`page_start`、`page_end` 及由页码驱动的 `section_path` 是本阶段允许变化的字段，变化必须符合“阶段 4 验收口径”。

进入门禁：

- 阶段 1/2/3 已完成，逐页锚点已生成并完成旧包回填。
- Step 0 回归样本、统计口径和基线哈希已固定。
- 验证方式、完成条件、风险和回滚边界已定义；当前无阻塞项。

阶段 4 实施前必须重新运行基线统计，并按“阶段 4 验收口径”对修改前后 `quick_lookup_draft.csv` 做对比；修改 `scripts/pdf-extract-data` 前仍需按项目规则执行 GitNexus `impact`。

## 风险和回滚

风险：

- `content_list` 与 md 失配（TOC 及未来新增的「只改 md」后处理）→ 首尾双指纹失配即整段回退段级兜底。
- 极端重复内容（跨页大表格）首尾指纹误配 → 前向单调约束 + 双指纹 + 失败回退，宁缺毋误。
- 回填会覆盖旧包合并 md → merge 幂等且 A′ 不改正文；实施前确认旧包 md 无人工手改。
- `extract-data` 逐页收窄属行为迁移 → 需现状快照做回归基线（阶段 4 Step 0）。

回滚：

- 逐页锚点为新增注释，段级锚点与正文不变；回退旧版 `pdf-merge` 即恢复现状，下游正则不受影响。
- 各阶段独立，可单独回滚。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 回填入口形态（薄封装脚本 vs 文档化重跑 merge） | 阶段 2 决定，优先复用 `pdf-merge` 不新增脚本 | 否 | 待定 |
| 「近似定位」页是否需在 md 锚点上标注（vs 仅 manifest） | 阶段 1 决定，默认仅 manifest，md 锚点保持纯净 | 否 | 待定 |
| `read_page` 对回退段级的段是否需返回粒度提示字段 | 阶段 3 已决：`page_start!=page_end` 自然表达，无需新增字段 | 否 | 已决 |
| pdf2md skill 同步时机 | 各阶段实施完成即同步项目级 + 用户级 skill；若无法同步在此表记录补同步动作 | 否 | 待跟踪 |
| L-3：整段缺 `content_list.json` → 整段逐页锚点缺失且不记 warning | 走 `cl is None` 分支加段级 warning；阶段 2 回填时处理 | 否 | 待处理（阶段 1 复验发现） |
| L-4：`strip_page_anchors` 自校验对源 md 本含 `<!-- page N -->` 行会误判 | 罕见（样本 0 行），阶段 3 `read_page` 前评估 | 否 | 已登记 |
| 整段全 tail 段（每页首失配尾命中，miss=0 不回退）逐页定位退化为无效 | 真实样本未出现；如出现按失配率纳入回退判定 | 否 | 已登记边角 |

## 关联

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) — `pdf-merge`/`pdf-auto` CLI 契约
- [PDF 输出包目录结构计划](pdf-output-package-layout.md) — 合并 md 输出契约（本计划扩展其锚点格式）
- [覆盖率验证口径优化计划](coverage-validation-optimization.md) — `toc_repair` TOC 段后处理来源
- [输出包结构化数据抽取计划](structured-data-extraction.md) — `page_start/page_end` 与 `refine_page_numbers` 现状
- [PDF 工作流增强路线图](pdf-workflow-enhancement-roadmap.md) — `read_page`（P3a）消费方；不变量「增强工具不修改合并 md」指事后消费工具，本计划改的是 merge 生成阶段，不冲突
