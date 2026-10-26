#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/health.sh"

evaluate_servers() {
    local results_file=$(mktemp)
    while IFS=\t' read -r primary name; do
        local start=$(date +%s%N)
        if dig +time=2 +tries=1 +short @"$primary" google.com &>/dev/null; then
            local end=$(date +%s%N)
            local time_ms=$(( (end - start) / 1000000 ))
            update_health "$primary" "$time_ms" "true"
            echo "$time_ms $primary $name" >> "$results_file"
        else
            update_health "$primary" "0" "false"
        fi
    done < <(jq -r '.servers[] | select(.enabled != false) | "\(.primary)\t\(.name)"' "$CONFIG" 2>/dev/null)
    
    if [[ -s "$results_file" ]]; then
        local best_line=$(sort -n "$results_file" | head -n 1)
        BEST_TIME=$(echo "$best_line" | awk '{print $1}')
        BEST_SERVER=$(echo "$best_line" | awk '{print $2}')
        BEST_NAME=$(echo "$best_line" | awk '{print $3}')
        rm -f "$results_file"
        return 0
    fi
    rm -f "$results_file"
    return 1
}
