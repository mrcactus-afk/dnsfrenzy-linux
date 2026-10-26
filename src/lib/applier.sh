#!/bin/bash
apply_dns() {
    local best_server="$1"; local best_time="$2"; local best_name="$3"
    local export_resolv=$(jq -r '.export_resolv // true' "$CONFIG")
    local fallback_primary=$(jq -r '.fallback_primary // "1.1.1.1"' "$CONFIG")
    local cached_server=$(jq -r '.server // "none"' "$CACHE" 2>/dev/null || echo "none")
    
    if [[ "$best_server" != "$cached_server" ]]; then
        write_log "INFO" "Server changed to $best_name ($best_server) [${best_time}ms]"
        if [[ "$export_resolv" == "true" ]]; then
            if [[ -L /etc/resolv.conf ]]; then
                local target=$(readlink /etc/resolv.conf)
                if [[ "$target" == *"systemd"* ]]; then
                    command -v resolvectl &>/dev/null && resolvectl global "$best_server" "$fallback_primary"
                fi
            else
                echo -e "# Managed by DNSFrenzy\nnameserver $best_server\nnameserver $fallback_primary" > /etc/resolv.conf
            fi
        fi
    fi
}
