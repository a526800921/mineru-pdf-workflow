#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/segment-consistency"

log() { echo "$@"; }

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

PDF="$ROOT_DIR/pdf/demo20/demo20.pdf"
PDF_HASH="$(shasum -a 256 "$PDF" | awk '{print $1}')"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

write_manifest() {
  local pkg="$1" pages="$2"
  python3 - "$pkg/manifest.json" "$PDF_HASH" "$pages" <<'PY'
import json, sys
path, pdf_hash, pages = sys.argv[1], sys.argv[2], int(sys.argv[3])
manifest = {
    "hash": {"sha256": pdf_hash},
    "segmentation": {
        "schema_version": 1,
        "layout": "single_page",
        "segment_size": 1,
        "total_pages": pages,
        "mineru": {
            "backend": "hybrid-engine",
            "method": "auto",
            "effort": "medium",
            "lang": "ch",
        },
    },
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

assert_missing() {
  local description="$1" path="$2"
  if [[ ! -e "$path" ]]; then ok "$description"; else fail "$description"; fi
}

assert_present() {
  local description="$1" path="$2"
  if [[ -e "$path" ]]; then ok "$description"; else fail "$description"; fi
}

echo "=== 阶段 1：旧格式和旧多页目录触发清理 ==="
T1="$TEST_ROOT/t1"
mkdir -p "$T1/segments/p0001-0010" "$T1/segments/p0011-0020"
cp "$ROOT_DIR/pdf/demo20 copy/manifest.json" "$T1/manifest.json"
if check_segment_consistency "$T1/segments" "$PDF" 20 1 hybrid-engine auto medium ch; then
  fail "旧格式应触发清理"
else
  ok "旧格式触发清理"
fi
assert_missing "旧多页目录已清理" "$T1/segments/p0011-0020"

echo "=== 阶段 1：匹配指纹和完整单页目录保留 ==="
T2="$TEST_ROOT/t2"
mkdir -p "$T2/segments/p0001-0001" "$T2/segments/p0002-0002"
write_manifest "$T2" 2
echo keep > "$T2/segments/p0001-0001/page.md"
if check_segment_consistency "$T2/segments" "$PDF" 2 1 hybrid-engine auto medium ch; then
  ok "匹配输出通过检查"
else
  fail "匹配输出不应被清理"
fi
assert_present "匹配单页目录保留" "$T2/segments/p0001-0001/page.md"

echo "=== 阶段 1：缺页触发整体清理 ==="
T3="$TEST_ROOT/t3"
mkdir -p "$T3/segments/p0001-0001"
write_manifest "$T3" 2
if check_segment_consistency "$T3/segments" "$PDF" 2 1 hybrid-engine auto medium ch; then
  fail "缺页应触发清理"
else
  ok "缺页触发清理"
fi
assert_missing "缺页场景清理旧单页目录" "$T3/segments/p0001-0001"

echo "=== 阶段 1：backup 和 rerun 残留触发清理 ==="
T4="$TEST_ROOT/t4"
mkdir -p "$T4/segments/p0001-0001" "$T4/segments/p0002-0002" \
  "$T4/segments/p0001-0001.backup" "$T4/segments/p0002-0002-rerun"
write_manifest "$T4" 2
if check_segment_consistency "$T4/segments" "$PDF" 2 1 hybrid-engine auto medium ch; then
  fail "残留临时目录应触发清理"
else
  ok "残留临时目录触发清理"
fi
assert_missing "backup 残留已清理" "$T4/segments/p0001-0001.backup"
assert_missing "rerun 残留已清理" "$T4/segments/p0002-0002-rerun"

echo "=== 阶段 1：pdf-auto 接入全量重解析 ==="
if rg -q 'check_segment_consistency "\$segments_dir"' "$ROOT_DIR/scripts/pdf-auto" \
  && rg -q '"\$_scripts_dir/pdf-seg" "\$pdf_path"' "$ROOT_DIR/scripts/pdf-auto"; then
  ok "pdf-auto 已接入一致性检查和全量 pdf-seg 重解析"
else
  fail "pdf-auto 未完整接入一致性检查和全量重解析"
fi

echo ""
echo "通过: $PASS  失败: $FAIL"
[[ "$FAIL" -eq 0 ]]
