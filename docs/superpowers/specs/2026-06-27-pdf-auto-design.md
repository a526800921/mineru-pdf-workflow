# pdf-auto 设计规格

## 背景

阶段 2 已完成 `pdf-validate` 的 JSON 机器可读输出。阶段 3 需要在此基础上实现自动重跑闭环：验证 → 可疑段 high 精度重跑 → 再验证 → 合并 → 人工兜底。

## 目标

实现 `scripts/pdf-auto`，一键完成：

```
验证 → 重跑可疑段 → 再验证 → 合并 → 人工兜底清单
```

## 非目标

- 不重新分段（分段必须已由 `pdf-seg` 生成）。
- 不自动重试超过一次（不循环重跑直到通过）。
- 不处理扫描件 PDF 验证（无文本层段标记 skipped，不阻塞流程）。
- 不在此阶段实现 MCP server。

## 不变量

- 重跑阶段不修改原始分段目录，结果写入独立 `-rerun/` 目录。
- 合并前 pdf-auto 将 `-rerun/` 中的 .md 拷贝覆盖对应原始段目录中的 .md（images/、JSON 等保持不动），此为合并准备步骤。
- 最终一定会合并生成 merge 文件（即使有人工兜底项）。
- 原始 PDF 不被修改或删除。

## 目录结构

```
xxx-mineru-segments/
├── p0000-0019/          ← 原始 medium 结果（保留不动）
├── p0000-0019-rerun/    ← high 重跑结果（如果该段可疑）
├── p0020-0039/          ← 通过的段，没重跑
└── p0040-0059/          ← 另一个通过的段
```

## 流程

```
pdf-auto <pdf> <segments_dir>

  1. pdf-validate（PDF_VALIDATE_JSON=1）
     │
     ├── 全部 passed → 合并（优选 rerun 目录）→ exit 0
     │
     └── 有 suspicious 段
           │
           ▼
  2. 对每个 suspicious 段：
     mineru -s <start> -e <end> --effort high
     -o <segment_dir>-rerun/
     如果 mineru 退出非 0 → 跳过该段（保留原始结果），继续处理下一个
           │
           ▼
  3. pdf-validate（再验证，PDF_VALIDATE_JSON=1）
           │
           ├── 全部 passed → 合并（优选 rerun 目录）→ exit 0
           │
           └── 仍有 suspicious/failed 段
                 │
                 ▼
  4. 合并（优选 rerun 目录）
     + 输出人工兜底清单 → exit 2
```

## 合并优先级

`pdf-auto` 在合并前将 `-rerun/` 结果拷贝到对应原始段目录（覆盖），然后调 `pdf-merge`：

- 有 `pXXXX-YYYY-rerun/` 且包含 .md → 用 rerun 结果覆盖原始段
- 没有 `-rerun/` 或 rerun 失败（无 .md）→ 保留原始段

`pdf-merge` 本身不改动。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 全部通过，合并完成 |
| 1 | 脚本自身错误（PDF 不存在、分段目录空、json 解析失败等） |
| 2 | 合并完成，但有段仍需人工兜底 |

## 人工兜底清单

文件名：`<PDF目录>/<PDF stem>-review.md`

格式：

```markdown
# 人工兜底清单

生成时间: 2026-06-27 19:30
原始 PDF: /path/to/manual.pdf
分段目录: /path/to/manual-mineru-segments
阈值: 0.82

## 可疑分段（需人工核对）

| 分段 | 页码范围 | 覆盖率 | 备注 |
|------|----------|--------|------|
| p0000-0019 | 1-20 | 0.77 | high 重跑后仍未通过阈值 |
| p0080-0099 | 81-100 | - | 重跑失败（mineru 退出非0），使用原始 medium 结果 |
```

备注生成规则：

| 第二次验证 status | reason | 备注 |
|---|---|---|
| `suspicious` | — | `high 重跑后仍未通过阈值 {threshold}` |
| `failed` | `missing_markdown` | `重跑失败（mineru 退出非0），使用原始 medium 结果` |
| `skipped` | `no_text_layer` | `原 PDF 文本层为空，无法验证` |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PDF_VALIDATE_THRESHOLD` | `0.82` | 覆盖率阈值，透传给 pdf-validate |
| `MINERU_RERUN_EFFORT` | `high` | 重跑所用的 mineru effort 级别 |
| `PDF_AUTO_MERGE_OUTPUT` | 自动推导 | 合并文件路径，透传给 pdf-merge |
| `MINERU_BACKEND` | `hybrid-engine` | 继承现有默认值，不额外声明 |
| `MINERU_METHOD` | `auto` | 继承现有默认值 |
| `MINERU_LANG` | `ch` | 继承现有默认值 |

## mineru 重跑参数

重跑时拼接 mineru 命令：

```
mineru \
  -p <pdf_path> \
  -o <segment_dir>-rerun \
  -b <MINERU_BACKEND> \
  -m <MINERU_METHOD> \
  --effort <MINERU_RERUN_EFFORT> \
  -l <MINERU_LANG> \
  -s <start_page> \
  -e <end_page>
```

并发参数沿用 `pdf-seg` 的默认值：
- `MINERU_PDF_RENDER_THREADS=2`
- `MINERU_API_MAX_CONCURRENT_REQUESTS=1`
- `MINERU_PROCESSING_WINDOW_SIZE=8`
- `MINERU_DEVICE_MODE=mps`

## 错误处理

| 场景 | 行为 |
|------|------|
| PDF 不存在 | stderr 报错，exit 1 |
| 分段目录不存在 | stderr 报错，exit 1 |
| 分段目录无 pXXXX-YYYY 子目录 | stderr 报错，exit 1 |
| pdf-validate JSON 解析失败 | stderr 输出原始 stdout，exit 1 |
| mineru 重跑退出非 0 | stderr 告警，跳过该段继续处理下一个 |
| 所有段重跑失败 | 合并原始段 + 输出兜底清单，exit 2 |
| 合并前无有效分段（全部 missing_markdown） | stderr 报错，exit 1 |
| `-rerun/` 目录已存在 | 先删除再重跑（幂等重跑） |

## 公共契约

CLI 契约：

```
scripts/pdf-auto <pdf> <segments_dir>
```

- 输出到 stdout 的内容取决于内部调用的脚本。
- 人工兜底清单写入 `<stem>-review.md`。
- 合并文件写入 `<stem>-merged.md`（或 `PDF_AUTO_MERGE_OUTPUT` 指定路径）。

此为稳定 CLI，后续 MCP `rerun_segments` 工具可包装此脚本或复用其内部逻辑。

## 影响文件

- `scripts/pdf-auto`（新增）
- `docs/PLAN_MAP.md`（更新阶段状态）
- `docs/plans/automated-pdf-pipeline.md`（更新阶段 3 状态）
- `.gitignore`（已有 `*-merged.md` 和 `*-review.md`，无需变更）

## 不影响的文件

- `scripts/pdf`、`scripts/pdf-seg`、`scripts/pdf-validate`、`scripts/pdf-merge`：均不改动
- `mcp/README.md`：`rerun_segments` 契约已定义，本次不更新

## 验证方式

```bash
# 语法检查
bash -n scripts/pdf-auto

# 帮助命令
scripts/pdf-auto --help

# 用 191 页说明书样本验证全流程：
# 1. 确保分段已存在
# 2. 运行 pdf-auto
scripts/pdf-auto \
  /path/to/manual.pdf \
  /path/to/manual-mineru-segments

# 验证退出码和输出文件
# 3. 确认 merged.md 和 review.md 生成
# 4. 确认重跑段目录 p0000-0019-rerun/ 存在

# 治理检查
python3 scripts/check_plan_governance.py .
```

## 完成条件

- `pdf-auto --help` 可运行。
- 全通过场景：不触发重跑，直接合并，exit 0。
- 有可疑段场景：触发重跑，再验证，通过后合并，exit 0。
- 重跑后仍有可疑段：合并 + 输出 review.md，exit 2。
- 重跑失败不阻塞其他段继续处理。
- 计划治理检查通过。

## 关联文档

- [自动化 PDF 解析流水线计划](../plans/automated-pdf-pipeline.md)
- [最小自动化执行手册](../plans/minimal-automation-runbook.md)
- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [MCP 接入设计](../../mcp/README.md)
