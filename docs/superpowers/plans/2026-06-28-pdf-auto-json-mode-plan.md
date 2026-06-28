# pdf-auto JSON 模式实施计划

> 归档说明：本 superpowers 实施计划已合并到正式治理计划 [自动化 PDF 解析流水线](../../plans/automated-pdf-pipeline.md)。当前状态、依赖、证据索引以 [PLAN_MAP](../../PLAN_MAP.md) 为准；字段方案、完成条件和验证结果以正式专项计划为准。本文件只保留为历史实施记录。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `scripts/pdf-auto` 新增 `PDF_AUTO_JSON=1` 环境变量，使其输出结构化 JSON 到 stdout，供 MCP server 消费。

**Architecture:** 纯增量改动，仅修改 `scripts/pdf-auto`。遵循 `pdf-validate` 已有的 `PDF_VALIDATE_JSON=1` 模式：JSON 模式时人读日志写 stderr，JSON 写 stdout。在每个退出点显式调用 `emit_json()`，针对内联 Python 错误使用 `|| { emit_json "error" 1; exit 1; }` 捕获。不使用 EXIT trap（会与脚本已有的两处 `trap ... EXIT` 冲突）。

**Tech Stack:** bash 3.2+ (macOS 默认), Python 3 (内联脚本), jq 仅用于测试验证

## Global Constraints

- 默认行为不变：不设 `PDF_AUTO_JSON` 时输出和现在完全一致
- 退出码不变：0=全部通过，1=脚本错误，2=合并完成但有段需人工复核
- `set -euo pipefail` 下不能有未捕获的错误
- JSON 输出必须在 stdout，人类可读日志在 stderr
- `merged_markdown` / `review_markdown` 字段存放绝对文件路径，非文件内容

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `scripts/pdf-auto` (修改) | 新增 JSON 模式基础设施 + 所有退出点 JSON 输出 |
| `scripts/pdf-auto` | 唯一改动文件，无新增文件 |

---

### Task 1: 添加 JSON 模式基础设施

**Files:**
- Modify: `scripts/pdf-auto:1-46`

**Interfaces:**
- Consumes: 无（此任务最先执行）
- Produces:
  - `json_mode` — bash 变量，"1" 或 "0"
  - `_rerun_names_file` — 临时文件路径，记录重跑段名称（一行一个）
  - `log()` — bash 函数，JSON 模式写 stderr，否则写 stdout
  - `emit_json(status, exit_code, merged_path, review_path, validate_tmp)` — 输出 JSON 到 stdout

> **trap 说明：** 原脚本在第 63 行和第 183 行有 `trap ... EXIT`，用于清理 `$validate_tmp` / `$validate2_tmp`。`_rerun_names_file` 的清理通过追加到这两个已有 trap 实现，详见 Task 2 Step 8。

- [ ] **Step 1: 在脚本顶部（`set -euo pipefail` 之后、`usage()` 之前）添加变量和 helper 函数**

在 `set -euo pipefail` 行（第 2 行）之后插入以下代码块：

```bash
# --- JSON mode infrastructure ---
json_mode="${PDF_AUTO_JSON:-0}"

# Temp file for rerun segment name tracking (cleanup added to existing traps in Task 2)
_rerun_names_file="$(mktemp)"

# Human-readable log: stderr in JSON mode, stdout otherwise
log() {
  if [[ "$json_mode" == "1" ]]; then
    echo "$@" >&2
  else
    echo "$@"
  fi
}

# Emit final JSON to stdout
emit_json() {
  local status="$1"
  local exit_code="$2"
  local merged_path="${3:-}"
  local review_path="${4:-}"
  local validate_tmp="${5:-}"

  python3 - "$status" "$exit_code" "$merged_path" "$review_path" "$validate_tmp" "$_rerun_names_file" <<'PY'
import json, sys

status = sys.argv[1]
exit_code = int(sys.argv[2])
merged = sys.argv[3] if sys.argv[3] else None
review = sys.argv[4] if sys.argv[4] else None

# Read rerun names
rerun_names = set()
rerun_names_file = sys.argv[6]
if rerun_names_file:
    try:
        with open(rerun_names_file) as f:
            rerun_names = {line.strip() for line in f if line.strip()}
    except Exception:
        pass

# Read validation JSON to get rerun segment statuses
rerun_segments = []
validate_tmp = sys.argv[5]
if validate_tmp and rerun_names:
    try:
        with open(validate_tmp) as f:
            report = json.load(f)
        for seg in report.get("segments", []):
            if seg["name"] in rerun_names:
                rerun_segments.append({"name": seg["name"], "status": seg["status"]})
    except Exception:
        pass

output = {
    "status": status,
    "exit_code": exit_code,
    "merged_markdown": merged,
    "review_markdown": review,
    "rerun_segments": rerun_segments,
}
json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
PY
}
# --- end JSON mode infrastructure ---
```

> **注意：** 此处不设置 EXIT trap。原脚本第 63 行和第 183 行已有 `trap ... EXIT`（清理临时文件），再加 trap 会冲突。内联 Python 的错误处理在 Task 2 中通过 `|| { emit_json ...; exit 1; }` 显式捕获。

- [ ] **Step 2: 更新 `usage()` 函数，文档化 `PDF_AUTO_JSON=1`**

在 usage() 的「可选环境变量」部分末尾，`EOF` 之前添加：

```bash
  PDF_AUTO_JSON=1                输出机器可读 JSON（stdout），人类可读信息改到 stderr
```

修改后的 usage() 中可选环境变量区域应变为：

```bash
可选环境变量:
  PDF_VALIDATE_THRESHOLD=0.82    覆盖率阈值
  MINERU_RERUN_EFFORT=high       重跑精度
  PDF_AUTO_MERGE_OUTPUT           合并输出路径（默认自动推导）
  PDF_AUTO_JSON=1                输出机器可读 JSON（stdout），人类可读信息改到 stderr
```

- [ ] **Step 3: 验证脚本语法仍然有效**

```bash
bash -n scripts/pdf-auto
```
Expected: 无输出（语法正确）

- [ ] **Step 4: 验证 `--help` 仍然可用且显示新选项**

```bash
scripts/pdf-auto --help
```
Expected: 显示 usage 信息，包含 `PDF_AUTO_JSON=1` 说明

- [ ] **Step 5: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add JSON mode infrastructure (env var, log helper, emit_json)"
```

---

### Task 2: 将所有 echo 替换为 log + 在每个退出点调用 emit_json

**Files:**
- Modify: `scripts/pdf-auto:49-317`

**Interfaces:**
- Consumes: `json_mode`, `_rerun_names_file`, `log()`, `emit_json()` (from Task 1)
- Produces: 无新增接口（完整 JSON 输出行为）

- [ ] **Step 1: 将 stderr 错误信息（PDF/目录不存在）改为 log，退出前 emit_json**

找到第 34 行 `echo "错误：找不到 PDF 文件：$pdf" >&2`，它已经是 stderr，无需改动。但在其上一行插入 JSON 模式的 emit：

```bash
if [[ ! -f "$pdf" ]]; then
  if [[ "$json_mode" == "1" ]]; then
    emit_json "error" 1 "" "" ""
  fi
  echo "错误：找不到 PDF 文件：$pdf" >&2
  exit 1
fi
```

同样处理第 38-39 行的 segments_dir 检查：

```bash
if [[ ! -d "$segments_dir" ]]; then
  if [[ "$json_mode" == "1" ]]; then
    emit_json "error" 1 "" "" ""
  fi
  echo "错误：找不到分段目录：$segments_dir" >&2
  exit 1
fi
```

- [ ] **Step 2: 将第 49-52 行的人读日志替换为 `log` 调用**

原代码：
```bash
echo "pdf-auto: $pdf_path"
echo "分段目录: $segments_dir"
echo "阈值: $threshold"
echo "重跑精度: $rerun_effort"
```

改为：
```bash
log "pdf-auto: $pdf_path"
log "分段目录: $segments_dir"
log "阈值: $threshold"
log "重跑精度: $rerun_effort"
```

- [ ] **Step 3: 将第 58-59 行验证阶段标题替换为 `log`**

```bash
log
log "=== 第一次验证 ==="
```

- [ ] **Step 4: 包装第一个内联 Python 块（第 69 行），使其 JSON 解析错误时 emit error JSON**

原代码：
```bash
action="$(python3 - "$threshold" "$validate_tmp" <<'PY'
...
PY
)"
```

改为 — 在 `)"` 之后添加 `|| { ... }`：
```bash
action="$(python3 - "$threshold" "$validate_tmp" <<'PY'
...
PY
)" || {
  if [[ "$json_mode" == "1" ]]; then
    emit_json "error" 1 "" "" ""
  fi
  exit 1
}
```

- [ ] **Step 5: 包装第二个内联 Python 块（第 188 行），使其 JSON 解析错误时 emit error JSON**

原代码：
```bash
decision="$(python3 - "$threshold" "$validate2_tmp" <<'PY'
...
PY
)"
```

同样在 `)"` 之后添加：
```bash
decision="$(python3 - "$threshold" "$validate2_tmp" <<'PY'
...
PY
)" || {
  if [[ "$json_mode" == "1" ]]; then
    emit_json "error" 1 "" "" ""
  fi
  exit 1
}
```

- [ ] **Step 6: 确认内联 Python 块中的 `print()` 都使用 stderr**

第一处（第 69-98 行）已经使用 `print(..., file=sys.stderr)` — 无需改动。
第二处（第 188-214 行）已经使用 `print(..., file=sys.stderr)` — 无需改动。

- [ ] **Step 7: 更新第一个 trap（第 63 行）加入 `_rerun_names_file` 清理 + 首次验证全部通过路径添加 emit_json**

第 63 行，原 trap：
```bash
trap 'rm -f "$validate_tmp"' EXIT
```
改为（追加 `_rerun_names_file` 清理，防止提前退出时泄漏临时文件）：
```bash
trap 'rm -f "$validate_tmp" "$_rerun_names_file"' EXIT
```

第 101-106 行，原代码：
```bash
if [[ "$action" == "merge" ]]; then
  merge_output="${PDF_AUTO_MERGE_OUTPUT:-$(dirname "$segments_dir")/${pdf_stem}-merged.md}"
  echo "全部通过，开始合并..."
  echo "合并输出: $merge_output"
  PDF_MERGE_OUTPUT="$merge_output" scripts/pdf-merge "$segments_dir"
  exit 0
fi
```

改为：
```bash
if [[ "$action" == "merge" ]]; then
  merge_output="${PDF_AUTO_MERGE_OUTPUT:-$(dirname "$segments_dir")/${pdf_stem}-merged.md}"
  log "全部通过，开始合并..."
  log "合并输出: $merge_output"
  PDF_MERGE_OUTPUT="$merge_output" scripts/pdf-merge "$segments_dir"
  if [[ "$json_mode" == "1" ]]; then
    emit_json "all_passed" 0 "$merge_output" "" "$validate_tmp"
  fi
  exit 0
fi
```

- [ ] **Step 8: 将中间进度的 echo 替换为 log（重跑相关）**

将第 109、112、149、153、165、167、173 行的 `echo` 替换为 `log`：

```bash
log "需要重跑可疑段，继续执行..."
```

```bash
log
log "=== 重跑可疑段（effort=${rerun_effort}） ==="
```

- [ ] **Step 9: 在重跑循环中，记录重跑段名称到 `$_rerun_names_file`**

在第 165 行原本的 `echo "重跑完成: $name"`（已改为 `log "重跑完成: $name"`）之后添加：

```bash
echo "$name" >> "$_rerun_names_file"
```

同时也记录重跑失败的段（第 168 行 `rerun_failures` 处）：

在 `rerun_failures="$rerun_failures $name"` 之后添加：
```bash
echo "$name" >> "$_rerun_names_file"
```

- [ ] **Step 10: 将第二次验证和合并相关 echo 替换为 log + 更新 trap 清理**

第 179-180 行：
```bash
log
log "=== 第二次验证 ==="
```

第 183 行，原 trap：
```bash
trap 'rm -f "$validate_tmp" "$validate2_tmp"' EXIT
```
追加 `_rerun_names_file` 清理：
```bash
trap 'rm -f "$validate_tmp" "$validate2_tmp" "$_rerun_names_file"' EXIT
```

第 219-220 行：
```bash
log
log "=== 准备合并 ==="
```

第 232 行 echo：
```bash
log "用重跑结果覆盖: ${name} ($(basename "$rerun_md") → $(basename "$original_md"))"
```

第 241-243 行合并部分：
```bash
log
log "=== 合并 ==="
PDF_MERGE_OUTPUT="$merge_output" scripts/pdf-merge "$segments_dir"
log "合并完成: $merge_output"
```

> 原脚本第 63 行的 `trap 'rm -f "$validate_tmp"' EXIT` 保持不变（此时 `$_rerun_names_file` 尚未创建，无需清理）。

- [ ] **Step 11: 在「has_issues → review → exit 2」路径添加 emit_json**

原代码第 247-315 行，将 `echo` 替换为 `log`，修复 Python print，并在 `exit 2` 之前添加 emit_json：

```bash
if echo "$decision" | grep -q "^has_issues$"; then
  review_output="$(dirname "$segments_dir")/${pdf_stem}-review.md"

  log
  log "=== 人工兜底清单 ==="

  python3 - "$threshold" "$pdf_path" "$segments_dir" "$review_output" "$validate2_tmp" "$rerun_failures" <<'PY'
# ... (Python 块不变，仅最后一行 print 改为 stderr，见下)
PY

  log "需要人工复核的分段："
  for seg in $(echo "$decision" | grep "^ISSUE:"); do
    log "  $seg"
  done

  if [[ "$json_mode" == "1" ]]; then
    emit_json "merged_with_issues" 2 "$merge_output" "$review_output" "$validate2_tmp"
  fi
  exit 2
fi
```

Python 块（第 253-307 行）中的最后一行 `print(...)` 需要改为 stderr（内联 Python 无法调用 bash `log` 函数）：

将：
```python
print(f"人工兜底清单已生成: {review_path}")
```
改为：
```python
import sys as _sys
print(f"人工兜底清单已生成: {review_path}", file=_sys.stderr)
```

- [ ] **Step 12: 在最后的「all_passed → exit 0」路径添加 emit_json**

脚本末尾第 317 行：
```bash
exit 0
```
改为：
```bash
if [[ "$json_mode" == "1" ]]; then
  emit_json "all_passed" 0 "$merge_output" "" "$validate2_tmp"
fi
exit 0
```

- [ ] **Step 13: 验证语法**

```bash
bash -n scripts/pdf-auto
```
Expected: 无输出

- [ ] **Step 14: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): wire JSON output at all exit points"
```

---

### Task 3: 测试默认行为回归

**Files:**
- 无代码改动（仅测试）

**Interfaces:**
- Consumes: `scripts/pdf-auto`（完整修改后）

- [ ] **Step 1: 验证 `--help` 输出**

```bash
scripts/pdf-auto --help
```
Expected: 显示完整 usage，不出现 JSON 相关内容（因为没设 `PDF_AUTO_JSON`）。

- [ ] **Step 2: 验证无参数时的错误消息**

```bash
scripts/pdf-auto 2>&1 || true
```
Expected: 显示 usage 信息到 stdout（非 JSON），退出码 1。

- [ ] **Step 3（环境依赖）: 如果存在 191 页样本的 segments 目录，运行默认模式回归**

```bash
# 不设 PDF_AUTO_JSON，使用已有样本
scripts/pdf-auto /path/to/191-sample.pdf /path/to/191-sample-mineru-segments
```
Expected: 输出格式与修改前一致（中文日志到 stdout），退出码 0 或 2。

- [ ] **Step 4: Commit 测试记录**

```bash
git add -A
git commit -m "test: verify pdf-auto default behavior unchanged after JSON mode addition"
```

---

### Task 4: 测试 JSON 模式各路径

**Files:**
- 无代码改动（仅测试）

- [ ] **Step 1: 测试 error 路径 — 传入不存在的 PDF**

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto /tmp/nonexistent.pdf /tmp/nonexistent-segments 2>/dev/null | python3 -m json.tool
```
Expected:
```json
{
    "status": "error",
    "exit_code": 1,
    "merged_markdown": null,
    "review_markdown": null,
    "rerun_segments": []
}
```
退出码应为 1。

- [ ] **Step 2: 测试 error 路径 — 传入不存在的 segments 目录**

```bash
# 用一个真实 PDF 但不存在的 segments 目录
PDF_AUTO_JSON=1 scripts/pdf-auto /path/to/real.pdf /tmp/nonexistent-segments 2>/dev/null | python3 -m json.tool
```
Expected: 同上，status=error, exit_code=1。

- [ ] **Step 3: 验证 stderr 在 JSON 模式下仍有日志输出**

```bash
PDF_AUTO_JSON=1 scripts/pdf-auto /tmp/nonexistent.pdf /tmp/nonexistent-segments 2>&1 >/dev/null
```
Expected: stderr 上有 "错误：找不到 PDF 文件" 日志。

- [ ] **Step 4（环境依赖）: 测试 all_passed 路径**

如果存在全部通过的 segments：
```bash
PDF_AUTO_JSON=1 PDF_VALIDATE_THRESHOLD=0.5 scripts/pdf-auto /path/to/sample.pdf /path/to/sample-segments > /tmp/test_output.json 2>/dev/null
python3 -m json.tool /tmp/test_output.json
```
Expected:
```json
{
    "status": "all_passed",
    "exit_code": 0,
    "merged_markdown": "/absolute/path/to/merged.md",
    "review_markdown": null,
    "rerun_segments": []
}
```

- [ ] **Step 5（环境依赖）: 测试 merged_with_issues 路径**

如果存在可疑段的样本（阈值设很低以触发重跑）：
```bash
PDF_AUTO_JSON=1 PDF_VALIDATE_THRESHOLD=0.99 scripts/pdf-auto /path/to/sample.pdf /path/to/sample-segments > /tmp/test_output.json 2>/dev/null
python3 -m json.tool /tmp/test_output.json
```
Expected: status=merged_with_issues, exit_code=2, review_markdown 非 null, rerun_segments 非空。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test: verify pdf-auto JSON mode output for all paths"
```

---

### Task 5: 更新文档

**Files:**
- Modify: `docs/plans/automated-pdf-pipeline.md:113-119`（更新 JSON summary 状态）
- Modify: `mcp/README.md`（如有，更新 MCP 接入设计中对 pdf-auto 的描述）

- [ ] **Step 1: 更新自动化流水线计划文档**

在 `docs/plans/automated-pdf-pipeline.md` 的阶段 4 契约决策部分，将 JSON summary 状态从"推荐"改为"已实施"。

找到第 113 行附近：
```markdown
推荐先补 `pdf-auto` 的 JSON summary 模式：
```
改为：
```markdown
已实施 `pdf-auto` 的 JSON summary 模式（`PDF_AUTO_JSON=1`）：
```

- [ ] **Step 2: 更新未决问题表**

在未决问题表中，将 `pdf-auto 暂无 JSON summary` 的状态从"待实施"改为"已完成"。

- [ ] **Step 3: Commit**

```bash
git add docs/plans/automated-pdf-pipeline.md
git commit -m "docs: mark pdf-auto JSON summary as implemented"
```
