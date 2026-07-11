#!/usr/bin/env bash
# 阶段 2 回归测试：pdf-rerun 备份/恢复、产物同步、事务安全
# 覆盖：成功/无 md/非零退出/残留 backup/原子覆盖/JSON 契约/单页+多页段
# 使用 mock mineru + mock modelpad 服务，不依赖真实 MinerU
set -eo pipefail

PASS=0
FAIL=0

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 创建 mock 目录结构 ──────────────────────────────────────────────
MOCK_DIR="$(mktemp -d)"
MOCK_HOME="$(mktemp -d)"
TEST_ROOT="$(mktemp -d)"

cleanup_all() { rm -rf "$MOCK_DIR" "$MOCK_HOME" "$TEST_ROOT"; }
trap cleanup_all EXIT

# mock 依赖 (lib/modelpad-pdf-service + pdf-merge + mineru)
mkdir -p "$MOCK_DIR/lib"

# mock modelpad-pdf-service（阻止 ensure_pdf_api 启动真实 ModelPad）
cat > "$MOCK_DIR/lib/modelpad-pdf-service" << 'EOF'
# mock — 不启动真实 PDF 服务
api_url="http://127.0.0.1:9999"
ensure_pdf_api() { :; }
modelpad_stop_pdf_if_started() { :; }
EOF

# mock mineru（接受真实参数，按模式产生模拟输出）
cat > "$MOCK_DIR/mineru" << 'MOCK'
#!/usr/bin/env bash
output_dir=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o) output_dir="$2"; shift 2 ;;
        -p|-b|-m|-l|-s|-e) shift 2 ;;
        --effort) shift 2 ;;
        --api-url) shift 2 ;;
        *) shift ;;
    esac
done
[[ -n "$output_dir" ]] || output_dir="."
mkdir -p "$output_dir"
case "${MINERU_MOCK_MODE:-success}" in
    success)
        mkdir -p "$output_dir/content"
        echo "# mock rerun content" > "$output_dir/content/page.md"
        echo '{"pages":[{"page_idx":0}]}' > "$output_dir/content/page_content_list.json"
        echo '{"pages":[{"page_idx":0,"type":"text"}]}' > "$output_dir/content/page_content_list_v2.json"
        echo '{"mock":true}' > "$output_dir/content/middle.json"
        echo '{"mock":true}' > "$output_dir/content/model.json"
        mkdir -p "$output_dir/content/images"
        printf "mock-img" > "$output_dir/content/images/fig1.png"
        exit 0
        ;;
    no_markdown)
        mkdir -p "$output_dir/content"
        echo '{"pages":[]}' > "$output_dir/content/page_content_list.json"
        exit 0
        ;;
    failed)
        exit 1
        ;;
esac
MOCK
chmod +x "$MOCK_DIR/mineru"

# mock pdf-merge（生成最小输出文件）
cat > "$MOCK_DIR/pdf-merge" << 'EOF'
#!/usr/bin/env bash
output="${PDF_MERGE_OUTPUT:-$(dirname "$1")/../test.md}"
mkdir -p "$(dirname "$output")"
echo "# mock merge output" > "$output"
echo "mock pdf-merge: $*"
EOF
chmod +x "$MOCK_DIR/pdf-merge"

# mock pdf-validate（通过计数器和环境变量控制返回的验证结果）
cat > "$MOCK_DIR/pdf-validate" << 'MOCKVAL'
#!/usr/bin/env python3
import json, os, sys
stage_file = os.path.join(os.path.dirname(__file__), '.validate_stage')
try:
    with open(stage_file) as f:
        stage = int(f.read().strip())
except (FileNotFoundError, ValueError):
    stage = 1
with open(stage_file, 'w') as f:
    f.write(str(stage + 1))
behavior = os.environ.get('PDF_VALIDATE_BEHAVIOR', 'rerun_pass')

if behavior == 'all_pass':
    report = {"status":"completed","segments":[
        {"name":"p0001-0001","start_page":1,"end_page":1,"status":"passed","coverage":0.95,"rerunnable":False,"decision":"pass"}]}
elif behavior == 'rerun_pass' or behavior == 'rerun_fail':
    if stage == 1:
        report = {"status":"completed","segments":[
            {"name":"p0001-0001","start_page":1,"end_page":1,"status":"suspicious","coverage":0.50,"rerunnable":True,"decision":"rerun","reason":"low coverage"},
            {"name":"p0002-0002","start_page":2,"end_page":2,"status":"passed","coverage":0.95,"rerunnable":False,"decision":"pass"}]}
    else:
        if behavior == 'rerun_pass':
            report = {"status":"completed","segments":[
                {"name":"p0001-0001","start_page":1,"end_page":1,"status":"passed","coverage":0.95,"rerunnable":False,"decision":"pass"},
                {"name":"p0002-0002","start_page":2,"end_page":2,"status":"passed","coverage":0.95,"rerunnable":False,"decision":"pass"}]}
        else:
            report = {"status":"completed","segments":[
                {"name":"p0001-0001","start_page":1,"end_page":1,"status":"suspicious","coverage":0.50,"rerunnable":True,"decision":"rerun","reason":"low coverage"},
                {"name":"p0002-0002","start_page":2,"end_page":2,"status":"passed","coverage":0.95,"rerunnable":False,"decision":"pass"}]}
json.dump(report, sys.stdout, ensure_ascii=False)
print()
MOCKVAL
chmod +x "$MOCK_DIR/pdf-validate"

# mock Python lib stubs（供 pdf-auto 内嵌 Python 导入）
mkdir -p "$MOCK_DIR/lib"
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

# 复制 pdf-auto 和 pdf-rerun 到 mock 目录
cp "$SCRIPTS_DIR/pdf-auto" "$MOCK_DIR/pdf-auto"
chmod +x "$MOCK_DIR/pdf-auto"
cp "$SCRIPTS_DIR/pdf-rerun" "$MOCK_DIR/pdf-rerun"
chmod +x "$MOCK_DIR/pdf-rerun"
cp "$SCRIPTS_DIR/pdf-seg" "$MOCK_DIR/pdf-seg"
chmod +x "$MOCK_DIR/pdf-seg"

# ── 辅助函数：重置 pdf-validate 调用计数器 ────────────────
reset_validate_stage() { echo 1 > "$MOCK_DIR/.validate_stage"; }

# ── 辅助函数：为 mock pdf-auto 创建最小 manifest.json（通过一致性检查）─
ok()   { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

create_mock_manifest() {
  local pkg_dir="$1" pdf_path="$2" pages="${3:-2}"
  # 空文件 SHA-256
  local sha256
  if [[ -s "$pdf_path" ]]; then
    sha256="$(shasum -a 256 "$pdf_path" | awk '{print $1}')"
  else
    # 空文件固定 SHA-256
    sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  fi
  python3 - "$pkg_dir" "$pdf_path" "$sha256" "$pages" << 'PY'
import json, sys
pkg_dir = sys.argv[1]
pdf_path = sys.argv[2]
sha256 = sys.argv[3]
pages = int(sys.argv[4])
manifest = {
    "model": "test-model",
    "version": None,
    "source_pdf": pdf_path,
    "files": {
        "pdf": "dummy.pdf",
        "markdown": None,
        "review": None,
        "segments": "segments",
        "images": "images",
        "data": "data"
    },
    "hash": {"sha256": sha256},
    "segmentation": {
        "schema_version": 1,
        "layout": "single_page",
        "segment_size": 1,
        "total_pages": pages,
        "mineru": {
            "backend": "hybrid-engine",
            "method": "auto",
            "effort": "medium",
            "lang": "ch"
        }
    },
    "parse_status": "segmented"
}
with open(f"{pkg_dir}/manifest.json", "w") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}
cp "$SCRIPTS_DIR/pdf-rerun" "$MOCK_DIR/pdf-rerun"
chmod +x "$MOCK_DIR/pdf-rerun"

assert_file_exists() {
    local desc="$1" path="$2"
    if [[ -f "$path" || -d "$path" ]]; then
        ok "$desc"
    else
        fail "$desc (missing: $path)"
    fi
}
assert_file_missing() {
    local desc="$1" path="$2"
    if [[ ! -f "$path" && ! -d "$path" ]]; then
        ok "$desc"
    else
        fail "$desc (still exists: $path)"
    fi
}
assert_str_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        ok "$desc"
    else
        fail "$desc (expected: $expected; actual: $actual)"
    fi
}

# 运行 pdf-rerun 并捕获 JSON 到文件
run_rerun_to_file() {
    local test_dir="$1" mock_mode="$2" pdf="$3" seg="$4" outfile="$5"
    shift 5
    HOME="$MOCK_HOME" \
    MINERU_MOCK_MODE="$mock_mode" \
    PATH="$MOCK_DIR:$PATH" \
    PDF_RERUN_JSON=1 \
    bash "$MOCK_DIR/pdf-rerun" "$pdf" "$seg" "$@" 2>/dev/null > "$outfile" || true
}

# ── 场景 1：成功重跑 ──────────────────────────────────────────────
echo ""
echo "=== 场景 1：成功重跑 → 备份清理 + 产物同步 ==="
T1="$TEST_ROOT/t1"
OUT1="$T1/out.json"
mkdir -p "$T1/segments/p0001-0001" "$T1/segments/p0002-0002"
echo "original p1" > "$T1/segments/p0001-0001/page.md"
echo '{"pages":[{"page_idx":0}]}' > "$T1/segments/p0001-0001/page_content_list.json"
echo "original p2" > "$T1/segments/p0002-0002/page.md"
touch "$T1/dummy.pdf"

run_rerun_to_file "$T1" success "$T1/dummy.pdf" "$T1/segments" "$OUT1" p0001-0001

assert_file_missing "备份已清理" "$T1/segments/p0001-0001.backup"
assert_file_exists "重跑 MD 已写入" "$T1/segments/p0001-0001/content/page.md"
assert_file_exists "v1 content_list 已同步" "$T1/segments/p0001-0001/page_content_list.json"
assert_file_exists "v2 content_list 已同步" "$T1/segments/p0001-0001/page_content_list_v2.json"
assert_file_exists "middle.json 已同步"    "$T1/segments/p0001-0001/middle.json"
assert_file_exists "model.json 已同步"     "$T1/segments/p0001-0001/model.json"
assert_file_exists "images 已同步"         "$T1/segments/p0001-0001/images/fig1.png"
assert_str_eq "p2 未被覆盖" "original p2" "$(cat "$T1/segments/p0002-0002/page.md")"

python3 << PYEOF
import json, sys
with open("$OUT1") as f: data = json.load(f)
seg = [s for s in data['segments'] if s['name']=='p0001-0001'][0]
assert seg['status'] == 'done', f'expected done, got {seg["status"]}'
assert seg['restored'] == False, f'expected false, got {seg["restored"]}'
assert seg['final_source'] == 'rerun', f'expected rerun, got {seg["final_source"]}'
PYEOF
if [[ $? -eq 0 ]]; then
    ok "JSON 契约正确 (status=done, restored=false, final_source=rerun)"
else
    fail "JSON 契约校验失败"
fi

# ── 场景 2：无 Markdown 输出 ──────────────────────────────────────
echo ""
echo "=== 场景 2：mineru 无 MD → 恢复备份 ==="
T2="$TEST_ROOT/t2"
OUT2="$T2/out.json"
mkdir -p "$T2/segments/p0001-0001"
echo "original content" > "$T2/segments/p0001-0001/page.md"
touch "$T2/dummy.pdf"

run_rerun_to_file "$T2" no_markdown "$T2/dummy.pdf" "$T2/segments" "$OUT2" p0001-0001

assert_str_eq "原段 MD 已恢复" "original content" "$(cat "$T2/segments/p0001-0001/page.md")"
assert_file_missing "backup 已清理" "$T2/segments/p0001-0001.backup"

python3 << PYEOF
import json
with open("$OUT2") as f: data = json.load(f)
seg = [s for s in data['segments'] if s['name']=='p0001-0001'][0]
assert seg['status'] == 'no_markdown', f'expected no_markdown, got {seg["status"]}'
assert seg['restored'] == True, f'expected true, got {seg["restored"]}'
assert seg['final_source'] == 'original', f'expected original, got {seg["final_source"]}'
PYEOF
if [[ $? -eq 0 ]]; then
    ok "JSON 契约正确 (status=no_markdown, restored=true, final_source=original)"
else
    fail "JSON 契约校验失败"
fi

# ── 场景 3：mineru 退出非零 ──────────────────────────────────────
echo ""
echo "=== 场景 3：mineru 退出非零 → 恢复备份 ==="
T3="$TEST_ROOT/t3"
OUT3="$T3/out.json"
mkdir -p "$T3/segments/p0001-0001"
echo "original content" > "$T3/segments/p0001-0001/page.md"
touch "$T3/dummy.pdf"

run_rerun_to_file "$T3" failed "$T3/dummy.pdf" "$T3/segments" "$OUT3" p0001-0001

assert_str_eq "原段 MD 已恢复" "original content" "$(cat "$T3/segments/p0001-0001/page.md")"
assert_file_missing "backup 已清理" "$T3/segments/p0001-0001.backup"

python3 << PYEOF
import json
with open("$OUT3") as f: data = json.load(f)
seg = [s for s in data['segments'] if s['name']=='p0001-0001'][0]
assert seg['status'] == 'failed', f'expected failed, got {seg["status"]}'
assert seg['restored'] == True, f'expected true, got {seg["restored"]}'
assert seg['final_source'] == 'original', f'expected original, got {seg["final_source"]}'
PYEOF
if [[ $? -eq 0 ]]; then
    ok "JSON 契约正确 (status=failed, restored=true, final_source=original)"
else
    fail "JSON 契约校验失败"
fi

# ── 场景 4：原目录不存在，重跑成功 → 无备份操作 ─────────────────
echo ""
echo "=== 场景 4：原段不存在 + 重跑成功 → 无备份恢复逻辑 ==="
T4="$TEST_ROOT/t4"
OUT4="$T4/out.json"
mkdir -p "$T4/segments"
touch "$T4/dummy.pdf"

run_rerun_to_file "$T4" success "$T4/dummy.pdf" "$T4/segments" "$OUT4" p0001-0001

assert_file_missing ".backup 不存在" "$T4/segments/p0001-0001.backup"
assert_file_exists "新段已创建" "$T4/segments/p0001-0001/content/page.md"

python3 << PYEOF
import json
with open("$OUT4") as f: data = json.load(f)
seg = [s for s in data['segments'] if s['name']=='p0001-0001'][0]
assert seg['status'] == 'done', f'expected done, got {seg["status"]}'
assert seg['restored'] == False, f'expected false, got {seg["restored"]}'
assert seg['final_source'] == 'rerun', f'expected rerun, got {seg["final_source"]}'
PYEOF
if [[ $? -eq 0 ]]; then
    ok "JSON 契约正确 (status=done, restored=false, final_source=rerun)"
else
    fail "JSON 契约校验失败"
fi

# ── 场景 5：残留 backup（seg_dir 不存在）→ 还原备份 ────────────
echo ""
echo "=== 场景 5：残留 .backup + seg_dir 不存在 → 还原备份 ==="
T5="$TEST_ROOT/t5"
OUT5="$T5/out.json"
mkdir -p "$T5/segments/p0001-0001.backup"
echo "backup data" > "$T5/segments/p0001-0001.backup/page.md"
# seg_dir 故意不存在
touch "$T5/dummy.pdf"

run_rerun_to_file "$T5" success "$T5/dummy.pdf" "$T5/segments" "$OUT5" p0001-0001

assert_file_missing ".backup 已还原" "$T5/segments/p0001-0001.backup"
assert_file_exists "seg_dir 已存在" "$T5/segments/p0001-0001/content/page.md"

# ── 场景 6：残留 backup（seg_dir 也存在）→ 陈旧 backup 被清理 ──
echo ""
echo "=== 场景 6：残留 .backup + seg_dir 也存在 → 清理陈旧 backup ==="
T6="$TEST_ROOT/t6"
OUT6="$T6/out.json"
mkdir -p "$T6/segments/p0001-0001" "$T6/segments/p0001-0001.backup"
echo "original" > "$T6/segments/p0001-0001/page.md"
echo "stale" > "$T6/segments/p0001-0001.backup/page.md"
touch "$T6/dummy.pdf"

run_rerun_to_file "$T6" success "$T6/dummy.pdf" "$T6/segments" "$OUT6" p0001-0001

assert_file_missing "陈旧 backup 已清理" "$T6/segments/p0001-0001.backup"
assert_file_exists "新 MD 已生成" "$T6/segments/p0001-0001/content/page.md"

# ── 场景 7：JSON 输出完整性 ────────────────────────────────────
echo ""
echo "=== 场景 7：JSON 输出完整性 ==="
T7="$TEST_ROOT/t7"
OUT7="$T7/out.json"
mkdir -p "$T7/segments/p0001-0001"
echo "original" > "$T7/segments/p0001-0001/page.md"
touch "$T7/dummy.pdf"

run_rerun_to_file "$T7" success "$T7/dummy.pdf" "$T7/segments" "$OUT7" p0001-0001

python3 << PYEOF
import json
with open("$OUT7") as f: data = json.load(f)
assert 'status' in data and data['status'] == 'completed'
assert 'exit_code' in data
assert 'rerun_count' in data
assert 'merged_markdown' in data
assert 'segments' in data and len(data['segments']) == 1
s = data['segments'][0]
assert 'name' in s
assert 'start_page' in s
assert 'end_page' in s
assert 'status' in s
assert 'restored' in s
assert 'final_source' in s
PYEOF
if [[ $? -eq 0 ]]; then
    ok "JSON 输出包含所有必选字段"
else
    fail "JSON 必选字段缺失"
fi

# ── 场景 8：content_list 位于段根目录（v1 + v2） ──
echo ""
echo "=== 场景 8：content_list 位于段根目录 ==="
T8="$TEST_ROOT/t8"
mkdir -p "$T8/segments/p0001-0001"
echo "original" > "$T8/segments/p0001-0001/page.md"
touch "$T8/dummy.pdf"

run_rerun_to_file "$T8" success "$T8/dummy.pdf" "$T8/segments" "$T8/out.json" p0001-0001

assert_file_exists "v1 content_list 在根目录" "$T8/segments/p0001-0001/page_content_list.json"
assert_file_exists "v2 content_list 在根目录" "$T8/segments/p0001-0001/page_content_list_v2.json"

# ── 场景 9：单页段名 ───
echo ""
echo "=== 场景 9：单页段名解析 ==="
T9="$TEST_ROOT/t9"
OUT9="$T9/out.json"
mkdir -p "$T9/segments/p0001-0001"
echo "original" > "$T9/segments/p0001-0001/page.md"
touch "$T9/dummy.pdf"

run_rerun_to_file "$T9" success "$T9/dummy.pdf" "$T9/segments" "$OUT9" p0001-0001

python3 << PYEOF
import json
with open("$OUT9") as f: data = json.load(f)
seg = data['segments'][0]
assert seg['start_page'] == 1 and seg['end_page'] == 1, f"got {seg['start_page']}-{seg['end_page']}"
PYEOF
if [[ $? -eq 0 ]]; then
    ok "单页段起止页正确"
else
    fail "单页段起止页异常"
fi

# ── 场景 10：去重 ───
echo ""
echo "=== 场景 10：重复段名去重 ==="
T10="$TEST_ROOT/t10"
OUT10="$T10/out.json"
mkdir -p "$T10/segments/p0001-0001"
echo "original" > "$T10/segments/p0001-0001/page.md"
touch "$T10/dummy.pdf"

run_rerun_to_file "$T10" success "$T10/dummy.pdf" "$T10/segments" "$OUT10" p0001-0001 p0001-0001

python3 << PYEOF
import json
with open("$OUT10") as f: data = json.load(f)
assert data['rerun_count'] == 1, f'rerun_count = {data["rerun_count"]}'
PYEOF
if [[ $? -eq 0 ]]; then
    ok "重复段名去重正确 (rerun_count=1)"
else
    fail "重复段名未正确去重"
fi

# ── 场景 11：pdf-auto 全部通过（无重跑）─────────────────────
echo ""
echo "=== 场景 11：pdf-auto 全部通过（无重跑）==="
T11="$TEST_ROOT/t11"
OUT11="$T11/out.json"
mkdir -p "$T11/segments/p0001-0001"
echo "original p1" > "$T11/segments/p0001-0001/page.md"
echo '{"pages":[{"page_idx":0}]}' > "$T11/segments/p0001-0001/page_content_list.json"
echo '{"pages":[{"page_idx":0,"type":"text"}]}' > "$T11/segments/p0001-0001/page_content_list_v2.json"
touch "$T11/dummy.pdf"
create_mock_manifest "$T11" "$T11/dummy.pdf" 1

reset_validate_stage
HOME="$MOCK_HOME" PDF_VALIDATE_BEHAVIOR=all_pass PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T11/dummy.pdf" "$T11/segments" 2>/dev/null > "$OUT11" || true

python3 << PYEOF11
import json
with open("$OUT11") as f: data = json.load(f)
assert data.get('status') == 'all_passed', f'expected all_passed, got {data.get("status")}'
assert data.get('exit_code') == 0, f'expected exit 0, got {data.get("exit_code")}'
assert data.get('merged_markdown'), 'merged_markdown missing'
PYEOF11
if [[ $? -eq 0 ]]; then
    ok "pdf-auto 全部通过路径正确 (status=all_passed, exit=0)"
else
    fail "pdf-auto 全部通过路径校验失败"
fi

# ── 场景 12：pdf-auto 重跑成功 → 全部通过 ──────────────────
echo ""
echo "=== 场景 12：pdf-auto 重跑成功 → 全部通过 ==="
T12="$TEST_ROOT/t12"
OUT12="$T12/out.json"
mkdir -p "$T12/segments/p0001-0001" "$T12/segments/p0002-0002"
echo "original p1" > "$T12/segments/p0001-0001/page.md"
echo '{"pages":[{"page_idx":0}]}' > "$T12/segments/p0001-0001/page_content_list.json"
echo '{"pages":[{"page_idx":0,"type":"text"}]}' > "$T12/segments/p0001-0001/page_content_list_v2.json"
echo "original p2" > "$T12/segments/p0002-0002/page.md"
touch "$T12/dummy.pdf"
create_mock_manifest "$T12" "$T12/dummy.pdf" 2

reset_validate_stage
HOME="$MOCK_HOME" MINERU_MOCK_MODE=success PDF_VALIDATE_BEHAVIOR=rerun_pass PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T12/dummy.pdf" "$T12/segments" 2>/dev/null > "$OUT12" || true

python3 << PYEOF12
import json
with open("$OUT12") as f: data = json.load(f)
assert data.get('status') == 'all_passed', f'expected all_passed, got {data.get("status")}'
assert data.get('exit_code') == 0, f'expected exit 0, got {data.get("exit_code")}'
rd = data.get('rerun_detail')
assert rd is not None and len(rd) == 1, f'expected 1 rerun_detail, got {rd}'
d = rd[0]
assert d['name'] == 'p0001-0001', f'expected p0001-0001, got {d["name"]}'
assert d['status'] == 'done', f'expected done, got {d["status"]}'
assert d['restored'] == False, f'expected false, got {d["restored"]}'
PYEOF12
if [[ $? -eq 0 ]]; then
    ok "pdf-auto 重跑成功路径正确 (rerun_detail 含 1 条 done 记录)"
else
    fail "pdf-auto 重跑成功路径校验失败"
fi

# ── 场景 13：pdf-auto 重跑失败 → 保留原结果 ────────────────
echo ""
echo "=== 场景 13：pdf-auto 重跑失败 → 保留原结果 ==="
T13="$TEST_ROOT/t13"
OUT13="$T13/out.json"
mkdir -p "$T13/segments/p0001-0001" "$T13/segments/p0002-0002"
echo "original p1" > "$T13/segments/p0001-0001/page.md"
echo '{"pages":[{"page_idx":0}]}' > "$T13/segments/p0001-0001/page_content_list.json"
echo '{"pages":[{"page_idx":0,"type":"text"}]}' > "$T13/segments/p0001-0001/page_content_list_v2.json"
echo "original p2" > "$T13/segments/p0002-0002/page.md"
touch "$T13/dummy.pdf"
create_mock_manifest "$T13" "$T13/dummy.pdf" 2

reset_validate_stage
HOME="$MOCK_HOME" MINERU_MOCK_MODE=failed PDF_VALIDATE_BEHAVIOR=rerun_fail PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T13/dummy.pdf" "$T13/segments" 2>/dev/null > "$OUT13" || true

assert_str_eq "重跑失败后原 MD 保留" "original p1" "$(cat "$T13/segments/p0001-0001/page.md")"

python3 << PYEOF13
import json
with open("$OUT13") as f: data = json.load(f)
assert data.get('status') == 'needs_review', f'expected needs_review, got {data.get("status")}'
assert data.get('exit_code') == 2, f'expected exit 2, got {data.get("exit_code")}'
rd = data.get('rerun_detail')
assert rd is not None and len(rd) == 1, f'expected 1 rerun_detail, got {rd}'
d = rd[0]
assert d['name'] == 'p0001-0001', f'expected p0001-0001, got {d["name"]}'
assert d['status'] == 'failed', f'expected failed, got {d["status"]}'
assert d['restored'] == False, f'expected false, got {d["restored"]}'
assert d['final_source'] == 'original', f'expected original, got {d["final_source"]}'
PYEOF13
if [[ $? -eq 0 ]]; then
    ok "pdf-auto 重跑失败路径正确 (rerun_detail 含 1 条 failed 记录)"
else
    fail "pdf-auto 重跑失败路径校验失败"
fi

# ── 场景 15：pdf-auto 一致性检查通过 → 保留旧输出 ──
echo ""
echo "=== 场景 15：pdf-auto 一致性检查通过 → 保留旧输出 ==="
T15="$TEST_ROOT/t15"
OUT15="$T15/out.json"
mkdir -p "$T15/segments/p0001-0001" "$T15/segments/p0002-0002"
echo "keep p1" > "$T15/segments/p0001-0001/page.md"
echo "keep p2" > "$T15/segments/p0002-0002/page.md"
touch "$T15/dummy.pdf"
create_mock_manifest "$T15" "$T15/dummy.pdf" 2

echo 1 > "$MOCK_DIR/.validate_stage"
HOME="$MOCK_HOME" PDF_VALIDATE_BEHAVIOR=all_pass PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T15/dummy.pdf" "$T15/segments" 2>/dev/null > "$OUT15" || true

assert_str_eq "pdf-auto 一致性检查后原内容保留" "keep p1" "$(cat "$T15/segments/p0001-0001/page.md")"

# ── 场景 16：pdf-auto 文件变更 → 一致性检查触发清理 ──
echo ""
echo "=== 场景 16：pdf-auto 文件变更 → 一致性检查触发清理 ==="
T16="$TEST_ROOT/t16"
OUT16="$T16/out.json"
mkdir -p "$T16/segments/p0001-0001" "$T16/segments/p0002-0002"
echo "will be cleaned" > "$T16/segments/p0001-0001/page.md"
echo "will be cleaned" > "$T16/segments/p0002-0002/page.md"
touch "$T16/dummy.pdf"

# 创建一个 hash 不匹配的 manifest（写入错误 hash）
python3 -c "
import json
sha = '0000000000000000000000000000000000000000000000000000000000000000'
m = {'model':'test','files':{'pdf':'dummy.pdf','segments':'segments'},'hash':{'sha256':sha},'segmentation':{'schema_version':1,'layout':'single_page','segment_size':1,'total_pages':2,'mineru':{'backend':'hybrid-engine','method':'auto','effort':'medium','lang':'ch'}},'parse_status':'segmented'}
with open('$T16/manifest.json','w') as f:
    json.dump(m, f, indent=2)
    f.write('\n')
"
echo 1 > "$MOCK_DIR/.validate_stage"
HOME="$MOCK_HOME" MINERU_MOCK_MODE=success PDF_VALIDATE_BEHAVIOR=all_pass PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T16/dummy.pdf" "$T16/segments" 2>/dev/null > "$OUT16" || true

# hash 不匹配 → 清理触发 → 原内容被删 → pdf-auto 重新创建
# pdf-auto 在清理后直接继续运行，mock 环境会创建新的 rerun/merge 内容
# 因此 p0001-0001 的原始内容不再存在
assert_file_missing "hash 不匹配触发清理，原内容已删除" "$T16/segments/p0001-0001/page.md"

# ── 场景 17：pdf-auto 旧多页段残留 → 一致性检查触发清理 ──
echo ""
echo "=== 场景 17：pdf-auto 旧多页段残留 → 一致性检查触发清理 ==="
T17="$TEST_ROOT/t17"
OUT17="$T17/out.json"
mkdir -p "$T17/segments/p0001-0001" "$T17/segments/p0011-0020" "$T17/segments/p0002-0002"
echo "clean me" > "$T17/segments/p0001-0001/page.md"
echo "multi-page" > "$T17/segments/p0011-0020/page.md"
echo "keep" > "$T17/segments/p0002-0002/page.md"
touch "$T17/dummy.pdf"
create_mock_manifest "$T17" "$T17/dummy.pdf" 2

echo 1 > "$MOCK_DIR/.validate_stage"
HOME="$MOCK_HOME" MINERU_MOCK_MODE=success PDF_VALIDATE_BEHAVIOR=all_pass PATH="$MOCK_DIR:$PATH" PDF_AUTO_JSON=1 bash "$MOCK_DIR/pdf-auto" "$T17/dummy.pdf" "$T17/segments" 2>/dev/null > "$OUT17" || true

# 多页段残留 → 清理触发 → 所有段目录被删除
assert_file_missing "多页段残留触发清理" "$T17/segments/p0001-0001/page.md"
assert_file_missing "多页段本身被删除" "$T17/segments/p0011-0020/page.md"
assert_file_missing "正常单页段也被删除（因为清理是整体 rm -rf）" "$T17/segments/p0002-0002/page.md"

echo ""
echo "═══════════════════════════════════════════"
echo "  通过: $PASS  失败: $FAIL"
echo "═══════════════════════════════════════════"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
