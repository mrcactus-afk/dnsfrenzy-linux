#!/bin/bash
set -e
dnf install -y jq bind-utils
mkdir -p /opt/dnsfrenzy /var/log/dnsfrenzy /var/cache/dnsfrenzy
cat > /opt/dnsfrenzy/config.json << 'CFG'
{
    "interval": 30,
    "http_test": false,
    "http_timeout": 3,
    "http_url": "",
    "smart_mix": true,
    "fallback_chain": true,
    "blacklist_threshold": 3,
    "blacklist_duration": 300,
    "multi_interface": true,
    "export_resolv": true,
    "log_history": true,
    "history_file": "/var/log/dnsfrenzy/history.jsonl",
    "fallback_primary": "1.1.1.1",
    "fallback_secondary": "1.0.0.1",
    "servers": [
        {"name":"Radar","primary":"10.202.10.10","secondary":"10.202.10.11"},
        {"name":"403","primary":"10.202.10.202","secondary":"10.202.10.102"},
        {"name":"Begzar","primary":"185.55.226.26","secondary":"185.55.225.25"},
        {"name":"LagSlayer","primary":"5.160.132.222","secondary":"5.160.132.221"},
        {"name":"Shelter","primary":"94.103.125.158","secondary":"94.103.125.157"},
        {"name":"LagZero","primary":"95.38.132.152","secondary":"95.38.132.153"},
        {"name":"Electro","primary":"78.157.42.100","secondary":"78.157.42.101"},
        {"name":"Lag Zero","primary":"95.38.132.153","secondary":"95.38.132.152"},
        {"name":"Mokhaberat","primary":"217.218.127.127","secondary":"217.218.155.155"}
    ]
}
CFG
cat > /opt/dnsfrenzy/dnsfrenzy.sh << 'SCR'
#!/bin/bash
CONFIG="/opt/dnsfrenzy/config.json"
CACHE="/var/cache/dnsfrenzy/best.json"
HISTORY="/var/log/dnsfrenzy/history.jsonl"
LOG="/var/log/dnsfrenzy/dnsfrenzy.log"
BLACKLIST_FILE="/var/cache/dnsfrenzy/blacklist.json"
RESOLV_CONF="/etc/resolv.conf.dnsfrenzy.tmp"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG"; }
INTERVAL=$(jq -r '.interval' "$CONFIG")
HTTP_TEST=$(jq -r '.http_test' "$CONFIG")
HTTP_URL=$(jq -r '.http_url' "$CONFIG")
HTTP_TIMEOUT=$(jq -r '.http_timeout' "$CONFIG")
SMART_MIX=$(jq -r '.smart_mix' "$CONFIG")
FALLBACK_CHAIN=$(jq -r '.fallback_chain' "$CONFIG")
BLACKLIST_THRESHOLD=$(jq -r '.blacklist_threshold' "$CONFIG")
BLACKLIST_DURATION=$(jq -r '.blacklist_duration' "$CONFIG")
MULTI_INTERFACE=$(jq -r '.multi_interface' "$CONFIG")
EXPORT_RESOLV=$(jq -r '.export_resolv' "$CONFIG")
LOG_HISTORY=$(jq -r '.log_history' "$CONFIG")
declare -A BLACKLIST
if [ -f "$BLACKLIST_FILE" ]; then
    while IFS= read -r line; do
        ip=$(echo "$line" | jq -r '.ip')
        until=$(echo "$line" | jq -r '.until')
        BLACKLIST["$ip"]=$until
    done < <(jq -c '.[]' "$BLACKLIST_FILE" 2>/dev/null)
fi
is_blacklisted() {
    local ip="$1"; local until=${BLACKLIST[$ip]}
    if [ -n "$until" ] && [ "$(date +%s)" -lt "$until" ]; then return 0; else unset BLACKLIST[$ip]; return 1; fi
}
test_latency() {
    local ip="$1"
    if is_blacklisted "$ip"; then echo "99999"; return; fi
    if [ "$HTTP_TEST" = "true" ]; then
        local start=$(date +%s%N)
        curl -s -o /dev/null --connect-timeout "$HTTP_TIMEOUT" --max-time "$HTTP_TIMEOUT" "$HTTP_URL" --dns-servers "$ip" 2>/dev/null > /dev/null
        local exit_code=$?; local end=$(date +%s%N)
        if [ $exit_code -eq 0 ]; then local elapsed=$(( (end - start) / 1000000 )); echo "$elapsed"; else echo "99999"; fi
    else
        local result=$(ping -c 2 -W 1 "$ip" 2>/dev/null | tail -1 | awk -F '/' '{print $5}')
        if [[ -z "$result" || "$result" == "" ]]; then echo "99999"; else printf "%.0f" "$result"; fi
    fi
}
get_best_dns() {
    local best_primary=""; local best_secondary=""; local best_name="Fallback"
    local second_primary=""; local second_secondary=""; local second_name=""
    local best_latency=999999; local second_latency=999999
    local servers=$(jq -c '.servers[]' "$CONFIG")
    local scores=()
    while IFS= read -r server; do
        name=$(echo "$server" | jq -r '.name')
        primary=$(echo "$server" | jq -r '.primary')
        secondary=$(echo "$server" | jq -r '.secondary')
        latency=$(test_latency "$primary")
        log "Tested $name: ${latency}ms"
        if [ "$latency" -lt 99999 ]; then
            scores+=("$latency|$primary|$secondary|$name")
        else
            local fail_count=$(jq -r ".fail_count.\"$primary\" // 0" "$BLACKLIST_FILE" 2>/dev/null || echo "0")
            fail_count=$((fail_count + 1))
            if [ "$fail_count" -ge "$BLACKLIST_THRESHOLD" ]; then
                until_time=$(( $(date +%s) + BLACKLIST_DURATION ))
                BLACKLIST["$primary"]=$until_time
                log "Blacklisted $primary until $(date -d @$until_time)"
                jq ". + [{\"ip\":\"$primary\",\"until\":$until_time}]" "$BLACKLIST_FILE" 2>/dev/null | jq -s 'unique_by(.ip)' > "$BLACKLIST_FILE.tmp" && mv "$BLACKLIST_FILE.tmp" "$BLACKLIST_FILE"
            fi
        fi
    done <<< "$servers"
    IFS=$'\n' scores=($(sort -n -t '|' -k1 <<<"${scores[*]}"))
    if [ ${#scores[@]} -ge 1 ]; then
        IFS='|' read -r best_latency best_primary best_secondary best_name <<< "${scores[0]}"
        if [ ${#scores[@]} -ge 2 ] && [ "$SMART_MIX" = "true" ]; then
            IFS='|' read -r second_latency second_primary second_secondary second_name <<< "${scores[1]}"
            best_secondary=$second_secondary
        fi
    fi
    if [ -z "$best_primary" ]; then
        best_primary=$(jq -r '.fallback_primary' "$CONFIG")
        best_secondary=$(jq -r '.fallback_secondary' "$CONFIG")
        best_name="Fallback"; best_latency=99999
    fi
    log "Best: $best_name ($best_primary) - ${best_latency}ms"
    echo "{\"primary\":\"$best_primary\",\"secondary\":\"$best_secondary\",\"name\":\"$best_name\",\"latency\":$best_latency,\"timestamp\":\"$(date -Iseconds)\"}" > "$CACHE"
    if [ "$LOG_HISTORY" = "true" ]; then
        echo "{\"timestamp\":\"$(date -Iseconds)\",\"primary\":\"$best_primary\",\"secondary\":\"$best_secondary\",\"name\":\"$best_name\",\"latency\":$best_latency}" >> "$HISTORY"
    fi
    echo "$best_primary|$best_secondary|$best_name|$best_latency"
}
apply_dns() {
    local primary="$1"; local secondary="$2"; local name="$3"; local latency="$4"
    if [ "$MULTI_INTERFACE" = "true" ]; then
        for iface in $(ip link show | grep -E '^[0-9]+: (en|wl)' | awk -F': ' '{print $2}'); do
            resolvectl dns "$iface" "$primary" "$secondary" 2>/dev/null
        done
    else
        resolvectl dns "$primary" "$secondary" 2>/dev/null
    fi
    resolvectl domain ~. 2>/dev/null
    if [ "$EXPORT_RESOLV" = "true" ]; then
        echo "nameserver $primary" > "$RESOLV_CONF"
        echo "nameserver $secondary" >> "$RESOLV_CONF"
        cp "$RESOLV_CONF" /etc/resolv.conf 2>/dev/null || log "Could not update /etc/resolv.conf"
    fi
    log "Applied DNS: $name ($primary / $secondary) - ${latency}ms"
}
log "DNSFrenzy v1.1.1 started"
while true; do
    output=$(get_best_dns | tail -n1)
    primary=$(echo "$output" | cut -d'|' -f1)
    secondary=$(echo "$output" | cut -d'|' -f2)
    name=$(echo "$output" | cut -d'|' -f3)
    latency=$(echo "$output" | cut -d'|' -f4)
    current=$(jq -r '.primary' "$CACHE" 2>/dev/null || echo "none")
    if [[ "$primary" != "$current" ]]; then
        apply_dns "$primary" "$secondary" "$name" "$latency"
    else
        log "No change – $name still best (${latency}ms)"
    fi
    sleep "$INTERVAL"
done
SCR
chmod +x /opt/dnsfrenzy/dnsfrenzy.sh
cat > /usr/local/bin/dnsfrenzy << 'CMD'
#!/bin/bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
VERSION=$(cat /opt/dnsfrenzy/VERSION 2>/dev/null || echo "1.1.1")
show_help() { cat << HELP
${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════╗
║              SHADOWKIT DNSFRENZY – Management Tool              ║
╚══════════════════════════════════════════════════════════════════╝${NC}
${BOLD}Usage:${NC} dnsfrenzy ${BOLD}<command>${NC}
${BOLD}Commands:${NC}
  ${GREEN}start${NC}     Start the daemon
  ${GREEN}stop${NC}      Stop the daemon
  ${GREEN}restart${NC}   Restart the daemon
  ${GREEN}status${NC}    Show detailed status
  ${GREEN}enable${NC}    Enable at boot
  ${GREEN}disable${NC}   Disable at boot
  ${GREEN}logs${NC}      Tail the log file
  ${GREEN}config${NC}    Edit config (nano)
  ${GREEN}reload${NC}    Reload after config change
  ${GREEN}version${NC}   Show version
  ${GREEN}help${NC}      Show this help
HELP
}
show_status() {
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║              DNSFRENZY – SYSTEM STATUS                         ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════════╝${NC}"
    if systemctl is-active --quiet dnsfrenzy; then STATUS="${GREEN}● Running${NC}"; else STATUS="${RED}● Stopped${NC}"; fi
    if systemctl is-enabled --quiet dnsfrenzy 2>/dev/null; then ENABLED="${GREEN}Yes${NC}"; else ENABLED="${RED}No${NC}"; fi
    UPTIME=$(systemctl show dnsfrenzy --property=ActiveEnterTimestamp --no-pager 2>/dev/null | cut -d= -f2); [ -z "$UPTIME" ] && UPTIME="N/A"
    CACHE="/var/cache/dnsfrenzy/best.json"
    if [ -f "$CACHE" ]; then
        PRIMARY=$(jq -r '.primary' "$CACHE" 2>/dev/null || echo "N/A")
        SECONDARY=$(jq -r '.secondary' "$CACHE" 2>/dev/null || echo "N/A")
        NAME=$(jq -r '.name' "$CACHE" 2>/dev/null || echo "N/A")
        LATENCY=$(jq -r '.latency' "$CACHE" 2>/dev/null || echo "N/A")
        TIMESTAMP=$(jq -r '.timestamp' "$CACHE" 2>/dev/null || echo "N/A")
    else
        PRIMARY="N/A"; SECONDARY="N/A"; NAME="N/A"; LATENCY="N/A"; TIMESTAMP="N/A"
    fi
    echo ""; echo -e "${BOLD}Version:${NC}      $VERSION"; echo -e "${BOLD}Status:${NC}       $STATUS"; echo -e "${BOLD}Boot enable:${NC}  $ENABLED"; echo -e "${BOLD}Uptime:${NC}       $UPTIME"; echo ""
    echo -e "${CYAN}─── Best DNS ───${NC}"; echo -e "  ${BOLD}Name:${NC}        $NAME"; echo -e "  ${BOLD}Primary:${NC}     $PRIMARY"; echo -e "  ${BOLD}Secondary:${NC}   $SECONDARY"; echo -e "  ${BOLD}Latency:${NC}     ${YELLOW}${LATENCY}ms${NC}"; echo -e "  ${BOLD}Cached:${NC}      $TIMESTAMP"; echo ""
    echo -e "${CYAN}─── Recent Log (last 3 lines) ───${NC}"; tail -n 3 /var/log/dnsfrenzy/dnsfrenzy.log 2>/dev/null | while read line; do echo -e "  ${BLUE}$line${NC}"; done || echo -e "  ${YELLOW}No log entries yet${NC}"
    echo -e "${CYAN}────────────────────────────────────────────────────────────────────${NC}"
}
case "$1" in
    start)   systemctl start dnsfrenzy && echo -e "${GREEN}✅ Started${NC}" ;;
    stop)    systemctl stop dnsfrenzy && echo -e "${RED}⏹ Stopped${NC}" ;;
    restart) systemctl restart dnsfrenzy && echo -e "${GREEN}🔄 Restarted${NC}" ;;
    status)  show_status ;;
    enable)  systemctl enable --now dnsfrenzy && echo -e "${GREEN}✅ Enabled at boot${NC}" ;;
    disable) systemctl disable --now dnsfrenzy && echo -e "${RED}❌ Disabled at boot${NC}" ;;
    logs)    tail -f /var/log/dnsfrenzy/dnsfrenzy.log ;;
    config)  nano /opt/dnsfrenzy/config.json ;;
    reload)  systemctl restart dnsfrenzy && echo -e "${GREEN}🔄 Reloaded${NC}" ;;
    version) echo -e "${CYAN}DNSFrenzy version ${BOLD}$VERSION${NC}" ;;
    help|--help|-h) show_help ;;
    *) echo -e "${RED}❌ Unknown command: $1${NC}"; show_help ;;
esac
CMD
chmod +x /usr/local/bin/dnsfrenzy
cat > /etc/systemd/system/dnsfrenzy.service << 'SVC'
[Unit]
Description=ShadowKit DNSFrenzy Daemon
After=network.target
[Service]
ExecStart=/opt/dnsfrenzy/dnsfrenzy.sh
Restart=always
RestartSec=5
User=root
StandardOutput=append:/var/log/dnsfrenzy/dnsfrenzy.log
StandardError=append:/var/log/dnsfrenzy/dnsfrenzy.log
[Install]
WantedBy=multi-user.target
SVC
cat > /usr/local/bin/dnsfrenzy-uninstall << 'UNI'
#!/bin/bash
systemctl disable --now dnsfrenzy 2>/dev/null
rm /etc/systemd/system/dnsfrenzy.service
rm /usr/local/bin/dnsfrenzy
rm -rf /opt/dnsfrenzy /var/log/dnsfrenzy /var/cache/dnsfrenzy
systemctl daemon-reload
echo "DNSFrenzy removed."
UNI
chmod +x /usr/local/bin/dnsfrenzy-uninstall
cat > /usr/local/bin/dnsfrenzy-packager << 'PKG'
#!/bin/bash
VERSION=$(cat /opt/dnsfrenzy/VERSION 2>/dev/null || echo "1.1.1")
mkdir -p /tmp/dnsfrenzy-pkg/opt /tmp/dnsfrenzy-pkg/usr/local/bin /tmp/dnsfrenzy-pkg/etc/systemd/system
cp -r /opt/dnsfrenzy /tmp/dnsfrenzy-pkg/opt
cp /usr/local/bin/dnsfrenzy /tmp/dnsfrenzy-pkg/usr/local/bin/
cp /etc/systemd/system/dnsfrenzy.service /tmp/dnsfrenzy-pkg/etc/systemd/system/
mkdir -p /tmp/dnsfrenzy-pkg/DEBIAN
cat > /tmp/dnsfrenzy-pkg/DEBIAN/control << CTL
Package: dnsfrenzy
Version: $VERSION
Section: net
Priority: optional
Architecture: all
Depends: jq, bind-utils
Maintainer: Your Name <you@example.com>
Description: ShadowKit DNSFrenzy Linux port - automatic DNS switching with real latency testing.
CTL
dpkg-deb --root-owner-group --build /tmp/dnsfrenzy-pkg /tmp/dnsfrenzy-$VERSION.deb 2>/dev/null || dpkg-deb --build /tmp/dnsfrenzy-pkg /tmp/dnsfrenzy-$VERSION.deb 2>/dev/null
if command -v fpm &>/dev/null; then
    fpm -s dir -t rpm -n dnsfrenzy -v $VERSION --prefix / -C /tmp/dnsfrenzy-pkg . 2>/dev/null
fi
echo "Package built: /tmp/dnsfrenzy-$VERSION.deb"
PKG
chmod +x /usr/local/bin/dnsfrenzy-packager
echo "1.1.1" > /opt/dnsfrenzy/VERSION
systemctl daemon-reload
systemctl enable --now dnsfrenzy
echo -e "\n\033[0;32m✅ ShadowKit DNSFrenzy v1.1.1 installed successfully.\033[0m"
