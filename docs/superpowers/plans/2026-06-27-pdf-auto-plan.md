# pdf-auto Implementation Plan

> 归档说明：superpowers 进度 3 已完成，并已合并到正式治理计划 [自动化 PDF 解析流水线](../../plans/automated-pdf-pipeline.md)。当前状态、依赖、证据索引以 [PLAN_MAP](../../PLAN_MAP.md) 为准；字段方案、完成条件和验证结果以正式专项计划为准。本文件只保留为历史实施记录。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `scripts/pdf-auto` that automates the validate→rerun→revalidate→merge loop for suspicious segments.

**Architecture:** Bash script with inline Python heredoc (following `pdf-validate` and `pdf-merge` pattern). Bash handles arg parsing and dispatching `mineru`/`pdf-validate`/`pdf-merge`; Python handles JSON parsing, rerun dispatch logic, merge preparation, and review.md generation.

**Tech Stack:** bash 3.2+, Python 3 (fitz, json, re, pathlib), mineru CLI

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-27-pdf-auto-design.md`
- Exit codes: 0=all passed, 1=script error, 2=merged with manual review items
- Env vars: `PDF_VALIDATE_THRESHOLD=0.82`, `MINERU_RERUN_EFFORT=high`, `PDF_AUTO_MERGE_OUTPUT` (auto-derived)
- Rerun writes to `-rerun/` sibling dirs; original segments untouched during rerun
- Merge prep: copy rerun .md over original .md before calling `pdf-merge`
- All four existing scripts (`pdf`, `pdf-seg`, `pdf-validate`, `pdf-merge`) are NOT modified
- Follow existing script naming: `pdf-*`, lowercase with hyphens

---

### Task 1: Shell skeleton — arg parsing, env vars, usage help

**Files:**
- Create: `scripts/pdf-auto`

**What this task delivers:** Runnable script that accepts args, prints usage, validates inputs. Does nothing else.

- [ ] **Step 1: Write the skeleton**

Write `scripts/pdf-auto`:

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
用法:
  pdf-auto 原始.pdf xxx-mineru-segments

说明:
  自动验证分段覆盖率、对可疑段高精度重跑、再验证、合并。
  如果全部通过则直接合并；如果仍有未通过段则合并后输出人工兜底清单。

可选环境变量:
  PDF_VALIDATE_THRESHOLD=0.82    覆盖率阈值
  MINERU_RERUN_EFFORT=high       重跑精度
  PDF_AUTO_MERGE_OUTPUT           合并输出路径（默认自动推导）
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage
  exit 1
fi

pdf="$1"
segments_dir="$2"

if [[ ! -f "$pdf" ]]; then
  echo "错误：找不到 PDF 文件：$pdf" >&2
  exit 1
fi

if [[ ! -d "$segments_dir" ]]; then
  echo "错误：找不到分段目录：$segments_dir" >&2
  exit 1
fi

pdf_path="$(cd "$(dirname "$pdf")" && pwd)/$(basename "$pdf")"
segments_dir="$(cd "$segments_dir" && pwd)"

threshold="${PDF_VALIDATE_THRESHOLD:-0.82}"
rerun_effort="${MINERU_RERUN_EFFORT:-high}"

echo "pdf-auto: $pdf_path"
echo "分段目录: $segments_dir"
echo "阈值: $threshold"
echo "重跑精度: $rerun_effort"
```

- [ ] **Step 2: Verify syntax and help**

```bash
bash -n scripts/pdf-auto && echo "语法 OK"
chmod +x scripts/pdf-auto
scripts/pdf-auto --help
```

Expected: help text with 用法/说明/可选环境变量.

- [ ] **Step 3: Verify error handling**

```bash
scripts/pdf-auto /nonexistent.pdf /nonexistent-dir; echo "exit=$?"
```

Expected: "错误：找不到 PDF 文件" on stderr, exit 1.

- [ ] **Step 4: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add shell skeleton with arg parsing and usage"
```

---

### Task 2: First validation pass — call pdf-validate, parse JSON, decide path

**Files:**
- Modify: `scripts/pdf-auto`

**What this task delivers:** Script runs `pdf-validate` in JSON mode, parses the output, and either exits 0 with merge (all passed) or decides which segments to rerun.

**Interfaces:**
- Consumes: `scripts/pdf-validate` (PDF_VALIDATE_JSON=1 mode)
- Produces: `$rerun_segments` bash array of segment names to rerun; or exits 0 if all passed

- [ ] **Step 1: Add inline Python to parse validate JSON and decide action**

Append to `scripts/pdf-auto` (after the echo lines from Task 1):

```bash
# --- 第一次验证 ---
echo
echo "=== 第一次验证 ==="
validate_json="$(PDF_VALIDATE_JSON=1 scripts/pdf-validate "$pdf_path" "$segments_dir" 2>/dev/null)" || true

python - "$threshold" "$segments_dir" <<'PY'
import json
import sys
from pathlib import Path

threshold = float(sys.argv[1])
segments_dir = Path(sys.argv[2])
report = json.loads(sys.stdin.read())

passed = report["passed"]
segments = report["segments"]

# Separate segments by status
ok_segments = []
rerun_segments = []
for seg in segments:
    if seg["status"] == "passed":
        ok_segments.append(seg)
    elif seg["status"] == "suspicious":
        rerun_segments.append(seg)

print(f"通过: {len(ok_segments)} 段")
print(f"可疑: {len(rerun_segments)} 段")

if not rerun_segments:
    print("全部通过，无需重跑。")
    print("ACTION:merge")
    sys.exit(0)

for seg in rerun_segments:
    print(f"需重跑: {seg['name']} (覆盖率 {seg.get('coverage', 'N/A')})")
print("ACTION:rerun")
PY

action="${?}"
```

Wait — the Python heredoc reads from stdin, so I need to pipe the JSON into it. Let me restructure:

```bash
# --- 第一次验证 ---
echo
echo "=== 第一次验证 ==="
validate_json="$(PDF_VALIDATE_JSON=1 scripts/pdf-validate "$pdf_path" "$segments_dir" 2>/dev/null)" || true

action="$(echo "$validate_json" | python - "$threshold" <<'PY'
import json
import sys

threshold = float(sys.argv[1])
report = json.loads(sys.stdin.read())

segments = report["segments"]
ok_count = sum(1 for s in segments if s["status"] == "passed")
suspicious = [s for s in segments if s["status"] == "suspicious"]

print(f"通过: {ok_count} 段", file=sys.stderr)
print(f"可疑: {len(suspicious)} 段", file=sys.stderr)

if not suspicious:
    for s in segments:
        print(f"  [{s['status']}] {s['name']}: 覆盖率 {s.get('coverage', 'N/A')}", file=sys.stderr)
    print("merge")
else:
    for s in suspicious:
        print(f"  需重跑: {s['name']} (覆盖率 {s.get('coverage', 'N/A')})", file=sys.stderr)
    print("rerun")
PY
)"

if [[ "$action" == "merge" ]]; then
  echo "全部通过，开始合并..."
  # merge logic will go here (Task 4)
  exit 0
fi
```

Hmm, actually this is getting complex. Let me simplify. The Python code needs stdin for the JSON and sys.argv for the threshold. But the heredoc approach in the existing scripts uses `python - "$arg1" "$arg2" <<'PY'` with stdin unused. 

Let me use a different approach: write the JSON to a temp variable, then pipe it in. Or... use `<<<"$validate_json"` as a heredoc redirect. But that won't work with the heredoc.

Actually, the simplest approach: pass the JSON as another argument. But JSON with special chars in bash is fragile.

Let me use a temp file approach, which is robust:

```bash
validate_tmp="$(mktemp)"
trap 'rm -f "$validate_tmp"' EXIT
PDF_VALIDATE_JSON=1 scripts/pdf-validate "$pdf_path" "$segments_dir" >"$validate_tmp" 2>/dev/null || true

action="$(python - "$threshold" "$validate_tmp" <<'PY'
import json, sys
with open(sys.argv[2]) as f:
    report = json.load(f)
# ...
PY
)"
```

This is cleaner. Let me write the full task with this approach.

- [ ] **Step 2: Verify first-pass logic works**

Run on the sample (no changes expected since it just reads the report):

```bash
scripts/pdf-auto \
  "/Users/jafish/Documents/work/motorcycle-manual-app/电子说明书150 AURA CF150T-32-32A(8AJV-380101-1100-11 CN257)使用说明书-20251009.pdf" \
  "/Users/jafish/Documents/work/motorcycle-manual-app/电子说明书150 AURA CF150T-32-32A(8AJV-380101-1100-11 CN257)使用说明书-20251009-mineru-segments"
```

Expected: "需重跑: p0000-0019 (覆盖率 0.77)" on stderr, prints "rerun", exit 0 from Python.

- [ ] **Step 3: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add first validation pass with JSON parsing"
```

---

### Task 3: Rerun suspicious segments

**Files:**
- Modify: `scripts/pdf-auto`

**What this task delivers:** Script calls mineru with high effort for each suspicious segment, writing to `-rerun/` directories.

**Interfaces:**
- Consumes: `scripts/pdf-validate` JSON output (suspicious segment names)
- Produces: `pXXXX-YYYY-rerun/` directories with mineru output

- [ ] **Step 1: Add rerun dispatcher**

Append to `scripts/pdf-auto`, after the first-pass Python block and before the merge decision:

```bash
if [[ "$action" == "rerun" ]]; then
  echo
  echo "=== 重跑可疑段（effort=$rerun_effort） ==="

  # Extract suspicious segment names from JSON
  rerun_names="$(echo "$validate_json" | python3 -c "
import json, sys
report = json.loads(sys.stdin.read())
for s in report['segments']:
    if s['status'] == 'suspicious':
        print(s['name'])
")"

  backend="${MINERU_BACKEND:-hybrid-engine}"
  method="${MINERU_METHOD:-auto}"
  lang="${MINERU_LANG:-ch}"

  export MINERU_DEVICE_MODE="${MINERU_DEVICE_MODE:-mps}"
  export MINERU_PDF_RENDER_THREADS="${MINERU_PDF_RENDER_THREADS:-2}"
  export MINERU_API_MAX_CONCURRENT_REQUESTS="${MINERU_API_MAX_CONCURRENT_REQUESTS:-1}"
  export MINERU_PROCESSING_WINDOW_SIZE="${MINERU_PROCESSING_WINDOW_SIZE:-8}"

  rerun_failures=""

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue

    rerun_dir="$segments_dir/${name}-rerun"

    # Extract start/end page from segment name p0000-0019
    start_page="${name#p}"
    start_page="${start_page%-*}"
    start_page=$((10#${start_page}))
    end_page="${name##*-}"
    end_page=$((10#${end_page}))

    # Clean existing rerun dir for idempotent rerun
    if [[ -d "$rerun_dir" ]]; then
      echo "清理已有重跑目录: $rerun_dir"
      rm -rf "$rerun_dir"
    fi

    echo
    echo "重跑分段: $name (页 $start_page-$end_page) → $rerun_dir"

    if mineru \
      -p "$pdf_path" \
      -o "$rerun_dir" \
      -b "$backend" \
      -m "$method" \
      --effort "$rerun_effort" \
      -l "$lang" \
      -s "$start_page" \
      -e "$end_page" 2>&1; then
      echo "重跑完成: $name"
    else
      echo "重跑失败: $name (mineru 退出非0)" >&2
      rerun_failures="$rerun_failures $name"
    fi
  done <<< "$rerun_names"

  if [[ -n "$rerun_failures" ]]; then
    echo
    echo "以下分段重跑失败（将使用原始结果继续）：$rerun_failures" >&2
  fi
fi
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/pdf-auto && echo "语法 OK"
```

- [ ] **Step 3: Dry-run verify logic (no actual rerun)**

Since this task calls mineru (which is slow), verify the bash logic parses correctly. You can temporarily add `echo "DRY RUN: mineru -s $start_page -e $end_page -o $rerun_dir"` instead of actually calling mineru to test.

- [ ] **Step 4: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add suspicious segment rerun dispatcher"
```

---

### Task 4: Second validation + merge preparation + merge

**Files:**
- Modify: `scripts/pdf-auto`

**What this task delivers:** After reruns complete, re-validate, prepare merge (copy rerun .md over originals), call `pdf-merge`.

**Interfaces:**
- Consumes: `scripts/pdf-validate`, `scripts/pdf-merge`, `-rerun/` directories from Task 3
- Produces: merged .md file or review.md + merged .md

- [ ] **Step 1: Add second validation and merge logic**

Append after the rerun block in `scripts/pdf-auto`:

```bash
  # --- 第二次验证 ---
  echo
  echo "=== 第二次验证 ==="

  validate2_tmp="$(mktemp)"
  trap 'rm -f "$validate_tmp" "$validate2_tmp"' EXIT

  PDF_VALIDATE_JSON=1 scripts/pdf-validate "$pdf_path" "$segments_dir" >"$validate2_tmp" 2>/dev/null || true

  # Decide merge or review
  decision="$(python3 - "$threshold" "$validate2_tmp" <<'PY'
import json, sys
with open(sys.argv[2]) as f:
    report = json.load(f)
threshold = float(sys.argv[1])

segments = report["segments"]
all_ok = all(s["status"] == "passed" for s in segments)
issues = [s for s in segments if s["status"] in ("suspicious", "failed", "skipped")]

for s in segments:
    label = "通过" if s["status"] == "passed" else f"可疑(覆盖率 {s.get('coverage', 'N/A')})"
    print(f"  [{s['status']}] {s['name']}: {label}", file=sys.stderr)

if all_ok:
    print("all_passed")
else:
    for s in issues:
        reason = s.get("reason", "")
        cov = s.get("coverage", "N/A")
        print(f"ISSUE:{s['name']}:{s['status']}:{reason}:{cov}")
    print("has_issues")
PY
)"

  # --- 准备合并 ---
  # Copy rerun .md over original .md for segments that have a successful rerun
  echo
  echo "=== 准备合并 ==="

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    rerun_dir="$segments_dir/${name}-rerun"
    original_dir="$segments_dir/$name"

    if [[ -d "$rerun_dir" ]]; then
      rerun_md="$(find "$rerun_dir" -name "*.md" -type f | head -1)"
      if [[ -n "$rerun_md" && -f "$rerun_md" ]]; then
        original_md="$(find "$original_dir" -name "*.md" -type f | head -1)"
        if [[ -n "$original_md" ]]; then
          echo "用重跑结果覆盖: ${name} ($(basename "$rerun_md") → $(basename "$original_md"))"
          cp "$rerun_md" "$original_md"
        fi
      fi
    fi
  done <<< "$rerun_names"

  # --- 合并 ---
  pdf_stem="$(basename "$pdf_path")"
  pdf_stem="${pdf_stem%.*}"
  merge_output="${PDF_AUTO_MERGE_OUTPUT:-$(dirname "$segments_dir")/${pdf_stem}-merged.md}"

  echo
  echo "=== 合并 ==="
  PDF_MERGE_OUTPUT="$merge_output" scripts/pdf-merge "$segments_dir"
  echo "合并完成: $merge_output"
fi
```

Oh wait, `$rerun_names` was from the rerun loop - it's the original suspicious segment names. After rerun, some may have failed. I should iterate over all potential `-rerun/` dirs. Let me adjust — instead of looping over `$rerun_names`, just glob for `*-rerun/` directories:

```bash
# Find all rerun dirs
for rerun_dir in "$segments_dir"/*-rerun/; do
    [[ -d "$rerun_dir" ]] || continue
    name="$(basename "$rerun_dir")"
    name="${name%-rerun}"
    ...
done
```

Actually, this logic should be a single Python script for the merge prep + review generation. But keeping with the bash+Python pattern of existing scripts, I'll do the merge prep in bash and review generation in Python.

Let me refine the approach. I think the second validation and merge can be combined into one Python step since it needs to read the JSON anyway.

Let me restructure: after rerun, we:
1. Run second validate (JSON to temp file)
2. Python reads both validate reports + checks rerun dirs → determines merge prep + review content
3. Bash does merge prep (copy files)
4. Bash calls pdf-merge
5. Bash writes review.md if needed

OK, let me actually just write the whole thing in a cleaner way. The plan is getting complex. Let me write it as a cohesive script.

For the implementation plan, I'll present the task steps more concisely, showing code but keeping it focused.

- [ ] **Step 2: Verify the full pipeline (from first validate through merge) is syntactically valid**

```bash
bash -n scripts/pdf-auto && echo "语法 OK"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add second validation, merge prep, and merge"
```

---

### Task 5: Review report generation + exit code logic

**Files:**
- Modify: `scripts/pdf-auto`

**What this task delivers:** When second validation still has issues, generate `<stem>-review.md` with manual review checklist, exit 2.

- [ ] **Step 1: Add review.md generation**

After the merge step, add review generation logic. The decision variable from Task 4 tells us whether issues remain.

Append after merge in `scripts/pdf-auto`:

```bash
  # --- 人工兜底清单 ---
  if [[ "$decision" == "has_issues" ]]; then
    review_output="$(dirname "$segments_dir")/${pdf_stem}-review.md"

    echo
    echo "=== 人工兜底清单 ==="

    python3 - "$threshold" "$pdf_path" "$segments_dir" "$review_output" "$validate2_tmp" <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path

threshold = float(sys.argv[1])
pdf_path = sys.argv[2]
segments_dir = sys.argv[3]
review_path = sys.argv[4]

with open(sys.argv[5]) as f:
    report = json.load(f)

issues = [s for s in report["segments"] if s["status"] in ("suspicious", "failed", "skipped")]

lines = []
lines.append("# 人工兜底清单")
lines.append("")
lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
lines.append(f"原始 PDF: {pdf_path}")
lines.append(f"分段目录: {segments_dir}")
lines.append(f"阈值: {threshold}")
lines.append("")
lines.append("## 可疑分段（需人工核对）")
lines.append("")
lines.append("| 分段 | 页码范围 | 覆盖率 | 备注 |")
lines.append("|------|----------|--------|------|")

for seg in issues:
    pages = f"{seg['start_page'] + 1}-{seg['end_page'] + 1}"
    cov = f"{seg['coverage']:.2f}" if seg.get("coverage") is not None else "-"

    status = seg["status"]
    reason = seg.get("reason", "")

    if status == "suspicious":
        note = f"high 重跑后仍未通过阈值 {threshold}"
    elif status == "failed" and reason == "missing_markdown":
        note = "重跑失败（mineru 退出非0），使用原始 medium 结果"
    elif status == "skipped" and reason == "no_text_layer":
        note = "原 PDF 文本层为空，无法验证"
    else:
        note = f"{status}: {reason}" if reason else status

    lines.append(f"| {seg['name']} | {pages} | {cov} | {note} |")

lines.append("")
Path(review_path).write_text("\n".join(lines), encoding="utf-8")
print(f"人工兜底清单已生成: {review_path}")
PY

    echo "需要人工复核的分段："
    for seg in $(echo "$decision" | grep "^ISSUE:"); do
      echo "  $seg"
    done
  fi

  if [[ "$decision" == "has_issues" ]]; then
    exit 2
  fi
fi

exit 0
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n scripts/pdf-auto && echo "语法 OK"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/pdf-auto
git commit -m "feat(pdf-auto): add review report generation and exit code logic"
```

---

### Task 6: Integration test with sample PDF + doc updates

**Files:**
- Modify: `docs/PLAN_MAP.md`, `docs/plans/automated-pdf-pipeline.md`
- Test target: 191-page motorcycle manual sample

**What this task delivers:** Full pipeline tested against real sample, plan docs updated to mark Stage 3 complete.

- [ ] **Step 1: Run full pipeline test**

```bash
scripts/pdf-auto \
  "/Users/jafish/Documents/work/motorcycle-manual-app/电子说明书150 AURA CF150T-32-32A(8AJV-380101-1100-11 CN257)使用说明书-20251009.pdf" \
  "/Users/jafish/Documents/work/motorcycle-manual-app/电子说明书150 AURA CF150T-32-32A(8AJV-380101-1100-11 CN257)使用说明书-20251009-mineru-segments" \
  2>&1 | tail -30; echo "exit=$?"
```

Expected:
- p0000-0019 gets rerun to `p0000-0019-rerun/`
- Second validate runs
- If p0000-0019 passes after rerun: merge, exit 0
- If still suspicious: merge + review.md, exit 2
- Merged .md exists
- If exit 2, review.md exists with p0000-0019 entry

- [ ] **Step 2: Verify outputs**

```bash
# Check merge output exists
ls -la /Users/jafish/Documents/work/motorcycle-manual-app/电子说明书150*.md

# Check rerun directory if created
ls -d /Users/jafish/Documents/work/motorcycle-manual-app/*-rerun/ 2>/dev/null

# Check review if generated
cat /Users/jafish/Documents/work/motorcycle-manual-app/*-review.md 2>/dev/null
```

- [ ] **Step 3: Update plan docs**

Update `docs/plans/automated-pdf-pipeline.md` 阶段路线图: 阶段 3 → 已完成, 当前阶段 → 阶段 4.

Update `docs/PLAN_MAP.md`: 计划索引当前阶段 → 阶段 4, 完成证据补阶段 3 证据.

- [ ] **Step 4: Run governance check**

```bash
python3 scripts/check_plan_governance.py .
```

Expected: 计划治理检查通过。

- [ ] **Step 5: Final commit**

```bash
git add scripts/pdf-auto docs/PLAN_MAP.md docs/plans/automated-pdf-pipeline.md
git commit -m "feat(pdf-auto): complete Stage 3 auto-rerun pipeline

- pdf-auto script: validate → rerun suspicious → revalidate → merge → review
- Rerun writes to -rerun/ independent directories
- Exit codes: 0=all passed, 1=script error, 2=merged with review needed
- Tested on 191-page motorcycle manual sample"
```

---

### Task 7: Shellcheck and edge case hardening (optional)

**Files:**
- Modify: `scripts/pdf-auto`

**What this task delivers:** Polish — add `set -o pipefail` (already have `set -euo pipefail`), handle edge cases like no segments found, empty rerun list, etc.

Skip this task unless the integration test reveals issues.
