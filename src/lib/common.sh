#!/bin/bash
CONFIG="/opt/dnsfrenzy/config.json"
CACHE="/var/cache/dnsfrenzy/best.json"
HEALTH="/var/cache/dnsfrenzy/health.json"
LOCK_FILE="/var/run/dnsfrenzy.lock"
STATE_FILE="/var/cache/dnsfrenzy/state.json"
LOG="/var/log/dnsfrenzy/dnsfrenzy.log"

write_log() {
    local level="$1"; shift; local msg="$1"; shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $msg" | tee -a "$LOG"
}

acquire_lock() {
    exec 9>"$LOCK_FILE"
    flock -n 9 || { write_log "WARN" "Another instance running."; exit 0; }
}

is_locked() {
    [[ -f "$STATE_FILE" ]] && [[ "$(jq -r '.locked // false' "$STATE_FILE" 2>/dev/null)" == "true" ]]
}

check_dependencies() {
    command -v jq >/dev/null 2>&1 && command -v dig >/dev/null 2>&1 || {
        write_log "ERROR" "Missing jq or dnsutils."; exit 1;
    }
}
