#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/root/dev/doctoralia-scrapper"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
LOG_DIR="$PROJECT_ROOT/data/logs"
RUN_LOG="$LOG_DIR/daily_scrape.$(date +%F).log"
LOCK_FILE="/var/lock/doctoralia-daily.lock"
TMP_DIR="$PROJECT_ROOT/data/temp"
HEALTH_DIR="$PROJECT_ROOT/data/health"
STATUS_JSON="$HEALTH_DIR/status.json"

mkdir -p "$LOG_DIR" "$TMP_DIR" "$HEALTH_DIR"

export PATH="$PROJECT_ROOT/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

send_telegram() {
  local text="$1"
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" -d text="${text}" -d disable_web_page_preview=true >/dev/null || true
  fi
}

log() {
  echo "[$(date '+%F %T')] $*" | tee -a "$RUN_LOG"
}

wait_for_network() {
  local tries=30
  local url="https://www.doctoralia.com.br"
  for ((i=1;i<=tries;i++)); do
    if curl -sSf -m 10 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

get_url_from_config() {
  "$VENV_PYTHON" - "$PROJECT_ROOT/config/config.json" <<'PY'
import json,sys
p=sys.argv[1]
url=""
try:
  with open(p,'r',encoding='utf-8') as f:
    cfg=json.load(f)
    if 'urls' in cfg and isinstance(cfg['urls'], dict):
      url = cfg['urls'].get('profile_url', '')
    if not url:
      for k in ("profile_url","url","doctoralia_url","profile"):
        if isinstance(cfg.get(k),str):
          url=cfg.get(k).strip(); break
except Exception: pass
print(url)
PY
}

write_status() {
  local phase="$1"
  local attempts="$2"
  local message="$3"
  mkdir -p "$HEALTH_DIR"
  "$VENV_PYTHON" - <<PY
import json, time
path="$STATUS_JSON"
try:
  data={}
  try:
    with open(path,'r',encoding='utf-8') as f: data=json.load(f)
  except Exception: pass
  now=int(time.time())
  if "$phase"=="starting":
    data.update({"last_run_start": now, "last_run_status": "running", "attempts": 0, "message": ""})
  elif "$phase"=="success":
    data.update({"last_run_end": now, "last_run_status": "success", "attempts": $attempts, "message": "$message"})
  else:
    data.update({"last_run_end": now, "last_run_status": "failure", "attempts": $attempts, "message": "$message"})
  with open(path,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
except Exception: pass
PY
}

# Concurrency lock
exec 9>"$LOCK_FILE" 2>/dev/null || true
if ! flock -n 9 2>/dev/null; then
  log "Another run is in progress. Exiting."
  exit 0
fi
trap 'rc=$?; flock -u 9 2>/dev/null || true; rm -f "$LOCK_FILE" 2>/dev/null || true; exit $rc' EXIT

if [[ ! -x "$VENV_PYTHON" ]]; then
  log "ERROR: venv interpreter not found at $VENV_PYTHON"
  send_telegram "🔴 Doctoralia: venv missing at $VENV_PYTHON on $(hostname)"
  write_status "failure" 0 "venv missing"
  exit 1
fi

ln -sf "$(basename "$RUN_LOG")" "$LOG_DIR/latest.log"

log "🚀 Starting Doctoralia full workflow"
send_telegram "⏳ Doctoralia: job started at $(date '+%F %T')"
write_status "starting" 0 ""

if ! wait_for_network; then
  log "ERROR: Network not available after waiting. Aborting."
  send_telegram "🔴 Doctoralia: network unavailable, aborting"
  write_status "failure" 0 "network unavailable"
  exit 2
fi

cd "$PROJECT_ROOT"

URL="$(get_url_from_config)"
DEFAULT_URL="https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
if [[ -z "$URL" ]]; then
  URL="$DEFAULT_URL"
  log "Config URL not found; using default URL: $URL"
else
  log "Using URL from config: $URL"
fi

attempt=0
max_attempts=3
backoff=60

run_once() {
  set +e
  "$VENV_PYTHON" -u "$PROJECT_ROOT/main.py" run --url "$URL" 2>&1
  rc=$?
  if [[ $rc -ne 0 ]]; then
    "$VENV_PYTHON" -u "$PROJECT_ROOT/main.py" run 2>&1
    rc=$?
  fi
  set -e
  echo "__RC__=$rc"
  return 0
}

while (( attempt < max_attempts )); do
  attempt=$((attempt+1))
  log "📍 Attempt $attempt of $max_attempts"
  output="$(run_once | tee -a "$RUN_LOG")"
  rc="$(echo "$output" | awk -F= '/^__RC__=/ {print $2}' | tail -1)"
  if [[ "$rc" == "0" ]]; then
    log "✅ Workflow completed successfully"
    send_telegram "✅ Doctoralia: SUCCESS on attempt $attempt at $(date '+%F %T')"
    write_status "success" "$attempt" "ok"
    exit 0
  fi

  if echo "$output" | grep -qiE 'Too Many Requests|HTTP 429|rate limit'; then
    log "⚠️  Detected rate limiting. Backing off longer."
    sleep $(( backoff * 3 ))
  elif echo "$output" | grep -qiE 'Timeout|timed out|Connection.*reset|Read error'; then
    log "⚠️  Detected network/timeout error. Backing off."
    sleep "$backoff"
  elif echo "$output" | grep -qiE 'Selenium|WebDriver|chromedriver|no such session|disconnected'; then
    log "⚠️  Detected Selenium/WebDriver issue. Backing off and retrying."
    sleep "$backoff"
  else
    log "⚠️  Unknown error (rc=$rc). Backing off."
    sleep "$backoff"
  fi
  backoff=$(( backoff * 2 ))
done

log "❌ All attempts failed"
send_telegram "🔴 Doctoralia: FAILED after $max_attempts attempts at $(date '+%F %T'). Check logs: $(hostname):$RUN_LOG"
write_status "failure" "$max_attempts" "max attempts failed"
exit 3
