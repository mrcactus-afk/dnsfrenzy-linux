#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/vpn.sh"
source "$SCRIPT_DIR/lib/evaluator.sh"
source "$SCRIPT_DIR/lib/applier.sh"

acquire_lock
check_dependencies

is_locked && { write_log "DEBUG" "System locked. Skipping."; exit 0; }
is_vpn_active && { write_log "INFO" "VPN detected. Pausing."; exit 0; }

MODE_FILE="/var/cache/dnsfrenzy/mode.json"
[[ ! -f "$MODE_FILE" ]] && echo '{"mode": "auto"}' > "$MODE_FILE"
CURRENT_MODE=$(jq -r '.mode // "auto"' "$MODE_FILE")

if [[ "$CURRENT_MODE" == "manual" ]]; then
    write_log "DEBUG" "Manual mode active. Skipping auto-evaluation."
    exit 0
fi

write_log "INFO" "Starting evaluation cycle..."
if evaluate_servers; then
    write_log "INFO" "Best: $BEST_NAME ($BEST_SERVER) [${BEST_TIME}ms]"
    echo "{\"server\": \"$BEST_SERVER\", \"time\": \"$BEST_TIME\", \"timestamp\": $(date +%s)}" > "$CACHE"
    apply_dns "$BEST_SERVER" "$BEST_TIME" "$BEST_NAME"
else
    write_log "WARN" "No servers responded."
fi
