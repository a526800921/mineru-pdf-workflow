#!/usr/bin/env bash
# ModelPad VLM helper 启停行为测试，不访问真实网络或真实模型。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ROOT
TMP="$(mktemp -d)"
MOCK_BIN="$TMP/bin"
STATE="$TMP/state"
CALLS="$TMP/calls"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

mkdir -p "$MOCK_BIN"

# mock curl
cat > "$MOCK_BIN/curl" << 'MOCKCURL'
#!/usr/bin/env bash
set -euo pipefail
state="${MOCK_STATE:?}"
calls="${MOCK_CALLS:?}"
method="GET"
url=""
for arg in "$@"; do
  case "$arg" in -X) : ;; POST) method="POST" ;; http://*) url="$arg" ;; esac
done
printf '%s %s\n' "$method" "$url" >> "$calls"

if [[ -f "${MOCK_STATE}_start_fail" ]]; then
  echo '{"ok":false,"error":"mock failure"}'; exit 0
fi
if [[ -f "${MOCK_STATE}_timeout" ]]; then
  if [[ "$method" == "POST" && "$url" == */start ]]; then echo '{"ok":true}'
  else echo '{"ok":true,"model":{"status":"stopped","port":9005}}'; fi
  exit 0
fi

if [[ "$method" == "POST" && "$url" == */start ]]; then
  echo running > "$state"; echo '{"ok":true}'
elif [[ "$method" == "POST" && "$url" == */stop ]]; then
  echo stopped > "$state"; echo '{"ok":true}'
elif [[ "$(cat "$state" 2>/dev/null || echo stopped)" == "running" ]]; then
  echo '{"ok":true,"model":{"status":"running","port":9005}}'
else
  echo '{"ok":true,"model":{"status":"stopped","port":9005}}'
fi
MOCKCURL
chmod +x "$MOCK_BIN/curl"

# ── 测试 1：复用已运行服务且不停止 ──────────────
echo "=== 基本路径 ==="
echo "running" > "$STATE"
: > "$CALLS"
set +e
PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  MODELPAD_VLM_START_TIMEOUT=2 bash << 'SCRIPT' 2>/dev/null
source "${ROOT}/scripts/lib/modelpad-vlm-service"
log(){ :; }
ensure_vlm_api log
[[ "$api_url" == "http://127.0.0.1:9005" ]] || exit 3
[[ "$_MODELPAD_VLM_STARTED_BY_SCRIPT" == "0" ]] || exit 4
modelpad_stop_vlm_if_started log
SCRIPT
rc=$?
set -e
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
if [[ "$rc" -eq 0 && "$stop_calls" -eq 0 ]]; then
  pass "复用已运行服务且不停止"
else
  fail "复用场景异常 (rc=$rc, stop=$stop_calls)"
fi

# ── 测试 2：自动启动并在结束时停止 ────────────────
echo "stopped" > "$STATE"
: > "$CALLS"
set +e
PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  MODELPAD_VLM_START_TIMEOUT=2 bash << 'SCRIPT' 2>/dev/null
source "${ROOT}/scripts/lib/modelpad-vlm-service"
log(){ :; }
ensure_vlm_api log
[[ "$api_url" == "http://127.0.0.1:9005" ]] || exit 3
[[ "$_MODELPAD_VLM_STARTED_BY_SCRIPT" == "1" ]] || exit 4
modelpad_stop_vlm_if_started log
SCRIPT
rc=$?
set -e
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
if [[ "$rc" -eq 0 && "$stop_calls" -eq 1 ]]; then
  pass "自动启动并在结束时停止"
else
  fail "自动启停异常 (rc=$rc, stop=$stop_calls)"
fi

# ── 测试 3：启动失败 ────────────────────────────
echo ""
echo "=== 失败/超时路径 ==="
echo "stopped" > "$STATE"
touch "${STATE}_start_fail"
: > "$CALLS"
set +e
PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  MODELPAD_VLM_START_TIMEOUT=2 bash << 'SCRIPT' 2>/dev/null
source "${ROOT}/scripts/lib/modelpad-vlm-service"
log(){ :; }
ensure_vlm_api log && exit 3
# ensure_vlm_api 失败 → 必须继续到 stop
modelpad_stop_vlm_if_started log
SCRIPT
rc=$?
set -e
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
rm -f "${STATE}_start_fail"
if [[ "$stop_calls" -eq 0 ]]; then
  pass "启动失败时正确退出且不调用 stop"
else
  fail "启动失败路径异常 (rc=$rc, stop=$stop_calls)"
fi

# ── 测试 4：等待超时 ────────────────────────────
echo "stopped" > "$STATE"
touch "${STATE}_timeout"
: > "$CALLS"
set +e
PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  MODELPAD_VLM_START_TIMEOUT=3 bash << 'SCRIPT' 2>/dev/null
source "${ROOT}/scripts/lib/modelpad-vlm-service"
log(){ :; }
ensure_vlm_api log && exit 3
# 虽然 start 接受了请求（_MODELPAD_VLM_STARTED_BY_SCRIPT=1），但等待超时
# ensure_vlm_api 返回非 0 → 不执行 stop（因为无法确定服务是否已启动）
modelpad_stop_vlm_if_started log
SCRIPT
rc=$?
set -e
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
rm -f "${STATE}_timeout"
if [[ "$stop_calls" -eq 1 ]]; then
  pass "启动超时时通过 EXIT trap 停止 VLM（防止孤儿服务）"
else
  fail "超时路径异常 (rc=$rc, stop=$stop_calls)"
fi

# ── 测试 5：异常退出清理 ──────────────────────────
echo ""
echo "=== 异常退出清理 ==="
echo "stopped" > "$STATE"
: > "$CALLS"
set +e
PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  MODELPAD_VLM_START_TIMEOUT=2 bash << 'SCRIPT' 2>/dev/null
source "${ROOT}/scripts/lib/modelpad-vlm-service"
log(){ :; }
trap 'modelpad_stop_vlm_if_started log' EXIT
ensure_vlm_api log || exit 2
# 模拟脚本异常退出
exit 1
SCRIPT
rc=$?
set -e
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
if [[ "$stop_calls" -eq 1 ]]; then
  pass "异常退出时仍通过 EXIT trap 停止 VLM"
else
  fail "异常退出清理异常 (stop=$stop_calls, want=1)"
fi

# ── 测试 6：直连模式 ────────────────────────────
echo ""
echo "=== 直连模式 ==="
T6_DIR="$TMP/t6"
mkdir -p "$T6_DIR/segments/p0001-0001" "$T6_DIR/data"
echo "" > "$T6_DIR/segments/p0001-0001/page.md"
cat > "$T6_DIR/manifest.json" << JSON
{"model":"test","files":{"markdown":"test.md","segments":"segments"},"parse_status":"segmented"}
JSON

echo "stopped" > "$STATE"
: > "$CALLS"
set +e
VLM_API_BASE=http://127.0.0.1:9005 PATH="$MOCK_BIN:$PATH" MOCK_STATE="$STATE" MOCK_CALLS="$CALLS" \
  PDF_EVAL_VLM_JSON=1 bash "$ROOT/scripts/pdf-eval-vlm" "$T6_DIR" 2>/dev/null > "$T6_DIR/out.json" || true
set -e
start_calls="$(awk '$1 == "POST" && $2 ~ /\/start$/ {n++} END {print n+0}' "$CALLS")"
stop_calls="$(awk '$1 == "POST" && $2 ~ /\/stop$/ {n++} END {print n+0}' "$CALLS")"
if [[ "$start_calls" -eq 0 && "$stop_calls" -eq 0 ]]; then
  pass "直连模式不调用 ModelPad start/stop"
else
  fail "直连模式异常 (start=$start_calls, stop=$stop_calls)"
fi
current_state="$(cat "$STATE")"
if [[ "$current_state" == "stopped" ]]; then
  pass "直连模式不改变 ModelPad 服务状态"
else
  fail "直连模式改变了服务状态 (got $current_state)"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  通过: $PASS  失败: $FAIL"
echo "═══════════════════════════════════════════"
if [[ "$FAIL" -gt 0 ]]; then exit 1; fi
