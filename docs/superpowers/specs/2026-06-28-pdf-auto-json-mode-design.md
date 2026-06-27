# pdf-auto JSON 模式设计

## 背景

`scripts/pdf-auto` 是 MinerU PDF 自动处理流水线的编排脚本，串联"验证→重跑→再验证→合并→兜底"闭环。阶段 4 需要把它包装为 MCP tool，但 MCP server 不应解析中文日志。因此需要新增结构化 JSON 输出模式。

`scripts/pdf-validate` 已有 `PDF_VALIDATE_JSON=1` 先例：JSON 写 stdout，人读日志写 stderr。本设计完全遵循同一模式。

## 设计决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 开关方式 | `PDF_AUTO_JSON=1` 环境变量 | 和 `PDF_VALIDATE_JSON=1` 一致 |
| JSON 输出位置 | stdout | MCP server 从 stdout 读取，不解析日志 |
| 人读日志位置 | stderr | 终端用户仍能看到进度 |
| merged/review 字段 | 文件路径 | JSON 轻量，MCP server 按需读文件 |
| rerun_segments | 名称 + 最终验证状态 | 足够 MCP 判断结果，不需要覆盖率/耗时 |
| status 字段 | 枚举字符串 | MCP 直接 switch，无需映射数字 |

## JSON Schema

```json
{
  "status": "all_passed | merged_with_issues | error",
  "exit_code": 0 | 2 | 1,
  "merged_markdown": "/absolute/path/to/merged.md | null",
  "review_markdown": "/absolute/path/to/review.md | null",
  "rerun_segments": [
    {"name": "p0000-0019", "status": "passed | suspicious | failed"}
  ]
}
```

### 状态-退出码映射

| 场景 | status | exit_code | merged_markdown | review_markdown |
|---|---|---|---|---|
| 首次验证全部通过 | `all_passed` | 0 | 合并文件路径 | null |
| 重跑后全部通过 | `all_passed` | 0 | 合并文件路径 | null |
| 重跑后仍有可疑段 | `merged_with_issues` | 2 | 合并文件路径 | review 文件路径 |
| 脚本错误（如缺参数） | `error` | 1 | null | null |

### rerun_segments 示例

```json
[
  {"name": "p0000-0019", "status": "passed"},
  {"name": "p0040-0059", "status": "suspicious"}
]
```

所有被重跑的段都出现在此数组中。`status` 反映二次验证后的最终结果。

## 实现方式

### 改动范围

仅修改 `scripts/pdf-auto` 一个文件。

### 改动点

1. **usage()** — 文档化 `PDF_AUTO_JSON=1`
2. **日志输出** — JSON 模式下 `echo` 全部追加 `>&2`
3. **JSON 累积** — 关键决策点追加状态到临时 JSON 文件（路径、重复段信息等）
4. **末尾输出** — 在 `exit` 之前，组装完整 JSON 对象输出到 stdout

### 关键约束

- 默认行为不变：不设 `PDF_AUTO_JSON` 时，输出和现在完全一致
- 退出码不变：JSON 模式下仍然返回 0/1/2
- `set -euo pipefail` 下不能有未捕获的错误

## 测试策略

1. **默认行为回归**：不设 `PDF_AUTO_JSON`，运行 191 页样本，输出和之前一致
2. **all_passed 路径**：模拟全部通过的 segments，验证 JSON 输出
3. **merged_with_issues 路径**：模拟有可疑段的场景，验证 review_markdown 和 rerun_segments
4. **error 路径**：传入不存在的 PDF，验证 status=error, exit_code=1
5. **JSON 有效性**：`PDF_AUTO_JSON=1 ... | python3 -m json.tool` 验证输出合法
