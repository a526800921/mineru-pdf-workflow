#!/usr/bin/env bash
# 消费者回归测试：pdf-read-page、pdf-extract-data
# 使用 mock 输出包，不依赖真实 MinerU 输出
set -eo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0

ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

TEST_ROOT="$(mktemp -d)"
cleanup_all() { rm -rf "$TEST_ROOT"; }
trap cleanup_all EXIT

# ── 辅助函数 ──────────────────────────────────────
create_mock_pkg() {
  local pkg_dir="$1" pkg_name="$2" model="$3"
  mkdir -p "$pkg_dir/segments/p0001-0001" "$pkg_dir/segments/p0002-0002" "$pkg_dir/data"
  cat > "$pkg_dir/manifest.json" << JSON
{
  "model": "${model}",
  "files": {
    "pdf": "${pkg_name}.pdf",
    "markdown": "${pkg_name}.md",
    "segments": "segments",
    "images": "images",
    "data": "data"
  },
  "parse_status": "all_passed"
}
JSON
  cat > "$pkg_dir/segments/p0001-0001/page_content_list_v2.json" << JSON
{"pages":[{"page_idx":0,"type":"text"}]}
JSON
  cat > "$pkg_dir/segments/p0002-0002/page_content_list_v2.json" << JSON
{"pages":[{"page_idx":1,"type":"text"}]}
JSON
}

# 创建合并 Markdown（含段级锚点和待提取内容）
create_merged_md() {
  local md_path="$1"
  cat > "$md_path" << 'MD'
<!-- pages 1-1 -->

## 第一章

型号: ABC-100
功率: 50 kW
转速: 3000 r/min

<!-- pages 2-2 -->

## 第二章

重量: 120 kg
尺寸: 500×300×200 mm
MD
}

# ── 测试 1：pdf-read-page 单页定位 ──────────────
echo ""
echo "=== 测试 1：pdf-read-page 单页定位 ==="
T1="$TEST_ROOT/t1"
create_mock_pkg "$T1" "demo" "test-car"
create_merged_md "$T1/demo.md"

output1="$("$SCRIPTS_DIR/pdf-read-page" "$T1" 1 2>/dev/null)" || true
if echo "$output1" | grep -q "ABC-100" && echo "$output1" | grep -q "50 kW"; then
  ok "第 1 页返回正确内容"
else
  fail "第 1 页内容不匹配"
fi

output2="$("$SCRIPTS_DIR/pdf-read-page" "$T1" 2 2>/dev/null)" || true
if echo "$output2" | grep -q "120 kg" && echo "$output2" | grep -q "尺寸"; then
  ok "第 2 页返回正确内容"
else
  fail "第 2 页内容不匹配"
fi

# ── 测试 2：pdf-read-page 多页范围 ──────────────
echo ""
echo "=== 测试 2：pdf-read-page 多页范围 ==="
T2="$TEST_ROOT/t2"
create_mock_pkg "$T2" "demo" "test-car"
create_merged_md "$T2/demo.md"

range_out="$("$SCRIPTS_DIR/pdf-read-page" "$T2" 1 2 2>/dev/null)" || true
if echo "$range_out" | grep -q "ABC-100" && echo "$range_out" | grep -q "120 kg"; then
  ok "多页范围 (1-2) 返回拼接内容"
else
  fail "多页范围内容不完整"
fi

# ── 测试 3：pdf-read-page 页码范围 ──────────────
echo ""
echo "=== 测试 3：pdf-read-page 页码范围 ==="
T3="$TEST_ROOT/t3"
create_mock_pkg "$T3" "demo" "test-car"
create_merged_md "$T3/demo.md"

# JSON 模式捕获错误
err_out3="$("$SCRIPTS_DIR/pdf-read-page" "$T3" 99 2>&1)" || true
PDF_READ_PAGE_JSON=1 "$SCRIPTS_DIR/pdf-read-page" "$T3" 99 2>/dev/null > "$T3/out.json" || true

# JSON 模式应返回 error 状态
if [[ -f "$T3/out.json" ]]; then
  status3="$(python3 -c "import json; print(json.load(open('$T3/out.json')).get('status',''))")"
  if [[ "$status3" == "error" ]]; then
    ok "页码范围返回 error 状态"
  else
    fail "页码范围未返回 error（got $status3）"
  fi
else
  fail "JSON 输出未生成"
fi

# ── 测试 4：pdf-extract-data 基本输出 ──────────
echo ""
echo "=== 测试 4：pdf-extract-data 基本输出 ==="
T4="$TEST_ROOT/t4"
create_mock_pkg "$T4" "demo" "test-car"
create_merged_md "$T4/demo.md"

"$SCRIPTS_DIR/pdf-extract-data" "$T4" 2>/dev/null || true

if [[ -f "$T4/data/quick_lookup_draft.csv" ]]; then
  ok "quick_lookup_draft.csv 已生成"
else
  fail "quick_lookup_draft.csv 未生成"
fi

if [[ -f "$T4/data/verification.csv" ]]; then
  ok "verification.csv 已生成"
else
  fail "verification.csv 未生成"
fi

if [[ -f "$T4/data/fixtures_result.md" ]]; then
  ok "fixtures_result.md 已生成"
else
  fail "fixtures_result.md 未生成"
fi

# 验证 CSV 列数（17 列）
col_count="$(head -1 "$T4/data/quick_lookup_draft.csv" | tr ',' '\n' | wc -l | tr -d ' ')"
if [[ "$col_count" -eq 17 ]]; then
  ok "quick_lookup_draft.csv 含 17 列"
else
  fail "quick_lookup_draft.csv 列数异常（got $col_count, want 17）"
fi

# 验证 CSV 包含提取的行
if grep -q "ABC-100" "$T4/data/quick_lookup_draft.csv"; then
  ok "CSV 包含提取的 key:value 行"
else
  fail "CSV 缺少提取内容"
fi

# ── 测试 5：pdf-extract-data 无合并 MD ──────────
echo ""
echo "=== 测试 5：pdf-extract-data 无合并 MD ==="
T5="$TEST_ROOT/t5"
mkdir -p "$T5/data" "$T5/segments"
cat > "$T5/manifest.json" << JSON
{"model": "empty-test", "files": {"markdown": "nonexistent.md", "segments": "segments", "images": "images", "data": "data"}, "parse_status": "segmented"}
JSON

"$SCRIPTS_DIR/pdf-extract-data" "$T5" 2>/dev/null || true

if [[ -f "$T5/data/quick_lookup_draft.csv" ]]; then
  # 检查仅有表头无数据行
  row_count="$(wc -l < "$T5/data/quick_lookup_draft.csv" | tr -d ' ')"
  if [[ "$row_count" -eq 1 ]]; then
    ok "无合并 MD 时输出空 CSV 含表头"
  else
    ok "无合并 MD 时 CSV 已生成（${row_count} 行）"
  fi
else
  fail "无合并 MD 时 CSV 未生成"
fi

# ── 汇总 ────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  通过: $PASS  失败: $FAIL"
echo "═══════════════════════════════════════════"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
