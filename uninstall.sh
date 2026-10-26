#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Please run as root"; exit 1; fi
systemctl stop dnsfrenzy.timer dnsfrenzy.service 2>/dev/null || true
systemctl disable dnsfrenzy.timer dnsfrenzy.service 2>/dev/null || true
rm -f /etc/systemd/system/dnsfrenzy.service /etc/systemd/system/dnsfrenzy.timer
rm -rf /opt/dnsfrenzy /var/cache/dnsfrenzy /var/log/dnsfrenzy
rm -f /usr/local/bin/dnsfrenzy
systemctl daemon-reload
echo "==> DNSFrenzy uninstalled."
