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

# ── 汇总 ──
echo ""
echo "=== 测试完成 ==="
echo "通过: $ok"
echo "失败: $fail"
if [[ "$fail" -gt 0 ]]; then exit 1; fi
