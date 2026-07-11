# 计划：通用表格字段缺失检测与页级 fallback 触发

## 计划状态

- 状态：待实施
- 当前阶段：阶段 4：整表头/顶部列头漏报补强
- 最后更新：2026-07-11
- 依赖：`single-page-segmentation-migration` 阶段 3、`pdf-evaluation-suite` P4b、PyMuPDF 原生文本层

## 背景

demo20 第 16 页的表格中，PDF 页面原生文本包含“百公里综合油耗”，但 MinerU 单页输出的 HTML 表格缺少该字段。现有四类页级质量信号均未命中：空 `<td>`、单行列数、体积膨胀和整页文本覆盖率都可能保持在正常范围内。

这不是一个应为特定字段增加白名单的需求。“百公里综合油耗”只是当前样本中的缺失字段，检测器必须对未知字段同样有效。

## 目标

- 从 PDF 原生文本及其坐标中提取表格区域的候选文字。
- 将 PDF 原生表格文字与 MinerU HTML 表格的逻辑单元格进行通用比对。
- 发现“PDF 表格区域存在、HTML 表格缺失”的字段时，产生机器可读信号并触发既有页级 fallback。
- fallback 后重新比对：恢复字段则允许选择 fallback；仍缺失或无法判断则保留原始结果并进入 `review`。
- 将检测证据写入 `manifest.page_fallback`，支持后续追溯和人工复核。

## 非目标

- 不硬编码“百公里综合油耗”或其他业务字段白名单。
- 不直接使用 VLM 输出覆盖 MinerU HTML；VLM 只作为无文本层或原生检测不确定时的补充证据。
- 不改变已完成阶段 3 的单页 fallback 参数和双版本目录契约。
- 不把所有 PDF 原生文字都要求出现在 HTML；页眉、页脚、图片说明和表格外文字必须排除。

## Step 0 证据

### 已确认的真实样本基线

- PDF 原生第 16 页包含字段“百公里综合油耗”，其坐标约为 `[44.3, 44.3, 114.3, 54.3]`；同一视觉行的值“≤2.7L”坐标约为 `[360.5, 43.8, 387.9, 55.0]`。
- 单页 MinerU 原始段输出和最终合并 Markdown 均缺少该字段，`content_list.json`、`content_list_v2.json`、`middle.json`、`model.json` 也未包含该字段，因此不是 merge 阶段丢失。
- 当前 `assess_page_quality` 对该页返回 `quality_ok=true`，文本覆盖率约 `0.9162`，说明整页覆盖率不能发现这种局部表格字段遗漏。
- 现有 fallback 对该页已执行过，但 fallback 结果仍未恢复该字段；因此需要先记录“检测到但修复未成功”的结果，而不是静默认为质量正常。
- VLM 视觉评测报告 `pdf/demo20/data/vlm_comparison_p16.md` 能识别完整行“百公里综合油耗 ≤2.7L”，可作为补充检测证据，但不能作为主输出覆盖源。

### 可复现基线

在仓库根目录执行以下检查，应确认 PDF 原生文本有该字段而当前单页 Markdown 没有：

```bash
python3 - <<'PY'
from pathlib import Path
import fitz

pdf = Path("pdf/demo20/demo20.pdf")
md = Path("pdf/demo20/segments/p0016-0016/demo20/hybrid_auto/demo20.md")
with fitz.open(pdf) as doc:
    native = doc[15].get_text()
assert "百公里综合油耗" in native
assert "百公里综合油耗" not in md.read_text(encoding="utf-8")
print("red baseline: native-only table field omission reproduced")
PY
```

## 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- Step 0 真实失败基线已固定：PDF 原生文本包含字段，单页 MinerU 输出及中间结构缺失字段。
- 影响范围已限定为页级质量检测、`pdf-auto` fallback 触发和 `manifest.page_fallback` 证据，不改变主解析参数和既有双版本目录契约。
- 通用检测契约已明确：使用原生文字 bbox、视觉行聚类、表格区域和 HTML 逻辑单元格比对，不维护业务字段白名单。
- 失败策略已明确：坐标无法对齐、无文本层、fallback 未恢复或结果无法判断时进入 `review`，不自动覆盖原始结果。
- 验证方式、边界 fixture、完成条件和回滚方式已具备；当前没有未解决的实施前置阻塞项。

进入阶段 1 后，修改共享质量检测符号前必须先执行 GitNexus upstream impact；完成实现后执行 `detect_changes()`、测试和治理检查。

## 阶段 1 验收记录（2026-07-11）

结论：**不通过，暂不能标记阶段 1 已完成。**

### 已通过

- `5a325ee feat: 阶段1 通用原生表格检测器` 已实现 `native_table_text_missing` 信号，并接入 `pdf-auto` 的质量检测调用。
- demo20 p16 能检测到缺失字段“百公里综合油耗”，实际结果为 `native_table_missing=1`。
- 检测结果包含 `signals`、`native_table_candidates`、`native_table_missing` 和 `missing_text`。
- 现有 `tests/test_page_quality.py`：37/37 通过；全量 Python 测试：96/96 通过；`test-phase3.sh`：11/11 通过；阶段1清理回归：10/10 通过。
- 旧调用方不传 `pdf_words` 时仍保持原有四类质量信号行为。

### 未通过项

1. **没有真正按表格区域检测**：当前 `_find_pdf_table_labels()` 使用“页面左侧 40% + 非页脚”作为表格区域，没有使用 PDF/MinerU 表格 bbox；表格外左侧正文会被误报为缺失字段。
2. **没有视觉行聚类或字段重组**：`get_text("words")` 的每个词直接作为候选。PDF 中的多词字段会被拆成多个候选词，即使 HTML 有完整单元格也会误报。
3. **只解析第一个 HTML 表格**：页面存在多个表格时，后续表格的字段无法正确比较。
4. **`rowspan/colspan` 仅写在注释中，未真正展开逻辑网格**：当前实现只是提取原始 `<td>` 文本集合，契约与实现不一致。
5. **尚未完成未知字段 fixture**：p16 测试证明了当前案例，但还不能证明替换成未出现在代码中的多词字段、第二个表格字段后仍能正确工作。

### 已复现的边界探针

```text
表格外左侧正文：误报 native_table_text_missing，missing_text=["正文遗漏词"]
PDF 多词字段 Max + power、HTML 单元格 Max power：误报 missing_text=["Max", "power"]
第二个 HTML 表格字段：只读取第一个表格，误报第二个表格的 X/Y/Z/缺失字段
```

### 后续通过条件

- 使用实际表格 bbox 或等价可靠区域边界，不再用页面左侧比例代替表格区域。
- 按 bbox 的 y 坐标聚类并重组同一视觉行/字段，支持多词标签和中英文混合字段。
- 遍历页面全部 HTML 表格，并真正处理 `rowspan/colspan` 逻辑单元格。
- 增加至少一个未知多词字段、多个表格、表格外正文和合并单元格 fixture；所有边界测试通过后再重新验收。

## 阶段 1 再次验收（2026-07-11）

结论：**仍不通过，暂不能标记阶段 1 已完成。**

本次复验基于提交 `05245a0 fixup: 通用表格检测器重构——视觉行聚类+逻辑网格+多table`：

- 全量 Python 测试：97/97 通过。
- `test-phase3.sh`：11/11 通过。
- 计划治理检查和 `git diff --check`：通过。
- p16 真实样本仍能发现 `native_table_text_missing`，缺失字段为“百公里综合油耗”。
- 上次的表格外正文误报探针：通过。
- 上次的多表格探针：通过。
- `colspan` 网格展开探针：通过。

仍未通过：

1. **多词字段仍误报**：PDF words 为 `Max`、`power`，HTML 单元格为 `Max power` 时，结果仍为 `missing_text=["Max", "power"]`；视觉行已聚类，但没有把同一行相邻 words 重组为字段文本后再比较。
2. **`rowspan` 尚未实现**：当前逻辑网格只展开 `colspan`，`rowspan` 单元格不会填充到后续行，与检测契约不一致。
3. **回归测试缺口**：现有 97 个测试没有覆盖上述多词字段和 `rowspan` 失败用例，因此“全绿”不能证明阶段1完成。

因此阶段状态继续保持“实施中”，下一次验收至少必须补齐多词字段重组、`rowspan` 网格展开及对应回归测试。

## 阶段 1 再次验收（第二次，2026-07-11）

结论：**通过，阶段 1 已完成。**

基于提交 `997a932 fixup: rowspan展开+多词字段n-gram合并+回归测试` 的独立复验结果：

- p16 真实样本仍能发现 `native_table_text_missing`，缺失字段为“百公里综合油耗”。
- 多词字段 `Max power` 的同视觉行 n-gram 重组通过，不再误报 `Max`、`power`。
- `rowspan` 逻辑网格展开通过；`colspan`、多表格和表格外正文边界均通过。
- 全量 Python 测试：100/100 通过。
- `test-phase3.sh`：11/11 通过，其中页质量单测 41/41 通过。
- 计划治理检查、`git diff --check`：通过。

本次验收前的收尾条件：

- `skills/pdf2md/SKILL.md` 与 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 已同步记录“PDF 原生表格字段遗漏检测”的触发边界、`native_table_text_missing` 证据和不硬编码字段白名单原则。

因此当前判断为：阶段 1 的代码、边界回归、治理文档和双份 skill 已完成同步；阶段 1 标记为“已完成”，专项计划继续进入阶段 2。

### 阶段 1 完成证据

- 提交：`997a932 fixup: rowspan展开+多词字段n-gram合并+回归测试`。
- p16 真实样本检测到 `native_table_text_missing`，并识别缺失字段“百公里综合油耗”。
- 多词字段、`rowspan`、`colspan`、多表格、表格外正文边界测试通过。
- 全量 Python 测试 100/100，`test-phase3.sh` 11/11，治理检查和 `git diff --check` 通过。
- 项目级与用户级 `pdf2md` skill 已同步。

## 阶段 2 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- 执行顺序已固定：`pdf-auto` 在 consistency check 后、`pdf-validate` 前调用 `assess_page_quality`；调用时传入 PDF 原生 `words` 和页面 bbox 信息。
- fallback 参数已固定：仅重跑异常单页，使用 `effort=high` 与 `--image-analysis false`，不改变首次解析参数。
- 结果边界已固定：原始页与 `-fallback` 候选并存，`manifest.page_fallback.selected` 是合并选择依据；成功改善选择 `fallback`，无法判断或未恢复选择 `review`。
- 失败策略已固定：fallback 失败、无有效 Markdown、跨次已尝试或指标无法判断时保留原始结果并进入 `review`，不循环重跑。
- 既有阶段 3 回归已覆盖 fallback 的 `fallback/original/review/failed`、同源候选、manifest Schema、合并选择和 `needs_review` 兜底。
- 当前没有需要用户确认的阶段2前置问题；阶段2实施时只需补齐原生表格遗漏信号的专用闭环 fixture 和 demo20 p16 端到端证据。

进入阶段 2 后，修改 `pdf-auto`、`page_quality` 或 `pdf-merge` 相关符号前，必须先执行 GitNexus upstream impact；完成后执行 `detect_changes()`、专项回归、全量测试和治理检查。

## 检测契约

### 检测顺序

1. 先根据 `content_list.json` 的 `type=table` 或 Markdown `<table>` 判断页面是否存在表格候选。
2. 从 PDF 原生 `words` 提取文字和 bbox，按视觉 y 坐标聚类；不能依赖 PyMuPDF 的逻辑行号。
3. 结合 MinerU 表格 bbox 做坐标归一化，过滤表格区域外的页眉、页脚和正文。
4. 将 HTML 表格解析为考虑 `rowspan`、`colspan` 的逻辑单元格，而不是按原始 `<td>` 数量比较。
5. 对两侧文本执行统一规范化；当候选字段在 PDF 表格区域存在、邻近值或单位存在、但 HTML 逻辑单元格缺失时，产生遗漏信号。

### 机器字段

检测阶段返回：

```json
{
  "page": 16,
  "quality_ok": false,
  "signals": ["native_table_text_missing"],
  "missing_text": ["百公里综合油耗"],
  "detector": "pdf_native",
  "metrics": {
    "native_table_candidates": 1,
    "native_table_missing": 1
  }
}
```

`missing_text` 只是运行时从 PDF 提取出的证据，不是字段配置或白名单。

最终写入 `manifest.page_fallback` 时至少保留 `selected`、`reason`、`quality_signals`、`missing_text`、`detector`、`fb_status` 以及原始/fallback 指标。VLM 参与时追加 `vlm_table_text_missing` 或 `detectors: ["pdf_native", "vlm"]`，不得替代原生检测结果。

## 实施阶段

### 阶段 1：通用原生表格检测器

- 在 `scripts/lib/page_quality.py` 或独立共享模块中实现 bbox/y 聚类、表格区域筛选、逻辑单元格解析和文本比对。
- 先写 p16 缺失字段回归测试，再扩展未知字段、跨行、合并单元格、页眉干扰和无文本层页面 fixture。
- 通过 GitNexus upstream impact 后再修改被调用函数。

### 阶段 2：接入既有 fallback 闭环

- 在 `pdf-auto` 的 consistency check 之后、`pdf-validate` 之前执行该检测。
- 复用阶段 3 的单页 `effort=high + image_analysis=false` fallback、双目录保存、manifest 选择和 `review` 兜底。
- 确保 fallback 恢复字段时选择 `fallback`，未恢复时选择 `review`，不能因为整页覆盖率正常而返回 `all_passed`。

#### 阶段 2 实施记录（552319b，2026-07-11）

提交 `552319b`（此提交仅完成比较逻辑，完成声明由下方独立验收推翻）：

1. **`compare_quality` 新增 `native_table_missing` 优先判定规则**
   - 原始页有表格字段缺失（`native_table_missing > 0`）：
     - fallback 恢复（`fb_missing == 0`）且文本 OK → `fallback`
     - fallback 恢复但文本丢失 → `review`
     - 未恢复或部分改善 → `review`（已知有问题不选 `original`）
   - 无 `native_table_missing` 时完全不影响既有判定逻辑

2. **`pdf-auto` 比较选择阶段传入 `pdf_words` + page bbox**
   - 检测阶段已传 `pdf_words`（阶段 1），比较选择阶段补齐
   - `assess_page_quality` 在原始/fallback Markdown 上均能检测 `native_table_text_missing`

3. **回归测试 5 个新增 fixture**
   - `test_missing_resolved_text_ok` → fallback ✓
   - `test_missing_resolved_text_lost` → review ✓
   - `test_missing_not_resolved` → review ✓
   - `test_missing_partially_resolved` → review ✓
   - `test_missing_not_present_fallthrough` → 既有逻辑不变 ✓
   - 全量 Python 测试 105/105 通过；test-phase2 37/37 通过
   - 治理检查通过

4. **mock 修复**：`test-phase2.sh` 的 mock `page_quality.py` 签名补上 `**kwargs`

#### 阶段 2 独立验收（2026-07-11）

结论：**不通过，阶段 2 暂不能标记为已完成。**

虽然提交 `552319b` 已补齐原生字段检测参与比较的逻辑，但独立验收发现以下闭环缺口：

1. **manifest 证据字段不完整**：`page_fallback` 当前写入了 `reason`、`original_metrics`、`fallback_metrics`，但没有显式写入契约要求的 `quality_signals`、`missing_text`、`detector`（或 `detectors`）。下游只能从指标内部推断，机器契约不完整。
2. **缺少原生遗漏信号的 `pdf-auto` 级闭环回归**：现有测试覆盖了通用 `fallback/original/review/failed` 和 `compare_quality`，但没有覆盖“原生字段检测触发 → fallback 恢复并选择 fallback”“仍缺失并选择 review”“fallback 失败并进入 review”“跨执行跳过并保留证据”四条路径。

独立复核证据：

- `pdf-auto` 检测阶段已传入 `pdf_words` 和页面 bbox。
- 比较阶段已传入 `pdf_words`，仅改变 `native_table_missing: 1 → 0` 时 `compare_quality` 返回 `fallback`。
- 全量 Python 测试 105/105、`test-phase3.sh` 11/11、治理检查和 `git diff --check` 通过；但这些测试未覆盖上述 manifest 和原生信号端到端缺口。

阶段2通过前需补齐 manifest 字段和四条原生遗漏信号闭环 fixture，再重新验收。

#### 阶段 2 修复记录（2026-07-11）

结论：**两处验收缺口已修复，待用户复验。**

提交 `c8668bd`：

**Fix 1 — manifest 契约字段补齐**

在 `pdf-auto` 的三处 `page_fallback` 写入点（成功比较、fallback 失败页、全失败写入器）显式写入契约要求字段：

- `quality_signals`：触发信号列表（例如 `["native_table_text_missing"]`）
- `missing_text`：PDF 原生表格缺失字段证据（例如 `["百公里综合油耗"]`）
- `detector`：`pdf_native`（原生信号触发）或 `page_quality`（四类旧信号触发）

下游不再需要从 `original_metrics` 内部推断，机器契约完整。

**Fix 2 — 四条原生信号 `pdf-auto` 级闭环回归**

新增 `scripts/test-native-fallback.sh`，内容驱动 mock（`[[MISSING]]` 标记 + `NATIVE_FB_MODE`），覆盖：

1. 检测触发 → fallback 恢复字段 → `selected=fallback`，exit 0，契约字段完整。
2. 检测触发 → 字段仍缺失 → `selected=review` → `needs_review`，exit 2。
3. 检测触发 → fallback 重跑失败 → `fb_status=failed`、`fallback_path=None` → `needs_review`，exit 2。
4. 跨执行跳过 → 第二次运行不重复检测，`missing_text`/`quality_signals`/`detector` 证据保留，`attempt_count` 未递增。

**验证**

- `scripts/test-native-fallback.sh`：4/4 通过。
- `scripts/test-phase2.sh`：37/37 通过。
- 全量 Python 测试：105/105 通过。
- `python3 scripts/check_plan_governance.py .` 与 `git diff --check`：通过。

#### 阶段 2 再次验收（2026-07-11）

结论：**通过，阶段 2 已完成。**

- `scripts/test-native-fallback.sh`：4/4 通过，覆盖字段恢复选择 `fallback`、仍缺失进入 `review`、fallback 失败进入 `review`、跨执行跳过并保留证据。
- `scripts/test-phase2.sh`：37/37 通过；`test-phase3.sh`：11/11 通过。
- 全量 Python 测试：105/105 通过。
- `manifest.page_fallback` 已显式记录 `quality_signals`、`missing_text`、`detector`，并保留旧 `reason` 字段兼容性。
- 治理检查和 `git diff --check` 通过。

阶段 2 的实现与独立验收完成，专项计划进入阶段 3：真实样本与边界验收。

### 阶段 3：真实样本与边界验收

- 用 demo20 p16 验证从发现、fallback、比较、合并到 review 的完整链路。
- 增加没有 PDF 文本层、表格外同名文本、跨页表格和多个表格同页样本。
- 验证不硬编码字段、不误报页眉页脚，并保持既有 JSON/manifest 兼容契约。

#### 阶段 3 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- Step 0 已固定：demo20 p16 的 PDF 原生文字包含“百公里综合油耗”，当前 MinerU 单页 Markdown 和中间结构缺失该字段；VLM 报告可识别完整视觉行，仅作为补充证据。
- 阶段3目标已限定为真实样本和边界验收，不再扩展检测器算法、fallback 参数或 manifest Schema。
- 验收边界已明确：无文本层、表格外同名文字、跨页表格、多表格、页眉页脚和未知字段；不硬编码字段白名单。
- 通过条件已明确：p16 触发并产生完整 manifest 证据；fallback 修复成功/未修复/失败分别得到正确选择；最终 Markdown、review.md 和同源中间产物可追溯。
- 风险与回滚已明确：无法可靠判断进入 `review`；原始和 fallback 双目录保留，可重新合并；VLM 不直接覆盖 MinerU HTML。
- 没有需要用户确认的阶段3前置问题；真实样本运行本身属于阶段3实施内容。

进入阶段3后，涉及真实 PDF 运行或边界 fixture 扩展时，先更新运行证据，再按 GitNexus impact → 实现/测试 → `detect_changes()` → 治理检查的顺序推进。

#### 阶段 3 实施记录（2026-07-11）

结论：**真实样本与边界验收完成，待用户最终验收。**

提交 `acf04b5`（边界 fixture）+ `4a6ba55`（review.md 页级质量复核段）。

**demo20 p16 真实全链路验收**

重置 manifest fallback 状态后用当前代码全量重跑 `pdf-auto pdf/demo20/demo20.pdf pdf/demo20/segments`，退出码 2（needs_review）：

- p16 触发 `native_table_text_missing`，clean 检测识别缺失字段“百公里综合油耗”。
- 真实 `manifest.page_fallback["16"]` 含完整契约字段：`selected=review`、`detector=pdf_native`、`quality_signals=["native_table_text_missing"]`、`missing_text=["百公里综合油耗"]`、`fb_status=completed`。
- detector 区分正确：p16=`pdf_native`；p12/p15=`page_quality`（四类旧信号，`missing_text=[]`）。
- `parse_status=needs_review`，`review.md` 生成，p16 出现在新“页级质量复核”段。
- TOC 页 p2–p8 仍由 pdf-validate 的 `review_only` 路径覆盖，两条复核路径互补。

**边界 fixture（`tests/test_page_quality.py`，50/50）**

- `test_no_text_layer_no_false_positive`：扫描件无文本层（`pdf_words=[]`）跳过检测。
- `test_multi_table_missing_in_second_detected`：同页多表格，第二个表格缺失字段“湿度”（代码中不存在的字段）被发现。
- `test_multi_table_present_no_false_positive`：跨表格多词首列（“进气温度”）完整时不误报。
- `test_footer_text_no_false_positive`：页脚区域（底部 15%）文字排除，不误报。

**review.md 纳入页级质量复核（用户要求）**

- `review_report._append_page_fallback_review` 读取 `manifest.page_fallback`，新增“页级质量复核”段列出 `selected=review`/`fb_status=failed` 页；`selected=fallback` 页排除。
- 新增 `tests/test_review_report.py` 5/5；项目级与用户级 `pdf2md` skill 已同步说明。

**验证**

- 全量 Python 测试：114/114 通过（page_quality 50、review_report 5、native-fallback 依赖等）。
- `scripts/test-native-fallback.sh`：4/4；`scripts/test-phase2.sh`：37/37。
- `python3 scripts/check_plan_governance.py .`、`git diff --check`：通过。
- GitNexus `detect-changes`：风险 low，0 影响流程。

#### 阶段 3 最终验收（2026-07-11）

结论：**阶段 3（真实样本与边界验收）已完成；随后在 p14 发现整表头/顶部列头漏报缺口，计划重开阶段 4，见下文。**

- demo20 p16 真实运行退出码为 2（`needs_review`），p16 触发 `native_table_text_missing`，识别缺失字段“百公里综合油耗”。
- `manifest.page_fallback["16"]` 含完整证据：`selected=review`、`detector=pdf_native`、`quality_signals`、`missing_text`、原始/fallback 参数与指标。
- `review.md` 的“页级质量复核”列出 p16，字段遗漏不会被静默吞掉。
- 无文本层、未知字段、多表格、跨表格多词字段和页脚边界均通过。
- 全量 Python 测试 114/114，`scripts/test-native-fallback.sh` 4/4，`scripts/test-phase2.sh` 37/37，`test-phase3.sh` 11/11。
- 治理检查、`git diff --check` 和 GitNexus detect-changes 通过。

注意：p16 fallback 未能可靠修复字段，因此最终 Markdown 保留原结果并进入 `review`；这是当前安全兜底契约允许的结果，不代表字段已经自动恢复。

## 阶段 4：整表头/顶部列头漏报补强

### 阶段 4 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- p14 的真实失败基线已固定：PDF 原生文本包含车型列头，MinerU HTML 首行为空，当前检测器未产生遗漏信号。
- 实施范围已限定为检测器对整表头/顶部列头的补强，复用现有 `native_table_text_missing`、页级 fallback、manifest 和 review 契约。
- 检测边界已明确：只在表格候选、顶部/列头位置及空表头结构等几何证据同时成立时判定；不能把所有无 HTML 锚点的视觉行当作缺失。
- 失败策略已明确：fallback 未恢复、重跑失败或坐标无法可靠判断时进入 `review`，不得静默返回 `all_passed`。
- p14 真实 fixture、反例范围、验证命令、完成条件和回滚方式均已写入本阶段；当前没有未解决的实施前置阻塞项。

进入阶段4实施后，修改共享检测器符号前必须先执行 GitNexus upstream impact；完成实现后执行 `detect_changes()`、专项回归、全量测试和治理检查。

### 背景与范围

demo20 p14 参数规格表的顶部车型列头 `150 AURA`、`CF150T-32`、`CF150T-32A` 在 PDF 原生文本中存在，但 MinerU 将整行输出为空 `<td>`。当前检测器因为该视觉行没有任何 HTML 单元格匹配，且列头位于右侧/居中区域，直接跳过并返回 `native_table_missing=0`。

这是阶段1–3已完成检测器的覆盖缺口，不是新的检测协议；继续复用 `native_table_text_missing`、页级 fallback、manifest 和 review 契约。

### Step 0 红基线

- PDF p14 原生文本包含 `150 AURA`、`CF150T-32`、`CF150T-32A`。
- p14 单页 Markdown 三个型号均缺失，表格首行是空单元格。
- 当前检测结果为 `signals=[]`、`native_table_missing=0`，p14 会被判为 pass。
- 红基线文件：[native-detector-header-row-false-negative.md](../issues/native-detector-header-row-false-negative.md)。

可复现断言：

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from lib.page_quality import detect_native_table_text_omission
import fitz

doc = fitz.open("pdf/demo20/demo20.pdf")
words = doc[13].get_text("words")
w, h = doc[13].rect.width, doc[13].rect.height
native = doc[13].get_text()
doc.close()
md = open("pdf/demo20/segments/p0014-0014/demo20/hybrid_auto/demo20.md").read()
assert "150 AURA" in native and "CF150T-32A" in native
assert "150 AURA" not in md and "CF150T-32A" not in md
signals, metrics = detect_native_table_text_omission(md, words, w, h)
assert signals == [] and metrics["native_table_missing"] == 0
print("red baseline: p14 header-row omission false negative reproduced")
PY
```

### 实施契约

- 当 HTML 表格顶部存在空表头行、而 PDF 表格区域顶部存在原生文字时，检测器必须检查该行，即使整行没有 HTML 锚点。
- 顶部列头不限定在左列；右侧、居中列头也必须纳入候选。
- 仍使用 `native_table_text_missing`，并在 `missing_text` 中记录原生存在而 HTML 缺失的候选文字；可在 metrics 中增加 `missing_scope=header_row` 供 review 解释。
- 不能把所有“无 HTML 锚点的视觉行”直接判为缺失；必须同时满足表格候选、顶部/列头位置、空表头结构或等价几何证据，否则进入 `review` 或跳过。
- p14 fallback 恢复车型列头则选择 `fallback`；仍缺失、重跑失败或无法判断则选择 `review`，不得返回 `all_passed`。

### 实施步骤

1. 扩展 `detect_native_table_text_omission`：识别顶部表头区域、空 HTML 首行和右侧/居中原生文字。
2. 保持现有 `pdf-auto` fallback 和 manifest 证据契约，不新增业务字段白名单。
3. 增加 p14 真实 fixture，以及合法空表头、正文无锚点行、页脚和无文本层反例。
4. 用 demo20 p14 运行完整检测、fallback、比较、合并和 review 流程。

### 验收条件

- [ ] p14 红基线从静默 pass 变为 `native_table_text_missing`，并记录至少一个缺失车型列头。
- [ ] p14 fallback 恢复时选择 `fallback`；未恢复/失败/不确定时选择 `review`。
- [ ] `manifest.page_fallback["14"]` 含 `quality_signals`、`missing_text`、`detector`、选择结果和双版本指标。
- [ ] `review.md` 在 p14 进入 review 时显示缺失车型列头证据。
- [ ] p16、现有多词字段、多表格、页脚和无文本层测试不回归。
- [ ] 全量测试、治理检查、`git diff --check` 和 GitNexus `detect_changes()` 通过。

## 验证方式

```bash
python3 -m pytest tests/test_page_quality.py -q
bash scripts/test-phase3.sh
python3 scripts/check_plan_governance.py .
git diff --check
```

新增验收至少包括：

- p16 的“百公里综合油耗”能被通用规则发现；
- 换用未出现在代码中的其他字段，仍能被发现；
- 字段恢复后选择 fallback；字段未恢复或检测不确定时选择 review；
- 表格外同名文字、页眉页脚和无文本层页面不误触发；
- `manifest.page_fallback` 证据完整，Markdown、content list、middle/model JSON 和图片保持同源。

## 风险与回滚

- PDF bbox 坐标系与 MinerU content bbox 可能不同，必须显式归一化；坐标未对齐时回退为 `review`，不能自动覆盖。
- PDF 原生文本可能包含表格外重复文字，需用表格区域和邻近值约束降低误报。
- 扫描件没有原生文本层时跳过原生检测，保留既有质量检测，并按需使用 VLM/OCR 补充证据。
- 检测器误报时可关闭新 signal，保留阶段 3 的四类旧信号和 fallback 主流程；原始目录始终保留，可重新合并。

## 完成条件（阶段 1–3）

- [x] 无字段白名单的原生表格遗漏检测器实现并通过单元测试。
- [x] p16 red baseline 转为 green，且至少一个未知字段 fixture 通过。
- [x] 检测结果接入页级 fallback，成功修复、未修复、失败和不确定四条路径均有回归。
- [x] `manifest.page_fallback` 记录检测器、缺失文本、选择结果和执行状态。
- [x] demo20 p16 真实验收通过，或明确进入 `review` 且报告包含缺失字段证据。
- [x] 项目级 `skills/pdf2md/SKILL.md` 与用户级 skill 同步说明该检测边界。
- [x] 治理检查、全量测试、`git diff --check` 和 GitNexus `detect_changes()` 通过。

> 阶段 4（整表头/顶部列头漏报补强）的完成定义见上文 [阶段 4 验收条件](#验收条件)；阶段 4 未通过前，本专项计划整体状态为"待实施"。
