# 计划：pdf-merge 表格可读性格式化落地

## 计划状态

- 状态：实施中
- 当前阶段：阶段 1：实现纯格式化器 ✅ 已完成
- 最后更新：2026-07-12

本文档是“表格 pretty-print 真正落地”专项计划的实施细节事实源。它承接已完成的 [pdf2md-fix 人工复核与内容修复工作流](pdf2md-fix-manual-workflow.md)，只解决“设计声明存在、实际 `pdf-merge` 未执行格式化”的实现漂移，不重新打开人工修复、VLM 或目录语义范围。

## 背景与 Step 0 证据

此前计划规定：表格格式化应在 merge-time 发生，格式化后的 canonical `<stem>.md` 直接作为人工校对输入，并由 manifest 记录格式化状态。但 2026-07-12 的真实复核发现该行为尚未实现：

- `scripts/pdf-merge` 当前只选择分段/fallback、拼接页锚点和收集图片，最终直接执行 `output.write_text(...)`，不存在 HTML table pretty-print 调用。
- `pdf/春风250Sr/春风250Sr.md` 当前包含 87 个 `<table>`、373 个 `<tr>`、25628 个 `<td>`，87 个 `<table>` 均为单行紧凑输出；`<table>` 后紧接换行的数量为 0。
- `pdf/春风250Sr/manifest.json` 的 `formatting.status` 虽为 `verified`，但实际 Markdown 仍未格式化，说明当前状态字段可能只是历史产物声明，不能作为验收证据。
- `pdf-auto` 的实际路径为：
  - `merge`：`pdf-merge` → `toc_repair.repair_merged` → review → manifest 更新；
  - `needs_review`：段级 TOC 修复 → `pdf-merge` → `toc_repair.repair_merged` → review → manifest 更新；
  - `pdf-rerun`：直接调用 `pdf-merge`。

上述基线是本计划的失败复现和回归 fixture。实施前不得用“manifest 已有 formatting 块”替代真实格式化证据。

## 目标

- 在所有合并入口中真正执行 HTML 表格 pretty-print。
- 保持 canonical `<stem>.md` 路径不变，不生成 `*-formatted.md` 或其他第二正文入口。
- 只改变表格标签的换行和缩进，不改变表格数量、行数、单元格文本、标签属性、`rowspan`、`colspan`、图片引用或实体内容。
- 使格式化幂等：重复执行不会继续增加空行或改变 hash。
- 将格式化前备份、格式化后 hash 和状态写入 manifest，并让 `pdf-check-fixes` 能实际验证前后结构一致。
- 覆盖 `pdf-auto` 的通过/需复核路径和 `pdf-rerun` 直接合并路径。

## 非目标

- 不把 HTML 表格转换成 Markdown 管道表格。
- 不自动补表头、猜测列数、合并跨页表格或修复业务内容。
- 不修改 `rowspan`、`colspan`、标签属性顺序或单元格内部语义。
- 不修改 MinerU 主解析、fallback 选择、TOC 语义归属或 VLM 边界。
- 不在本计划中处理 `toc.md`/`toc_tree.json` 的目录语义修复；目录产物契约沿用已同步的 `pdf2md`/`pdf2md-fix` skill。

## 冻结的格式化契约

### 输入与输出

- 输入：最终选择的分段 Markdown，以及所有后续会修改 Markdown 的 TOC 后处理结果。
- 输出：原地更新 canonical `<stem>.md`。
- 只处理真实 HTML `<table>...</table>` 块；无法完整解析、标签不闭合或发现嵌套结构超出支持范围时，整次最终化失败，不写入半格式化文件。

### 输出样式

```html
<table>
  <tr>
    <td colspan="2">字段</td>
    <td>值</td>
  </tr>
</table>
```

- `<table>`、`<tr>`、`<td>`、`<th>` 的结构标签按层级换行和缩进。
- 单元格内部文字默认保持原始内容；不对文本做 trim、实体解码、数字或单位规范化。
- 标签属性及其原始值必须保留；图片、公式、嵌套 inline HTML 必须保持语义和引用不变。
- 对代码块、普通文本中的伪标签和不完整 HTML 不做猜测性格式化。

### 失败策略

- 格式化器必须先在内存中生成完整结果，再一次性写入临时文件并原子替换 canonical Markdown。
- 任一表格结构校验失败时，保留原 Markdown，manifest 不得标记 `verified`。
- 格式化前 Markdown 保存为 `data/pre_format_md_<source_hash[:16]>.md`，供结构一致性和回滚校验使用。

## Manifest 契约

格式化后的 manifest 至少包含：

```json
{
  "files": {
    "markdown": "<stem>.md"
  },
  "formatting": {
    "schema_version": 1,
    "mode": "merge_time",
    "status": "verified",
    "source_markdown_sha256": "<格式化前 hash>",
    "formatted_markdown_sha256": "<格式化后 hash>"
  },
  "fixes": {
    "markdown_sha256": "<格式化后 hash>"
  }
}
```

- `source_markdown_sha256` 必须能在 `data/pre_format_md_<hash[:16]>.md` 找到同 hash 备份。
- `formatted_markdown_sha256`、`fixes.markdown_sha256` 和当前 canonical Markdown hash 必须一致。
- `formatting.status=verified` 只有在表格结构前后比较通过后才能写入。
- 不改变 `files.markdown` 的 canonical 路径；不引入 `files.formatted_markdown`。

## 分阶段计划

### 阶段 0：失败基线与契约冻结

状态：设计中。

工作项：

1. 固定春风250Sr 87 个单行表格作为最小真实 fixture。
2. 明确格式化前后结构比较字段：表格数、行数、列数、单元格文本、属性、`rowspan/colspan`、图片引用。
3. 明确 malformed HTML、嵌套 inline HTML、代码块和空表格的失败策略。
4. 确认共享最终化调用点，避免只修 `pdf-auto` 而遗漏 `pdf-rerun`。

准入条件：本节契约、Step 0 证据和可运行的失败复现 fixture 已提交；未满足前不改生产脚本。

#### 阶段 0 准入验收（2026-07-12）

结论：达到阶段 1 的 `待实施` 标准。

`pdf/春风250Sr/` 作为持久化真实 fixture，使用以下只读检查复现当前缺陷：

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('pdf/春风250Sr/春风250Sr.md')
t = p.read_text(encoding='utf-8')
print('tables=', t.count('<table>'))
print('multiline_table_open=', sum(x.startswith('\\n') for x in t.split('<table>')[1:]))
PY
```

当前输出为 `tables=87`、`multiline_table_open=0`；manifest 的 `formatting.status=verified` 与该实际结果不一致。该真实包同时保留原始分段、manifest 和格式化前备份，可在阶段 1–4 复用，不需要新增故意失败的常规回归测试。

阶段 1 已具备：目标、范围、非目标、格式化契约、失败策略、验证命令、完成条件、回滚方式和真实失败 fixture；可以开始实现，但本次推进不代表代码已经修改。

### 阶段 1：实现纯格式化器 ✅ 已完成

实施产物：
- `scripts/lib/markdown_table_formatter.py`（317 行）
- `tests/test_markdown_table_formatter.py`（26 个测试）

完成证据（2026-07-12）：

1. **春风250Sr 真实 fixture**：87 个表格全部多行输出，`multiline_table_open=87`（格式化前为 0）。
2. **结构校验**：`validate_structure` 返回 0 错误——表格数量、标签数量（`<table>`、`<tr>`、`<td>`、`<th>`）前后一致。
3. **表格外区域**：88 个非表格文本块逐块比对 0 不一致。
4. **幂等性**：`is_idempotent` 连续两次 `format_tables` 输出一致，`format_tables(result) == result`。
5. **图片**：11 张图片全部保留，引用不变。
6. **malformed HTML**：缺失 `</table>` / `</tr>` / `</td>` 及标签错配均抛出 `TableFormatError`。
7. **单元测试**：26/26 通过（含 4 个真实 fixture 测试）。

```bash
$ python3 -m pytest tests/test_markdown_table_formatter.py -v
============================== 26 passed in 0.20s ==============================
```

格式输出样板（p13 参数表）：

```html
<table>
  <tr>
    <td></td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td colspan="3">性能</td>
  </tr>
  ...
</table>
```

已确认的边界覆盖：空 td、colspan、rowspan、rowspan+colspan 复合、`<th>` 标签、`<img>` 单元格、多表格文脉、中文字形、特殊符号（N·m、Kw/rpm）。

工作项：

1. ✅ 实现保留原始标签和单元格内容的 token/结构格式化器。
2. ✅ 支持普通表格、`rowspan`/`colspan`、嵌套图片/inline HTML 和空单元格。
3. ✅ 实现幂等性和 malformed HTML 失败回滚。
4. ✅ 增加最小单元测试和春风250Sr 代表性表格 fixture。

### 阶段 2：接入合并与最终化链路

候选文件：`scripts/pdf-merge`、`scripts/pdf-auto`、`scripts/pdf-rerun`、`scripts/pdf-check-fixes` 或共享 manifest helper。

工作项：

1. 在 Markdown 最后一次内容修改之后调用格式化器；`toc_repair.repair_merged` 后必须再次确保格式化状态成立。
2. 覆盖 `pdf-auto` 的 `merge`、`needs_review` 和 `pdf-rerun` 入口。
3. 写入格式化前备份、manifest hash 和 `formatting` 块。
4. 将 `pdf-check-fixes` 从“只检查 formatting 字段存在”提升为“检查备份、后 hash 和表格结构一致”。
5. 保持全流程原子写入和失败回滚。

完成条件：新建临时包可通过三个入口生成格式化 Markdown；失败时原文件和 manifest 均保持不变。

### 阶段 3：真实样本回填与兼容验证

工作项：

1. 在临时副本上回填 `pdf/春风250Sr/`、`pdf/demo20/`、`pdf/demo60/`，验证不生成第二正文入口。
2. 对已有 `formatting.status=verified` 但实际未格式化的包重新计算状态；不能继续保留虚假的 verified。
3. 验证后续 `pdf2md-fix`、`pdf-extract-data`、`pdf-prepare-ingest` 仍读取同一路径且结构结果不漂移。
4. 补齐目录三件套契约的 manifest 登记检查，但不修改原始 `segments/**/content_list*.json`。

完成条件：三个真实样本格式化结果可读、结构等价、manifest 可验证，现有下游测试无回归。

### 阶段 4：独立验收与收口

验收至少包括：

- 春风250Sr：87 个表格全部多行输出，表格结构和单元格文本前后一致；
- demo20/demo60：覆盖普通表格、跨页表格、8192 fallback 表格和图片单元格；
- 三条入口：`pdf-auto` 通过路径、`pdf-auto` needs_review 路径、`pdf-rerun`；
- 幂等性：第二次执行不改变 Markdown 和 manifest hash；
- 失败回滚： malformed HTML 或一致性失败不产生半成品；
- 回归：`bash tests/test-fix-validate.sh`、`pytest -q`、三个真实包 `scripts/pdf-check-fixes`、治理检查和 drift 检查。

## 风险与回滚

| 风险 | 防护 | 回滚 |
|---|---|---|
| formatter 改变单元格文本空白 | 保留原始 inner text，前后结构比较 | 恢复 `pre_format_md_*` 并将 formatting 置为 pending |
| 只覆盖 pdf-auto，遗漏 pdf-rerun | 三入口回归 fixture | 禁止发布未覆盖入口的实现 |
| TOC 后处理重新写入未格式化正文 | 在最后一次 Markdown 修改后统一最终化 | 从 segments 重新 merge |
| 历史 manifest 虚报 verified | 真实结构检测替代字段信任 | 降级为 pending，重新格式化 |
| 大文件/8192 表格导致内存或耗时问题 | 记录耗时并用临时文件原子替换 | 保留原始 Markdown，不部分写入 |

## 后续边界

本计划只负责“语义保持的可读性格式化”。表格结构重建、跨页逻辑关系、目录语义修复和字段规范化继续由 `pdf2md-fix` 人工流程或独立计划负责。
