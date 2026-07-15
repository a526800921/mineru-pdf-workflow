# 计划：pdf-merge 表格可读性格式化落地

## 计划状态

- 状态：已完成
- 当前阶段：阶段 4：独立验收与收口 ✅
- 最后更新：2026-07-12

本文档是“表格 pretty-print 真正落地”专项计划的实施细节事实源。它承接已完成的 [pdf2md-fix 人工复核与内容修复工作流](pdf2md-fix-manual-workflow.md)，只解决“设计声明存在、实际 `pdf-merge` 未执行格式化”的实现漂移，不重新打开人工修复、VLM 或目录语义范围。

## Step 0 证据

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

#### 阶段 1 独立验收（2026-07-12）

结论：未通过阶段完成验收，状态保持 `实施中`。

已验证：

- `scripts/lib/markdown_table_formatter.py` 和 `tests/test_markdown_table_formatter.py` 已存在。
- 阶段单测 `pytest -q tests/test_markdown_table_formatter.py`：26 passed。
- 春风250Sr真实 fixture 可生成 87 个多行表格，基本幂等性和简单 malformed HTML 测试通过。

阻塞问题：

1. **已格式化外观会绕过 malformed 校验**：输入一个已经带换行但闭合标签错配的表格时，`_is_formatted()` 先返回原文，没有执行 `_validate_tags()`，因此标签错配没有抛出 `TableFormatError`。
2. **代码块伪表格被误处理**：Markdown fenced code block 中的 `<table>` 会被 `format_tables()` 改写，违反“代码块、普通文本中的伪标签不做格式化”的冻结契约。
3. **结构校验覆盖不足**：当前 `validate_structure()` 主要比较表格和结构标签数量，不能可靠校验单元格文本、属性、逐行列数及 `rowspan/colspan` 前后等价；例如带 `class` 属性的 `<tr>` 不会被完整计入验证。

完成阶段 1 前需要补齐：

- 先无条件校验每个 table 块的结构，再判断是否已经格式化；
- 识别并跳过 Markdown fenced code block 内的伪表格；
- 扩展结构比较到表格数量、逐行单元格数量、单元格文本、标签属性、`rowspan/colspan` 和图片/inline HTML 引用；
- 为上述边界增加回归测试，并重新独立验收。

#### 阶段 1 重新验收（2026-07-12）

结论：阶段 1 验收通过，状态推进为 `已完成`；阶段 2 达到 `待实施` 标准。

修复与验证结果：

- 已格式化外观的 malformed HTML 现在仍会先执行结构校验，标签错配正确抛出 `TableFormatError`。
- Markdown fenced code block 和 tilde fenced code block 内的伪 `<table>` 均保持原文，不再被格式化。
- `validate_structure()` 已扩展到逐表逐行逐格比较文本、标签属性、`rowspan`、`colspan`、图片引用和列数。
- `pytest -q tests/test_markdown_table_formatter.py`：41 passed；全量 `pytest -q`：176 passed。
- 春风250Sr真实 fixture：格式化前后均为 87 个表格、373 行、25628 个单元格；多行表格 87 个；结构错误 0；重复格式化结果一致。
- 治理检查和 drift 检查通过。

阶段 2 的实施前置条件已具备：纯格式化器、边界测试、真实 fixture、失败策略和结构等价校验均已完成；下一步可接入 `pdf-auto`、`pdf-rerun` 和 manifest 最终化，但本次未实施链路接入。

### 阶段 2：接入合并与最终化链路

候选文件：`scripts/pdf-merge`、`scripts/pdf-auto`、`scripts/pdf-rerun`、`scripts/pdf-check-fixes` 或共享 manifest helper。

工作项：

1. 在 Markdown 最后一次内容修改之后调用格式化器；`toc_repair.repair_merged` 后必须再次确保格式化状态成立。
2. 覆盖 `pdf-auto` 的 `merge`、`needs_review` 和 `pdf-rerun` 入口。
3. 写入格式化前备份、manifest hash 和 `formatting` 块。
4. 将 `pdf-check-fixes` 从“只检查 formatting 字段存在”提升为“检查备份、后 hash 和表格结构一致”。
5. 保持全流程原子写入和失败回滚。

完成条件：新建临时包可通过三个入口生成格式化 Markdown；失败时原文件和 manifest 均保持不变。

#### 阶段 2 验收（2026-07-12）

结论：阶段 2 未通过，保持 `实施中`，暂不推进阶段 3。

已通过的检查：

- `pytest -q tests/test_markdown_table_formatter.py`：41 passed。
- `pytest -q`：176 passed。
- 临时包正向合并：`pdf-merge` 已生成多行格式化 Markdown、`data/pre_format_md_<hash>.md` 备份，以及 `manifest.formatting` 的前后 hash。
- 调用链检查：`pdf-auto` 的 `merge` 和 `needs_review` 路径均在 `toc_repair.repair_merged` 后再次最终化；`pdf-rerun` 通过 `pdf-merge` 覆盖最终化入口。

阻塞项：

1. `finalize_markdown_formatting()` 仍直接使用 `write_text()` 写入备份、canonical Markdown 和 manifest，没有按契约先写临时文件再原子替换；中途失败可能留下半成品。
2. `scripts/pdf-merge` 在格式化失败时只打印错误，明确保留已写入的合并结果且不阻塞退出。临时 malformed table 验证结果为：退出码 `0`、canonical Markdown 已被覆盖、manifest 未同步更新，违反“失败时原文件和 manifest 均保持不变”。`pdf-auto` 的两个最终化内嵌调用也只打印错误，没有将失败传递给流程。
3. 最小新建包没有 `manual_fixes.jsonl` 和 `manifest.fixes` 时，`scripts/pdf-check-fixes` 仍会因这两个历史修复契约报错；因此格式化契约的独立校验范围还没有与“无人工修复的新包”完全对齐。

阶段 2 的下一步不是扩展格式化语义，而是补齐最终化事务边界：格式化、备份和 manifest 更新必须可回滚；任一失败都应返回非零并恢复原 canonical Markdown 与 manifest。修复后需重新执行本节全部检查，再决定是否推进阶段 3。

#### 阶段 2 重新验收（2026-07-12）

结论：仍未通过，保持 `实施中`，暂不推进阶段 3。

本次复验结果：

- `pytest -q tests/test_markdown_table_formatter.py`：41 passed。
- `pytest -q`：176 passed。
- `pdf-merge` 现在会在格式化失败时返回非零，错误传播较上次有所改善。
- 格式化器已增加单文件级临时文件替换，但这还不等于 Markdown、备份和 manifest 的整体事务回滚。

仍存在的阻塞项：

1. 临时 malformed table 实测返回码已为 `1`，但原有 canonical Markdown 仍被合并结果覆盖，manifest 也被改写为 `formatting.status=pending`。因此“失败时原文件和 manifest 均保持不变”仍未满足。
2. `finalize_markdown_formatting()` 先替换 Markdown，再替换 manifest；如果后一个替换失败，仍可能出现正文已更新、manifest 未同步的部分成功状态。格式化前备份也不是整体事务回滚机制。
3. `pdf-rerun` 的 JSON 路径仍使用 `pdf-merge ... || true`，会吞掉合并失败并继续输出成功的 `completed` JSON，不满足失败状态向调用方传播的要求。
4. `pdf-auto` 在 TOC 后再次调用最终化时，内嵌 Python 失败分支只打印错误，没有显式非零退出；该路径仍缺少统一失败门禁。

本次复验不改变阶段2完成条件，也不进入阶段3。下一步仍应先建立“合并输出临时文件 → TOC 后处理 → 格式化 → manifest 更新 → 一次性提交”的事务边界，并在 `pdf-auto`/`pdf-rerun` 三条入口统一传播失败后再复验。

#### 阶段 2 最终重新验收（2026-07-12）

结论：阶段 2 验收通过，状态推进为 `已完成`；阶段 3 达到 `待实施` 标准。

本次修复：

- `finalize_markdown_formatting()` 对备份、Markdown 和 manifest 增加事务式准备与回滚；单文件写入使用临时文件替换。
- `pdf-merge` 在格式化失败时恢复合并前的 Markdown 与 manifest，并返回非零；不再写入虚假的 `pending` 半成品状态。
- `pdf-auto` 的 `merge`/`needs_review` 路径把 TOC 后处理和最终化放入同一回滚边界，失败时恢复 Markdown 与 manifest。
- `pdf-rerun` JSON 路径不再吞掉 `pdf-merge` 失败，正确返回错误状态和退出码。
- 即使 TOC 只修改表格外文本，最终化也会同步当前 `formatted_markdown_sha256` 和 `fixes.markdown_sha256`。
- 补齐 mock 测试对 `markdown_table_formatter.py` 的依赖，并增加 `pdf-rerun` 合并失败传播场景。

验证证据：

- `pytest -q`：181 passed，5 warnings。
- `pytest -q tests/test_markdown_table_formatter.py tests/test_pdf_merge_formatting.py`：46 passed。
- `bash scripts/test-phase2.sh`：38/38 通过，覆盖 `pdf-auto` 通过/needs_review、`pdf-rerun` 成功和合并失败 JSON 传播。
- `bash tests/test-fix-validate.sh`：67/67 通过。
- 临时 malformed table：退出码为 1，canonical Markdown 与 manifest hash 均保持不变。
- 临时正向合并重复执行：Markdown 和 manifest hash 均保持幂等。
- `bash -n`、治理检查、drift 检查和 `git diff --check` 通过。

阶段 3 现在只需进行真实样本回填和兼容性验证，不再修改阶段 2 的公共格式化契约。

### 阶段 3：真实样本回填与兼容验证

工作项：

1. 在临时副本上回填 `pdf/春风250Sr/`、`pdf/demo20/`、`pdf/demo60/`，验证不生成第二正文入口。
2. 对已有 `formatting.status=verified` 但实际未格式化的包重新计算状态；不能继续保留虚假的 verified。
3. 验证后续 `pdf2md-fix`、`pdf-extract-data`、`pdf-prepare-ingest` 仍读取同一路径且结构结果不漂移。
4. 补齐目录三件套契约的 manifest 登记检查，但不修改原始 `segments/**/content_list*.json`。

完成条件：三个真实样本格式化结果可读、结构等价、manifest 可验证，现有下游测试无回归。

#### 阶段 3 验收（2026-07-12）

结论：阶段 3 验收通过，阶段 4 达到 `待实施` 标准。

验证方式：复制 `pdf/春风250Sr/`、`pdf/demo20/`、`pdf/demo60/` 到临时目录，在副本上运行最终化、校验和下游流程；原始输出包未修改。

验证结果：

- 三个临时包均保持原 canonical Markdown 路径：`春风250Sr.md`、`demo20.md`、`demo60.md`，没有生成第二正文入口。
- 表格数量与多行格式：春风250Sr `87/87`、demo20 `11/11`、demo60 `29/29`；当前 Markdown hash 均与 `formatting.formatted_markdown_sha256` 一致，格式化前备份均存在。
- `scripts/pdf-check-fixes`：三个临时包均返回 0。
- `scripts/pdf-extract-data` 和 `scripts/pdf-prepare-ingest`：三个临时包均返回 0；下游继续读取 manifest 的同一 `files.markdown`，未产生路径漂移。
- demo20 的 p14–p16 `cross_page_table` 记录存在；demo60 的 8192 候选、p37/p47/p48/p50 修复记录和 manifest 登记存在。
- 真实包原先“单行格式化”的复核统计口径已纠正：应按 `<table>` 切分检查，不能按 `<table` 切分；直接检查确认三个 canonical Markdown 的表格均为多行格式。

阶段 3 未修改真实包内容，阶段 4 只需做三入口、幂等性、失败回滚和最终回归的独立收口验收。

### 阶段 4：独立验收与收口

验收至少包括：

- 春风250Sr：87 个表格全部多行输出，表格结构和单元格文本前后一致；
- demo20/demo60：覆盖普通表格、跨页表格、8192 fallback 表格和图片单元格；
- 三条入口：`pdf-auto` 通过路径、`pdf-auto` needs_review 路径、`pdf-rerun`；
- 幂等性：第二次执行不改变 Markdown 和 manifest hash；
- 失败回滚： malformed HTML 或一致性失败不产生半成品；
- 回归：`bash tests/test-fix-validate.sh`、`pytest -q`、三个真实包 `scripts/pdf-check-fixes`、治理检查和 drift 检查。

#### 阶段 4 独立验收（2026-07-12）

结论：✅ 阶段 4 验收通过，全计划完成。

验证证据（30/30 项通过）：

**A. 三条入口**
- pdf-auto merge 路径：pdf-merge 内置 `finalize_markdown_formatting` ✅
- pdf-auto needs_review 路径：2 处 toc_repair 后重新格式化 ✅
- pdf-rerun：调用 pdf-merge → 继承格式化 ✅

**B. 表格结构完整性（逐格验证）**
- 春风250Sr：87 表，25,628 单元格，0 结构差异 ✅
- demo20：11 表，150 单元格，0 结构差异 ✅
- demo60：29 表，33,178 单元格，0 结构差异 ✅

**C. 幂等性**
- 三个包二次 `finalize_markdown_formatting` 均返回 `status=unchanged`，MD 和 manifest hash 均不变 ✅

**D. 失败回滚**
- malformed HTML → pdf-merge exit≠0，manifest 保持 `status=pending`，原文件不损坏 ✅
- `_atomic_write` 使用 `tempfile.mkstemp` + `fsync` + `os.rename` ✅

**E. 回归**
- `test-fix-validate.sh`：67/67 通过 ✅
- `pytest -q`：181 passed ✅
- `pdf-check-fixes`：春风250Sr / demo20 / demo60 均 exit=0 ✅
- 治理检查通过 ✅

**F. 表格特征覆盖（三包 127 表）**
- 简单表 97、colspan 9、rowspan 8、colspan+rowspan 13、img 5、空td表 54、8192fallback 10 ✅

**G. manifest 契约**
- 三个包 `status=verified`、`schema_version=1`、`mode=merge_time`、hash 一致 ✅

#### 阶段 4 再次独立验收复核（2026-07-12）

结论：再次复核通过，阶段 4 的“已完成”结论有效。

本次独立复核证据：

- 全量 `pytest -q`：181 passed，5 warnings。
- `bash scripts/test-phase2.sh`：38/38 通过，覆盖 `pdf-auto` merge/needs_review、`pdf-rerun` 成功和合并失败传播。
- `bash tests/test-fix-validate.sh`：67/67 通过。
- 三个真实包直接运行 `scripts/pdf-check-fixes` 均返回 0。
- 三个真实包的 canonical Markdown 分别包含 87、11、29 个多行 HTML 表格；春风250Sr 和 demo60 的图片单元格、demo20 的 p14–p16 跨页记录、demo60 的 8192 候选均可复核。
- 临时 malformed HTML 验证：`pdf-merge` 返回非零，原 canonical Markdown 与 manifest hash 保持不变；临时正向合并二次执行的 Markdown/manifest hash 保持不变。
- `python3 scripts/check_plan_governance.py .`、`--drift` 和 `git diff --check` 均通过。

## 验证方式

```bash
pytest -q
bash scripts/test-phase2.sh
bash tests/test-fix-validate.sh
scripts/pdf-check-fixes 'pdf/春风250Sr'
scripts/pdf-check-fixes pdf/demo20
scripts/pdf-check-fixes pdf/demo60
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```

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

## Test Coverage（测试覆盖率证据）

这是 2026-07-15 的仓库级回归基线：`python -m pytest -q` 为 `312 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`。该证据用于确认当前仓库回归状态，不冒充本历史计划的行覆盖率百分比。
