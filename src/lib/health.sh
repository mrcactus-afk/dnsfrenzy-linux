#!/bin/bash
HEALTH_FILE="/var/cache/dnsfrenzy/health.json"
[[ ! -f "$HEALTH_FILE" ]] && echo "{}" > "$HEALTH_FILE"

update_health() {
    local ip="$1"; local time_ms="$2"; local success="$3"
    local tmp=$(mktemp)
    local s=$(jq -r --arg ip "$ip" '.[$ip].success // 0' "$HEALTH_FILE")
    local f=$(jq -r --arg ip "$ip" '.[$ip].failures // 0' "$HEALTH_FILE")
    local total_t=$(jq -r --arg ip "$ip" '.[$ip].total_time // 0' "$HEALTH_FILE")
    local checks=$(jq -r --arg ip "$ip" '.[$ip].checks // 0' "$HEALTH_FILE")
    
    if [[ "$success" == "true" ]]; then s=$((s + 1)); total_t=$((total_t + time_ms)); else f=$((f + 1)); fi
    checks=$((checks + 1))
    if [[ $checks -gt 20 ]]; then s=$((s * 19 / 20)); f=$((f * 19 / 20)); total_t=$((total_t * 19 / 20)); checks=20; fi
    
    local avg=0; [[ $s -gt 0 ]] && avg=$((total_t / s))
    local rate=0; [[ $checks -gt 0 ]] && rate=$((s * 100 / checks))
    
    jq --arg ip "$ip" --argjson s "$s" --argjson f "$f" --argjson tt "$total_t" --argjson c "$checks" --argjson avg "$avg" --argjson rate "$rate" \
       '.[$ip] = {success: $s, failures: $f, total_time: $tt, checks: $c, avg_time: $avg, success_rate: $rate}' "$HEALTH_FILE" > "$tmp" && mv "$tmp" "$HEALTH_FILE"
}
