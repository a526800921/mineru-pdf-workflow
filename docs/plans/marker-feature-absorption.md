# 计划：从 marker-pdf-workflow 吸纳特性

## 背景

同级项目 [marker-pdf-workflow](../../../marker-pdf-workflow/) 是基于 Marker Server 的 PDF 分段解析工作流，与本项目共享"分段解析 → 自动验证 → 合并 → 人工兜底"的流程骨架。marker 项目已完成阶段 0–2，其 README、脚本输出格式、review.md 呈现和治理文档中有部分设计优于本项目的当前状态。

本计划筛选可吸纳的特性，按优先级分阶段实施，避免与已在进行的阶段 8（PDF 输出包目录结构）产生重复。

## 事实源职责

本文档是 `marker-feature-absorption` 的实施细节事实源，记录吸纳范围、阶段路线图、公共契约变化、Step 0 证据、验证方式、完成条件、风险和回滚。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。输出包契约以 [PDF 输出包目录结构计划](pdf-output-package-layout.md) 为准。自动化流水线总体契约以 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

从 marker-pdf-workflow 吸纳以下可复用设计：

1. **review.md 段级汇总表**：在页级明细前增加全量段级汇总，让用户先看全貌再深入具体页。
2. **探针报告（Probe Report）机制**：固化为项目治理规范，后续涉及新技术方案时先写探针报告再实施。
3. **分步进度输出 + 单步耗时统计**：`pdf-auto` 增加步骤编号（`[1/N]`）和每步耗时。
4. **图片路径幂等性验收**：将图片幂等性作为输出包的显式验收项。

## 非目标

- 不迁移 marker 的 Python 单文件实现方式（本项目 Bash 多脚本拆分更适合独立复用和 MCP 包装）。
- 不引入 marker 的 `--retry-failed` 机制（本项目已有 `pdf-rerun` 独立脚本和 `pdf-auto` 的重跑闭环）。
- 不改变 MinerU 解析引擎。
- 不新增 MCP 工具（当前 `run_pdf_auto` 边界不变）。
- 不引入 marker 的 Python 依赖链（PyMuPDF、requests 等）。
- 不复制 marker 的 token 化逻辑（本项目已验证覆盖率算法与 MinerU `content_list_v2.json` 匹配）。

## 不变量

- 原始 PDF 不被修改或删除。
- CLI 和 MCP JSON 输出保持向后兼容。
- 现有 `PDF_AUTO_JSON=1` / `PDF_VALIDATE_JSON=1` 的 JSON 结构不删除字段。
- review.md 的页级明细表格列不减少，只新增段级汇总节。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。
- 同一事实只在计划或 ADR 中定义一次。

## 影响模块或文件

- `scripts/pdf-auto`（段级汇总、分步进度输出）
- `docs/PLAN_MAP.md`
- `docs/plans/automated-pdf-pipeline.md`
- `docs/plans/pdf-output-package-layout.md`（图片幂等性验收项）
- `README.md`（段级汇总和进度输出说明）

## 公共契约变化

### 1. review.md 段级汇总表

在现有页级明细前增加全量段级汇总表，参考 marker 设计：

```markdown
# 人工兜底清单

生成时间: 2026-06-29 10:30
原始 PDF: /path/to/demo20.pdf
分段目录: /path/to/segments
阈值: 0.82

## 段级汇总

| 分段 | 页码范围 | 段级状态 | 可重跑 | 需复核页数 | 页级分布 |
|------|----------|----------|--------|-----------|----------|
| p0000-0009 | 1-10 | `review_only` | 否 | 7 | passed:3, review_only:7 |
| p0010-0019 | 11-20 | `needs_review` | 是 | 3 | passed:7, needs_review:3 |
| p0020-0029 | 21-30 | `passed` | 否 | 0 | passed:10 |

## 需复核分段
...（现有表格保留）
```

**与现有输出对比**：

| 维度 | 现有 | 吸纳后 |
|------|------|--------|
| 段级信息 | 仅列需复核段 | 先列全量段级汇总，再列需复核段详情 |
| 可重跑标记 | 无 | 显示每段是否 `rerunnable` |
| 页级分布 | 仅在逐页详情中可查 | 段级汇总一目了然 |
| 人工审核约定 | 无 | 增加 `pass`/`fix_md`/`rerun` 约定说明 |

### 2. 探针报告机制

固化为治理规范，不改变代码。规范内容：

- 涉及新技术方案（外部 API、新版 MinerU 参数、文件格式）时，必须先写探针报告再实施。
- 探针报告最低内容：请求/响应结构、分页/分隔格式、资源表达方式、基础指标试算、对实施的约束。
- 探针报告存放位置：`docs/reports/<topic>-probe.md`。
- 参考样例：[marker-demo5-probe.md](../../../marker-pdf-workflow/docs/reports/marker-demo5-probe.md)。

### 3. 分步进度输出 + 单步耗时

`pdf-auto` 控制台输出增加步骤编号和每步耗时：

```
[1/5] 验证分段覆盖率 (阈值: 0.82)
  → 通过: 8, 需复核: 2
  → 耗时 2.3s

[2/5] 重跑可疑段 (effort: high)
  p0001-0010: rerun ... OK (1.2s)
  → 成功重跑: 1, 跳过: 1
  → 耗时 15.8s

[3/5] 二次验证
  → 通过: 1, 仍可疑: 1
  → 耗时 1.8s
```

`PDF_AUTO_JSON=1` 模式下不输出步骤进度（保持 JSON 纯净）。

### 4. 图片幂等性验收

在 [PDF 输出包目录结构计划](pdf-output-package-layout.md) 的验证方式中增加图片幂等性检查：

- 连续运行两次后 `images/` 图片数不变。
- 连续运行两次后不出现重复前缀或重复文件名。
- Markdown 图片引用路径在重跑后仍正确。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|------|------|----------|----------|------|
| 阶段 0 | 固化 Step 0 证据 | 本计划已记录 | 确认当前 review.md、进度输出和治理文档基线 | 待实施 |
| 阶段 1 | review.md 段级汇总表 | 阶段 0 完成 | 全量段级汇总表 + 人工审核约定 + 向后兼容 | 候选 |
| 阶段 2 | 探针报告机制治理化 | 阶段 1 完成 | `docs/reports/` 目录就绪、探针模板到位 | 候选 |
| 阶段 3 | 分步进度输出 + 耗时统计 | 阶段 1 完成 | `pdf-auto` 控制台输出步骤编号和耗时 | 候选 |
| 阶段 4 | 图片幂等性验收 + 治理收尾 | 阶段 1-3 完成 | 验证命令、治理检查和 PLAN_MAP 同步 | 候选 |

## 当前阶段

阶段 0（Step 0 证据固化）。

### Step 0 证据

#### review.md 基线

当前 `scripts/pdf-auto` 的 review.md 结构（来自两处内联 Python 代码，行 438–530 和 800–860）：

- 标题：`# 人工兜底清单`
- 元信息：生成时间、原始 PDF、分段目录、阈值
- 段级表格：**仅列需复核段**（`decision` 为 `review_only` 或 `rerun`），列名为「分段｜页码范围｜覆盖率｜处理建议｜原因」
- 逐页详情：按需复核段分组，每段一个 `## {seg_name} 逐页详情` 节
- **无**：全量段级汇总、可重跑标记、人工审核约定

#### 进度输出基线

当前 `pdf-auto` 的步骤输出（行 230–260 附近）：

```
验证分段覆盖率... 8/10 通过，2 段可疑/需复核
重跑可疑段 (high)... p0001-0010: done
二次验证...
```

- 无步骤编号（`[1/N]`）
- 无单步耗时
- 无结构化日志（如 `→ 通过: 8, 需复核: 2`）

#### 治理文档基线

- 无 `docs/reports/` 目录
- 无探针报告机制
- 验收记录内嵌在专项计划中（如 `coverage-validation-optimization.md#验收记录2026-06-28`）

#### GitNexus 影响分析

`scripts/pdf-auto` 文件层面：
- 风险：LOW，图谱无上游符号调用。
- 受影响执行流：0（`pdf-auto` 不在任何 execution flow 中）。
- 实际影响范围：CLI 用户和 MCP `run_pdf_auto` 的 `review_markdown` 返回字段。

`scripts/pdf-merge` 文件层面：
- 风险：LOW。
- 受影响执行流：0。

## 验证方式

### 阶段 1（review.md 段级汇总表）

```bash
# 语法检查和 JSON 模式兼容
bash -n scripts/pdf-auto
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo20/demo20.pdf demo20-output/segments > /tmp/review-test.json
python3 -m json.tool /tmp/review-test.json > /dev/null

# 验证 review.md 结构
grep -c "段级汇总" /path/to/review.md     # ≥ 1
grep -c "人工审核结论约定" /path/to/review.md  # ≥ 1
grep -c "可重跑" /path/to/review.md       # ≥ 1（段级汇总表列名）
```

### 阶段 2（探针报告机制）

```bash
# docs/reports/ 目录存在
ls docs/reports/

# 治理检查通过
python3 scripts/check_plan_governance.py .
```

### 阶段 3（分步进度输出）

```bash
# 非 JSON 模式输出包含步骤编号
scripts/pdf-auto pdf/demo5/demo5.pdf demo5-output/segments 2>&1 | grep -E "\[[0-9]+/[0-9]+\]"

# JSON 模式不输出步骤进度（stdout 为纯 JSON）
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf demo5-output/segments 2>/dev/null | python3 -m json.tool > /dev/null
```

### 阶段 4（图片幂等性验收 + 治理收尾）

```bash
# 图片幂等性
python3 -c "
from pathlib import Path
import os
# 连续跑两次，对比 images/ 内容
"

# 全量验证
bash -n scripts/pdf-auto
bash -n scripts/pdf-merge
cd mcp/server && npm run build
python3 scripts/check_plan_governance.py .
git diff --check
```

## 完成条件

### 全阶段

- review.md 包含全量段级汇总表、可重跑标记和人工审核结论约定。
- `docs/reports/` 目录存在，探针报告模板就绪。
- `pdf-auto` 非 JSON 模式输出步骤编号和每步耗时。
- 图片幂等性验收项已写入阶段 8 验证方式。
- `PDF_AUTO_JSON=1` 和 MCP `run_pdf_auto` 向后兼容。
- `python3 scripts/check_plan_governance.py .` 通过。
- `docs/PLAN_MAP.md` 状态、阻塞项和完成证据已同步。

### 阶段 1 单独完成条件

- review.md 新增「段级汇总」节，列出所有分段（含已通过段）。
- 汇总表包含：分段名、页码范围、段级状态、可重跑、需复核页数、页级分布。
- review.md 新增「人工审核结论约定」节（`pass`/`fix_md`/`rerun`）。
- 现有页级明细表格保留不变。
- JSON 模式输出保持不变。

## 风险和回滚

风险：

- 段级汇总表中"页级分布"字段依赖 `pdf-validate` 输出的 `page_type_summary`，如果验证阶段 JSON 结构变化需同步更新。
- 探针报告机制是治理规范，无强制工具检查，依赖人工遵守。
- 步骤编号输出在 `stderr`，不影响 MCP 的 stdout JSON 读取，但需确保 `PDF_AUTO_JSON=1` 模式下不会意外输出到 stdout。
- 图片幂等性仅作为验收项，不改变现有合并逻辑。

回滚：

- review.md 段级汇总表在现有页级明细前新增，可随时移除该节而不影响后续内容。
- 探针报告机制是纯文档约定，无代码依赖，可随时调整。
- 分步进度输出在 `stderr`，移除不影响任何功能。
- 所有变更均在 `pdf-auto` 和治理文档内，不涉及 `pdf-seg`、`pdf-validate`、`pdf-merge` 的核心逻辑。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|------|----------|-----------------|------|
| 段级汇总表的「页级分布」列格式  | 沿用 marker 的 `{status: count}` 字典格式，如 `passed:3, review_only:7` | 否 | 待确认 |
| 探针报告是否加入治理检查脚本 | 初期不加入，先作为文档约定；后续可加入 `check_plan_governance.py` 做存在性检查 | 否 | 候选 |
| 分步进度输出的步骤编号是否需要动态计算 | 根据实际执行分支决定步骤数（如无重跑则跳过第 2 步），但总步骤数在开始时声明 | 否 | 待实施时确认 |
| `--quiet` 是否需要单独参数 | 初期复用 `PDF_AUTO_JSON=1` 抑制进度输出，不新增参数 | 否 | 已确认 |

## 关联 ADR、迁移、spec 或 issue

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)
- [marker-pdf-workflow 项目](../../../marker-pdf-workflow/)
- [marker 设计草案](../../../marker-pdf-workflow/marker_pdf_workflow_draft.md)
- [marker Phase 2 验收报告](../../../marker-pdf-workflow/docs/reports/phase2-acceptance.md)
