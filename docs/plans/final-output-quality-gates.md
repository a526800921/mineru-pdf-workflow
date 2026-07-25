# 计划：最终 Markdown 与入库前结果质量门禁

## 计划状态

- 状态：待实施
- 当前阶段：阶段 1
- 最后更新：2026-07-25
- 计划定位：把质量控制中心从中间证据产物收敛到人工真正审核的最终 Markdown 和 `data/ingest_ready.csv`，不改变单页 canonical、MinerU 主解析参数或跨页表格策略。

本计划的状态、依赖、推荐顺序和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准；本文件承载最终输出异常分类、门禁契约、样本矩阵、阶段准入和验收证据。

本计划依赖 [pdf2md-quality-performance-optimization](pdf2md-quality-performance-optimization.md)、[table-text-omission-detection](table-text-omission-detection.md)、[pdf-table-repair](pdf-table-repair.md)、[pdf-extract-data-table-coverage](pdf-extract-data-table-coverage.md)、[data-ingestion-pipeline](data-ingestion-pipeline.md) 和 [pdf-output-package-layout](pdf-output-package-layout.md)；各计划的字段和历史实现细节仍以其自身事实源为准。

## 需求探索

### 已确认事实

- 人工审核的主要输入只有最终生成的 `<stem>.md` 和 `data/ingest_ready.csv`。
- `manifest.json`、`page_fallback`、`table_candidates.jsonl`、`table_repair_draft.jsonl`、VLM sidecar、原生 PDF 文本等属于中间证据、追溯或脚本输入，不应成为人工审核的主要入口。
- `ingest_ready.csv` 不是从 Markdown 直接机械转换而来，而是经过 `quick_lookup_draft.csv`、包级抽取配置、审核覆盖、冲突处理、页码安全门禁和 ready 状态门禁后生成。
- 用户确认：明确损坏或字段未恢复时，不强行自动修改最终 Markdown；但不得让这些问题继续生成/更新可交付的 `ingest_ready.csv`，必须先人工修正最终 Markdown 或完成明确审核处置。
- 跨页表格自动关联暂不实施；人工审核阶段继续手动识别跨页关系。

### 已确认的异常根因

现有单元格异常计划解决的是“检测 → fallback → 选择/ review”，不是“所有异常自动消失”。当前安全策略如下：

```text
发现异常
→ 尝试 high fallback
→ fallback 未恢复字段或无法判断
→ selected=review，保留原始结果和候选
→ 最终 Markdown 仍可能保留原始异常
```

真实包证据：

- `pdf/demo60` p50：原始和 fallback 均为 `empty_td=8192`、`max_td_per_row=8192`，最终 `selected=review`，因此异常保留在最终 MD。
- `pdf/demo60` p46：原始 `empty_td=61`，fallback 降至 2，但 `上电方式` 仍未恢复；`compare_quality()` 的字段缺失优先规则返回 `review`，最终仍保留原始 61 个空单元格。
- `pdf/demo60` p16：fallback 减少空单元格，但“百公里综合油耗”仍未恢复，因此同样进入 `review`。
- 部分空单元格来自 `rowspan`、`colspan` 或图片/布局表格，不能按 `<td></td>` 总数无条件删除。

因此，用户观察到“最终 MD 仍有异常”是事实，不是认知偏差；此前计划的完成语义是“异常不静默放行并进入 review”，不是“异常已被自动修复”。

## 目标

1. 对最终 Markdown 做面向交付的异常分类，区分明确损坏、内容未恢复、合法空单元格和仅需人工确认的结构风险。
2. 对明确损坏或影响结构化字段的未解决异常，在 `ingest_ready.csv` 生成前阻断，而不是让人工从多个中间产物中自行发现。
3. 保留最终 Markdown 作为人工修复和审核事实入口，不自动删除无法证明为冗余的单元格，不让门禁替代人工语义判断。
4. 对 `quick_lookup_draft.csv` → `ingest_ready.csv` 建立可复现的行数、状态、冲突和排除原因对账。
5. 后续支持只重跑失败页/指定页，避免为修复一个 MD 页面重新处理整份 PDF。

## 非目标

- 不把所有空 `<td>` 视为异常；必须考虑 `rowspan`、`colspan`、图片表格和合法布局空位。
- 不在本计划中实现跨页表格自动关联或多页 canonical。
- 不把 VLM、PDF 原生文本或候选 JSON 直接写入最终 Markdown 或 `ingest_ready.csv`。
- 不通过删除空单元格、猜测字段或放宽状态门禁来制造“看起来正常”的结果。
- 不调整 MinerU 默认 `medium`、页级 fallback `high` 的既有参数，除非新的 Step 0 证据证明参数变化是必要的。
- 不把页图 manifest 作为人工审核必需入口；页图是否生产由其独立计划和下游硬需求决定。

## 不变量与安全边界

- 最终 Markdown 仍由现有 canonical 合并/修复链路生成；门禁只检查和阻断，不直接改写正文。
- `ingest_ready.csv` 只有在最终 Markdown 门禁、抽取覆盖、冲突和页码安全门禁均通过后才允许原子生成或替换。
- 门禁失败时保留原有可追溯产物，输出明确失败原因；不得用空文件、旧状态或部分新文件伪装为成功。
- 合法的 `rowspan/colspan` 空位、图片单元格和无业务字段的视觉布局不得仅因空单元格计数阻断。
- 失败页面必须可回指物理页、canonical 页锚点、原始/fallback hash 和抽取受影响的候选行。
- 中间证据继续保留用于诊断，但不增加人工审核必须阅读的产物数量。

## 候选门禁分类（阶段 1 待实现前冻结）

| 分类 | 示例 | 最终 MD | `ingest_ready.csv` | 处理方式 |
|---|---|---|---|---|
| `malformed_table` | 8192 个重复空单元格、单行异常列数、明显体积爆炸 | 保留，等待人工修正 | 阻断 | 输出页码、表格和原因，不自动删除 |
| `unresolved_text` | PDF 原生字段存在但 MD/fallback 均未恢复 | 保留，等待人工补全 | 若影响业务抽取则阻断 | 记录缺失文本和受影响候选 |
| `layout_blank` | `rowspan/colspan` 展开产生的合法空位、图片表格布局 | 保留 | 不阻断 | 仅在结构检查无法解释时进入 review |
| `review_only` | 视觉页、表头/列语义无法自动确认 | 保留 | 按是否影响业务字段决定 | 人工看最终 MD，必要时处置审核文件 |

具体阈值、跨字段影响判定和 `ingest_ready` 原子替换行为必须在阶段 1 Step 0 fixture 上验证后才能冻结；本表先冻结状态语义，不把现有 `EMPTY_TD_THRESHOLD=100` 直接当作最终交付阈值。

## 影响模块或文件

- `scripts/lib/page_quality.py`
- `scripts/pdf-final-output-gate`（阶段 1 新增候选入口）
- `scripts/pdf-merge`
- `scripts/pdf-table-fix`
- `scripts/pdf-extract-data`
- `scripts/pdf-prepare-ingest`
- `scripts/pdf-export-ingest`
- `scripts/lib/review_report.py`
- `tests/test_page_quality.py`
- `tests/test_pdf_extract_data.py`
- `tests/test_pdf_prepare_ingest.py`
- `tests/test_pdf_export_ingest.py`
- `tests/` 中的 PDF 输出包/最终交付回归
- `docs/PLAN_MAP.md`

涉及 PDF 解析流程、最终输出包或入库门禁契约的实现变更，实施前必须先更新本计划；若新增用户可见产物、字段或状态，再同步项目级与用户级 `pdf2md` skill。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 主要产物 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 复现最终 MD 异常并冻结人工审核边界 | 真实包和用户审核口径可复现 | 根因报告、异常分类、门禁取舍 | 已完成 |
| 阶段 1 | 最终 MD 异常门禁与 `ingest_ready.csv` 阻断 | 阶段 0 通过；用户确认异常阻断策略 | 最终输出 gate、对账报告、阻断回归 | 待实施 |
| 阶段 2 | 失败页增量重跑与审核队列收敛 | 阶段 1 完成且有重复处理耗时基线 | 页级缓存/指定页重跑、简化 review 入口 | 设计中 |
| 阶段 3 | 真实样本验收与治理收尾 | 阶段 1～2 实际范围稳定 | MD/CSV 交付验收、回归、skill/PLAN_MAP 同步 | 设计中 |

## 当前阶段

阶段 1：最终 Markdown 异常门禁与 `ingest_ready.csv` 阻断。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 待实施 |
| Step 0 | 已复现 demo60 p16/p46/p50 的最终 MD 异常保留路径，并确认现有计划只保证 review 不静默放行；用户确认阻断 `ingest_ready.csv` 的取舍。 |
| 样本矩阵 | F0 demo60 p16/p46/p50；F1 春风250Sr p44/p47；F2 demo20 p14-p16；F3 150AURA 多页/图片/表格包；F4 合法 rowspan/colspan 和图片布局 fixture。 |
| 验证方式 | 对最终 canonical MD 逐页统计异常分类；从同一包重跑抽取和入库前导出；验证阻断页影响范围、ready 行集合、失败原因、幂等性和旧产物不被破坏。 |
| 完成条件 | 明确异常分类和阈值；明确异常到业务行的影响映射；阻断时不生成/替换可交付 ready；正常包和合法布局包不误阻断；重复运行结果稳定。 |
| 失败/回滚边界 | 门禁自身失败时拒绝生成新的 `ingest_ready.csv`，保留旧文件和完整诊断；删除新增 gate 分支即可回到现有 review/导出路径，不改 canonical。 |
| 当前阻塞项 | 无；用户已确认阻断策略。具体阈值和 gate 接入点在实施前需通过 GitNexus impact 和 fixture 验证。 |
| 最新独立准入复核 | 2026-07-25：通过：达到 `待实施` 标准；只建立计划，不实施代码。 |

## 阶段 0 Step 0 证据（2026-07-25）

### 可复现实验命令

```bash
python3 -m pytest -q
python3 - <<'PY'
import json
from pathlib import Path

for pkg in [Path("pdf/demo60"), Path("pdf/春风250Sr"), Path("pdf/demo20"), Path("pdf/春风 150AURA")]:
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    print(pkg, manifest.get("files", {}).get("markdown"))
    for page, entry in sorted(manifest.get("page_fallback", {}).items()):
        if entry.get("selected") == "review" and (
            entry.get("quality_signals") or entry.get("missing_text")
        ):
            print(page, entry.get("selected"), entry.get("quality_signals"), entry.get("missing_text"), entry.get("original_metrics", {}).get("empty_td"), entry.get("fallback_metrics", {}).get("empty_td"))
PY
```

### 证据结论

- `table-text-omission-detection` 已完成检测器、fallback、manifest 证据和 review 兜底；其完成证据明确记录 p14/p16 fallback 未恢复时选择 `review`，最终 Markdown 保留原始结果。这是设计行为，不是检测器漏记。
- `compare_quality()` 对 `native_table_missing` 采用优先门禁：原始有缺失而 fallback 仍有缺失时直接返回 `review`，即使空单元格数显著下降，也不会自动选择 fallback。这避免了“结构变好但正文仍缺失”的结果进入 canonical，但也解释了最终 MD 中异常仍存在。
- `demo60` p50 的原始/fallback 指标完全相同，说明这类 8192 空列不是当前 high fallback 可以解决的普通参数问题，而是需要人工整表修复或明确的最终交付阻断。
- p16、p46 这类页面不能只按空单元格数优化：fallback 的结构指标更好，但字段仍未恢复；直接选 fallback 会把另一类内容损失带入最终 MD。
- `春风250Sr` 和 `150AURA` 中部分空单元格出现在 `rowspan/colspan`、图片表格或布局表格中；它们是 F4 合法结构样本，不能由简单正则全部判为损坏。

### 现有计划边界核对

- 已有表格异常计划负责发现和 fallback 候选，不负责把所有 review 页面自动修成可交付 MD。
- 已有 `pdf-table-repair` 负责人工候选 draft 和安全应用；它不会自动应用未确认 draft，因此 p50 类问题如果没有人工修复，最终 MD 仍会保留异常。
- 已有结构化抽取计划负责从 canonical MD 生成候选和 ready 门禁，不应把“没有 ready 行”解释成 Markdown 已修好。

## 阶段 1 实施设计（待实施）

1. 在最终 canonical MD 完成后执行只读 gate，先识别页面锚点、HTML 表格、图片引用和已登记的 fallback/review 信息。
2. 将异常归类为 `malformed_table`、`unresolved_text`、`layout_blank`、`review_only`，每条记录带页锚点、来源 hash、检测器、原始/fallback 指标和受影响候选范围。
3. 在 `quick_lookup_draft.csv` 和 `ingest_ready.csv` 生成边界建立影响映射：异常页没有业务行时不因视觉问题误阻断；异常页有待入库字段且字段来源不可靠时阻断 ready。
4. 将 gate 失败转换为稳定、非零、可读的机器结果；不得先写半成品 `ingest_ready.csv` 再返回失败。
5. 为 `quick_lookup_draft → review_overrides/conflicts/page_numbering → ingest_ready` 输出行数和状态对账，确保人工只需看最终 MD 与 ready CSV，异常时再按页回查。
6. 所有新函数/方法实施前执行 GitNexus upstream impact；完成后执行专项回归、全量测试和 `detect_changes()`。

## 阶段 2 候选：失败页增量重跑

- 记录源 PDF hash、页码、MinerU 配置、输入 segment hash 和最终 MD hash。
- 只重跑 `malformed_table`、`unresolved_text` 或人工指定页；未变化页面不重复请求 MinerU。
- 不新增默认并发；继续复用现有 ModelPad 服务生命周期和单页 canonical。
- 只有阶段 1 完成并有真实重复运行耗时基线后，才冻结缓存 key、失效策略和回滚契约。

## 风险与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 合法 rowspan/colspan 被误判 | 无意义阻断或人工负担增加 | F4 合法布局 fixture、逻辑网格解析、只对明确损坏阻断 | 关闭新分类，恢复现有 review 路径 |
| 未恢复字段进入 ready | 错误入库 | gate 在 ready 生成前阻断并保留缺失字段/页锚点 | 保留旧 ready，修复 MD 后重新导出 |
| gate 自身失败破坏旧产物 | 交付中断或文件损坏 | 原子写入、临时输出、失败不替换旧文件 | 删除临时产物，恢复旧 gate 入口 |
| 只修结构不修内容 | MD 看起来整齐但事实缺失 | `native_table_missing` 继续优先；结构改善不能单独放行 | 重新进入人工 review |
| 中间证据反客为主 | 人工审核复杂化 | 最终 MD/ready 为唯一审核入口，sidecar 只做诊断 | 删除非必要展示入口，不删除追溯证据 |

## 验证方式

### 阶段 1

- F0：demo60 p16/p46/p50 必须分别复现“字段未恢复导致 review”“结构改善但仍 review”“原始/fallback 均 8192 空列”。
- F1：春风250Sr p44/p47 必须证明合法空位和未恢复表头可以区分，不能按总空 `<td>` 数直接放行或阻断。
- F2：demo20 p14-p16 保持既有人工修复/Review 边界，不能改变单页 canonical 或跨页处理。
- F3：150AURA 真实包重跑后，抽取、冲突、页码和 ready 门禁无回归。
- F4：合成 rowspan/colspan、图片表格、合法空位 fixture 不误阻断。
- 回归：定向 pytest、`bash tests/test-fix-validate.sh`、`bash test-phase3.sh`、全量 pytest、`git diff --check`、GitNexus `detect_changes()`、`plan-governance-cli check . --strict-readiness`。

### 阶段 1 完成条件

- 明确损坏不会进入新的 `ingest_ready.csv`；门禁失败原因可定位到 MD 页锚点和抽取行。
- 字段未恢复但不影响业务抽取的页面不会被错误写入 ready；是否阻断有可复现规则。
- 合法布局空单元格不误报；demo60 p50 类异常不会再被标记为可交付成功。
- 正常包、已人工修复包、重复执行和失败回滚全部通过。
- 不改变既有 canonical Markdown 内容，不修改跨页表格策略，不改变 MinerU 默认配置。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 复核者 | 独立治理复核（基于真实输出包、当前代码、已有计划和用户确认） |
| 日期 | 2026-07-25 |
| 阶段 | 阶段 1 |
| 结论 | 通过：达到 `待实施` 标准；只建立计划，不实施代码 |
| 证据 | demo60 p16/p46/p50 根因复现；已有计划明确 review 保留原始；用户确认异常页面阻断 `ingest_ready.csv`；F0-F4 样本和回滚边界已定义 |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-25 | 独立治理复核 | 阶段 0 | 通过：根因和人工审核边界已确认 | 真实包指标、manifest 选择结果、`compare_quality` 字段缺失优先规则、已有表格异常计划完成证据 |
| 2026-07-25 | 独立治理复核（用户确认后） | 阶段 1 | 通过：达到 `待实施` 标准；只建立计划，不实施代码 | 用户确认明确损坏/未恢复字段不得继续生成/更新 `ingest_ready.csv`；Step 0、样本矩阵、验证和回滚边界齐备 |

## 当前测试覆盖基线

- 当前仓库既有回归：`python3 -m pytest -q`、`bash tests/test-fix-validate.sh`、`bash test-phase3.sh`；阶段 1 实施前必须重新记录当前工作区结果。
- 已有 `tests/test_page_quality.py` 覆盖 `compare_quality` 的字段缺失优先和结构指标比较；本计划需要新增最终输出 gate、合法布局不误阻断、ready 原子阻断和对账回归。

## 完成定义

- 阶段 0 完成：最终 MD 异常保留根因、人工审核边界和阻断取舍有真实证据。
- 阶段 1 完成：最终 MD 门禁、`ingest_ready.csv` 阻断、行数对账、原子写入和 F0-F4 回归通过。
- 阶段 2 完成：失败页增量重跑有耗时收益证据、缓存失效和回滚边界明确。
- 计划完成：最终 MD 和 `ingest_ready.csv` 成为人工审核中心；中间证据可追溯但不增加人工入口；PLAN_MAP、计划和必要 skill 无漂移。
