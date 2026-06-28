# 计划：最小自动化执行手册

## 背景

在完整自动化和 MCP 接入完成前，用户需要一套可手动执行、可复现的最小流程，用来完成当前 PDF 的分段解析、验证和合并。

## 事实源职责

本文档是 `minimal-automation-runbook` 的实施细节事实源，记录最小人工执行流程、Step 0 证据、验证方式和完成条件。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。自动化闭环和 MCP 契约以 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

记录当前已可执行的最小流程：

```text
分段解析 -> 覆盖率验证 -> 合并 Markdown -> 人工兜底
```

## 非目标

- 不实现自动重跑。
- 不实现 MCP server。
- 不替代完整流水线计划。

## 不变量

- 手册只描述当前脚本已支持的行为。
- 不承诺自动修复所有识别错误。
- 不覆盖 `automated-pdf-pipeline` 中定义的公共契约。

## 影响模块或文件

- `README.md`
- `scripts/pdf-seg`
- `scripts/pdf-validate`
- `scripts/pdf-merge`

## 公共契约变化

无。该计划只记录现有 CLI 使用方式。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 记录最小执行流程 | 基础 CLI 脚本存在 | 用户可按文档完成流程 | 已完成 |

## 当前阶段

### 范围

当前阶段已完成，范围是文档化最小人工执行流程。

### 实施步骤

1. 记录 `pdf-seg` 分段解析命令。
2. 记录 `pdf-validate` 验证命令。
3. 记录 `pdf-merge` 合并命令。
4. 记录可疑段进入人工兜底的标准。

### Step 0 证据

- `scripts/pdf-seg --help` 可运行。
- `scripts/pdf-validate --help` 可运行。
- `scripts/pdf-merge --help` 可运行。
- 191 页说明书样本已证明分段运行比单次全量更稳定。

### 验证方式

```bash
cd /Users/jafish/Documents/work/mineru-pdf-workflow

scripts/pdf-seg --help
scripts/pdf-validate --help
scripts/pdf-merge --help
python3 scripts/check_plan_governance.py .
```

### 完成条件

- 最小流程文档存在。
- 脚本帮助命令通过。
- 计划治理检查通过。

## 一键人工执行版

假设 PDF 路径为：

```text
/path/to/manual.pdf
```

执行：

```bash
cd /Users/jafish/Documents/work/mineru-pdf-workflow

scripts/pdf-seg /path/to/manual.pdf
```

验证：

```bash
scripts/pdf-validate \
  /path/to/manual.pdf \
  /path/to/manual-mineru-segments
```

如果全部通过：

```bash
scripts/pdf-merge /path/to/manual-mineru-segments
```

如果存在可疑分段：

1. 记录可疑分段，例如 `p0000-0019`。
2. 用高精度重跑对应页段。
3. 再次执行验证。
4. 仍失败则进入人工兜底。

## 自动化控制逻辑

伪代码：

```text
parse_segments(pdf, effort=medium)
report = validate_segments(pdf, segments_dir)

if report.passed:
    merge_segments(segments_dir)
    exit success

for segment in report.suspicious_segments:
    rerun_segment(pdf, segment.start, segment.end, effort=high)

report2 = validate_segments(pdf, segments_dir)

if report2.passed:
    merge_segments(segments_dir)
    exit success

merge_segments(segments_dir)
create_review_report(report2)
exit needs_manual_review
```

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| - | - | 否 | 已延后 |

## 风险和回滚

风险：

- 用户可能把未完成的分段目录拿去合并。
- 验证覆盖率不能发现所有图片和表格问题。

回滚：

- 删除合并文件后重新执行 `scripts/pdf-merge`。
- 删除单个分段目录后重新跑对应页段。

## 关联 ADR、迁移、spec 或 issue

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
