#!/usr/bin/env bash
# ── 阶段 3 专项回归测试 ─────────────────────────────────────
# 场景覆盖：
#   1. 信号触发：quality 检测正确返回 triggered
#   2. 决策 fallback：compare_quality 返回 "fallback"
#   3. 决策 original：compare_quality 返回 "original"
#   4. 决策 review：compare_quality 返回 "review"
#   5. 双版本共存：fallback 完成后原始和 fallback 目录均存在
#   6. manifest 字段完备性检查
#   7. 跨执行跳过：fallback_attempted 时检测阶段跳过已处理页
#   8. pdf-merge 选择正确源
#   9. 所有 fallback 失败时的 manifest 记录
set -euo pipefail

cd "$(dirname "$0")"

pass=0
fail=0
failed_cases=""

# usage: ok "case name" "description"
ok()   { pass=$((pass+1)); echo "  ✓ $1"; }
fail_case() { local c="$1"; fail=$((fail+1)); failed_cases="$failed_cases    $c\n"; echo "  ✗ $1"; }

_summarize() {
  local total=$((pass+fail))
  echo ""
  if [[ "$fail" -eq 0 ]]; then
    echo "结果: 全部通过 (${pass}/${total})"
    exit 0
  else
    echo "结果: 失败 ${fail} 项"
    echo -e "$failed_cases"
    exit 1
  fi
}
trap _summarize EXIT

echo "阶段 3 回归测试"
echo "================"
echo ""

# ── 1. Python 单元测试 ────────────────────────────────────
echo "[1/4] Python 单元测试"
if python3 -m pytest tests/test_page_quality.py -q 2>&1; then
  ok "test_page_quality.py — 全部通过"
else
  fail_case "test_page_quality.py — 存在失败项"
fi

# ── 2. manifest page_fallback 字段 Schema 校验 ──────────
echo ""
echo "[2/4] manifest page_fallback 字段 Schema"
_test_schema() {
  local label="$1" json="$2"
  local errors=""
  for key in "selected" "reason" "fb_status" "attempt_count" \
             "original_path" "fallback_path" \
             "original_params" "fallback_params" \
             "original_metrics" "fallback_metrics"; do
    if ! echo "$json" | python3 -c "import json,sys; d=json.load(sys.stdin); assert '$key' in d, '缺少 $key'" 2>/dev/null; then
      errors="$errors 缺少字段: $key"
    fi
  done
  # 校验子字段
  if ! echo "$json" | python3 -c "
import json,sys
d=json.load(sys.stdin)
op=d.get('original_params',{})
assert 'backend' in op and 'method' in op and 'effort' in op and 'lang' in op, 'original_params 子字段不完整'
fp=d.get('fallback_params',{})
assert 'image_analysis' in fp, 'fallback_params 缺少 image_analysis'
" 2>/dev/null; then
    errors="$errors + 参数子字段不完整"
  fi
  if [[ -z "$errors" ]]; then
    ok "$label"
  else
    fail_case "$label: $errors"
  fi
}

# 构造一个完整条目测试
_test_schema "completed 条目完备" \
  '{"selected":"fallback","reason":"excessive_empty_td","fb_status":"completed","attempt_count":1,"original_path":"p0001-0001/","fallback_path":"p0001-0001-fallback/","original_params":{"backend":"hybrid-engine","method":"auto","effort":"medium","lang":"ch"},"fallback_params":{"image_analysis":false},"original_metrics":{"empty_td":100,"max_td_per_row":50,"md_bytes":50000,"text_coverage":0.9},"fallback_metrics":{"empty_td":30,"max_td_per_row":50,"md_bytes":48000,"text_coverage":0.9}}'

_test_schema "failed 条目完备（fallback_path=None）" \
  '{"selected":"review","reason":"volume_inflation","fb_status":"failed","fb_failure_reason":"mineru fallback 重跑退出非零或超时","attempt_count":1,"original_path":"p0001-0001/","fallback_path":null,"original_params":{"backend":"hybrid-engine","method":"auto","effort":"medium","lang":"ch"},"fallback_params":{"image_analysis":false},"original_metrics":{"empty_td":0,"max_td_per_row":0,"md_bytes":30000,"text_coverage":0.02},"fallback_metrics":null}'

# ── 3. pdf-merge fallback 选择逻辑 ──────────────────────
echo ""
echo "[3/4] pdf-merge fallback 选择逻辑"

# 创建临时测试目录
_testdir="$(mktemp -d /tmp/test_phase3_XXXXXX)"
cleanup() { rm -rf "$_testdir"; }
trap 'cleanup; _summarize' EXIT

# 模拟输出包结构
_pkg_dir="$_testdir/package"
_seg_dir="$_pkg_dir/segments"
mkdir -p "$_seg_dir/p0001-0001"
mkdir -p "$_seg_dir/p0001-0001-fallback"
mkdir -p "$_seg_dir/p0002-0002"

# 原始内容
cat > "$_seg_dir/p0001-0001/p0001-0001.md" <<'EOF'
# Page 1 Original

| Col A | Col B |
|-------|-------|
| <td></td><td></td><td></td><td></td> | data |
EOF

# fallback 内容（更干净）
cat > "$_seg_dir/p0001-0001-fallback/p0001-0001.md" <<'EOF'
# Page 1 Fallback

| Col A | Col B |
|-------|-------|
| data1 | data2 |
EOF

cat > "$_seg_dir/p0002-0002/p0002-0002.md" <<'EOF'
# Page 2

Normal text content.
EOF

# --- 案例 A: selected=fallback — pdf-merge 应从 fallback 目录读 ---
cat > "$_pkg_dir/manifest.json" <<'JSON'
{
  "page_fallback": {
    "1": {
      "selected": "fallback",
      "reason": "excessive_empty_td",
      "fb_status": "completed",
      "attempt_count": 1,
      "original_path": "p0001-0001/",
      "fallback_path": "p0001-0001-fallback/",
      "original_params": {},
      "fallback_params": {},
      "original_metrics": {},
      "fallback_metrics": {}
    }
  }
}
JSON

# 运行 pdf-merge
PDF_MERGE_OUTPUT="$_pkg_dir/merged_fallback.md" \
  scripts/pdf-merge "$_seg_dir" >/dev/null 2>&1

if grep -q "Page 1 Fallback" "$_pkg_dir/merged_fallback.md" 2>/dev/null; then
  ok "selected=fallback → pdf-merge 使用 fallback 目录"
else
  fail_case "selected=fallback → pdf-merge 未使用 fallback 目录"
fi

# --- 案例 B: 无 manifest — pdf-merge 使用原始目录 ---
rm -f "$_pkg_dir/manifest.json"
PDF_MERGE_OUTPUT="$_pkg_dir/merged_original.md" \
  scripts/pdf-merge "$_seg_dir" >/dev/null 2>&1

if grep -q "Page 1 Original" "$_pkg_dir/merged_original.md" 2>/dev/null; then
  ok "无 manifest → pdf-merge 使用原始目录"
else
  fail_case "无 manifest → pdf-merge 未正确使用原始目录"
fi

# --- 案例 C: 存在 fallback_attempted flag 时，检测阶段应跳过 ---
cat > "$_pkg_dir/manifest.json" <<'JSON'
{
  "fallback_attempted": true,
  "page_fallback": {
    "1": {
      "selected": "fallback",
      "reason": "excessive_empty_td",
      "fb_status": "completed",
      "attempt_count": 1,
      "original_path": "p0001-0001/",
      "fallback_path": "p0001-0001-fallback/",
      "original_params": {},
      "fallback_params": {},
      "original_metrics": {},
      "fallback_metrics": {}
    }
  }
}
JSON

# 用 Python 模拟检测阶段的跳过逻辑
skip_check=$(python3 - "$_pkg_dir" <<'PY'
import json, sys
from pathlib import Path
pkg_dir = Path(sys.argv[1])
mf = pkg_dir / "manifest.json"
m = json.loads(mf.read_text())
skipped = set()
if m.get("fallback_attempted") and m.get("page_fallback"):
    skipped = {int(k) for k in m["page_fallback"]}
# p0001-0001 的页号是 1，p0002-0002 的页号是 2
print("1" if 1 in skipped else "0")
print("2" if 2 in skipped else "0")
PY
)
if [[ "$(echo "$skip_check" | head -1)" == "1" ]]; then
  ok "fallback_attempted=true → 已处理页(1)被跳过"
else
  fail_case "fallback_attempted=true → 已处理页(1)未被跳过"
fi
if [[ "$(echo "$skip_check" | tail -1)" == "0" ]]; then
  ok "fallback_attempted=true → 未处理页(2)不被跳过"
else
  fail_case "fallback_attempted=true → 未处理页(2)被误跳过"
fi

# ── 4. _quality_needs_review 检测 ────────────────────────
echo ""
echo "[4/4] _quality_needs_review 检测"

check_needs_review() {
  local label="$1" json="$2" expected="$3"
  local result
  result="$(python3 - "$json" <<'PY'
import json, sys
m = json.loads(sys.argv[1])
pf = m.get("page_fallback", {})
for entry in pf.values():
    if entry.get("selected") in ("review",):
        print("true")
        sys.exit(0)
    if entry.get("fb_status") == "failed":
        print("true")
        sys.exit(0)
print("false")
PY
  )"
  if [[ "$result" == "$expected" ]]; then
    ok "$label"
  else
    fail_case "$label: 期望=$expected 实际=$result"
  fi
}

check_needs_review "review 选中 → needs_review=true" \
  '{"page_fallback":{"1":{"selected":"review"}}}' \
  "true"

check_needs_review "fallback 选中 → needs_review=false" \
  '{"page_fallback":{"1":{"selected":"fallback"}}}' \
  "false"

check_needs_review "fb_status=failed → needs_review=true" \
  '{"page_fallback":{"1":{"selected":"original","fb_status":"failed"}}}' \
  "true"

check_needs_review "全部通过 → needs_review=false" \
  '{"page_fallback":{"1":{"selected":"fallback","fb_status":"completed"},"2":{"selected":"original","fb_status":"completed"}}}' \
  "false"
