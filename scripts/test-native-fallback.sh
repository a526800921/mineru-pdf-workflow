#!/usr/bin/env bash
# 原生表格字段缺失信号 → pdf-auto 页级 fallback 端到端回归
# 覆盖四条闭环路径：
#   1. 检测触发 → fallback 恢复字段 → selected=fallback
#   2. 检测触发 → 字段仍缺失 → selected=review → needs_review
#   3. 检测触发 → fallback 重跑失败 → fb_status=failed → needs_review
#   4. 跨执行跳过：第二次运行不重复检测，manifest 证据保留
# 使用内容驱动的 mock page_quality / mineru-runner，不依赖真实 MinerU / 真实 PDF 表格
set -eo pipefail

PASS=0
FAIL=0
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

MOCK_DIR="$(mktemp -d)"
MOCK_HOME="$(mktemp -d)"
TEST_ROOT="$(mktemp -d)"
cleanup_all() { rm -rf "$MOCK_DIR" "$MOCK_HOME" "$TEST_ROOT"; }
trap cleanup_all EXIT

mkdir -p "$MOCK_DIR/lib"
cp "$SCRIPTS_DIR/lib/segment-consistency" "$MOCK_DIR/lib/segment-consistency"

# mock modelpad-pdf-service
cat > "$MOCK_DIR/lib/modelpad-pdf-service" << 'EOF'
api_url="http://127.0.0.1:9999"
ensure_pdf_api() { :; }
modelpad_stop_pdf_if_started() { :; }
EOF

# mock pdf-merge
cat > "$MOCK_DIR/pdf-merge" << 'EOF'
#!/usr/bin/env bash
output="${PDF_MERGE_OUTPUT:-$(dirname "$1")/../test.md}"
mkdir -p "$(dirname "$output")"
echo "# mock merge output" > "$output"
EOF
chmod +x "$MOCK_DIR/pdf-merge"

# mock pdf-validate（始终 all_pass，隔离出原生信号为唯一 needs_review 驱动）
cat > "$MOCK_DIR/pdf-validate" << 'MOCKVAL'
#!/usr/bin/env python3
import json, sys
report = {"status": "completed", "segments": [
    {"name": "p0001-0001", "start_page": 1, "end_page": 1,
     "status": "passed", "coverage": 0.95, "rerunnable": False, "decision": "pass"}]}
json.dump(report, sys.stdout, ensure_ascii=False)
print()
MOCKVAL
chmod +x "$MOCK_DIR/pdf-validate"

# mock Python lib stubs
cat > "$MOCK_DIR/lib/toc_repair.py" << 'EOF'
def repair(pdf_path, segments_dir, validate_tmp): pass
def repair_merged(pdf_path, merged_md, validate_tmp): pass
def verify_entry_recall(pdf_path, segments_dir, validate_tmp): pass
EOF
cat > "$MOCK_DIR/lib/review_report.py" << 'EOF'
def generate_review_report(validate_json_path, review_output_path, threshold, pdf_path, segments_dir, rerun_failures=None, include_page_type=False):
    with open(review_output_path, 'w') as f:
        f.write("# review report\n")
EOF
cat > "$MOCK_DIR/lib/page_anchors.py" << 'EOF'
def insert_page_anchors(text, items, start, end):
    return text, []
EOF

# mock mineru-runner（内容驱动的 fallback 输出，NATIVE_FB_MODE 控制）
cat > "$MOCK_DIR/lib/mineru-runner" << 'EOF'
_run_mineru_page() {
  local pdf="$1" out_dir="$2"
  case "${NATIVE_FB_MODE:-recover}" in
    recover)
      mkdir -p "$out_dir/content"
      # 真实的字段恢复补回内容，md 体积增大（不含 [[MISSING]] 标记）
      printf '# spec table\n| 测试缺失字段 | 2.7L |\n恢复了缺失字段的完整表格内容行\n' > "$out_dir/content/page.md"
      echo '{"status":"done","exit_code":0}'; return 0 ;;
    stay)
      mkdir -p "$out_dir/content"
      printf '# still missing [[MISSING]]\n' > "$out_dir/content/page.md"
      echo '{"status":"done","exit_code":0}'; return 0 ;;
    fail)
      return 1 ;;
  esac
}
EOF

# mock page_quality：assess 内容驱动（[[MISSING]] 标记发原生信号），
# compare_quality 直接加载真实实现，避免手抄规则与真实逻辑漂移
cat > "$MOCK_DIR/lib/page_quality.py" << EOF
import importlib.util as _u
_spec = _u.spec_from_file_location("_real_pq", "$SCRIPTS_DIR/lib/page_quality.py")
_real = _u.module_from_spec(_spec)
_spec.loader.exec_module(_real)
compare_quality = _real.compare_quality  # 真实决策逻辑
EOF
cat >> "$MOCK_DIR/lib/page_quality.py" << 'EOF'

def assess_page_quality(md_text, pdf_page_text, **kwargs):
    signals = []
    metrics = {"empty_td": 0, "max_td_per_row": 0, "md_bytes": len(md_text.encode("utf-8")),
               "pdf_bytes": 0, "text_coverage": 1.0, "pdf_tokens": 0,
               "native_table_candidates": 0, "native_table_missing": 0}
    if "[[MISSING]]" in md_text:
        signals.append("native_table_text_missing")
        metrics["native_table_candidates"] = 1
        metrics["native_table_missing"] = 1
        metrics["missing_text"] = ["测试缺失字段"]
    return {"signals": signals, "metrics": metrics, "quality_ok": len(signals) == 0}
EOF

cp "$SCRIPTS_DIR/pdf-auto" "$MOCK_DIR/pdf-auto"
chmod +x "$MOCK_DIR/pdf-auto"

# ── 辅助函数 ─────────────────────────────────────────────
ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

create_dummy_pdf() {
  local path="$1" pages="${2:-1}"
  python3 - "$path" "$pages" <<'PY'
import sys, fitz
doc = fitz.open()
for _ in range(int(sys.argv[2])):
    doc.new_page()
doc.save(sys.argv[1])
doc.close()
PY
}

create_mock_manifest() {
  local pkg_dir="$1" pdf_path="$2" pages="${3:-1}"
  local sha256
  sha256="$(shasum -a 256 "$pdf_path" | awk '{print $1}')"
  python3 - "$pkg_dir" "$pdf_path" "$sha256" "$pages" << 'PY'
import json, sys
pkg_dir, pdf_path, sha256, pages = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
manifest = {
    "model": "test-model", "version": None, "source_pdf": pdf_path,
    "files": {"pdf": "dummy.pdf", "markdown": None, "review": None,
              "segments": "segments", "images": "images", "data": "data"},
    "hash": {"sha256": sha256},
    "segmentation": {"schema_version": 1, "layout": "single_page", "segment_size": 1,
                     "total_pages": pages,
                     "mineru": {"backend": "hybrid-engine", "method": "auto",
                                "effort": "medium", "lang": "ch"}},
    "parse_status": "segmented",
}
with open(f"{pkg_dir}/manifest.json", "w") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

# 创建一个含 [[MISSING]] 标记原始段的 mock 输出包
setup_pkg() {
  local dir="$1"
  mkdir -p "$dir/segments/p0001-0001/content"
  printf '# spec table [[MISSING]]\n' > "$dir/segments/p0001-0001/content/page.md"
  echo '{"pages":[{"page_idx":0}]}' > "$dir/segments/p0001-0001/content/page_content_list.json"
  echo '{"pages":[{"page_idx":0,"type":"table"}]}' > "$dir/segments/p0001-0001/content/page_content_list_v2.json"
  create_dummy_pdf "$dir/dummy.pdf" 1
  create_mock_manifest "$dir" "$dir/dummy.pdf" 1
}

run_auto() {
  local dir="$1" fb_mode="$2" outfile="$3"
  HOME="$MOCK_HOME" NATIVE_FB_MODE="$fb_mode" PATH="$MOCK_DIR:$PATH" \
    PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$dir/dummy.pdf" "$dir/segments" \
    2>/dev/null > "$outfile" || true
}

# ── 场景 1：检测触发 → fallback 恢复 → selected=fallback ──
echo ""
echo "=== 场景 1：原生字段恢复 → selected=fallback ==="
S1="$TEST_ROOT/s1"; setup_pkg "$S1"
run_auto "$S1" recover "$S1/out.json"
python3 << PY
import json
data = json.load(open("$S1/out.json"))
m = json.load(open("$S1/manifest.json"))
pf = m.get("page_fallback", {}).get("1", {})
errs = []
if data.get("status") != "all_passed": errs.append(f"status={data.get('status')} 期望 all_passed")
if data.get("exit_code") != 0: errs.append(f"exit={data.get('exit_code')} 期望 0")
if pf.get("selected") != "fallback": errs.append(f"selected={pf.get('selected')} 期望 fallback")
if pf.get("detector") != "pdf_native": errs.append(f"detector={pf.get('detector')} 期望 pdf_native")
if pf.get("quality_signals") != ["native_table_text_missing"]: errs.append(f"quality_signals={pf.get('quality_signals')}")
if pf.get("missing_text") != ["测试缺失字段"]: errs.append(f"missing_text={pf.get('missing_text')}")
if pf.get("fb_status") != "completed": errs.append(f"fb_status={pf.get('fb_status')}")
print("; ".join(errs))
raise SystemExit(1 if errs else 0)
PY
if [[ $? -eq 0 ]]; then ok "恢复路径：selected=fallback + 契约字段完整 (exit=0)"; else fail "恢复路径校验失败"; fi

# ── 场景 2：检测触发 → 字段仍缺失 → review ──
echo ""
echo "=== 场景 2：原生字段仍缺失 → selected=review → needs_review ==="
S2="$TEST_ROOT/s2"; setup_pkg "$S2"
run_auto "$S2" stay "$S2/out.json"
python3 << PY
import json
data = json.load(open("$S2/out.json"))
m = json.load(open("$S2/manifest.json"))
pf = m.get("page_fallback", {}).get("1", {})
errs = []
if data.get("status") != "needs_review": errs.append(f"status={data.get('status')} 期望 needs_review")
if data.get("exit_code") != 2: errs.append(f"exit={data.get('exit_code')} 期望 2")
if pf.get("selected") != "review": errs.append(f"selected={pf.get('selected')} 期望 review")
if pf.get("detector") != "pdf_native": errs.append(f"detector={pf.get('detector')}")
if pf.get("missing_text") != ["测试缺失字段"]: errs.append(f"missing_text={pf.get('missing_text')}")
if pf.get("fb_status") != "completed": errs.append(f"fb_status={pf.get('fb_status')}")
print("; ".join(errs))
raise SystemExit(1 if errs else 0)
PY
if [[ $? -eq 0 ]]; then ok "仍缺失路径：selected=review → needs_review (exit=2)"; else fail "仍缺失路径校验失败"; fi

# ── 场景 3：检测触发 → fallback 失败 → fb_status=failed → review ──
echo ""
echo "=== 场景 3：fallback 重跑失败 → fb_status=failed → needs_review ==="
S3="$TEST_ROOT/s3"; setup_pkg "$S3"
run_auto "$S3" fail "$S3/out.json"
python3 << PY
import json
data = json.load(open("$S3/out.json"))
m = json.load(open("$S3/manifest.json"))
pf = m.get("page_fallback", {}).get("1", {})
errs = []
if data.get("status") != "needs_review": errs.append(f"status={data.get('status')} 期望 needs_review")
if data.get("exit_code") != 2: errs.append(f"exit={data.get('exit_code')} 期望 2")
if pf.get("selected") != "review": errs.append(f"selected={pf.get('selected')}")
if pf.get("fb_status") != "failed": errs.append(f"fb_status={pf.get('fb_status')} 期望 failed")
if pf.get("fallback_path") is not None: errs.append(f"fallback_path={pf.get('fallback_path')} 期望 None")
if pf.get("detector") != "pdf_native": errs.append(f"detector={pf.get('detector')}")
if pf.get("missing_text") != ["测试缺失字段"]: errs.append(f"missing_text={pf.get('missing_text')}")
print("; ".join(errs))
raise SystemExit(1 if errs else 0)
PY
if [[ $? -eq 0 ]]; then ok "失败路径：fb_status=failed → needs_review (exit=2)"; else fail "失败路径校验失败"; fi

# ── 场景 4：跨执行跳过 → 第二次不重复检测，证据保留 ──
echo ""
echo "=== 场景 4：跨执行跳过 → manifest 证据保留 ==="
S4="$TEST_ROOT/s4"; setup_pkg "$S4"
run_auto "$S4" stay "$S4/out1.json"
cp "$S4/manifest.json" "$S4/manifest_after_run1.json"
run_auto "$S4" stay "$S4/out2.json"
python3 << PY
import json
m1 = json.load(open("$S4/manifest_after_run1.json"))
m2 = json.load(open("$S4/manifest.json"))
pf1 = m1.get("page_fallback", {}).get("1", {})
pf2 = m2.get("page_fallback", {}).get("1", {})
errs = []
# run1 必须已记录证据
if pf1.get("missing_text") != ["测试缺失字段"]: errs.append(f"run1 missing_text={pf1.get('missing_text')}")
# run2 后证据保留且不变（跳过检测，未覆盖）
if pf2.get("selected") != "review": errs.append(f"run2 selected={pf2.get('selected')}")
if pf2.get("missing_text") != ["测试缺失字段"]: errs.append(f"run2 missing_text 丢失={pf2.get('missing_text')}")
if pf2.get("quality_signals") != ["native_table_text_missing"]: errs.append(f"run2 quality_signals={pf2.get('quality_signals')}")
if pf2.get("detector") != "pdf_native": errs.append(f"run2 detector={pf2.get('detector')}")
# 仅有 1 页记录（未重复）
if len(m2.get("page_fallback", {})) != 1: errs.append(f"page_fallback 页数={len(m2.get('page_fallback', {}))} 期望 1")
# attempt_count 未被二次运行递增
if pf2.get("attempt_count") != 1: errs.append(f"attempt_count={pf2.get('attempt_count')} 期望 1（未重复重跑）")
print("; ".join(errs))
raise SystemExit(1 if errs else 0)
PY
if [[ $? -eq 0 ]]; then ok "跨执行跳过：证据保留 + 未重复重跑"; else fail "跨执行跳过校验失败"; fi

echo ""
echo "═══════════════════════════════════════════"
echo "  通过: $PASS  失败: $FAIL"
echo "═══════════════════════════════════════════"
[[ $FAIL -eq 0 ]]
