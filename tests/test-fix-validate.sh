#!/usr/bin/env bash
# pdf2md-fix 阶段2：修复记录与派生产物应用 —— 回归测试
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
m['formatting']={'schema_version':1,'mode':'merge_time','status':fm,'source_markdown_sha256':mdh}
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

# ── V1: demo60 无 manual_fixes 应失败 ──
echo "--- V1: 无 manual_fixes.jsonl ---"
out="$("$_scripts"/pdf-check-fixes "$_d60" 2>&1)" && rc=0 || rc=$?
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

# ── 汇总 ──
echo ""
echo "=== 测试完成 ==="
echo "通过: $ok"
echo "失败: $fail"
if [[ "$fail" -gt 0 ]]; then exit 1; fi
