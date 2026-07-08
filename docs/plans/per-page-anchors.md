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
   - 段内**多数页**失配（典型：TOC 段被 `toc_repair` 整段替换）→ **整段回退**，只保留段级锚点 `<!-- pages N-M -->`，`manifest.json` 记 warning。

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
| 0 | 设计与 Step 0 证据固化 | 有完整输出包样本（春风 150AURA） | 本会话实测数据固化为可复现脚本/记录 | 实施中 |
| 1 | `pdf-merge` 逐页锚点（A′ + X） | 阶段 0 完成、用户批准实施 | 春风包合并 md 每正文段逐页锚点连续，TOC 段回退段级，manifest 记 warning | 待实施 |
| 2 | 回填旧包 | 阶段 1 完成 | 对现有 `segments/` 重跑 merge，锚点正确、正文内容与旧 md 一致 | 待实施 |
| 3 | `read_page` 单页 | 阶段 1 完成 | 输入单页返回该页 md；无逐页锚点段回退段级 | 待实施 |
| 4 | 结构化数据逐页 | 阶段 1、3 完成 | `page_start==page_end` 精确到单页；与 `refine_page_numbers` 现状对比无回归 | 待实施 |

## Step 0 证据（本会话，2026-07-08）

样本：`pdf/春风 150AURA`（191 页，25 个 `content_list.json`）。

- **现状**：`pdf-merge:92-96` 仅插段级 `<!-- pages N-M -->`；合并 md 共 24 段锚点（`pages 1-8` … `pages 185-191`）。
- **数据可用性**：`content_list.json` 每块带 `page_idx`；字段含 `text_level`（标题层级）、`table_body`、`img_path`；每页有 `page_number` 块（印刷页码）。
- **全包 type 分布**：text 1205 / page_number 195 / image 175 / table 121 / header 4 / aside_text 2 / footer 1。
- **路线 B 实测**（p0009-0016）：页首单块 + 贪心游标 = 7/8，page15 因跨页表格误配、page16 丢失。
- **路线 A 重建保真实测**（全包，丢弃 header/footer/aside_text/page_number）：22/25 段逐字零差异；共 10 行差异集中在 3 段。
- **差异根因**：`p0001-0008` LCD/CD 系 `toc_repair` 只改 md 不改 `content_list`（`content_list` 为修复前）；`p0161-0168` 图注顺序；`p0185-0191-rerun` `image.content` 的 `<details>` 渲染遗漏。
- **后处理边界**：`toc_repair.py:191` 是唯一「只改 md 不改 content_list」的后处理，仅作用于 TOC 段；rerun 段 md 与 `content_list` 配套一致，不失配。

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

阶段 3/4：`read_page <pkg> N` 单页返回；`pdf-extract-data` 后抽查 `quick_lookup_draft.csv` 的 `page_start==page_end`，与改动前快照对比无回归。

治理检查：`python3 scripts/check_plan_governance.py .`

## 完成条件

- [ ] 阶段 1：正文段逐页锚点连续且落点正确；TOC/近似失败段回退段级并记 warning；正文内容零改动。
- [ ] 阶段 2：旧包回填后正文内容与旧 md 一致，逐页锚点正确。
- [ ] 阶段 3：`read_page` 单页返回；无逐页锚点段回退段级；MCP 编译通过。
- [ ] 阶段 4：`page_start==page_end` 精确到单页；对比现状无回归。
- [ ] 每阶段同步 `skills/pdf2md/SKILL.md` 及用户级副本。
- [ ] `detect_changes()` 仅影响预期符号；治理检查通过。

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
| `read_page` 对回退段级的段是否需返回粒度提示字段 | 阶段 3 评估，倾向复用现有 `segment_count`/`page_start!=page_end` 表达 | 否 | 待定 |
| pdf2md skill 同步时机 | 各阶段实施完成即同步项目级 + 用户级 skill；若无法同步在此表记录补同步动作 | 否 | 待跟踪 |

## 关联

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) — `pdf-merge`/`pdf-auto` CLI 契约
- [PDF 输出包目录结构计划](pdf-output-package-layout.md) — 合并 md 输出契约（本计划扩展其锚点格式）
- [覆盖率验证口径优化计划](coverage-validation-optimization.md) — `toc_repair` TOC 段后处理来源
- [输出包结构化数据抽取计划](structured-data-extraction.md) — `page_start/page_end` 与 `refine_page_numbers` 现状
- [PDF 工作流增强路线图](pdf-workflow-enhancement-roadmap.md) — `read_page`（P3a）消费方；不变量「增强工具不修改合并 md」指事后消费工具，本计划改的是 merge 生成阶段，不冲突
