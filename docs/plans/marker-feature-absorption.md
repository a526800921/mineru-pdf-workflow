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
| 阶段 0 | 固化 Step 0 证据 | 本计划已记录 | 确认当前 review.md、进度输出和治理文档基线 | 已完成 |
| 阶段 1 | review.md 段级汇总表 | 阶段 0 完成 | 全量段级汇总表 + 人工审核约定 + 向后兼容 | 已完成 |
| 阶段 2 | 探针报告机制治理化 | 阶段 1 完成 | `docs/reports/` 目录就绪、探针模板到位 | 已完成 |
| 阶段 3 | 分步进度输出 + 耗时统计 | 阶段 1 完成 | `pdf-auto` 控制台输出步骤编号和耗时 | 已完成 |
| 阶段 4 | 图片幂等性验收 + 治理收尾 | 阶段 1-3 完成 | 验证命令、治理检查和 PLAN_MAP 同步 | 已完成 |

## 当前阶段

全阶段（0-4）已完成（2026-06-30）。计划状态：已完成。

### Step 0 证据

#### review.md 基线

当前 `scripts/pdf-auto` 的 review.md 结构（来自三处内联 Python 代码：首次直接合并但仍有复核段的分支约行 446–538、首次 `needs_review` 分支约行 555–656、重跑后二次验证仍有问题的分支约行 935–1037）：

- 标题：`# 人工兜底清单`
- 元信息：生成时间、原始 PDF、分段目录、阈值
- 段级表格：**仅列需复核段**（`decision` 为 `review_only` 或 `rerun`），列名为「分段｜页码范围｜覆盖率｜处理建议｜原因」
- 逐页详情：按需复核段分组，每段一个 `## {seg_name} 逐页详情` 节
- **无**：全量段级汇总、可重跑标记、人工审核约定

#### 进度输出基线

当前 `pdf-auto` 的步骤输出（首次验证决策约行 199–248，重跑分支约行 666 以后）：

```
=== 第一次验证 ===
通过: 1 段
需重跑: 0 段
  [pass] p0001-0005: 覆盖率 0.4379 (coverage_ok)
全部通过，开始合并...
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

## 阶段 1 可实施说明

### 阶段 1 完成证据（2026-06-30）

- `pdf-auto` 三个 review 生成分支均已插入段级汇总表和人工审核结论约定。
- demo5 `needs_review` 路径验证：`review.md` 包含 `## 段级汇总`（1 段/6 列）、`## 人工审核结论约定`（3 行）、`## 需复核分段`（保留）、`## 逐页详情`（保留）。
- demo5 `all_passed` 路径验证：JSON 合法，`status: "all_passed"`，`review_markdown: null`。
- `bash -n`、`npm run build`、`check_plan_governance.py` 通过。
- JSON 契约、MCP 工具边界、验证判定口径未变更。

阶段 1 只落地 `review.md` 段级汇总表和人工审核结论约定，不改变 JSON 契约、不改变 MCP 工具边界、不改变验证判定口径。

### 修改范围

代码修改范围限定为 `scripts/pdf-auto` 的 `review.md` 生成逻辑：

- 首次直接合并后仍有复核段的 review 生成分支：约行 446–538。
- 首次验证直接 `needs_review` 的 review 生成分支：约行 555–656。
- 重跑后二次验证仍有问题的 review 生成分支：约行 935–1037。

阶段 1 不修改：

- `scripts/pdf-validate` 的 JSON 字段和判定逻辑。
- `scripts/pdf-seg`、`scripts/pdf-merge`、`scripts/pdf-rerun`。
- MCP `run_pdf_auto` 入参、出参和状态映射。
- `PDF_AUTO_JSON=1` stdout JSON 结构。

### 建议实现方式

优先在 `scripts/pdf-auto` 的内联 Python 中抽出或复制同一套 review 渲染逻辑，确保三处分支生成一致的 `review.md` 结构。

阶段 1 的目标结构：

```markdown
# 人工兜底清单

生成时间: 2026-06-30 21:30
原始 PDF: /abs/path/pdf/demo5/demo5.pdf
分段目录: /abs/path/pdf/demo5/segments
阈值: 0.82

## 段级汇总

| 分段 | 页码范围 | 段级状态 | 可重跑 | 需复核页数 | 页级分布 |
|------|----------|----------|--------|------------|----------|
| p0001-0005 | 1-5 | `review_only` | 否 | 5 | review_only:5 |

## 人工审核结论约定

| 结论 | 含义 |
|------|------|
| `pass` | 人工确认该段无需修改 |
| `fix_md` | 人工直接修正合并 Markdown |
| `rerun` | 人工决定后续重新解析该段 |

## 需复核分段

...（现有表格保留）
```

### 字段映射

段级汇总表字段来源：

| 列 | 来源 | 规则 |
|---|---|---|
| 分段 | `seg["name"]` | 原样输出 |
| 页码范围 | `seg["start_page"]` / `seg["end_page"]` | 1-based 页码范围，格式 `start-end` |
| 段级状态 | `seg["decision"]` 优先，否则 `seg["status"]` | 用反引号包裹 |
| 可重跑 | `seg["rerunnable"]` | `true` 输出“是”，其他输出“否” |
| 需复核页数 | `seg["pages"]` 中 `decision in ("review_only", "rerun")` 或 `status in ("failed", "skipped", "suspicious")` 的页数 | 无页级数据时，如果段本身需复核则记 `1`，否则记 `0` |
| 页级分布 | `seg["pages"]` 中页面 `decision` 或 `status` 计数 | 格式 `passed:3, review_only:7`；无页级数据时使用段级状态 `status:1` |

段级状态建议归一化：

| 原始字段组合 | 段级状态 |
|---|---|
| `decision == "review_only"` | `review_only` |
| `decision == "rerun"` | `rerun` |
| `decision == "pass"` 或 `status == "passed"` | `passed` |
| `status == "failed"` | `failed` |
| `status == "skipped"` | `skipped` |
| 其他 | 原始 `decision` 或 `status` |

### 保留现有内容

阶段 1 必须保留现有页级明细能力：

- 现有“需复核分段”表格不删列。
- 现有逐页详情不删列。
- 现有 `review_only`、`rerun`、`failed`、`skipped` 的处理建议文案不降低信息量。
- 已通过段只进入“段级汇总”，不进入“需复核分段”和逐页详情。

### 验收样本

阶段 1 默认使用 Phase 8 已跑通的输出包样本：

```text
pdf/demo5/demo5.pdf
pdf/demo5/segments/
```

验收时至少覆盖两个返回路径：

1. `needs_review`：`PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments`
2. `all_passed`：`PDF_VALIDATE_THRESHOLD=0.4 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments`

`needs_review` 路径必须生成 `pdf/demo5/review.md`，并包含“段级汇总”“人工审核结论约定”“可重跑”。

`all_passed` 路径的 JSON stdout 必须保持合法，且不要求生成 review；如果因后续样本存在 `review_only` 同时合并的情况生成 review，也必须使用同一结构。

### 阶段 1 完成后同步

阶段 1 完成后需要同步：

- `docs/plans/marker-feature-absorption.md`：阶段 1 状态改为 `已完成`，记录验收证据。
- `docs/PLAN_MAP.md`：`marker-feature-absorption` 当前阶段改为阶段 2 或后续阶段。
- 如 README 中已有 review.md 说明，则补充段级汇总和人工审核结论约定；没有相关说明时不强行新增。

阶段 1 完成前必须运行：

```bash
bash -n scripts/pdf-auto
PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/review-test.json
python3 -m json.tool /tmp/review-test.json > /dev/null
grep -c "段级汇总" pdf/demo5/review.md
grep -c "人工审核结论约定" pdf/demo5/review.md
grep -c "可重跑" pdf/demo5/review.md
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

## 阶段 2 可实施说明

阶段 2 只落地探针报告机制的治理文档和模板，不修改 PDF 解析脚本、不改变 CLI/MCP 契约、不引入运行时依赖。

### 阶段 2 目标

- 明确什么时候必须先写探针报告。
- 固化探针报告的存放位置、命名规则和最低内容。
- 提供可复制的探针报告模板。
- 让后续外部 API、新版 MinerU 参数、文件格式、模型策略等探索有统一证据入口。

### 修改范围

阶段 2 建议修改或新增：

- `docs/plans/marker-feature-absorption.md`：记录阶段 2 完成证据和状态。
- `docs/PLAN_MAP.md`：同步 `marker-feature-absorption` 当前阶段和证据链接。
- `docs/reports/README.md`：说明探针报告目录职责、命名规则、触发条件。
- `docs/reports/probe-template.md`：探针报告模板。

阶段 2 不修改：

- `scripts/*`。
- `mcp/server/*`。
- README 中的用户操作流程，除非后续需要面向用户说明探针报告入口。
- `scripts/check_plan_governance.py`。初期先作为文档约定，不把探针报告纳入强制脚本检查。

### 触发条件

后续工作满足任一条件时，实施前必须先写探针报告：

- 接入外部 API、远端模型服务、HTTP 服务或不稳定第三方能力。
- 尝试新版 MinerU 参数、后端、模型、OCR/VLM 策略或新的环境组合。
- 引入新的输入/输出文件格式、结构化数据格式或图片资源组织方式。
- 改变验证口径、阈值、状态语义、失败处理策略或人工复核策略。
- 需要用真实样本确认性能、内存、准确率、兼容性或幂等性假设。

不需要探针报告的情况：

- 只改错别字、链接、说明文案或治理状态。
- 小范围 bugfix 已有失败复现和明确修复路径。
- 只更新已存在计划中的验收记录，且不改变阶段假设。

### 命名和存放

探针报告统一存放在：

```text
docs/reports/<topic>-probe.md
```

命名规则：

- 使用小写 kebab-case。
- 文件名必须以 `-probe.md` 结尾。
- `<topic>` 应能表达技术对象或实验对象，例如：
  - `mineru-vlm-http-client-probe.md`
  - `image-path-idempotency-probe.md`
  - `toc-entry-validation-probe.md`

### 模板内容

`docs/reports/probe-template.md` 建议内容：

```markdown
# 探针报告：<主题>

## 背景

为什么需要这个探针，关联哪个计划或阶段。

## 问题和假设

- 待验证问题：
- 关键假设：
- 不验证范围：

## 环境和输入

- 日期：
- 仓库版本：
- 命令或入口：
- 样本文件：
- 外部服务或依赖：

## 请求、响应或文件结构

记录关键请求参数、响应字段、文件结构、分页/分段格式、资源路径或错误格式。

## 最小实验

```bash
# 可复现命令
```

## 观察结果

- 成功路径：
- 失败路径：
- 性能/耗时/内存：
- 输出文件：

## 约束和风险

- 对实施的约束：
- 兼容性风险：
- 回滚方式：

## 结论

- 是否建议进入实施：
- 必须同步到哪个计划：
- 后续验证命令：
```

### 阶段 2 验收步骤

实施阶段 2 时执行：

```bash
test -d docs/reports
test -f docs/reports/README.md
test -f docs/reports/probe-template.md
grep -c "触发条件" docs/reports/README.md
grep -c "探针报告" docs/reports/probe-template.md
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 2 完成条件

- `docs/reports/README.md` 已定义目录职责、触发条件、命名规则和最低内容。
- `docs/reports/probe-template.md` 可直接复制用于新探针报告。
- `marker-feature-absorption` 阶段 2 状态更新为 `已完成`，并记录验收证据。
- `PLAN_MAP.md` 同步当前阶段为阶段 3 或后续阶段。
- 没有把历史草案、superpowers 记录或 README 重新设为事实源。

### 阶段 2 完成证据（2026-06-30）

- `docs/reports/README.md`：已定义目录职责、触发条件、命名规则、最低内容和与治理的关系。
- `docs/reports/probe-template.md`：8 个标准章节模板，可直接复制用于新探针报告。
- `docs/reports/` 目录已创建，与 marker-pdf-workflow 参考探针（`marker-demo5-probe.md`）结构对齐。
- 文件验证：
  - `test -d docs/reports` ✅
  - `test -f docs/reports/README.md` ✅
  - `test -f docs/reports/probe-template.md` ✅
  - `grep -c "触发条件" docs/reports/README.md` → `1`
  - `grep -c "探针报告" docs/reports/probe-template.md` → `1`
- `check_plan_governance.py` 通过。GitNexus `detect_changes` 风险 low（纯文档新增）。
- 无脚本、CLI 或 MCP 契约变更。

### 后续衔接

阶段 3（分步进度输出 + 耗时统计）可直接实施；如涉及外部监控或结构化日志协议，则需先写探针报告。

## 阶段 3 可实施说明

阶段 3 只改进 `pdf-auto` 的非 JSON 人类可读进度输出：增加步骤编号、步骤摘要和单步耗时。不得改变 `PDF_AUTO_JSON=1` 的 stdout JSON 契约，不新增 MCP 工具，不改变验证判定口径。

阶段 3 不需要探针报告：本阶段不引入外部 API、新文件格式、远端服务或结构化日志协议，只是在现有 stderr/stdout 人类日志中增加可读进度。

### 修改范围

代码修改范围限定为 `scripts/pdf-auto`：

- `log()` 相关的人类可读输出。
- 第一次验证分支：当前约行 199–264。
- 首次 `merge` 分支：当前约行 258–601。
- 首次 `needs_review` 分支：当前约行 607–775。
- 重跑分支：当前约行 779–883。
- 第二次验证和后续合并 / review 分支：当前约行 885–1218。

阶段 3 不修改：

- `scripts/pdf-validate` JSON 字段和判定逻辑。
- `scripts/pdf-seg`、`scripts/pdf-merge`、`scripts/pdf-rerun`。
- `mcp/server/*`。
- `PDF_AUTO_JSON=1` stdout JSON 结构。
- review.md 内容结构。

实施代码改动前必须按项目 GitNexus 规则对 `scripts/pdf-auto` 相关变更点做影响分析；如果只改本文档，不需要符号影响分析。

### 输出格式

非 JSON 模式下，阶段 3 目标输出格式：

```text
[1/4] 验证分段覆盖率
  → 阈值: 0.82
  → 通过: 0, 需重跑: 0, 需复核: 1
  → 耗时 0.4s

[2/4] 生成人工兜底清单
  → review.md: /abs/path/pdf/demo5/review.md
  → 耗时 0.1s
```

如果进入全部通过路径：

```text
[1/3] 验证分段覆盖率
  → 阈值: 0.4
  → 通过: 1, 需重跑: 0, 需复核: 0
  → 耗时 0.4s

[2/3] 合并 Markdown
  → 输出: /abs/path/pdf/demo5/demo5.md
  → 耗时 0.1s
```

如果进入重跑路径：

```text
[1/5] 验证分段覆盖率
[2/5] 重跑可疑段
[3/5] 二次验证
[4/5] 合并 Markdown
[5/5] 生成人工兜底清单
```

步骤总数可以按实际分支动态确定，但必须在每个步骤输出中保持一致。例如 `needs_review` 直接结束路径可以是 `[1/2]`、`[2/2]`；全部通过路径可以是 `[1/2]`、`[2/2]`；重跑后需要 review 的路径可以是 `[1/4]` 到 `[4/4]`。

### 耗时口径

建议实现两个 Bash helper：

```bash
now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

elapsed_s() {
  python3 - "$1" "$2" <<'PY'
import sys
start = int(sys.argv[1])
end = int(sys.argv[2])
print(f"{(end - start) / 1000:.1f}s")
PY
}
```

要求：

- 单步耗时从该步骤开始到该步骤主要动作完成。
- 耗时输出只进入人类日志，不进入 JSON stdout。
- `PDF_AUTO_JSON=1` 模式下，人类日志仍走 stderr，stdout 只能是最终 JSON。
- 不要求总耗时；如实现总耗时，只能作为人类日志。

### 建议实现步骤

1. 增加轻量日志 helper，例如 `step_start <n> <total> <title>` 和 `step_done <start_ms> [summary...]`。
2. 将当前 `=== 第一次验证 ===` 替换或包裹为 `[1/N] 验证分段覆盖率`。
3. 在第一次验证后输出摘要：通过段数、需重跑段数、需复核段数。
4. 对 `needs_review` 直接结束路径增加“生成人工兜底清单”步骤。
5. 对 `merge` 路径增加“合并 Markdown”步骤；TOC 修复可作为合并步骤内的子日志，不单独计步骤。
6. 对 `rerun` 路径增加“重跑可疑段”“二次验证”“合并 Markdown”或“生成人工兜底清单”步骤。
7. 保留现有关键诊断信息，如段名、覆盖率、失败原因、review 输出路径和合并输出路径。

### 验收样本

阶段 3 默认使用 Phase 8 输出包样本：

```text
pdf/demo5/demo5.pdf
pdf/demo5/segments/
```

必须覆盖两条稳定路径：

1. `needs_review`：`PDF_VALIDATE_THRESHOLD=0.82 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments`
2. `all_passed`：`PDF_VALIDATE_THRESHOLD=0.4 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments`

如果当前样本无法稳定触发重跑路径，重跑路径的步骤编号可通过代码审查确认，后续遇到真实 `rerunnable=true` 样本时补验收记录。

### 阶段 3 验收命令

```bash
bash -n scripts/pdf-auto

PDF_VALIDATE_THRESHOLD=0.82 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-review.log 2>&1 || test "$?" -eq 2
grep -E "\[[0-9]+/[0-9]+\] 验证分段覆盖率" /tmp/pdf-auto-review.log
grep -E "\[[0-9]+/[0-9]+\] 生成人工兜底清单" /tmp/pdf-auto-review.log
grep -E "耗时 [0-9]+\\.[0-9]s" /tmp/pdf-auto-review.log

PDF_VALIDATE_THRESHOLD=0.4 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-pass.log 2>&1
grep -E "\[[0-9]+/[0-9]+\] 验证分段覆盖率" /tmp/pdf-auto-pass.log
grep -E "\[[0-9]+/[0-9]+\] 合并 Markdown" /tmp/pdf-auto-pass.log
grep -E "耗时 [0-9]+\\.[0-9]s" /tmp/pdf-auto-pass.log

PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-review.json 2>/tmp/pdf-auto-review-json.stderr || test "$?" -eq 2
python3 -m json.tool /tmp/pdf-auto-review.json > /dev/null
grep -E "\[[0-9]+/[0-9]+\]" /tmp/pdf-auto-review-json.stderr

PDF_VALIDATE_THRESHOLD=0.4 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-pass.json 2>/tmp/pdf-auto-pass-json.stderr
python3 -m json.tool /tmp/pdf-auto-pass.json > /dev/null
grep -E "\[[0-9]+/[0-9]+\]" /tmp/pdf-auto-pass-json.stderr

cd mcp/server && npm run build
cd ../..
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

JSON 模式验收重点：

- stdout 必须是合法 JSON。
- 步骤编号和耗时只能出现在 stderr。
- MCP 构建通过，证明 `run_pdf_auto` 消费 stdout JSON 不受影响。

### 阶段 3 完成证据（2026-06-30）

- `scripts/pdf-auto` 新增 `now_ms()` / `elapsed_s()` 计时 helper 和 `step_start()` / `step_done()` 步骤 helper。
- `needs_review` 路径（阈值 0.82）：`[1/2] 验证分段覆盖率` → `[2/2] 生成人工兜底清单`，各有 `→ 耗时`。
- `all_passed` 路径（阈值 0.4）：`[1/2] 验证分段覆盖率` → `[2/2] 合并 Markdown`，各有 `→ 耗时`。
- `rerun` 路径：`_step_total` 动态更新为 4（验证→重跑→二验→合并/兜底）。
- JSON 模式：stdout 纯 JSON（`python3 -m json.tool` 验证通过），步骤进度和耗时只出现在 stderr。
- 现有关键诊断信息保留：段名、覆盖率、review/merge 输出路径、TOC 修复日志。
- `bash -n`、`npm run build`、`check_plan_governance.py` 通过。
- JSON/MCP 契约不变。

### 阶段 3 完成条件
- `marker-feature-absorption` 阶段 3 状态更新为 `已完成`，记录验收证据。
- `PLAN_MAP.md` 同步当前阶段为阶段 4 或后续阶段。

### 阶段 3 完成后同步

阶段 3 完成后更新：

- `docs/plans/marker-feature-absorption.md`：记录阶段 3 完成证据，阶段路线图状态改为 `已完成`。
- `docs/PLAN_MAP.md`：当前阶段切到阶段 4。
- 如 README 已描述 `pdf-auto` 控制台输出，可补充步骤编号和耗时说明；没有相关说明时不强行新增。

## 阶段 4 可实施说明

阶段 4 只把图片路径幂等性纳入正式验收，并完成 `marker-feature-absorption` 的治理收尾。优先通过验收脚本或文档化命令证明现有输出包行为稳定；只有验收发现真实漂移时，才进入代码修复。

### 阶段 4 目标

- 明确图片幂等性验收口径：连续运行同一 PDF 输出包时，`images/` 文件集合稳定，Markdown 图片引用稳定。
- 将图片幂等性验收项同步到 [PDF 输出包目录结构计划](pdf-output-package-layout.md)，避免该契约只存在于 marker 吸纳计划中。
- 收尾 `marker-feature-absorption`：阶段 0-4 证据闭环，`PLAN_MAP.md` 状态、当前阶段和完成证据同步。

### 阶段 4 非目标

- 不改变 MinerU 解析引擎或图片抽取策略。
- 不改 MCP `run_pdf_auto` 入参、出参或状态映射。
- 不新增图片重命名规则，除非验收发现当前规则不可幂等。
- 不引入新的外部依赖或独立测试框架。
- 不把图片二进制内容纳入 Git 管理；验收只比较运行样本输出。

### Step 0 证据

阶段 4 实施前先固定图片输出基线：

- 样本：`pdf/demo5/demo5.pdf`
- 分段目录：`pdf/demo5/segments/`
- 输出包：`pdf/demo5/`
- 图片目录：`pdf/demo5/images/`
- 合并 Markdown：`pdf/demo5/demo5.md`

进入实施前执行一次只读盘点：

```bash
find pdf/demo5/images -type f | sort > /tmp/demo5-images.before
grep -oE '!\[[^]]*\]\([^)]+\)' pdf/demo5/demo5.md | sort > /tmp/demo5-image-refs.before
wc -l /tmp/demo5-images.before /tmp/demo5-image-refs.before
```

如果样本当前没有图片文件或 Markdown 图片引用，应在完成证据中记录为“无图片样本，仅覆盖空图片集合幂等性”；后续出现包含图片的真实 PDF 样本时，需要补充一次正向图片幂等性验收。

### 修改范围

优先只修改文档和验收命令：

- `docs/plans/marker-feature-absorption.md`：阶段 4 完成证据和状态收尾。
- `docs/plans/pdf-output-package-layout.md`：补充图片幂等性为输出包验收项。
- `docs/PLAN_MAP.md`：同步计划状态、当前阶段和完成证据链接。
- `README.md`：仅当已有输出包验收说明时，补充图片幂等性命令；没有相关说明时不强行新增。

如果 Step 0 或验收发现图片路径不幂等，再按项目 GitNexus 规则先做影响分析，然后限定修改：

- `scripts/pdf-merge`：Markdown 图片引用重写或复制策略。
- `scripts/pdf-auto`：连续运行时的输出包清理或合并调用顺序。
- `scripts/pdf-seg`：仅在根因明确为图片落盘命名不稳定时考虑。

阶段 4 不修改：

- `scripts/pdf-validate` 覆盖率和状态判定。
- MCP `mcp/server/*` 契约。
- `PDF_AUTO_JSON=1` stdout JSON 结构。
- review.md 段级汇总结构。

### 图片幂等性口径

同一 PDF、同一输出包连续运行两次后，满足以下条件即视为通过：

- `images/` 下相对路径集合一致。
- `images/` 下文件数量一致。
- 不出现重复前缀或连续重跑叠加式文件名，例如 `image_1_1.png`、`image_1_1_1.png` 这类由重跑产生的重复命名。
- 合并 Markdown 中的图片引用集合一致。
- Markdown 图片引用指向的本地文件均存在。
- `manifest.json` 中与 Markdown 和图片相关的路径仍指向当前输出包内文件。

幂等性只比较路径集合和引用有效性，不要求逐字节比较图片内容；如后续发现 MinerU 会重写同名图片但内容等价，本阶段不把它视为失败。

### 建议验收脚本

阶段 4 可先用临时脚本验收，确认口径稳定后再决定是否固化到 `scripts/`：

```bash
set -euo pipefail

pdf="pdf/demo5/demo5.pdf"
segments="pdf/demo5/segments"
package="pdf/demo5"

PDF_VALIDATE_THRESHOLD=0.4 scripts/pdf-auto "$pdf" "$segments" >/tmp/pdf-auto-idem-1.log 2>&1
find "$package/images" -type f -print | sed "s#^$package/##" | sort > /tmp/demo5-images.run1
grep -oE '!\[[^]]*\]\([^)]+\)' "$package/demo5.md" | sort > /tmp/demo5-image-refs.run1

PDF_VALIDATE_THRESHOLD=0.4 scripts/pdf-auto "$pdf" "$segments" >/tmp/pdf-auto-idem-2.log 2>&1
find "$package/images" -type f -print | sed "s#^$package/##" | sort > /tmp/demo5-images.run2
grep -oE '!\[[^]]*\]\([^)]+\)' "$package/demo5.md" | sort > /tmp/demo5-image-refs.run2

diff -u /tmp/demo5-images.run1 /tmp/demo5-images.run2
diff -u /tmp/demo5-image-refs.run1 /tmp/demo5-image-refs.run2

python3 - <<'PY'
from pathlib import Path
import re

package = Path("pdf/demo5")
md = package / "demo5.md"
refs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md.read_text())
missing = [ref for ref in refs if not (package / ref).exists()]
if missing:
    raise SystemExit("missing image refs: " + ", ".join(missing))

names = [p.name for p in (package / "images").glob("*") if p.is_file()]
stacked = [name for name in names if re.search(r'(_\d+){3,}\.', name)]
if stacked:
    raise SystemExit("suspicious duplicate image names: " + ", ".join(stacked))
print(f"image refs ok: {len(refs)}, images: {len(names)}")
PY
```

如果 `pdf/demo5` 不含图片，替换为最近一次包含图片的真实输出包，并在完成证据中记录样本路径。

### 阶段 4 验收命令

```bash
# 图片幂等性验收
# 使用上方建议验收脚本，或等价命令，记录 run1/run2 diff 为空。

# 既有契约回归
bash -n scripts/pdf-auto
bash -n scripts/pdf-merge
PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-review.json 2>/tmp/pdf-auto-review.stderr || test "$?" -eq 2
python3 -m json.tool /tmp/pdf-auto-review.json >/dev/null
PDF_VALIDATE_THRESHOLD=0.4 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/pdf-auto-pass.json 2>/tmp/pdf-auto-pass.stderr
python3 -m json.tool /tmp/pdf-auto-pass.json >/dev/null

# MCP 和治理
cd mcp/server && npm run build
cd ../..
python3 scripts/check_plan_governance.py .
git diff --check
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 4 完成证据（2026-06-30）

- 图片幂等性验收口径已同步到 `pdf-output-package-layout.md`（完成判定 > 图片幂等性）。
- demo5 幂等性验证：连续两次 `pdf-auto` 运行，`images: 0→0`（无漂移）、`refs: 0→0`（无新增引用）、无缺失引用、无叠加式文件名。
- demo5 当前为无图片 PDF 样本，本阶段已覆盖空图片集合幂等性；含图片正向样本未覆盖，作为后续测试缺口记录。
- `bash -n scripts/pdf-auto`、`bash -n scripts/pdf-merge`、JSON needs_review/pass 回归、`npm run build`、`check_plan_governance.py`、`git diff --check`、GitNexus `detect_changes` 均通过。无脚本/CLI/MCP 变更。

### 阶段 4 完成条件

- 图片幂等性验收口径已进入 `pdf-output-package-layout.md`，后续输出包验收有明确检查项。
- 当前仓库样本连续两次运行未产生图片文件集合或 Markdown 图片引用漂移。
- JSON/MCP 契约回归通过，阶段 4 没有引入脚本、CLI 或 MCP 行为变更。
- `marker-feature-absorption` 阶段 4 状态为 `已完成`，`PLAN_MAP.md` 完成证据指向阶段 4。
- 含图片真实样本的正向幂等性验证未覆盖，后续取得样本后补充验收记录。

### 阶段 4 完成后同步

阶段 4 完成后更新：

- `docs/plans/marker-feature-absorption.md`：阶段路线图状态改为 `已完成`，记录阶段 4 完成证据。
- `docs/plans/pdf-output-package-layout.md`：输出包验收方式包含图片幂等性。
- `docs/PLAN_MAP.md`：`marker-feature-absorption` 状态改为 `已完成`，完成证据指向阶段 4。
- 如 README 已描述输出包验证，补充图片幂等性验收命令；没有相关段落时不强行扩写。

## 验证方式

### 阶段 1（review.md 段级汇总表）

```bash
# 语法检查和 JSON 模式兼容
bash -n scripts/pdf-auto
PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments > /tmp/review-test.json
python3 -m json.tool /tmp/review-test.json > /dev/null

# 验证 review.md 结构
grep -c "段级汇总" pdf/demo5/review.md     # ≥ 1
grep -c "人工审核结论约定" pdf/demo5/review.md  # ≥ 1
grep -c "可重跑" pdf/demo5/review.md       # ≥ 1（段级汇总表列名）
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
scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments 2>&1 | grep -E "\[[0-9]+/[0-9]+\]"

# JSON 模式不输出步骤进度（stdout 为纯 JSON）
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments 2>/dev/null | python3 -m json.tool > /dev/null
```

### 阶段 4（图片幂等性验收 + 治理收尾）

```bash
# 图片幂等性
# 详见“阶段 4 可实施说明 / 阶段 4 验收命令”，连续跑两次并对比 images/ 和 Markdown 图片引用。

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
| 分步进度输出的步骤编号是否需要动态计算 | 根据实际执行分支决定步骤数（如无重跑则跳过第 2 步），但总步骤数在开始时声明 | 否 | 已确认 |
| `--quiet` 是否需要单独参数 | 初期复用 `PDF_AUTO_JSON=1` 抑制进度输出，不新增参数 | 否 | 已确认 |

## 关联 ADR、迁移、spec 或 issue

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)
- [marker-pdf-workflow 项目](../../../marker-pdf-workflow/)
- [marker 设计草案](../../../marker-pdf-workflow/marker_pdf_workflow_draft.md)
- [marker Phase 2 验收报告](../../../marker-pdf-workflow/docs/reports/phase2-acceptance.md)
