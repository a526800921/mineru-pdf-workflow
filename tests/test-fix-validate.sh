#!/usr/bin/env bash
# pdf2md-fix 阶段2/3：修复记录、派生产物应用与结构化字段修正 —— 回归测试
set -eo pipefail

_scripts="$(cd "$(dirname "$0")/../scripts" && pwd)"
_d20="$(cd "$(dirname "$0")/../pdf/demo20" && pwd)"
_d60="$(cd "$(dirname "$0")/../pdf/demo60" && pwd)"
_d5="$(cd "$(dirname "$0")/../pdf/demo5" && pwd)"

ok=0; fail=0
trap 'for d in "${_td[@]}"; do [[ -d "$d" ]] && rm -rf "$d"; done' EXIT
_td=()

_mk() { local d; d="$(mktemp -d /tmp/tfv.XXXXXX)"; _td+=("$d"); echo "$d"; }
_pass() { echo "  PASS: $1"; ok=$((ok+1)); }
_fail() { echo "  FAIL: $1"; fail=$((fail+1)); }

_ck0() { local r=$1 n="$2"; if [[ "$r" -eq 0 ]]; then _pass "$n"; else _fail "$n (exit=$r)"; fi; }
_ck1() { local r=$1 n="$2"; if [[ "$r" -ne 0 ]]; then _pass "$n"; else _fail "$n (exit=$r, expect non-zero)"; fi; }
_grep() { local o="$1" p="$2" n="$3"; if echo "$o" | grep -q "$p"; then _pass "$n"; else _fail "$n <no match: $p>"; fi; }

_inject() {
  local pkg="$1" mf_jsonl="$2" mf_st="${3:-applied}" fm_st="${4:-verified}"
  python3 -c "
import hashlib, json, sys
pkg = '$pkg'; mf = '$mf_jsonl'; fs = '$mf_st'; fm = '$fm_st'
m = json.loads(open(pkg+'/manifest.json',encoding='utf-8').read())
mh = hashlib.sha256(open(pkg+'/manifest.json','rb').read()).hexdigest()
fh = hashlib.sha256(open(mf,'rb').read()).hexdigest() if mf and __import__('os').path.getsize(mf) else 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
md = sorted(__import__('pathlib').Path(pkg).glob('*.md'))
mdh = hashlib.sha256([p for p in md if p.name != 'review.md'][0].read_bytes()).hexdigest()
m['fixes']={'schema_version':1,'status':fs,'source_manifest_sha256':mh,'manual_fixes_sha256':fh,'markdown_sha256':mdh}
m['formatting']={'schema_version':1,'mode':'merge_time','status':fm,'source_markdown_sha256':mdh,'formatted_markdown_sha256':mdh}
import pathlib
data_dir = pathlib.Path(pkg) / 'data'
data_dir.mkdir(parents=True, exist_ok=True)
(data_dir / ('pre_format_md_' + mdh[:16] + '.md')).write_bytes([p for p in md if p.name != 'review.md'][0].read_bytes())
open(pkg+'/manifest.json','w',encoding='utf-8').write(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
"
}

_chk() {
  local pkg="$1" out rc
  out="$("$_scripts"/pdf-check-fixes "$pkg" 2>&1)" && rc=0 || rc=$?
  echo "$out"
  return "$rc"
}

echo "=== pdf2md-fix 阶段2 回归测试 ==="
echo ""

# ── V1: 无 manual_fixes 应失败 ──
echo "--- V1: 无 manual_fixes.jsonl ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/manual_fixes.jsonl"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V1: 无 manual_fixes 返回非零"
_grep "$out" "manual_fixes.jsonl 不存在" "V1: 包含文件缺失信息"

# ── V2: 合法修复记录应通过 ──
echo ""
echo "--- V2: 合法修复记录 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"demo20-p14-rebuild-001","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[14],"before":"8192 empty td","after":"4 columns","evidence":"PDF p14 verified"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "V2: 合法修复记录校验通过"

# ── V3: 非法 fix_type ──
echo ""
echo "--- V3: 非法 fix_type ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"b","fix_type":"invalid_type","review_action":"fix_md","status":"applied","pages":[1],"before":"x","after":"y","evidence":"z"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "proposed" "none" > /dev/null
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V3: 非法 fix_type 返回非零"
_grep "$out" "fix_type 不合法" "V3: 包含 fix_type 错误"

# ── V4: 缺少 fix_id ──
echo ""
echo "--- V4: 缺少 fix_id ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[1],"before":"x","after":"y","evidence":"z"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "proposed" "none" > /dev/null
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V4: 缺少 fix_id 返回非零"
_grep "$out" "缺少必含字段" "V4: 包含 fix_id 缺失错误"

# ── V5: hash 不匹配 ──
echo ""
echo "--- V5: hash 不匹配 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"f1","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[1],"before":"x","after":"y","evidence":"z"}
EOF
# 注入错误 hash
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
Z = '0'*64
m['fixes']={'schema_version':1,'status':'applied','source_manifest_sha256':Z,'manual_fixes_sha256':Z,'markdown_sha256':Z}
m['formatting']={'schema_version':1,'mode':'merge_time','status':'applied','source_markdown_sha256':Z}
open(p,'w',encoding='utf-8').write(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V5: hash 不匹配返回非零"
_grep "$out" "不匹配" "V5: 包含 hash 不匹配错误"

# ── V6: VLM 证据缺少字段 ──
echo ""
echo "--- V6: VLM 证据缺少字段 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"f1","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[1],"before":"x","after":"y","evidence":"z","vlm_evidence":{"model":"qwen3-vl-8b"}}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "proposed" "none" > /dev/null
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V6: VLM 证据缺少字段返回非零"
_grep "$out" "vlm_evidence" "V6: 包含 VLM 证据错误"

# ── V7: pages 为空 ──
echo ""
echo "--- V7: pages 为空 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"f1","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[],"before":"x","after":"y","evidence":"z"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "proposed" "none" > /dev/null
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "V7: pages 为空返回非零"
_grep "$out" "pages 必须是非空列表" "V7: 包含 pages 错误"

# ── T1: demo20 8192 扫描 ──
echo ""
echo "--- T1: demo20 8192 扫描 ---"
out="$("$_scripts"/pdf-table-fix "$_d20" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T1: 扫描完成"
_grep "$out" "候选扫描完成：2 页" "T1: 找到 2 页候选"
rm -f "$_d20/data/table_candidates.jsonl"

# ── T2: demo5 无 candidate ──
echo ""
echo "--- T2: demo5 无 candidate ---"
out="$("$_scripts"/pdf-table-fix "$_d5" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T2: 无候选时正常退出"
_grep "$out" "未发现需扫描的候选页" "T2: 输出无候选信息"

# ── A1: pdf-apply-fixes 简单修复应用 ──
echo ""
echo "--- A1: pdf-apply-fixes 简单修复应用 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"d20-p14-kw","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[14],"before":"11.8 Kw / 8500 rpm","after":"11.8 kW / 8500 rpm","evidence":"功率单位归一化测试"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "A1: 修复应用成功"
_grep "$out" "成功" "A1: 显示成功信息"
# 验证 MD 已更新
grep -q "11.8 kW / 8500 rpm" "$t/demo20.md" && _pass "A1: after 文本存在于 MD" || _fail "A1: MD 未更新 after 文本"
! grep -q "11.8 Kw / 8500 rpm" "$t/demo20.md" && _pass "A1: before 文本已被替换" || _fail "A1: before 文本仍存在"

# ── A2: 幂等跳过（重复应用） ──
echo ""
echo "--- A2: 幂等跳过 ---"
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "A2: 重复应用返回 0"
_grep "$out" "幂等跳过" "A2: 显示幂等跳过信息"

# ── A3: before 不存在 → 失败 ──
echo ""
echo "--- A3: before 不存在 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"d20-nonexist","fix_type":"fill_content","review_action":"fix_md","status":"applied","pages":[14],"before":"THIS_TEXT_DOES_NOT_EXIST_ANYWHERE_ZZZ","after":"REPLACEMENT","evidence":"测试"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "A3: before 不存在时返回非零"
# 注意：第一个页块找不到 before 时报错，因此 exit 1
_grep "$out" "未找到 before" "A3: 包含 before 未找到信息"

# ── A4: p47/p48 同字符串误命中回归 ──
echo ""
echo "--- A4: p47/p48 同字符串误命中保护 ---"
t=$(_mk)
# 创建测试用 manifest 和 markdown
python3 -c "
import json
m = {'model':'p48test','files':{'markdown':'test.md','pdf':'test.pdf','data':'data'},'segmentation':{'total_pages':48}}
open('$t/manifest.json','w',encoding='utf-8').write(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
"
cat > "$t/test.md" <<'EOF'
<!-- pages 47-47 -->
<p>Page 47 unique</p>
<table><tr><td>SAME_TEXT</td></tr></table>

<!-- pages 48-48 -->
<p>Page 48 unique</p>
<table><tr><td>SAME_TEXT</td></tr></table>
EOF
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"p47-fix","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[47],"before":"SAME_TEXT","after":"REPLACED","evidence":"回归测试"}
EOF
# 注入 manifest.fixes 和 formatting 块
python3 -c "
import json, hashlib
m = json.loads(open('$t/manifest.json', encoding='utf-8').read())
md_hash = hashlib.sha256(open('$t/test.md','rb').read()).hexdigest()
mf_hash = hashlib.sha256(open('$t/data/manual_fixes.jsonl','rb').read()).hexdigest()
m['fixes'] = {'schema_version':1,'status':'applied','source_manifest_sha256':'0'*64,'manual_fixes_sha256':mf_hash,'markdown_sha256':md_hash}
m['formatting'] = {'schema_version':1,'mode':'merge_time','status':'none','source_markdown_sha256':'0'*64}
open('$t/manifest.json','w',encoding='utf-8').write(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
"
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "A4: p47 修复应用成功"
# 验证：p47 的 SAME_TEXT 被替换，p48 的 SAME_TEXT 保留
grep -q "REPLACED" "$t/test.md" && _pass "A4: p47 内容已更新" || _fail "A4: p47 未更新"
s=$(grep -c "SAME_TEXT" "$t/test.md" || true)
[[ "$s" -eq 1 ]] && _pass "A4: p48 的 SAME_TEXT 仍保留（计数=1）" || _fail "A4: p48 也被替换或计数异常（count=$s）"

# ── A5: check_idempotent 幂等性校验（对已应用包） ──
echo ""
echo "--- A5: check_idempotent 幂等性校验 ---"
# 沿用 A4 的包（fixes.status=applied，修复已应用）
out="$("$_scripts"/pdf-check-fixes --verbose "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "A5: 已应用包的校验通过（含幂等性检查）"
_grep "$out" "校验通过" "A5: 输出校验通过信息"

# ── A6: check_idempotent 未正确应用的修复 ──
echo ""
echo "--- A6: check_idempotent 检测未应用的修复 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
# 创建一条 status=applied 的修复，但 MD 中 before 仍在、after 不在
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"fake-applied","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[14],"before":"11.8 Kw / 8500 rpm","after":"11.8 XX / 8500 rpm","evidence":"假应用"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
out="$("$_scripts"/pdf-check-fixes --verbose "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "A6: 检测到未应用的修复返回非零"
_grep "$out" "幂等性" "A6: 包含幂等性错误信息"

# ── A7: pdf-apply-fixes 页锚点不存在 → 失败 ──
echo ""
echo "--- A7: 页锚点不存在 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"invalid-page","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[999],"before":"x","after":"y","evidence":"不存在页测试"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "A7: 页锚点不存在时返回非零"
_grep "$out" "未找到页锚点" "A7: 包含页锚点未找到信息"

# ── A8: 第一条成功第二条失败 → 全部回滚（原子性） ──
echo ""
echo "--- A8: 部分成功后失败 → 原子回滚 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
md_orig_hash=$(shasum -a 256 "$t/demo20.md" | awk '{print $1}')
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"valid-fix","fix_type":"rebuild_table","review_action":"fix_md","status":"applied","pages":[14],"before":"11.8 Kw / 8500 rpm","after":"11.8 kW / 8500 rpm","evidence":"有效修复"}
{"fix_id":"bad-fix","fix_type":"fill_content","review_action":"fix_md","status":"applied","pages":[14],"before":"THIS_STRING_NEVER_EXISTS_ZZZ_12345","after":"REPLACED","evidence":"无效修复"}
EOF
_inject "$t" "$t/data/manual_fixes.jsonl" "applied" "verified" > /dev/null
manifest_before_hash=$(shasum -a 256 "$t/manifest.json" | awk '{print $1}')
out="$("$_scripts"/pdf-apply-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "A8: 有错误修复时返回非零"
_grep "$out" "未修改任何文件" "A8: 提示未修改任何文件"
# 验证 MD 未变
md_after_hash=$(shasum -a 256 "$t/demo20.md" | awk '{print $1}')
[[ "$md_orig_hash" == "$md_after_hash" ]] && _pass "A8: Markdown hash 不变（已回滚）" || _fail "A8: Markdown 擅自修改（hash=$md_after_hash）"
# 验证 manifest 未变
mf_after_hash=$(shasum -a 256 "$t/manifest.json" | awk '{print $1}')
[[ "$manifest_before_hash" == "$mf_after_hash" ]] && _pass "A8: manifest hash 不变（未写入）" || _fail "A8: manifest 擅自修改"

# ═══════════════════════════════════════════════
# 阶段 3：结构化字段修正（fix_data）
# ═══════════════════════════════════════════════

echo ""
echo "=== 阶段 3：fix_data 结构化字段修正 ==="

# ── F1: fix_data 缺失字段应被 pdf-check-fixes 捕获 ──
echo ""
echo "--- F1: fix_data 缺少必含字段 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"fix-bad-1","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"x","after":"y","evidence":"缺少 target_record_id 等 fix_data 字段"}
EOF
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"demo20.md"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "F1: fix_data 缺失 target_record_id 返回非零"
_grep "$out" "缺少字段" "F1: 包含 fix_data 字段缺失信息"

# ── F2: fix_data 无效 field_action / target_field ──
echo ""
echo "--- F2: fix_data 无效枚举值 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
mkdir -p "$t/data"
cat > "$t/data/manual_fixes.jsonl" <<'EOF'
{"fix_id":"fix-enum-1","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"x","after":"y","evidence":"z","target_record_id":"abc123","target_field":"color","field_action":"paint","old_value":"red","new_value":"blue"}
EOF
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"demo20.md"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "F2: 无效 field_action 返回非零"
_grep "$out" "field_action 不合法" "F2: 包含 field_action 错误"
_grep "$out" "target_field 不合法" "F2: 包含 target_field 错误"

# ── F3: fix_data amend 端到端 ──
echo ""
echo "--- F3: fix_data amend 修正 value 端到端 ---"
t=$(_mk)
mkdir -p "$t/data"
# 创建最小 quick_lookup_draft.csv
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,引擎 / 性能,最大净功率,11.8 Kw / 8500 rpm,kW,14,14,最大净功率: 11.8 Kw / 8500 rpm,medium,draft,html_table,html_table:1,1,1,,business_key
EOFCSV
# 创建 manifest.json（含 formatting 块）
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","formatted_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},"fixes":{"schema_version":1,"status":"applied","source_manifest_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","manual_fixes_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
mkdir -p "$t/data"
cp "$t/test.md" "$t/data/pre_format_md_e3b0c44298fc1c14.md"
# 首次运行 pdf-prepare-ingest 生成 ingest_ready.csv（获得 record_id）
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 获取 record_id
record_id=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
# 创建 manual_fixes.jsonl，修正 value（Kw→kW 大小写）
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-amend-001","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"单位大小写修正: Kw→kW","after":"11.8 kW / 8500 rpm","evidence":"PDF p14 显示 kW","target_record_id":"$record_id","target_field":"value","field_action":"amend","old_value":"11.8 Kw / 8500 rpm","new_value":"11.8 kW / 8500 rpm"}
EOFJSONL
# 重新运行 pdf-prepare-ingest
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 验证修正后的 ingest_ready.csv
corrected_val=$(grep "$record_id" "$t/data/ingest_ready.csv" | cut -d',' -f6)
corr_fix_id=$(grep "$record_id" "$t/data/ingest_ready.csv" | cut -d',' -f22)
ingest_status=$(grep "$record_id" "$t/data/ingest_ready.csv" | cut -d',' -f13)
[[ "$corrected_val" == "11.8 kW / 8500 rpm" ]] && _pass "F3: value 已修正" || _fail "F3: value 未修正 (got=$corrected_val)"
[[ "$corr_fix_id" == "fix-amend-001" ]] && _pass "F3: correction_fix_id 已设置" || _fail "F3: correction_fix_id 缺失 (got=$corr_fix_id)"
[[ "$ingest_status" == "not_ready" ]] && _pass "F3: 修正后 ingest_status=not_ready" || _fail "F3: ingest_status 不是 not_ready (got=$ingest_status)"
# record_id 应不变
grep -q "$record_id" "$t/data/ingest_ready.csv" && _pass "F3: record_id 稳定不变" || _fail "F3: record_id 变化"

# ── F4: manifest data_fixes 字段一致性 ──
echo ""
echo "--- F4: manifest data_fixes 字段校验 ---"
# F3 的包已经有正确的 manifest.fixes
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "F4: 含 data_fixes 的 manifest 校验通过"

# 破坏 ingest_after_sha256 验证不匹配
python3 -c "
import json
m=json.load(open('$t/manifest.json','r'))
m['fixes']['ingest_after_sha256']='deadbeef'
open('$t/manifest.json','w').write(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "F4: ingest_after_sha256 不匹配返回非零"
_grep "$out" "ingest_after_sha256 不匹配" "F4: 包含 hash 不匹配信息"

# ── F5: review_overrides 仍然生效（amend 不改 record_id） ──
echo ""
echo "--- F5: amend 后 review_overrides 仍匹配 ---"
t=$(_mk)
mkdir -p "$t/data"
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,引擎 / 性能,最大净功率,11.8 Kw,kg,14,14,test,medium,draft,html_table,html_table:1,1,1,,business_key
EOFCSV
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
# 首次生成 ingest（F5）
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
record_id=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
# 创建 review_overrides.csv 将记录设为 approved
cat > "$t/data/review_overrides.csv" <<EOFCSV
record_id,review_status,notes
$record_id,approved,F5 人工审核通过
EOFCSV
# 创建 fix_data amend 修正（F5）
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-amend-002","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"x","after":"y","evidence":"z","target_record_id":"$record_id","target_field":"value","field_action":"amend","old_value":"11.8 Kw","new_value":"11.8 kW"}
EOFJSONL
# 重新运行（应用修正）
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 验证：修正后 ingest_status=not_ready（即使 review_overrides 已 approved）
ingest_status=$(grep "$record_id" "$t/data/ingest_ready.csv" | cut -d',' -f13)
review_status=$(grep "$record_id" "$t/data/ingest_ready.csv" | cut -d',' -f12)
[[ "$review_status" == "approved" ]] && _pass "F5: review_overrides approved 仍然生效" || _fail "F5: review_status 被错误覆盖 (got=$review_status)"
[[ "$ingest_status" == "not_ready" ]] && _pass "F5: 修正后强制 not_ready" || _fail "F5: ingest_status 未被修正强制 (got=$ingest_status)"
_grep "$(grep "$record_id" "$t/data/ingest_ready.csv")" "data_corrected" "F5: notes 包含 data_corrected"

# ── F6: rekey 端到端（旧行 superseded，新行 supersedes_record_id） ──
echo ""
echo "--- F6: rekey 端到端 ---"
t=$(_mk)
mkdir -p "$t/data"
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,引擎,旧参数名,100,kg,14,14,test,medium,draft,html_table,html_table:1,1,1,,business_key
EOFCSV
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
old_rid=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
# 创建 rekey 修正
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-rekey-001","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"旧参数名","after":"新参数名","evidence":"PDF p14 显示正确参数名","target_record_id":"$old_rid","target_field":"key","field_action":"rekey","old_value":"旧参数名","new_value":"新参数名"}
EOFJSONL
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 验证旧行（定位：以 record_id 开头的行）
old_line=$(grep "^$old_rid," "$t/data/ingest_ready.csv")
old_status=$(echo "$old_line" | cut -d',' -f13)
old_sup_by=$(echo "$old_line" | cut -d',' -f24)
[[ "$old_status" == "superseded" ]] && _pass "F6: 旧行 ingest_status=superseded" || _fail "F6: 旧行状态错误 (got=$old_status)"
[[ -n "$old_sup_by" ]] && _pass "F6: 旧行 superseded_by 非空" || _fail "F6: 旧行 superseded_by 为空"
# 验证新行（定位：以新 record_id 开头的行）
new_rid="$old_sup_by"
new_line=$(grep "^$new_rid," "$t/data/ingest_ready.csv")
new_status=$(echo "$new_line" | cut -d',' -f13)
new_supersedes=$(echo "$new_line" | cut -d',' -f23)
new_key=$(echo "$new_line" | cut -d',' -f5)
[[ "$new_key" == "新参数名" ]] && _pass "F6: 新行 key=新参数名" || _fail "F6: 新行 key 错误 (got=$new_key)"
[[ "$new_status" == "not_ready" ]] && _pass "F6: 新行 ingest_status=not_ready" || _fail "F6: 新行状态错误 (got=$new_status)"
[[ "$new_supersedes" == "$old_rid" ]] && _pass "F6: 新行 supersedes_record_id 指向旧行" || _fail "F6: supersedes_record_id 不匹配 (got=$new_supersedes, expect=$old_rid)"

# ── F7: suppress 端到端（目标行保持 suppressed） ──
echo ""
echo "--- F7: suppress 端到端 ---"
t=$(_mk)
mkdir -p "$t/data"
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,概述,废弃字段,删除,kg,1,1,test,medium,draft,html_table,html_table:1,1,1,,business_key
EOFCSV
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
sup_rid=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-suppress-001","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[1],"before":"废弃字段","after":"","evidence":"PDF 中不存在该字段","target_record_id":"$sup_rid","target_field":"value","field_action":"suppress","old_value":"删除","new_value":""}
EOFJSONL
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
sup_line=$(grep "$sup_rid" "$t/data/ingest_ready.csv")
sup_status=$(echo "$sup_line" | cut -d',' -f13)
sup_notes=$(echo "$sup_line" | cut -d',' -f21)
[[ "$sup_status" == "suppressed" ]] && _pass "F7: suppress 后 ingest_status=suppressed" || _fail "F7: suppress 后状态错误 (got=$sup_status)"
echo "$sup_notes" | grep -q "suppressed_by: fix-suppress-001" && _pass "F7: notes 包含 suppressed_by" || _fail "F7: notes 缺少 suppressed_by"

# ── F8: 修正后冲突重算 ──
echo ""
echo "--- F8: amend 修正后冲突重算 ---"
t=$(_mk)
mkdir -p "$t/data"
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,规格,发动机型号,A,cc,14,14,testA,medium,draft,html_table,html_table:1,html_table:1,1,,business_key
demo20.pdf,demo20,规格,发动机型号,B,cc,14,14,testB,medium,draft,html_table,html_table:1,html_table:1,2,,business_key
EOFCSV
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 首次应产生冲突（两行同 key 不同 value）
conflict_count=$(wc -l < "$t/data/conflicts.csv" | tr -d ' ')
[[ "$conflict_count" -ge 2 ]] && _pass "F8: 修正前存在冲突 (${conflict_count} 行含表头)" || _fail "F8: 修正前无冲突 (${conflict_count} 行)"
# 获取两行的 record_id
rid_a=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
rid_b=$(tail -1 "$t/data/ingest_ready.csv" | cut -d',' -f1)
# amend 将 rid_a 的 value 从 A 改为 B（一致）
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-conflict-resolve","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"A","after":"B","evidence":"PDF p14 p15 实际均为 B","target_record_id":"$rid_a","target_field":"value","field_action":"amend","old_value":"A","new_value":"B"}
EOFJSONL
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 修正后冲突应消除
new_conflict_count=$(wc -l < "$t/data/conflicts.csv" | tr -d ' ')
[[ "$new_conflict_count" -eq 1 ]] && _pass "F8: 修正后冲突消除 (仅表头)" || _fail "F8: 修正后仍有冲突 ($new_conflict_count 行)"
# 验证 rid_a 的 value 已变为 B
amended_val=$(grep "$rid_a" "$t/data/ingest_ready.csv" | cut -d',' -f6)
[[ "$amended_val" == "B" ]] && _pass "F8: amend 后 value=B" || _fail "F8: value 未更新 (got=$amended_val)"

# ── F9: export 门禁验证（superseded/not_ready 不导出） ──
echo ""
echo "--- F9: export 门禁 ---"
t=$(_mk)
mkdir -p "$t/data"
cat > "$t/data/quick_lookup_draft.csv" <<'EOFCSV'
source_pdf,model,section_path,key,value,unit,page_start,page_end,evidence_text,confidence,status,notes,source_block_id,table_id,row_index,parent_key,key_role
demo20.pdf,demo20,规格,额定功率,10,kW,14,14,evidence ok,medium,draft,html_table,html_table:1,1,1,,business_key
EOFCSV
cat > "$t/manifest.json" <<'EOFJSON'
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
EOFJSON
touch "$t/test.md"
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
exp_rid=$(head -2 "$t/data/ingest_ready.csv" | tail -1 | cut -d',' -f1)
# 先加 review_overrides 使记录 approved
cat > "$t/data/review_overrides.csv" <<EOFCSV
record_id,review_status,notes
$exp_rid,approved,F9 审核通过
EOFCSV
# approve 后应 ready
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
ready_status=$(grep "$exp_rid" "$t/data/ingest_ready.csv" | cut -d',' -f13)
[[ "$ready_status" == "ready" ]] && _pass "F9: approved 后 ingest_status=ready" || _fail "F9: ready 状态错误 (got=$ready_status)"
# 运行 export — 应导出 1 条
"$_scripts"/pdf-export-ingest "$t" > /dev/null 2>&1
batch_count=$(wc -l < "$t/data/ingest_batch.jsonl" | tr -d ' ')
[[ "$batch_count" -eq 1 ]] && _pass "F9: ready 记录已导出 (1 条)" || _fail "F9: 导出数量错误 (got=$batch_count)"
# 再创建 amend 修正 → not_ready
cat > "$t/data/manual_fixes.jsonl" <<EOFJSONL
{"fix_id":"fix-export-gate","fix_type":"field_correction","review_action":"fix_data","status":"applied","pages":[14],"before":"10","after":"10.5","evidence":"PDF p14 精确值","target_record_id":"$exp_rid","target_field":"value","field_action":"amend","old_value":"10","new_value":"10.5"}
EOFJSONL
"$_scripts"/pdf-prepare-ingest "$t" > /dev/null 2>&1
# 修正后 → not_ready
corr_status=$(grep "$exp_rid" "$t/data/ingest_ready.csv" | cut -d',' -f13)
[[ "$corr_status" == "not_ready" ]] && _pass "F9: 修正后 ingest_status=not_ready" || _fail "F9: 修正后状态错误 (got=$corr_status)"
# 重新 export → 应导出 0 条
"$_scripts"/pdf-export-ingest "$t" > /dev/null 2>&1
new_batch_count=$(wc -l < "$t/data/ingest_batch.jsonl" | tr -d ' ')
[[ "$new_batch_count" -eq 0 ]] && _pass "F9: 修正后 ready=0，export 为 0 条" || _fail "F9: 修正后仍有导出 (got=$new_batch_count)"

# ── 汇总 ──
echo ""
echo "=== 测试完成 ==="
echo "通过: $ok"
echo "失败: $fail"
if [[ "$fail" -gt 0 ]]; then exit 1; fi
