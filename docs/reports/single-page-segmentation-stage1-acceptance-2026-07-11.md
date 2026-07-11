# 单页分段迁移阶段 1 验收报告

## 结论

**通过，阶段 1 已完成，可以进入阶段 2。**

专项计划文件已恢复，刚才关于“计划文件缺失”的判断作废。本次结论仅基于恢复后的治理文档和当前代码现状。

本次验收只做只读检查和现状核对；合并产物写入 `/tmp`，没有修改项目原始 PDF/segments/Markdown，也没有启动 MinerU 服务。

## 验收范围

阶段 1 目标：单页默认与旧段级输入兼容。

## 证据

### 1. 单页默认：通过

当前 `scripts/pdf-seg` 已为：

```bash
segment_size="${MINERU_SEGMENT_SIZE:-1}"
```

提交 `9022eb7` 已完成默认值切换，环境变量覆盖仍保留。

### 2. 现有 demo20 仍是多页分段：通过（兼容样本存在）

当前目录：

```text
pdf/demo20/segments/p0001-0010
pdf/demo20/segments/p0011-0020
```

这证明旧的 10 页分段样本仍然存在，可以作为迁移兼容基线；但尚未证明单页输出能够被现有下游完整消费。

### 3. 页级重跑：留待阶段 2

旧多页目录下，`scripts/pdf-rerun` 接收单页参数仍会定位所属段并按段重跑；这属于阶段 2 的待实施范围，不作为阶段 1 的失败项。

`scripts/pdf-auto` 的页级 fallback 同样属于阶段 2/3，不作为阶段 1 的失败项。

### 4. 语法与基础命令：通过

已执行：

```bash
bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun scripts/pdf-merge
scripts/pdf-seg --help
scripts/pdf-rerun --help
scripts/pdf-merge --help
```

结果：Shell 语法检查和帮助命令均通过。这只能证明现有实现可执行，不能证明阶段 1 已实现。

### 5. 治理检查：通过

```bash
python3 scripts/check_plan_governance.py .
```

结果：`计划治理检查通过。`

## 未通过项

| 验收项 | 结果 | 说明 |
|---|---|---|
| 默认分段为单页 | 通过 | 实际默认值为 1 |
| 页码重跑只重跑一页 | 留待阶段 2 | 阶段 1 不包含页级重跑改造 |
| `pdf-auto` 页级 fallback | 留待阶段 2/3 | 阶段 1 不包含质量 fallback 改造 |
| 旧多页段级输入可继续读取 | 通过 | `pdf-validate` 可读取并解析两段旧目录 |
| 输出包和合并契约不回归 | 通过 | 临时路径合并成功，20 个逐页锚点生成成功 |
| `pdf-read-page` 兼容 | 通过 | 第 12 页读取成功 |
| 计划事实源完整 | 通过 | 专项计划已恢复并推进到阶段 2 |

## 下一阶段门禁

阶段 1 已完成。进入阶段 2 前需要：

1. 重新定义 `pdf-rerun <page>` 为精确单页调用。
2. 让 `pdf-auto` 按页生成重跑计划，同时保留旧段名兼容。
3. 固定重跑失败时保留原始页的行为和验证证据。
4. 后续清理 `scripts/pdf-seg --help` 中过时的分段示例。
