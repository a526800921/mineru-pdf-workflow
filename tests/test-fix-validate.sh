#!/usr/bin/env bash
# pdf2md-fix 阶段2/3：修复记录、派生产物应用与结构化字段修正 —— 回归测试
set -eo pipefail

_scripts="$(cd "$(dirname "$0")/../scripts" && pwd)"
_d20="$(cd "$(dirname "$0")/../pdf/demo20" && pwd)"
_d60="$(cd "$(dirname "$0")/../pdf/demo60" && pwd)"
_d5="$(cd "$(dirname "$0")/../pdf/demo5" && pwd)"
_cf="$(cd "$(dirname "$0")/../pdf/春风250Sr" && pwd)"

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
(m.setdefault('hash', {}))['manual_fixes_sha256'] = fh
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
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T1: 扫描完成"
_grep "$out" "候选扫描完成" "T1: 候选扫描成功"
_grep "$out" "native_missing:2" "T1: 包含 native_missing 候选"

# ── T2: demo5 无 candidate ──
echo ""
echo "--- T2: demo5 无 candidate ---"
out="$("$_scripts"/pdf-table-fix "$_d5" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T2: 无候选时正常退出"
_grep "$out" "未发现需扫描的候选页" "T2: 输出无候选信息"

# ═══════════════════════════════════════════════
# 阶段 1：table_candidates v2 schema 集成测试
# ═══════════════════════════════════════════════

echo ""
echo "=== 阶段 1：候选扫描与 manifest 同步 ==="

# ── T3: 写 candidates 并同步 manifest ──
echo "--- T3: 写入候选并同步 manifest ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
# 清空现有登记，确保 clean state
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('table_candidates', None)
m.get('hash', {}).pop('table_candidates_sha256', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
rm -f "$t/data/table_candidates.jsonl"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T3: 扫描完成"
_grep "$out" "status.*completed" "T3: JSON 状态为 completed"
# 验证 manifest 已更新
python3 -c "
import json
m = json.loads(open('$t/manifest.json', encoding='utf-8').read())
assert 'table_candidates' in m.get('files', {}), 'manifest.files.table_candidates 未设置'
assert m.get('hash', {}).get('table_candidates_sha256'), 'hash.table_candidates_sha256 为空'
assert (__import__('pathlib').Path('$t') / m['files']['table_candidates']).exists(), '候选文件不存在'
" && _pass "T3: manifest 已同步" || _fail "T3: manifest 同步失败"

# ── T4: 无候选时不修改 manifest ──
echo ""
echo "--- T4: 无候选包不修改 manifest ---"
t=$(_mk)
cp -R "$_d5/"* "$t/" 2>/dev/null || true
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('table_candidates', None)
m.get('hash', {}).pop('table_candidates_sha256', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
manifest_before=$(cat "$t/manifest.json")
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T4: 无候选正常退出"
manifest_after=$(cat "$t/manifest.json")
if [ "$manifest_before" = "$manifest_after" ]; then
  _pass "T4: manifest 未被修改"
else
  _fail "T4: manifest 被意外修改"
fi

# ── T5: native_table_text_missing 候选 ──
echo ""
echo "--- T5: native_table_text_missing 检测 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
# 该临时包只验证候选产物；去掉真实包的 manual_fixes，避免真实
# candidate_id（demo60_pXXXX）与临时目录名生成的 candidate_id 混用。
rm -f "$t/data/manual_fixes.jsonl"
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('manual_fixes', None)
m.get('hash', {}).pop('manual_fixes_sha256', None)
m.pop('fixes', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\\n')
"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
# demo60 has native_table_text_missing pages (14,16,36,42,43,44,46,51,60)
python3 -c "
import json
with open('$t/data/table_candidates.jsonl', encoding='utf-8') as f:
    types = set()
    for line in f:
        c = json.loads(line)
        types.add(c.get('candidate_type'))
assert 'native_missing' in types, f'未找到 native_missing 类型候选，已有: {types}'
" && _pass "T5: native_missing 候选已生成" || _fail "T5: 缺少 native_missing 候选"

# ── T6: pdf-check-fixes 验证候选文件（先修复 hash） ──
echo ""
echo "--- T6: pdf-check-fixes 验证候选文件 ---"
# T5 已写入候选并修复了 manifest hash，直接校验
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T6: 修复后 check-fixes 通过（含 table_candidates）"

# ── T7: 候选文件存在但 manifest 未登记 → 错误 ──
echo ""
echo "--- T7: manifest 登记缺失检测 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
# 先运行扫描生成候选文件 + 同步 manifest
"$_scripts"/pdf-table-fix "$t" > /dev/null 2>&1
# 再从 manifest 移除登记
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('table_candidates', None)
m.get('hash', {}).pop('table_candidates_sha256', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T7: manifest 登记缺失被检测到"
_grep "$out" "table_candidates" "T7: 错误信息包含 table_candidates"

# ── T8: 重复 candidate_id 检测 ──
echo ""
echo "--- T8: 重复 candidate_id 检测 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
"$_scripts"/pdf-table-fix "$t" > /dev/null 2>&1
python3 -c "
import json, hashlib
src = '$t/data/table_candidates.jsonl'
with open(src, encoding='utf-8') as f:
    lines = f.readlines()
# Append first line again to create duplicate
lines.append(lines[0])
with open(src, 'w', encoding='utf-8') as f:
    f.writelines(lines)
# Update manifest hash
m = json.loads(open('$t/manifest.json', encoding='utf-8').read())
m['hash']['table_candidates_sha256'] = hashlib.sha256(open(src, 'rb').read()).hexdigest()
open('$t/manifest.json', 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T8: 重复 candidate_id 被检测到"
_grep "$out" "重复" "T8: 错误信息包含重复提示"

# ── T9: malformed manifest → 优雅报错 ──
echo ""
echo "--- T9: malformed manifest ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_candidates.jsonl"
echo "this is not json" > "$t/manifest.json"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T9: malformed manifest 返回非零"
_grep "$out" "错误" "T9: 包含错误信息"
# 确保无半成品
if [ -f "$t/data/table_candidates.jsonl" ]; then
  _fail "T9: 残留了候选文件半成品"
else
  _pass "T9: 无半成品残留"
fi

# ── T10: 缺失 PDF → 优雅报错 ──
echo ""
echo "--- T10: 缺失 PDF ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
# 同时移除 files.pdf 和 source_pdf
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
# Remove pdf references
m.get('files', {}).pop('pdf', None)
m.pop('source_pdf', None)
# Also remove any actual PDF files
import pathlib
for pdf_file in pathlib.Path('$t').glob('*.pdf'):
    pdf_file.unlink()
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T10: 缺失 PDF 返回非零"
_grep "$out" "PDF" "T10: 错误信息包含 PDF"

# ── T11: 候选写入目标为目录 → 报错无残留 ──
echo ""
echo "--- T11: 候选写入失败（目标为目录）---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
# 让 data/table_candidates.jsonl 为目录
rm -f "$t/data/table_candidates.jsonl"
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('table_candidates', None)
m.get('hash', {}).pop('table_candidates_sha256', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\\n')
"
mkdir -p "$t/data/table_candidates.jsonl"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T11: 写入失败返回非零"
# 删除目录以便检查
rm -rf "$t/data/table_candidates.jsonl"
# 检查 manifest 未被修改
python3 -c "
import json
m = json.loads(open('$t/manifest.json', encoding='utf-8').read())
assert 'table_candidates' not in m.get('files', {}), 'manifest 不应登记 table_candidates'
assert 'table_candidates_sha256' not in m.get('hash', {}), 'hash 不应登记 table_candidates'
" && _pass "T11: manifest 未修改（半成品已清理）" || _fail "T11: manifest 被意外修改"

# ── T12: page_fallback 数据完整但无关注信号 → 返回 0 不写 ──
echo ""
echo "--- T12: page_fallback 但无关注信号 ---"
t=$(_mk)
cp -R "$_d20/"* "$t/" 2>/dev/null || true
# 清空 page_fallback 中的 quality_signals
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
pf = m.get('page_fallback', {})
for v in pf.values():
    v['quality_signals'] = []
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
rm -f "$t/data/table_candidates.jsonl"
out="$("$_scripts"/pdf-table-fix "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "T12: 无关注信号时正常退出"
_grep "$out" "未发现需扫描的候选页" "T12: 输出无候选信息"
if [ -f "$t/data/table_candidates.jsonl" ]; then
  _fail "T12: 不应写入候选文件"
else
  _pass "T12: 未产生任何候选文件"
fi

# ── T13: 重复 page_anchor 检测 ──
echo ""
echo "--- T13: 重复 page_anchor 检测 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
"$_scripts"/pdf-table-fix "$t" > /dev/null 2>&1
python3 -c "
import json, hashlib
src = '$t/data/table_candidates.jsonl'
with open(src, encoding='utf-8') as f:
    lines = f.readlines()
# 用不同的 candidate_id 但相同的 page_anchor 构造重复
first = json.loads(lines[0])
dup = dict(first)
dup['candidate_id'] = first['candidate_id'] + '_DUP'
lines.append(json.dumps(dup, ensure_ascii=False) + '\n')
with open(src, 'w', encoding='utf-8') as f:
    f.writelines(lines)
# Update manifest hash
m = json.loads(open('$t/manifest.json', encoding='utf-8').read())
m['hash']['table_candidates_sha256'] = hashlib.sha256(open(src, 'rb').read()).hexdigest()
open('$t/manifest.json', 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\n')
"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T13: 重复 page_anchor 被检测到"
_grep "$out" "page_anchor 重复" "T13: 错误信息包含 page_anchor 重复"

# ── T14: candidate_ref 无候选文件必须失败 ──
echo ""
echo "--- T14: candidate_ref 闭环校验 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
python3 -c "
import json
p = '$t/manifest.json'
m = json.loads(open(p, encoding='utf-8').read())
m.get('files', {}).pop('table_candidates', None)
m.get('hash', {}).pop('table_candidates_sha256', None)
open(p, 'w', encoding='utf-8').write(json.dumps(m, ensure_ascii=False, indent=2)+'\\n')
"
rm -f "$t/data/table_candidates.jsonl"
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "T14: candidate_ref 缺少候选文件返回非零"
_grep "$out" "含 candidate_ref" "T14: 包含 candidate_ref 闭环错误"

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
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},"page_numbering":{"mapping_type":"constant_offset","printed_to_physical_offset":0,"status":"verified"}}
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
{"model":"test","files":{"markdown":"test.md","pdf":"demo20.pdf"},"formatting":{"schema_version":1,"mode":"merge_time","status":"verified","source_markdown_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},"page_numbering":{"mapping_type":"constant_offset","printed_to_physical_offset":0,"status":"verified"}}
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

# ── R1: pdf-table-repair 单页 draft 生成 ──
echo ""
echo "--- R1: 单页 draft 生成 (--page 87) ---"
t=$(_mk)
cp -R "$_cf/"* "$t/" 2>/dev/null || true
if [ -f "$t/data/table_candidates.jsonl" ]; then
  rm -f "$t/data/table_repair_draft.jsonl"
  out="$("$_scripts"/pdf-table-repair "$t" --page 87 2>&1)" && rc=0 || rc=$?
  _ck0 $rc "R1: 单页 draft 生成成功"
  _grep "$out" "修复 draft 生成完成" "R1: 输出含完成信息"
  if [ -f "$t/data/table_repair_draft.jsonl" ]; then
    _pass "R1: draft 文件已生成"
    python3 -c "
import json
m=json.load(open('$t/manifest.json'))
f=m.get('files',{}).get('table_repair_draft','')
h=m.get('hash',{}).get('table_repair_draft_sha256','')
assert f=='data/table_repair_draft.jsonl', f'files 未登记: {f}'
assert len(h)>0, 'hash 为空'
print(f'  manifest: files={f}, hash={h[:16]}...')
" 2>&1 && _pass "R1: manifest 登记正确" || _fail "R1: manifest 登记异常"
    _ck0 "$(scripts/pdf-check-fixes "$t" 2>/dev/null; echo $?)" "R1: check-fixes 通过"
  else
    _fail "R1: draft 文件未生成"
  fi
else
  echo "  SKIP: 候选文件不存在"
fi

# ── R2: 全页 draft 生成（跨页检测） ──
echo ""
echo "--- R2: 全页 draft 生成 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_repair_draft.jsonl" "$t/manifest.json.tmp"
out="$("$_scripts"/pdf-table-repair "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "R2: 全页 draft 生成成功"
draft_lines=$(wc -l < "$t/data/table_repair_draft.jsonl" 2>/dev/null || echo 0)
if [ "$draft_lines" -gt 0 ]; then _pass "R2: draft 文件非空 ($draft_lines 行)"; else _fail "R2: draft 为空"; fi
python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    lines=[json.loads(l) for l in f if l.strip()]
total=len(lines)
assert total>0, 'draft 为空'
ok_nh=sum(1 for d in lines if d.get('needs_human')==True)
ok_st=sum(1 for d in lines if d.get('status')=='proposed')
ok_rt=sum(1 for d in lines if d.get('repair_type') in ('pretty_print','fill_missing_text','structure_warning'))
print(f'  总数={total}, needs_human={ok_nh}/{total}, status=proposed={ok_st}/{total}, 合法repair_type={ok_rt}/{total}')
assert ok_nh==total, f'{total-ok_nh} 条 needs_human 不为 true'
assert ok_st==total, f'{total-ok_st} 条 status 不为 proposed'
assert ok_rt==total, f'{total-ok_rt} 条 repair_type 不合法'
" 2>&1 && _pass "R2: 所有 draft 满足 schema v1" || _fail "R2: schema v1 异常"

# ── R3: 无效页返回空 ──
echo ""
echo "--- R3: 无效页返回空 ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_repair_draft.jsonl"
out="$("$_scripts"/pdf-table-repair "$t" --page 999 2>&1)" && rc=0 || rc=$?
_ck0 $rc "R3: 无效页返回 0（信息非错误）"
_grep "$out" "未生成" "R3: 输出含未生成信息"

# ── R4: 无候选时跳过 ──
echo ""
echo "--- R4: 无候选时跳过 ---"
t=$(_mk)
cp -R "$_d5/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_candidates.jsonl"
out="$("$_scripts"/pdf-table-repair "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "R4: 无候选返回 0"
_grep "$out" "无 table_candidates" "R4: 输出含无候选信息"

# ── R5: pdf-check-fixes 检测 repair_draft ──
echo ""
echo "--- R5: pdf-check-fixes 检测 repair_draft ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 47 > /dev/null 2>&1
out="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc=0 || rc=$?
_ck0 $rc "R5: check-fixes 检测 draft 通过"
python3 -c "
import json
m=json.load(open('$t/manifest.json'))
m['hash']['table_repair_draft_sha256']='badhash'
json.dump(m, open('$t/manifest.json','w'), ensure_ascii=False, indent=2)
" 2>/dev/null
out2="$("$_scripts"/pdf-check-fixes "$t" 2>&1)" && rc2=0 || rc2=$?
_ck1 $rc2 "R5: hash 异常返回非零"
_grep "$out2" "table_repair_draft_sha256" "R5: 含 hash 错误信息"

# ── R6: pdf-table-repair --apply 端到端 ──
echo ""
echo "--- R6: pdf-table-repair --apply ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/manual_fixes.jsonl" "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 47 > /dev/null 2>&1
fix_id=$(python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    print(json.loads(f.readline())['fix_id'])
" 2>/dev/null)
# 准备 manifest fixes/formatting
python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
md_hash=hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest()
src_hash=hashlib.sha256(open('$t/manifest.json','rb').read()).hexdigest()
m['fixes']={'schema_version':1,'status':'pending','markdown_sha256':md_hash,'manual_fixes_sha256':'','source_manifest_sha256':src_hash}
m['formatting']={'schema_version':1,'mode':'merge_time','status':'none','source_markdown_sha256':md_hash,'formatted_markdown_sha256':md_hash}
json.dump(m, open('$t/manifest.json','w'), ensure_ascii=False, indent=2)
" 2>/dev/null
md_hash_before=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
"$_scripts"/pdf-table-repair "$t" --apply "$fix_id" > /dev/null 2>&1 && rc=0 || rc=$?
_ck0 $rc "R6: --apply 成功"
# 校验 Markdown hash 已变化
md_hash_after=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
if [ "$md_hash_before" != "$md_hash_after" ]; then
  _pass "R6: Markdown hash 已变化"
else
  _fail "R6: Markdown hash 未变化"
fi
# manual_fixes 有 applied 记录
python3 -c "
import json
with open('$t/data/manual_fixes.jsonl') as f:
    applied=[l for l in f if json.loads(l).get('status')=='applied']
assert len(applied)>0, '没有 applied 记录'
" 2>/dev/null && _pass "R6: manual_fixes 含 applied 记录" || _fail "R6: manual_fixes 无 applied 记录"
# apply 后完整 checker 必须通过（含顶层和 fixes 块 hash）
out_check="$($_scripts/pdf-check-fixes "$t" 2>&1)" && rc_check=0 || rc_check=$?
_ck0 $rc_check "R6: apply 后 pdf-check-fixes 通过"
# 校验 manual_fixes_sha256 一致性
python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
top=m.get('hash',{}).get('manual_fixes_sha256','')
fix=m.get('fixes',{}).get('manual_fixes_sha256','')
act=hashlib.sha256(open('$t/data/manual_fixes.jsonl','rb').read()).hexdigest()
assert top==act, f'top hash mismatch: {top[:12]} vs {act[:12]}'
assert fix==act, f'fix hash mismatch: {fix[:12]} vs {act[:12]}'
print(f'  hash 一致性: {act[:16]}... ✅')
" 2>/dev/null && _pass "R6: manual_fixes_sha256 一致" || _fail "R6: manual_fixes_sha256 不一致"

# ── R7: pdf-table-repair --reject ──
echo ""
echo "--- R7: pdf-table-repair --reject ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/manual_fixes.jsonl" "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 48 > /dev/null 2>&1
fix_id=$(python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    print(json.loads(f.readline())['fix_id'])
" 2>/dev/null)
md_hash_before=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
"$_scripts"/pdf-table-repair "$t" --reject "$fix_id" "测试拒绝" > /dev/null 2>&1 && rc=0 || rc=$?
_ck0 $rc "R7: --reject 成功"
# Markdown hash 不变
md_hash_after=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
if [ "$md_hash_before" == "$md_hash_after" ]; then
  _pass "R7: Markdown hash 不变"
else
  _fail "R7: Markdown hash 不应变化"
fi
python3 -c "
import json
with open('$t/data/manual_fixes.jsonl') as f:
    rejected=[json.loads(l) for l in f if 'reject' in l]
assert len(rejected)>0, '没有 reject 记录'
assert rejected[0].get('status')=='rejected', 'status 不是 rejected'
" 2>/dev/null && _pass "R7: manual_fixes 含 rejected 记录" || _fail "R7: manual_fixes 记录异常"
"$_scripts"/pdf-check-fixes "$t" > /dev/null 2>&1 && _pass "R7: reject 后 pdf-check-fixes 通过" || _fail "R7: reject 后 check-fixes 失败"
python3 -c "
import hashlib,json
m=json.load(open('$t/manifest.json'))
h=hashlib.sha256(open('$t/data/manual_fixes.jsonl','rb').read()).hexdigest()
assert m.get('files',{}).get('manual_fixes')=='data/manual_fixes.jsonl'
assert m.get('hash',{}).get('manual_fixes_sha256')==h
assert m.get('fixes',{}).get('manual_fixes_sha256')==h
" 2>/dev/null && _pass "R7: reject 后 manifest hash 已同步" || _fail "R7: reject 后 manifest hash 未同步"

# ── R8: 重复 --apply 幂等跳过 ──
echo ""
echo "--- R8: 幂等 --apply ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/manual_fixes.jsonl" "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 47 > /dev/null 2>&1
fix_id=$(python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    print(json.loads(f.readline())['fix_id'])
" 2>/dev/null)
python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
md_hash=hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest()
src_hash=hashlib.sha256(open('$t/manifest.json','rb').read()).hexdigest()
m['fixes']={'schema_version':1,'status':'pending','markdown_sha256':md_hash,'manual_fixes_sha256':'','source_manifest_sha256':src_hash}
m['formatting']={'schema_version':1,'mode':'merge_time','status':'none','source_markdown_sha256':md_hash,'formatted_markdown_sha256':md_hash}
json.dump(m, open('$t/manifest.json','w'), ensure_ascii=False, indent=2)
" 2>/dev/null
# 第一次 apply
"$_scripts"/pdf-table-repair "$t" --apply "$fix_id" > /dev/null 2>&1
md_after_first=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
# 第二次 apply（幂等）
"$_scripts"/pdf-table-repair "$t" --apply "$fix_id" > /dev/null 2>&1 && rc=0 || rc=$?
md_after_second=$(python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
print(hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest())
" 2>/dev/null)
if [ "$md_after_first" == "$md_after_second" ]; then
  _pass "R8: 幂等跳过（hash 不变）"
else
  _fail "R8: 非幂等（hash 变化）"
fi

# ── R9: hash 漂移时拒绝 apply ──
echo ""
echo "--- R9: hash 漂移拒绝 apply ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/manual_fixes.jsonl" "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 47 > /dev/null 2>&1
fix_id=$(python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    print(json.loads(f.readline())['fix_id'])
" 2>/dev/null)
python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
md_rel=m.get('files',{}).get('markdown','')
md_hash=hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest()
src_hash=hashlib.sha256(open('$t/manifest.json','rb').read()).hexdigest()
m['fixes']={'schema_version':1,'status':'pending','markdown_sha256':md_hash,'manual_fixes_sha256':'','source_manifest_sha256':src_hash}
m['formatting']={'schema_version':1,'mode':'merge_time','status':'none','source_markdown_sha256':md_hash,'formatted_markdown_sha256':md_hash}
json.dump(m, open('$t/manifest.json','w'), ensure_ascii=False, indent=2)
" 2>/dev/null
# 模拟 hash 漂移：修改 Markdown
md_rel=$(python3 -c "
import json
print(json.load(open('$t/manifest.json')).get('files',{}).get('markdown',''))
" 2>/dev/null)
echo " " >> "$t/$md_rel"
out="$("$_scripts"/pdf-table-repair "$t" --apply "$fix_id" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "R9: hash 漂移返回非零"
_grep "$out" "hash 不匹配" "R9: 含 hash 漂移错误"

# ── R10: apply 失败时 manual_fixes 回滚 ──
echo ""
echo "--- R10: apply 失败回滚 manual_fixes ---"
t=$(_mk)
cp -R "$_d60/"* "$t/" 2>/dev/null || true
rm -f "$t/data/table_repair_draft.jsonl"
"$_scripts"/pdf-table-repair "$t" --page 47 > /dev/null 2>&1
fix_id=$(python3 -c "
import json
with open('$t/data/table_repair_draft.jsonl') as f:
    print(json.loads(f.readline())['fix_id'])
" 2>/dev/null)
python3 -c "
import json,hashlib
m=json.load(open('$t/manifest.json'))
draft='$t/data/table_repair_draft.jsonl'
rows=[json.loads(line) for line in open(draft,encoding='utf-8') if line.strip()]
rows[0]['expected_hit_count']=999
open(draft,'w',encoding='utf-8').write(''.join(json.dumps(x,ensure_ascii=False)+'\\n' for x in rows))
m.setdefault('hash',{})['table_repair_draft_sha256']=hashlib.sha256(open(draft,'rb').read()).hexdigest()
md_rel=m.get('files',{}).get('markdown','')
md_hash=hashlib.sha256(open('$t/'+md_rel,'rb').read()).hexdigest()
src_hash=hashlib.sha256(open('$t/manifest.json','rb').read()).hexdigest()
m['fixes']={'schema_version':1,'status':'pending','markdown_sha256':md_hash,'manual_fixes_sha256':'','source_manifest_sha256':src_hash}
m['formatting']={'schema_version':1,'mode':'merge_time','status':'none','source_markdown_sha256':md_hash,'formatted_markdown_sha256':md_hash}
json.dump(m, open('$t/manifest.json','w'), ensure_ascii=False, indent=2)
" 2>/dev/null
md_before=$(shasum -a 256 "$t/demo60.md" | awk '{print $1}')
manifest_before=$(shasum -a 256 "$t/manifest.json" | awk '{print $1}')
manual_before=$(shasum -a 256 "$t/data/manual_fixes.jsonl" | awk '{print $1}')
out="$($_scripts/pdf-table-repair "$t" --apply "$fix_id" 2>&1)" && rc=0 || rc=$?
_ck1 $rc "R10: apply 内部失败返回非零"
md_after=$(shasum -a 256 "$t/demo60.md" | awk '{print $1}')
manifest_after=$(shasum -a 256 "$t/manifest.json" | awk '{print $1}')
manual_after=$(shasum -a 256 "$t/data/manual_fixes.jsonl" | awk '{print $1}')
[ "$md_before" = "$md_after" ] && _pass "R10: Markdown 字节级回滚" || _fail "R10: Markdown 未回滚"
[ "$manifest_before" = "$manifest_after" ] && _pass "R10: manifest 字节级回滚" || _fail "R10: manifest 未回滚"
[ "$manual_before" = "$manual_after" ] && _pass "R10: manual_fixes 字节级回滚" || _fail "R10: manual_fixes 未回滚"

# ── 汇总 ──
echo ""
echo "=== 测试完成 ==="
echo "通过: $ok"
echo "失败: $fail"
if [[ "$fail" -gt 0 ]]; then exit 1; fi
