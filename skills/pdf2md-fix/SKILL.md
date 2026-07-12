---
name: pdf2md-fix
description: Use when pdf-auto 已完成且存在 review.md、需要人工复核和修复 PDF 转换结果、处理跨页表格逻辑连续性、修复 8192 空列/异常列数表格、修正字段遗漏/章节归属/结构语义、按页锚点边界执行安全内容修复、使用 VLM 辅助视觉证据确认、生成 manual_fixes.jsonl 修复记录并同步 manifest。
---

# pdf2md-fix — 人工复核与内容修复

本 skill 是 Claude Code 项目级 `pdf2md-fix` skill 的事实源，定义 `pdf-auto` 完成后的人工复核与内容修复工作流。

## 同步目标

```text
/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md
```

同步方式：

```bash
mkdir -p /Users/jafish/.claude/skills/pdf2md-fix
cp skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md
```

涉及修复记录契约、VLM 辅助边界、manifest 同步规则和页锚点安全修复规则的更新，必须先更新本文件，再同步到用户级 skill。

## 详细计划

本 skill 的实施细节事实源位于 `docs/plans/pdf2md-fix-manual-workflow.md`，包含完整的字段方案、Schema、枚举、验收标准、风险与回滚。本 skill 只记录操作流程，不重复 plan 中的字段级方案。引用格式为 `[plan](docs/plans/pdf2md-fix-manual-workflow.md#<section>)`。

## 触发条件

`pdf2md-fix` 位于 `pdf-auto` 完整结束之后、结构化抽取之前：

```text
pdf-seg（必要时）
  → pdf-auto（含表格 pretty-print、TOC 修复、review.md、manifest finalization）
  → pdf2md-fix
      ├─ 读取 canonical Markdown、review.md、manifest 和 segments
      ├─ 按需调用 VLM（仅作视觉证据）
      ├─ 人工确认和修复内容/表格语义
      └─ 同步 manifest
  → pdf-extract-data
  → pdf-prepare-ingest
  → pdf-export-ingest
```

### 介入决策

| 状态 | 动作 |
|---|---|
| `pass` | 不进入修复，直接继续结构化抽取 |
| `fix_md` 或跨页表格/字段语义问题 | 进入修复流程，修复后再抽取 |
| `rerun` | 回到 `pdf-rerun`/`pdf-auto` 解析修复路径，不由本 skill 伪装成内容修复 |
| 格式化未完成 | 先执行或要求执行表格 pretty-print，再进入内容修复 |

本 skill 不介入 MinerU 请求、页级 fallback、`pdf-merge` 内部或 TOC 修复中间步骤。

## 前置条件

- `pdf-auto` 已完成，输出包中包含：
  - `manifest.json`（含 `formatting.status`）
  - Canonical Markdown（已执行 HTML 表格 pretty-print）
  - `review.md`
  - `segments/`
- `formatting.status` 必须为 `verified` 或 `applied`；否则先执行格式化。
- 原始 PDF、原始分段和格式化前 Markdown hash 已保留。
- `pdf2md` 和 `pdf2md-fix` 技能均已可用。

阶段边界：阶段 2 只修复 canonical Markdown、表格逻辑关系和人工修复记录；不生成 `key/value/unit/evidence_text` 等结构化字段补丁。结构化字段修正由阶段 3 处理，`fix_data` 在阶段 2 只作为预留动作，不执行。

## 核心工作流

### 1. 读取并评估

```bash
# 读取包状态
cat <package>/manifest.json

# 查看复核清单
cat <package>/review.md

# 查看 canonical Markdown
cat <package>/<stem>.md | head -200

# 查看段边界结构（所有页锚点及行号）
grep -n '^<!-- pages' <package>/<stem>.md
```

### 2. 扫描可修复问题

从 `manifest.json` 和 `review.md` 筛选信号：

| 信号 | 含义 | 建议处理 |
|---|---|---|
| `excessive_empty_td` | 空单元格过多（如 8192） | 候选恢复 → PyMuPDF 提取页级原文 → 人工重建表格 |
| `excessive_columns` | 列数异常 | 同上 |
| `native_table_text_missing` | 原生文字缺失 | 确认缺失字段，人工填充 |
| `toc_unassigned` | 目录条目归属不明确 | 人工确认物理目录页 |
| **表格跨页** | 相邻页码各有一个 `<table>` | 确认是否同一逻辑表，记录 `table_id` |
| `needs_review` | 人工复核 | 按 review.md 逐项判断 |
| 字段异常/冲突 | 结构化草案异常 | 人工修正 key/value/unit |

### 3. 8192 空列候选恢复（高频场景）

1. 运行 `scripts/pdf-table-fix <package>` 扫描候选页，输出到 `data/table_candidates.jsonl`。
2. 读取候选页的原生文本片段和信号摘要。
3. 使用 PyMuPDF 或类似工具按页提取 PDF 原生文本（`pdf-table-fix` 已包含该步骤的输出）。
4. 保留原始 HTML、fallback HTML（如有）、页锚点和 segment 来源。
5. 输出"候选行"或候选 HTML 模板，明确标记 `needs_human`。
6. **人工**对照 PDF 原页确认最终列数、标题行、跨页连续性。
7. 不自动决定最终行列结构、rowspan/colspan。
8. 修复必须通过 `manual_fixes.jsonl` 记录后方可应用。

### 4. 跨页表格逻辑确认

当多个连续页各含一个 `<table>`，且视觉/语义上是同一张表：

1. 使用 `pdf-read-page` 逐页读取。
2. 对照 PDF 原页确认表头、列语义、连续行范围。
3. 记录 `table_id`、`page_start`、`page_end`、各页角色（start/middle/end）。
4. 逻辑列数记录在 `manual_fixes.jsonl` 中，不要求物理拼表。
5. 下游结构化抽取使用 `table_id` 关联；只有存在独立消费者时才生成由 `manual_fixes.jsonl` 派生的 `logical_tables.jsonl`。

### 5. 人工检查顺序

1. **表格页**（review_only）：检查列语义、表头、跨页连续性和 rowspan/colspan。
2. **8192 空列页**：PyMuPDF 提取原文 → 人工重建表格 → 记录候选 → 应用修复。
3. **字段遗漏/覆盖率低页**：对照 PDF 原页，确认缺失字段和可能原因。
4. **目录归属**（toc_unassigned）：确认条目物理目录页。
5. **冲突事实**（冲突检测列表）：判断是否真实矛盾。
6. **VLM 证据**（如已调用）：对照 PDF 原页确认关键数字和关系。
7. **最终审核状态**：确定 approved/rejected/needs_review。

### 6. 应用修复（仅限明确要求时）

**默认只读检查**——只有用户明确要求应用修复时才写入派生产物。

修复应用步骤：

1. 锁定目标页锚点 `<!-- pages N-N -->`。
2. 校验目标页锚点唯一性、目标内容 hash 和预期命中次数。
3. 在锚点范围内执行替换——禁止全局无边界替换。
4. 修复后校验页锚点唯一性、目标文本一致性和内容 hash。
5. 同步更新 `manifest.json`（文件角色、hash、修复状态）。
6. 记录到 `manual_fixes.jsonl`。

## VLM 使用边界

VLM 只生成候选证据，不直接产生最终事实或审核结论。

### 适用场景（优先）

- 跨页表格视觉连续性确认。
- 图片/扫描页关键文字提取。
- 图表标注解读。
- 结构不明确页面的纹理/布局辅助判断。

### 不适用场景

- 表格行列、rowspan/colspan 结构判断（VLM 不可靠）。
- 自动推断最终事实或审核结论。
- 替代 PDF 原页的人工对照。

### 每次调用必须记录

| 字段 | 说明 |
|---|---|
| `model` | 使用的 VLM 模型（如 qwen3-vl-8b） |
| `input_pages` | 输入 PDF 页码 |
| `crop_area` | 裁剪区域（如适用） |
| `output_file` | VLM 输出文件路径 |
| `human_conclusion` | 人工采纳/拒绝结论 |

关键数字和声明必须有 PDF 原生文本或视觉双重核对，VLM 输出不能作为唯一来源。

## HTML 表格 pretty-print 格式

`pdf-merge` 在 canonical Markdown 生成阶段已执行。格式化规则：

```html
<table>
  <tr>
    <td colspan="2">最大净功率</td>
    <td colspan="2">11.8 Kw / 8500 rpm</td>
  </tr>
</table>
```

强制规则：

- `<table>`、`<tr>`、`<td>`、`<th>` 独立换行并按层级缩进。
- 保留 `rowspan`、`colspan` 及其他已有属性的值和顺序口径。
- 只做边界空白规范化，不改数字、单位、标点和实体内容。
- 不自动补表头、不自动合并跨页表格、不自动删除空行——这些属于人工语义修复。

验收标准：格式化前后表格数量、行数、单元格文本、rowspan/colspan 和逻辑行宽必须一致。

## manifest 同步门禁

每次生成、替换或发布 Markdown 时，必须在同一变更中更新 `manifest.json`：

- `files.markdown` 始终指向 canonical Markdown。
- `files.markdown` 始终指向原地更新后的 canonical Markdown；不生成 `fixed.md` 或 `files.fixed_markdown`。
- 增加/维护 `files.manual_fixes`；只有存在独立消费者时才登记由其派生的 `files.logical_tables`。
- `fixes` 元数据必须包含 `schema_version`、`status`、`source_manifest_sha256` 和 `manual_fixes_sha256`。
- 当前 canonical Markdown 的 hash 必须登记在 `files.markdown_sha256` 和 `fixes.markdown_sha256`。
- `fixes.status`：`none` → `pending` → `applied` → `verified`。
- `formatting.status`：`none` → `applied` → `verified`。
- manifest 引用的每个派生文件都必须存在；hash 不匹配时 `pdf2md-fix` 必须失败。
- 不得把人工修复状态伪装成 `parse_status`。

## 修复记录格式

修复记录写入 `data/manual_fixes.jsonl`，每行 JSON：

| 字段 | 说明 |
|---|---|
| `fix_id` | 稳定修复 ID |
| `fix_type` | `rebuild_table` / `fix_header` / `fill_content` / `cross_page_table` / `table_layout` / `missing_text` / `section_attribution` / `field_correction` / `image_ocr` |
| `review_action` | `pass` / `fix_md` / `rerun` / `fix_data`（`fix_data` 阶段 3 预留） |
| `status` | `proposed` / `applied` / `verified` / `rejected` |
| `pages` | 相关 PDF 页码列表 |
| `source_refs` | segment、block_id、Markdown 行引用 |
| `before` | 修复前摘要 |
| `after` | 修复后摘要或规范化结果 |
| `evidence` | 原 PDF 页、原生文本、截图/视觉检查说明 |
| `vlm_evidence` | 可选：VLM 模型、输入页、输出引用和人工采纳说明 |
| `operator_note` | 人工判断和保留意见 |

详见 [plan: 候选修复记录契约](docs/plans/pdf2md-fix-manual-workflow.md#候选修复记录契约)。

## 禁止事项

- ❌ 不使用页锚点的全局 `replace()`；p37/p47/p48 曾因全局替换命中三页。
- ❌ 不自动推断最终行列、rowspan/colspan 或跨页合并结构。
- ❌ 不把 VLM 输出作为最终事实——必须人工对照 PDF 原页。
- ❌ 不把人工修复伪装成 `parse_status` 或 `approved`。
- ❌ 不修改原始 PDF、原始 `segments/` 和原始 `content_list.json`。
- ❌ 不在只读检查中自动写入任何派生文件。
- ❌ 不覆盖 `review_overrides.csv` 的审核状态职责（它只处理 `record_id,review_status,notes`）。
- ❌ 修复不幂等时不允许应用——第二遍不能产生重复行/重复表。
- ❌ 不把排版优化、无来源的文字润色当作事实修复。

## 验收清单

完成修复后验证：

- [ ] `manual_fixes.jsonl` 中所有 `applied` 记录都已人工确认。
- [ ] 修复后的 Markdown 页锚点唯一，目标块 hash 未漂移。
- [ ] 格式化前后表格结构（数量、行数、单元格、rowspan/colspan）一致。
- [ ] `manifest.json` 已同步：文件角色、hash、修复状态、版本号。
- [ ] manifest 引用的每个派生文件都存在且 hash 匹配。
- [ ] 跨页表格的 `table_id`、页段角色和逻辑列数已记录。
- [ ] VLM 证据（如使用）已记录模型、输入页和人工结论。
- [ ] 原始 PDF、原始段和格式化前 Markdown hash 未覆盖。
- [ ] 重复应用相同修复不会产生重复内容。
- [ ] 人工内容修正未改变 `review_overrides.csv` 的审核状态。
- [ ] 冲突未解决或证据缺失时仍保持 `not_ready`。
- [ ] 修复前后内容 hash 已记入 manifest。
- [ ] 无 `approved`/`ready` 记录在 `review_overrides.csv` 未设置时自动产生。
- [ ] `scripts/pdf-check-fixes <package>` 校验通过（exit 0）。
- [ ] 应用修复时使用 `scripts/pdf-apply-fixes <package>`（含 `--dry-run` 预览）。
- [ ] `scripts/pdf-apply-fixes` 不会因页块替换后长度变化产生页外内容误报。
- [ ] 重复运行 `pdf-apply-fixes` 幂等跳过，不重复修改内容。
- [ ] `data/table_candidates.jsonl`（如存在）中的候选标记为 `needs_human`。

## 排障

| 症状 | 处理 |
|---|---|
| `formatting.status` 不是 `verified` | 先执行或要求执行 HTML 表格 pretty-print |
| `pdf-check-fixes` 返回非零 | 查看 stderr 的具体错误：`manual_fixes.jsonl` 格式、manifest 块 hash 或不匹配的派生路径 |
| `pdf-table-fix` 无输出 | 确认 `manifest.json.page_fallback` 中 `quality_signals` 包含 `excessive_empty_td`/`excessive_columns` |
| `pdf-apply-fixes` 返回 1 | 查看 stderr：before 未找到（检查 `pages` 和目标页块）、页块外内容变化（检查 `before` 是否越界）、当前 MD hash 与 manifest 不一致（先运行 `pdf-check-fixes`） |
| 页面锚点不唯一 | 修复必须失败，保留原始 Markdown |
| 修复后页块 hash 不匹配 | 修复应用未命中目标；检查页锚点范围 |
| `manifest.json` 引用路径不存在 | 修复后手动校验所有派生文件存在性 |
| 同一页面有多条修复记录 | 校验 `fix_id` 和 `status`，避免冲突操作 |
| VLM 结果与 PDF 页面对不上 | 检查 VLM 的输入页码和裁剪区域记录 |
| 人工修正后 `review_overrides.csv` 被覆盖 | `review_overrides.csv` 只处理审核状态；内容修正独立记录 |

## 风险与回滚原则

详见 [plan: 风险与回滚](docs/plans/pdf2md-fix-manual-workflow.md#风险与回滚)。关键原则：

- **页锚点保护**：所有修复失败即恢复原始 Markdown，不接受部分替换。
- **VLM 幻觉控制**：VLM 无最终事实权，标记 rejected 即可回滚。
- **manifest 原子性**：回滚 canonical Markdown、`manual_fixes.jsonl` 和 manifest 的整组变更，不接受只有正文或只有 manifest 的部分更新。
- **`table_id` 混淆**：下游回退到原始来源块读取。
