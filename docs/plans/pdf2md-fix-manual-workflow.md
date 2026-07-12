# 计划：pdf2md-fix 人工复核与内容修复工作流

## 计划状态

- 状态：实施中
- 当前阶段：阶段 2：修复记录与派生产物应用
- 最后更新：2026-07-12

本文档是 `pdf2md-fix-manual-workflow` 的实施细节事实源。计划索引、状态、依赖、推荐顺序和证据入口以 [PLAN_MAP](../PLAN_MAP.md) 为准。

## 背景

当前 `pdf2md` 已能完成 PDF 分段解析、质量检测、页级 fallback、Markdown 合并、表格结构自检、结构化草案和入库前审核。但这些自动化结果仍有一类不能安全自动判定的问题：跨页表格的逻辑连续性、表头与列语义、图片/OCR 内容、章节归属、字段规范化和冲突事实判断。

`review.md` 可以发现并列出问题，`review_overrides.csv` 可以批准或拒绝结构化记录，但项目尚缺少一个独立的人工修复入口，来记录“对原始转换内容做了什么修复、依据哪一页、修复后下游应该如何理解”。

本计划新增一个项目级 `pdf2md-fix` skill，并将表格可读性格式化下沉到 `pdf-merge` 的 canonical Markdown 生成阶段。`pdf-merge` 生成的 `<stem>.md` 直接采用可校对的 HTML 表格格式，再由人工和 VLM 进行视觉确认与内容修复。VLM 只提供证据和候选，不直接产生最终事实或审核结论。该计划不改变 MinerU 主解析入口，也不把人工判断伪装成自动检测结果。

## 目标

- 定义 `pdf2md` 完成后人工复核的固定顺序、证据要求和退出条件。
- 明确哪些问题由 `pdf-auto` 自动处理、哪些问题只自动发现后交给人工、哪些问题必须人工决定。
- 创建项目级 `skills/pdf2md-fix/SKILL.md`，必要时同步到用户级 skill。
- 为跨页表格、表格布局、字段遗漏、章节归属和内容修正建立可追溯记录。
- 为 `excessive_empty_td`/`excessive_columns` 生成页级候选恢复内容，减少人工反复编写 PyMuPDF 提取代码。
- 以页锚点为边界执行修复，阻止全局文本替换造成跨页内容漂移。
- 在修复前冻结 `rebuild_table`、`fix_header`、`fill_content`、`fix_section` 等 `manual_fixes.jsonl` 类型模板。
- 允许人工复核阶段按需使用 VLM 生成视觉证据和候选修复，并记录模型、输入页和人工采纳结论。
- 为人工校对生成可读的 HTML 表格格式：结构标签分行、单元格可定位，同时保持表格语义不变。
- 将 HTML 表格格式化放在人工修复、VLM 确认和结构化抽取之前，作为稳定的校对输入。
- 保留原始 PDF、原始分段和格式化前 Markdown 的 hash，不让人工修复破坏回溯链。
- 让下游通过稳定的逻辑表格和修复记录知道人工结论，而不是根据 `<table>` 数量猜测语义。
- 规定 Markdown、`manifest.json`、修复记录和逻辑表格元数据必须作为一个原子发布单元同步更新。
- 保持现有 `review_overrides.csv` 的职责：只表达结构化记录的审核状态，不承担内容字段改写。

## 非目标

- 不在本计划中自动识别所有跨页表格。
- 不把 VLM 接入 `pdf-auto` 主解析或自动放行链路。
- 不把带 `rowspan/colspan` 的 HTML 表格直接转换成 Markdown 管道表格；格式化阶段只改变可读性，不改变表格模型。
- 不根据纯文本候选自动推断最终表格行列、`rowspan` 或 `colspan`；候选恢复结果必须进入人工确认。
- 不把 `MINERU_SEGMENT_SIZE` 全局改成多页模式。
- 不修改 MinerU 主解析、页级 fallback 或 CLI JSON 边界，除非后续阶段有独立证据证明必要；`pdf-merge` 的 Markdown 展示归一化属于本计划范围。
- 不直接写入业务数据库，不新增 MCP Server 或 MCP 兼容层。
- 不自动生成 `approved`、`ready` 或其他入库放行结论。
- 不覆盖 `quick_lookup_draft.csv`、原始 PDF 或原始 `segments/`；canonical `<stem>.md` 允许先做语义保持的原地格式化，内容修复仍需遵守 manifest 修复契约。
- 不把纯排版优化、无来源的文字润色当作事实修复。

## 影响模块或文件

阶段 0 只修改治理文档。后续实施候选范围：

- `scripts/pdf-merge`：在 canonical Markdown 生成阶段执行 HTML 表格 pretty-print，并参与 manifest 同步发布。
- `scripts/pdf-auto`、`scripts/pdf-seg` 或共享 manifest 辅助模块：登记 Markdown 内容 hash 和格式化状态，具体归属在 Step 0 后确定。
- `scripts/lib/toc_repair.py`：作为 Markdown 生成后的既有变更步骤，必须纳入最终 manifest hash 计算边界。
- `skills/pdf2md/SKILL.md`：补充 canonical Markdown 已格式化、manifest 同步和人工修复前置条件；完成后同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。
- `skills/pdf2md-fix/SKILL.md`：定义 VLM 辅助、人工内容修复和修复记录。
- `pdf2md-fix` 的配套 `pdf-table-fix` helper/脚本：扫描异常页并生成页级原文候选，初版不自动决定表格结构。
- `scripts/pdf-read-page`、`scripts/pdf-extract-data`：只做兼容性验证，除非真实样本证明需要调整。

阶段 0 不修改上述代码、skill 或用户级副本。

## 当前实际执行顺序

`pdf-seg` 是前置分段入口；已有 `segments/` 时可以跳过。`pdf-auto` 的当前主链路不是“先 merge 再 auto”，而是：

```text
pdf-seg（必要时）
  → pdf-auto：一致性检查、页级质量/fallback、pdf-validate
  → 根据验证结果选择 merge 或 needs_review
```

通过路径：

```text
pdf-merge
  → 合并级 toc_repair.repair_merged
  → 生成 review.md（如有待复核项）
  → 更新 manifest 状态
```

需要复核路径：

```text
TOC 段级修复 toc_repair.repair
  → pdf-merge
  → 合并级 toc_repair.repair_merged
  → 生成 review.md
  → 更新 manifest 状态
```

因此，表格 pretty-print 可以放在 `pdf-merge` 的 Markdown 生成阶段，但 manifest 的最终 Markdown hash 必须在最后一个可能修改 Markdown 的步骤之后计算。`pdf-merge`、TOC 修复和 manifest finalization 共同构成最终发布边界，不能只在 `pdf-merge` 内提前写入最终 hash。

## `pdf2md-fix` 介入点

`pdf2md-fix` 位于 `pdf-auto` 完整结束之后、结构化抽取之前：

```text
pdf-seg（必要时）
  → pdf-auto
      ├─ 一致性检查
      ├─ 页级质量检测 / fallback
      ├─ pdf-validate
      ├─ pdf-merge（含表格 pretty-print）
      ├─ TOC 修复
      ├─ review.md
      └─ manifest finalization
  → pdf2md-fix
      ├─ 读取 canonical Markdown、review.md、manifest 和 segments
      ├─ 按需调用 VLM
      ├─ 人工确认和修复内容/表格语义
      └─ 再次同步 manifest
  → pdf-extract-data
  → pdf-prepare-ingest
  → pdf-export-ingest
```

介入规则：

- `pass`：不进入 `pdf2md-fix`，直接继续结构化抽取。
- `fix_md` 或跨页表格/字段语义问题：进入 `pdf2md-fix`，修复后再抽取。
- `rerun`：回到 `pdf-rerun`/`pdf-auto` 的解析修复路径，不由 `pdf2md-fix` 伪装成内容修复。
- `pdf2md-fix` 不介入 MinerU 请求、页级 fallback、`pdf-merge` 内部或 TOC 修复中间步骤。
- `pdf2md-fix` 修改 Markdown 后，必须重新执行 manifest finalization；结构化抽取只能读取修复状态已登记的结果。

## 不变量与信任边界

- 原始 PDF、原始分段和格式化前 Markdown hash 必须保留；修复结果必须能回指原始页、段、块或 Markdown 行。
- 人工补写的字段必须带 PDF 页码和证据说明；无法确认时保持 `needs_review`。
- `table_id` 表示逻辑表格身份，不能仅用 `html_table:N` 这种当前页内/文件顺序编号代替跨页身份。
- `review_action` 与 `review_status` 分离：前者说明内容处理动作，后者说明是否批准结构化记录。
- 修复后的 Markdown 是阅读视图；下游结构化数据的事实源必须是带来源和状态的机器可读记录。
- 任何修改或发布 Markdown 的操作都必须同步修改 `manifest.json`；禁止正文与 manifest 对文件角色、hash 或修复状态产生漂移。
- 表格格式化必须是语义保持变换：除允许的空白和换行外，单元格文本、标签属性、`rowspan`、`colspan`、表格数量和行列关系不得改变。
- `pdf-merge` 生成的 canonical Markdown 必须在 `pdf2md-fix` 读取和人工修复之前完成格式化；人工修复不得以未格式化的单行表格作为唯一输入。
- 修复应用必须幂等；同一输入 hash 和同一修复记录重复运行，不得产生重复行或重复表格。
- 没有人工确认的内容不得因为“自动修复成功”而进入 `approved`/`ready`。
- VLM 输出只能作为人工复核证据或候选；未经人工对照 PDF 原页确认，不得写入修复后的事实字段。
- 修复默认必须限定在一个页锚点或显式声明的多页范围内；禁止无页边界的全局替换。
- 修复应用不得以全局 Markdown 字符串作为唯一目标；必须同时校验页锚点、目标块 hash、期望命中数和替换后页块 hash。

## Step 0 证据

### 现有功能证据

- `pdf-auto` 已生成 `review.md`，并将页级表格字段遗漏、低覆盖率、图片/目录页等问题暴露给人工；表格页默认进入 `review_only`，见 `skills/pdf2md/SKILL.md` 的页面类型策略。
- `pdf-eval-tables` 只做表格 HTML 的行列、空单元格、合并单元格和列一致性统计，明确属于启发式结构自检，不是语义验收。
- `pdf-extract-data` 会根据 Markdown 表格猜测 key/value 列、单位和章节路径，并将不确定行标记为 `needs_review`；这些规则不能决定跨页表格的全局语义。
- `review_overrides.csv` 当前只允许 `record_id,review_status,notes`，不能修改 `key/value/unit/evidence_text`；内容修正需要独立契约。
- `pdf-prepare-ingest` 已有保守门禁：只有人工批准、证据完整且无未解决冲突时才能进入 `ready`；该门禁不应由 `pdf2md-fix` 绕过。
- 当前已有 `scripts/pdf-eval-vlm`，在 `pdf-auto` 完成后按需读取输出包并写入 `data/vlm_eval.jsonl`；它不参与主解析或表格 `<td>` fallback，适合作为人工复核阶段的视觉证据入口。

### 本次人工修复反馈证据

根据 2026-07-12 人工修复总结：

- p37、p47、p48、p50 等页面出现同一类 8192 个空 `<td>`、异常列数问题，属于本次修复量最高且成本最高的类别。
- 本次约 15 页修复中，整表重建、表头修正、内容补全和格式化反复出现；“8192 空列爆炸表”约占修复量 60% 以上的判断需要后续用 manifest 统计复核，但已足以作为候选工具的优先级依据。
- p47/p48 曾因全局 `replace()` 误命中其他页面，证明修复必须使用 `<!-- pages N-N -->` 锚点和页级目标边界。
- VLM 对文字正确性、表头和符号确认较可靠，但对表格行列、`rowspan/colspan` 结构判断不可靠；VLM 使用边界应收窄到文字/视觉证据。

### demo20 真实样本证据

- `pdf/demo20/demo20.md` 的第 14、15、16 页分别包含一个 HTML `<table>`，但视觉和语义上是同一张连续参数表。
- 第 14 页包含表头和“性能/尺寸/发动机”，第 15 页是连续行，第 16 页继续该表并进入“电器装置/减震器”。
- `manifest.json` 对第 14、15、16 页分别记录了人工表头修复、fallback 和人工整表布局修复；说明现有页级质量流程能够发现局部问题，但不能表达跨页逻辑表身份。
- 第 15 页原始解析出现大量空单元格，fallback 后才得到可读表格；跨页分组必须基于最终选定候选和人工确认，不能只读原始 MinerU 结果。

### Step 0 实测补充（2026-07-12）

本轮直接读取现有输出包的 `manifest.json`，没有改动 PDF、Markdown 或代码。统计结果如下：

| 输出包 | `excessive_empty_td` / `excessive_columns` 页面 | 8192 空列页面 | 已登记人工修复备注 |
|---|---|---|---:|
| `pdf/demo20` | p12、p15 | p15（p12 为 16311 个空单元格） | 2 |
| `pdf/demo60` | p12、p15、p37、p47、p48、p50 | p15、p37、p47、p48、p50（p12 为 16311 个空单元格） | 15 |
| `pdf/demo5` | 无 | 无 | 0 |

这些统计来自现有 manifest，不把 `demo20` 与 `demo60` 当作同一份 PDF 的去重页数。它确认了候选工具的优先级，但尚不能证明所有异常页都适合用同一种表格模板恢复。

当前 Markdown 基线也已核对：

- `pdf/demo20/demo20.md` 的 p14、p15、p16 各自有一个 `<table>`，页锚点唯一；p15 对应的原始 manifest 指标为 `empty_td=8192`，fallback 后为 4 列可读候选。
- `pdf/demo60/demo60.md` 的 p37、p47、p48、p50 页锚点均唯一，且每个页块都能被单独截取；当前文件中每个目标页块各含一个完整 `<table>`。
- 现有 manifest 的 `human_fix_note` 已能说明部分人工动作，但没有稳定的 `fix_id`、前后 hash、VLM 证据和结构化 `status`，因此不能替代 `manual_fixes.jsonl`。

p37 修复脚本的漂移原因已经由人工复盘确认：合并 Markdown 中的 `<table><tr><td></td>…（重复 8192 个空 td）…</td></tr></table>` 字符串在 p37、p47、p48 三个页块完全相同，脚本按全局字符串执行 `replace()`，因此一次操作同时命中了三页。该证据可作为阶段 2 的最小回归 fixture，不再只是待验证假设。

因此，修复器必须先锁定 `<!-- pages N-N -->` 页锚点，再在锚点范围内匹配；若目标字符串在当前页块内不唯一、页锚点缺失或声明范围与实际命中数不一致，必须拒绝应用。验收时还要证明页锚点外内容 hash 不变。

### 可复现基线命令

```bash
sed -n '243,326p' pdf/demo20/demo20.md
cat pdf/demo20/manifest.json
sed -n '55,68p' pdf/demo20/review.md
python3 scripts/check_plan_governance.py .
```

## 功能分层与人工边界

| 功能 | 默认处理 | 人工职责 |
|---|---|---|
| PDF 分段、MinerU 解析、图片收集 | 自动 | 只在失败或参数不合适时决定是否重跑 |
| hash、页数、目录一致性 | 自动 | 处理输入或输出包不一致 |
| 覆盖率、缺失词、空单元格、列数异常 | 自动发现 | 判断是解析错误还是目录/图片/排版特例 |
| 页级 fallback | 自动候选与质量比较 | 对未改善、部分改善或表格语义变化做最终选择 |
| Markdown 合并、页码锚点 | 自动 | 检查修复后页码和来源是否仍可追溯 |
| TOC 物理页归属 | 明确匹配自动处理 | `toc_unassigned`、多级或跨行条目人工确认 |
| 表格结构统计 | 自动 | 判断列语义、表头、跨页连续性和 rowspan/colspan |
| 8192 空列候选恢复 | 读取 manifest 信号并按页提取 PDF 原文候选 | 人工决定是否重建表格和最终行列结构 |
| 表格可读性格式化 | 人工修复前自动原地执行 | 人工校对格式化后的结构和语义；发现结构异常时记录修复，不把格式化当作语义修复 |
| VLM 图片/图表和表格视觉辅助 | 人工阶段按需生成候选证据 | 对照 PDF 原页确认关键数字、警告、图中标注和表格关系；不得直接采纳 |
| 结构化字段草案 | 自动生成 draft | 修正 key/value/unit/parent_key/section_path |
| 冲突检测 | 自动列出候选冲突 | 判断是否真实矛盾、局部标签复用或上下文不同 |
| 审核放行 | 自动计算门禁 | 明确 `approved`、`rejected` 或继续 `needs_review` |

## 候选修复记录契约

阶段 1 需要冻结一个可扩展、可审计的修复记录。推荐使用 JSONL，以支持跨页表格和前后结构同时记录：

```text
<package>/data/manual_fixes.jsonl
```

每行至少包含：

| 字段 | 说明 |
|---|---|
| `fix_id` | 稳定修复 ID |
| `fix_type` | `rebuild_table`、`fix_header`、`fill_content`、`cross_page_table`、`table_layout`、`missing_text`、`section_attribution`、`field_correction`、`image_ocr` 等 |
| `review_action` | `pass`、`fix_md`、`rerun` 或 `fix_data` |
| `status` | `proposed`、`applied`、`verified`、`rejected` |
| `pages` | 相关 PDF 页码列表 |
| `source_refs` | `segment`、`source_block_id`、Markdown 行或 content list 文件引用 |
| `before` | 修复前摘要，不能依赖当前文件内容才能解释 |
| `after` | 修复后摘要或规范化结果 |
| `evidence` | 原 PDF 页、原生文本、截图/视觉检查说明 |
| `vlm_evidence` | 可选的 VLM 模型、输入页/裁剪区域、输出文件和人工采纳说明 |
| `operator_note` | 人工判断和保留意见 |

跨页表格的 `after` 至少应包含：

```json
{
  "table_id": "demo20-parameters-p14-p16",
  "page_start": 14,
  "page_end": 16,
  "continuation": true,
  "parts": [
    {"page": 14, "role": "start"},
    {"page": 15, "role": "middle"},
    {"page": 16, "role": "end"}
  ],
  "logical_columns": 4
}
```

该记录只表达人工确认的逻辑关系，不要求立即把三个原始 HTML 表格物理拼成一个表。

## 表格可校对格式

`pdf-merge` 生成 canonical Markdown 时，直接对 HTML 表格做稳定的 pretty-print；`pdf2md-fix` 读取同一个 `<stem>.md` 进行人工确认和修复。格式化阶段默认输出：

```html
<table>
  <tr>
    <td colspan="2">最大净功率</td>
    <td colspan="2">11.8 Kw / 8500 rpm</td>
  </tr>
</table>
```

格式化规则：

- `<table>`、`<tr>`、`<td>`、`<th>` 独立换行并按层级缩进；
- 保留 `rowspan`、`colspan` 及其他已有属性的值和顺序口径；
- 对单元格文本只做边界空白规范化，不改数字、单位、标点和实体内容；
- 不自动补表头、不自动合并跨页表格、不自动删除空行；这些属于人工语义修复；
- 格式化结果直接作为 `<stem>.md` 的 canonical 内容，保持现有下游入口不变；写入前记录来源 hash，写入后更新当前 Markdown hash 和格式化状态。
- `pdf-merge` 写 Markdown、TOC 后处理和 manifest finalization 必须作为一个原子发布单元；格式化或后处理失败时不生成半成功结果。
- `pdf2md-fix` 的默认输入仍为 manifest 中的 `files.markdown`；当 `formatting.status` 不是 `verified` 时先执行或要求执行格式化，不直接进入内容修复。

格式化验收必须比较格式化前后的逻辑表格：表格数量、行数、单元格文本、`rowspan/colspan`、逻辑行宽和来源页不得发生非预期变化。只允许空白、换行和缩进差异。

## 8192 空列候选恢复

`pdf2md-fix` 的人工修复前置步骤应扫描 `manifest.json`/`page_fallback` 和 `review.md`，筛选以下信号：

```text
excessive_empty_td
excessive_columns
```

对命中页生成候选恢复包：

- 按 PDF 页码调用 PyMuPDF 提取原生文本；
- 保留页级 `words`/bbox 或视觉行信息，便于人工对照布局；
- 同时保留原始 HTML、fallback HTML、页锚点和 segment 来源；
- 输出“候选行”或候选 HTML 模板，明确标记 `needs_human`；
- 不自动决定最终列数、父级关系、`rowspan`/`colspan` 或跨页合并；
- 候选内容必须通过 `manual_fixes.jsonl` 记录后才能进入修复产物。

初版可以实现为 `pdf2md-fix` 的配套 `pdf-table-fix` helper/脚本，先解决“按页提取原文并展示候选”的重复劳动；只有在多个样本证明模板稳定后，才考虑自动填充更多结构。

## 页锚点安全修复

所有内容修复必须先解析并锁定目标页锚点：

- 默认只允许修改 `<!-- pages N-N -->` 对应的页块；
- 跨页表格必须显式声明 `pages: [N, M, ...]` 和 `table_id`；
- 禁止对整个 Markdown 使用无边界 `replace()`；
- 修复前校验目标页、目标块、来源 hash 和预期命中次数；
- 修复后校验页锚点唯一性、目标文本未漂移、内容 hash 和 manifest；
- 目标不唯一或命中次数异常时失败，不进行部分替换。

## 候选输出边界

原始 PDF 和分段文件保持不变；`pdf-merge` 生成 canonical Markdown 后，人工修复还可生成：

```text
<package>/
  <stem>.md                 canonical Markdown（格式化后仍保持同一路径）
  manifest.json             必须同步登记 Markdown 角色、修复状态和派生文件 hash
  data/
    manual_fixes.jsonl      内容/结构修复记录
    logical_tables.jsonl    可选，由 manual_fixes.jsonl 派生的逻辑表格关系
    review_overrides.csv    现有审核状态覆盖，职责不变
```

`logical_tables.jsonl` 不是第二个事实源；没有独立消费者时不生成。

## manifest 同步契约

Markdown 修复不得只修改正文文件。每次生成、替换或发布 Markdown 时，必须在同一变更中更新 `manifest.json`：

- `files.markdown` 始终指向 canonical Markdown；格式化采用原地模式时路径不变，但内容 hash 和 `formatting` 元数据必须更新。
- 增加或维护 `files.manual_fixes`、`files.logical_tables` 等实际存在的派生文件路径。
- 增加 `fixes` 元数据，至少记录 `schema_version`、`status`、`source_manifest_sha256`、`manual_fixes_sha256` 和当前 canonical Markdown 的 `sha256`。
- `fixes.status` 使用 `none`、`pending`、`applied`、`verified`；未完成人工复核不得标记为 `verified`。
- `formatting.status` 使用 `none`、`applied`、`verified`；格式化校验失败时不得进入 `pdf2md-fix` 内容修复阶段。
- `formatting.mode` 固定记录为 `merge_time`；必须保留合并前的 `source_markdown_sha256`，并更新 `files.markdown` 对应的当前内容 hash。
- manifest 引用的每个派生文件都必须存在；hash 不匹配、路径缺失或状态与文件不一致时，`pdf2md-fix` 必须失败并保留原始包。
- `parse_status` 继续表达 PDF 解析状态；人工修复状态使用独立的 `fixes.status`，不得把人工修复伪装成解析成功。

推荐结构：

```json
{
  "files": {
    "markdown": "demo20.md",
    "markdown_sha256": "...",
    "manual_fixes": "data/manual_fixes.jsonl",
    "logical_tables": "data/logical_tables.jsonl"
  },
  "fixes": {
    "schema_version": 1,
    "status": "verified",
    "source_manifest_sha256": "...",
    "manual_fixes_sha256": "...",
    "markdown_sha256": "..."
  },
  "formatting": {
    "schema_version": 1,
    "mode": "merge_time",
    "status": "verified",
    "source_markdown_sha256": "...",
    "formatted_markdown_sha256": "..."
  }
}
```

## 分阶段计划

### 前置步骤：`pdf-merge` 生成可校对的 canonical Markdown

- 在 `pdf-merge` 合并分段并写入 `<stem>.md` 时执行 HTML 表格 pretty-print。
- 在最后一个 Markdown 变更完成后，由统一 finalization 步骤在 `manifest.json` 中登记来源 hash、当前 Markdown hash、`formatting.mode=merge_time` 和 `formatting.status`。
- 对格式化前后的表格做语义保持校验；失败时保留原始输出，不进入 VLM 或人工修复。
- `pdf2md-fix`、人工校对和 VLM 证据记录默认引用 manifest 中的 canonical Markdown。

### 阶段 0：Step 0 证据与契约设计

- 固定自动化、人工确认和入库审核三层边界。
- 固定 VLM 只在人工复核阶段按需运行，输出作为证据而不是最终事实。
- 用 demo20 p14–p16 作为跨页表格基线。
- 明确 `manual_fixes.jsonl`、`manifest.json.fixes` 和可选逻辑表格关系的字段。
- 固定 Markdown 与 `manifest.json` 的同步规则、原始/修复版文件角色和内容 hash 口径。
- 检查与 `review.md`、`review_overrides.csv`、`quick_lookup_draft.csv` 的重复字段，避免多个事实源。

进入阶段 1 的条件：字段契约、状态语义、canonical Markdown 原地更新和回滚规则、manifest 同步规则以及 demo20 验收标准明确。

### 阶段 1：创建 `pdf2md-fix` skill 与人工操作规范

阶段 0 已满足进入条件：字段契约、状态语义、canonical Markdown 原地更新与回滚规则、manifest 同步规则和 demo20 p14–p16 验收标准均已写入本计划；8192 空列问题和 p37/p47/p48 全局 `replace()` 漂移已有实际样本证据。阶段 1 已完成验收，阶段 2 的代码实现和自动应用现已具备进入条件。

- 新增项目级 `skills/pdf2md-fix/SKILL.md`。
- 写明触发条件：`pdf-auto` 已完成且存在 `review.md`、需要人工修复 PDF 转换结果、跨页表格或结构化字段。
- 写明 VLM 使用边界：优先用于跨页表格、图片/OCR、图表标注和结构不明确页面；每次调用必须记录输入页、模型和人工结论。
- 固化人工检查顺序、证据要求、禁止事项、修复记录格式和验收清单。
- 固化“修改 Markdown 必须同步 manifest”的操作门禁、原子替换和失败恢复。
- 固化 HTML 表格 pretty-print 的输出样式、语义保持校验和失败回滚。
- 固化 merge-time 格式化发生在人工修复之前，并成为 `pdf2md-fix` 的必需输入前置条件。
- 明确默认只读检查；只有用户明确要求应用修复时才写入派生产物。
- 同步到 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`，并用 skill 校验工具验证 frontmatter 和命名。

### 阶段 1 验收记录（2026-07-12）

- 项目级 `skills/pdf2md-fix/SKILL.md` 存在，frontmatter 和命名校验通过。
- 用户级 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md` 与项目级文件 `cmp` 一致。
- 已核对并通过：触发条件、VLM 证据边界、人工检查顺序、8192 空列候选恢复、页锚点安全应用、manifest 同步门禁、`manual_fixes.jsonl`、HTML pretty-print、默认只读门禁和 p37/p47/p48 漂移禁止规则。
- 验证命令通过：

  ```bash
  python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pdf2md-fix
  cmp skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md
  python3 scripts/check_plan_governance.py .
  git diff --check
  ```

阶段 1 验收结论：`已完成`。阶段 2 仍只登记为 `待实施`，尚未实现候选扫描器、修复应用器或自动 manifest 写入。

### 阶段 2：修复记录与派生产物应用

#### 阶段 2 准入审计（2026-07-12）

结论：通过“待实施”门禁。阶段 1 的人工操作 skill 已验收，以下公共契约按用户确认的方向冻结：

- `manual_fixes.jsonl` 是人工修复事实源；`logical_tables.jsonl` 只有在存在独立下游消费者时才生成，且只能由 `manual_fixes.jsonl` 派生，不能形成第二个事实源。
- 阶段 2 只处理 canonical Markdown、表格逻辑关系和人工修复记录；`key/value/unit/evidence_text` 等结构化字段修正放到阶段 3，不在阶段 2 生成结构化数据补丁。
- 不新增 `fix_manifest.json`；修复状态、来源 hash、修复记录 hash 和派生文件引用统一登记在现有 `manifest.json` 的 `fixes` 与 `files` 字段中。
- 不生成 `<stem>-fixed.md` 或 `files.fixed_markdown`；canonical `<stem>.md` 继续原地更新，原始 PDF、segments 和格式化前 Markdown hash 保留用于回滚。
- `review_action` 沿用 `pass`、`fix_md`、`rerun`、`fix_data`；其中 `fix_data` 仅作为阶段 3 的预留动作，阶段 2 不执行它。
- 人工修复结果纳入 `manifest.json` 的 `fixes` hash；是否扩展 `PDF_AUTO_JSON=1` 的返回内容属于阶段 3，不阻塞阶段 2。

上述决策已消除输出包结构、下游消费和回滚边界的歧义。VLM 边界、页锚点安全规则、8192 候选恢复方向、manifest 必须同步等事项已有 Step 0 证据；阶段 2 可以开始，但首先必须实现机器校验和失败门禁，再实现候选扫描或修复应用。

- 冻结 `manual_fixes.jsonl` 和 `manifest.json.fixes` 的机器校验规则。
- 新增并验证 8192 空列候选扫描和 PyMuPDF 页级原文提取 helper。
- 固化页锚点安全替换，禁止全局文本替换，并为单页、多页和误命中场景建立回归 fixture。
- 将 VLM 证据引用纳入修复记录校验，确保模型输出不会脱离 PDF 页码和人工结论单独流入下游。
- 增加表格格式化前后逻辑网格一致性校验，避免为了可读性破坏 `rowspan/colspan`。
- 设计幂等应用入口；是否新增 `scripts/pdf-apply-fixes` 取决于阶段 1 的重复人工操作证据。
- 支持跨页表格逻辑关系、字段内容修正和章节归属修正，不覆盖原始 PDF 和分段产物。
- 为修复后的 Markdown、结构化草案和逻辑表格输出建立来源映射。
- 实现或验证 manifest 原子更新、hash 校验、派生文件存在性校验和失败回滚。

#### 阶段 2 验收审计（2026-07-12）

结论：未通过阶段完成验收，当前状态为 `实施中`。

已验证部分：

- `scripts/pdf-check-fixes` 已能校验 `manual_fixes.jsonl` 必填字段和枚举、VLM 证据字段、`manifest.json.fixes`、`formatting`、文件存在性和 hash。
- `scripts/pdf-table-fix` 已能扫描 manifest 中的 `excessive_empty_td`/`excessive_columns`，使用 PyMuPDF 提取页级文本，并输出 `needs_human` 候选。
- `bash tests/test-fix-validate.sh` 通过 17 项，覆盖合法/非法修复记录、hash 不匹配、VLM 证据缺失、空页列表、demo20 候选扫描和无候选包。

未满足项：

- 尚无实际的页锚点安全应用入口；没有对 `<!-- pages N-N -->` 范围内目标块执行替换、拒绝跨页误命中和验证页外 hash 的实现。
- `check_idempotent()` 当前为空扩展点，尚未验证重复应用不会产生重复内容。
- manifest 目前只有校验器，没有“Markdown、`manual_fixes.jsonl`、manifest 原子写入及失败回滚”的应用流程。
- 表格格式化前后的逻辑网格校验目前只在存在备份时产生 warning，尚未成为应用门禁。
- 尚无 p47/p48 三处相同 8192 表字符串的页锚点误命中回归 fixture。
- 现有 demo20 输出包尚未包含 `data/manual_fixes.jsonl`、`manifest.fixes` 和 `formatting`，直接运行 `scripts/pdf-check-fixes pdf/demo20` 会按预期失败；尚未完成真实样本包的端到端修复验收。

因此，阶段 2 仍需继续实现安全应用器、原子 manifest 更新、幂等校验和 p47/p48 回归 fixture，完成后再进行阶段验收。

#### 阶段 2 补完实施（2026-07-12）

针对未满足项按顺序实施：

1. **`scripts/pdf-apply-fixes` — 页锚点安全修复应用器**（+x, Python 脚本，195 行）
   - 读取 `data/manual_fixes.jsonl` 中 `status=applied` 的修复记录
   - 对每条记录锁定 `<!-- pages N-N -->` 页锚点，在页块范围内执行替换
   - 前置校验：页锚点唯一性、before 文本在目标页块内的存在性
   - 后置校验：页锚点唯一性、页块前内容不变、页块后内容不变（用新的 `new_suffix_start` 防止替换后长度漂移导致的切片错误）
   - 页块外内容校验使用字符串直接比较（非 hash），避免长度变更后 `block_end` 偏移
   - 幂等跳过：before 已不存在（已被替换）且 after 已存在时静默跳过
   - 应用前校验当前 Markdown hash == manifest 记录的 `fixes.markdown_sha256`
   - 应用前备份到 `data/pre_fix_<hash[:16]>.md`
   - 应用后同步更新 manifest：`markdown_sha256`、`manual_fixes_sha256`、`fixes.status=applied`
   - 支持 `--dry-run`预览模式
   - 退出码：0 = 全部成功或幂等跳过，1 = 部分或全部失败

2. **`check_table_consistency` 升级为门禁**（`pdf-check-fixes` 修改）
   - 函数返回值从 `list[str]`（warnings）改为 `list[str]`（errors）
   - 备份存在时，表格结构不一致直接导致 exit 1
   - 移除 `pre_fix_` 备份路径（格式化校验只查 `pre_format_md_` 和 `-pre-format.md`，新防止修复后误报）
   - 新增 `pre_format_md_` 查找时也判断 `pre_fix_` 备份——页块外 hash 验证也合并到 `pdf-apply-fixes`

3. **`check_idempotent()` 完整实现**（`pdf-check-fixes` 修改）
   - 仅对 `fixes.status ∈ {applied, verified}` 的包执行
   - 校验 manifest 记录的 `markdown_sha256` 与当前文件一致
   - 逐条扫描 `status=applied` 的修复记录，在目标页块中：
     - before 仍存在且 after 不存在 → 错误（修复未应用）
     - before 和 after 同时存在 → 错误（可能重复应用或部分覆盖）
     - before 不存在且 after 存在 → 正确（已幂等应用）

4. **回归测试扩展**（`tests/test-fix-validate.sh`，7 个新测试用例，共 34 项）
   - A1: `pdf-apply-fixes` 简单修复应用 → 成功，MD 更新
   - A2: 幂等跳过 → 重复应用返回 0，提示幂等跳过
   - A3: before 不存在 → 返回 1，提示未找到
   - A4: p47/p48 同字符串误命中保护 → 修复后 p48 的 `SAME_TEXT` 计数仍为 1
   - A5: `check_idempotent` 通过（已正确应用的包） → 校验通过
   - A6: `check_idempotent` 检测未应用的修复 → 返回 1，包含幂等性错误
   - A7: 页锚点不存在 → 返回 1，包含锚点未找到

**补完后测试结果**：34/34 通过，覆盖全部 6 项未满足项。

**修复的关键 bug**：
- 页外 hash 校验中的长度漂移：`new_md[block_end:]` 在替换后长度变化时指向错误位置。改为直接用字符串前缀/后缀比较，后缀位置用 `block_start + len(new_block)` 计算。

**剩余未完成（非阻塞）**：
- demo20 输出包尚未包含 `data/manual_fixes.jsonl` 和 `manifest.fixes`（这属于真实样本迁移，不是代码缺失）
- `pdf-apply-fixes` 目前只处理 `status=applied` 的记录；`proposed`→`applied` 的状态推进由 skill 操作流程处理

### 阶段 3：结构化数据与入库审核衔接

- 让人工修复后的字段能进入结构化草案，但保留原始值、修正值、证据和修复 ID。
- 明确修正后 `record_id` 的稳定策略，避免人工修正导致无法追溯或重复记录。
- 保持 `review_overrides.csv` 只处理审核状态；内容修正不得伪装成状态覆盖。
- 验证冲突解除、`approved/ready` 门禁和导出批次均不会绕过人工确认。

### 阶段 4：真实样本扩展与收敛

- 用 demo20 跨页表格、图片/稀疏页、目录歧义页和春风 150AURA 冲突样本复核流程。
- 用至少一个跨页表格和一个图片/OCR 页面验证 VLM 证据记录、人工采纳和拒绝路径。
- 用 p37/p47/p48/p50 或等价 8192 空列样本验证候选恢复；用 p47/p48 误命中复现验证页锚点保护。
- 统计哪些人工动作重复出现，再决定是否自动化候选生成或批量应用。
- 不因单个样本把业务字段、表格名称或车型规则硬编码到通用流程中。

## 阶段验证方式

### 文档与 skill 验证

```bash
test -f skills/pdf2md-fix/SKILL.md
python3 /Users/jafish/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/pdf2md-fix
cmp skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md
```

如果 `quick_validate.py` 的实际路径或参数与当前 skill 包不同，以该 skill 的工具说明为准，并在验收记录中记录实际命令。

### demo20 人工复核验收

- 能从 `review.md` 定位第 14、15、16 页。
- `pdf-merge` 完成后直接得到可校对的 canonical Markdown，且 manifest 已登记来源 hash、当前 Markdown hash 和格式化状态。
- 能确认三页属于一个逻辑表格，而不是仅凭相邻页码猜测。
- 修复版 Markdown 中的 HTML 表格按 `<table>/<tr>/<td>` 分层换行，便于人工逐行校对。
- 格式化前后表格数量、行数、单元格文本、`rowspan/colspan` 和逻辑行宽一致。
- 修复记录包含 `table_id`、页段、start/middle/end 角色、逻辑列数和证据说明。
- 如使用 VLM，修复记录包含模型、输入页/区域、输出引用和人工采纳或拒绝结论。
- 8192 空列页的修复记录包含原始页文本候选、目标页锚点、人工选定的结构模板和最终状态。
- `demo20.md` 保持 canonical 路径；格式化前后 hash、格式化状态和修复状态均已同步写入 `manifest.json`，原始 `segments/` 未被覆盖。
- 修改 `demo20.md` 时，`manifest.json` 必须同步登记 canonical 文件 hash、修复状态和 `manual_fixes.jsonl` hash；不生成 `demo20-fixed.md`。
- 删除、改名或篡改 manifest 引用文件时，流程会失败而不会生成部分成功结果。
- 修复后的下游记录能保留原始页码、行号/块号和修复 ID。
- 重复应用相同修复不会重复生成表格行或重复注释。

### 入库边界验收

- 未有 `review_overrides.csv` 时，不产生 `approved/ready` 记录。
- 只修改内容修复记录，不会自动改变审核状态。
- 冲突未解决或证据缺失时仍保持 `not_ready`。
- `pdf-export-ingest` 只导出既有 `approved + ready` 记录。

### 治理验证

```bash
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```

代码实施阶段，修改函数、类或方法前必须运行 GitNexus `impact`；提交前必须运行 `detect_changes()`。本阶段仅修改治理文档，不触发代码符号影响分析。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 人工把猜测写成事实 | 强制页码、证据和状态字段；不确定则 `needs_review` | 删除派生修复产物，保留原始包 |
| VLM 幻觉或视觉误读 | VLM 只生成候选证据；人工必须回看 PDF 原页，关键数字需原生文本或视觉双重核对 | 标记 VLM 证据为 rejected，保留人工复核记录 |
| VLM 输出与当前 PDF 页面/裁剪区域脱节 | 记录输入 PDF hash、页码、裁剪区域、模型和输出文件 | 删除无来源 VLM 结果，不影响原始转换包 |
| 全局替换造成跨页内容漂移 | 强制页锚点、命中次数和来源 hash 校验 | 失败即恢复原始 Markdown，不接受部分替换 |
| 纯文本候选被误当成最终表格 | 候选明确标记 `needs_human`，不自动推断行列结构 | 删除候选修复产物，保留原始 HTML 和 PDF 证据 |
| 修复内容与原始表格失去对应 | 保存 source refs、before/after 和 fix_id | 根据原始 hash 重新生成派生文件 |
| `table_id` 与现有 `html_table:N` 混淆 | 明确逻辑表 ID 与来源块 ID 分离 | 下游回退到原始来源块读取 |
| 人工修正改变 record_id 导致审核覆盖失效 | 在阶段 3 固定修正后的 ID/映射策略 | 保留旧记录映射和未放行状态 |
| 新 skill 与项目级 `pdf2md` 事实源漂移 | 涉及公共输出契约时先更新项目 skill，再同步用户级 skill | 在风险清单记录未同步项，不宣称完成 |
| 修复后的 canonical Markdown 被旧消费者误认为未修复内容 | 通过 `manifest.fixes.status` 和 hash 明确修复状态，原始 segments 与格式化前 hash 保持可回溯 | 将 `fixes.status` 回退为 `pending`，从原始 hash 重新生成 canonical Markdown |
| Markdown 与 manifest 不同步 | 将文件路径、hash 和修复状态作为一个原子发布单元校验 | 回滚整组派生文件，不接受只有正文或只有 manifest 的部分更新 |

## 已冻结决策与后续边界

- `manual_fixes.jsonl` 是人工修复事实源；`logical_tables.jsonl` 仅在有独立消费者时作为派生视图生成。
- 阶段 2 不生成结构化字段补丁；`key/value/unit/evidence_text` 修正进入阶段 3。
- `fix_md`、`fix_data`、`rerun` 沿用现有动作枚举；阶段 2 不执行 `fix_data`。
- 不生成 `fixed.md`；canonical `<stem>.md` 原地更新，修复状态与 hash 写入 `manifest.json`。
- `PDF_AUTO_JSON=1` 是否返回人工修复摘要留到阶段 3；阶段 2 只保证输出包中的 `manifest.json` 一致。
- 项目级 `pdf2md-fix` skill 是事实源，并同步到 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`。

## 当前完成条件

阶段 0 完成前不得实施代码或自动应用修复。阶段 0 的完成条件：

- 本计划已登记到 `docs/PLAN_MAP.md`，阶段 2 准入审计已通过，但阶段 2 完成验收未通过，当前状态为 `实施中`。
- Step 0 证据、范围、非目标、人工边界、修复记录候选契约和验证方式已写入本计划。
- 8192 空列候选恢复、页锚点安全修复和 VLM 文字证据边界已写入本计划。
- 与 `minimal-automation-runbook`、`table-text-omission-detection`、`structured-data-extraction`、`data-ingestion-pipeline` 的职责边界已明确。
- 无新的公共 CLI、MCP 或数据库契约被未审议地引入。
- `python3 scripts/check_plan_governance.py .` 通过。

阶段 0 完成证据：2026-07-12 已读取 `demo20`、`demo60`、`demo5` 的现有 manifest，确认 8192/16311 空单元格异常页；核对 demo20 p14–p16 和 demo60 p37/p47/p48/p50 的页锚点唯一性；根据人工复盘确认 p37/p47/p48 全局 `replace()` 的三处误命中机制。上述证据已记录在“Step 0 实测补充”中。阶段 1 已完成验收，阶段 2 准入契约已按“已冻结决策与后续边界”收敛。
