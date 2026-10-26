#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Please run as root (sudo ./install.sh)"; exit 1; fi
echo "==> Installing DNSFrenzy v3.1..."
apt-get update -qq && apt-get install -y -qq jq dnsutils python3
mkdir -p /opt/dnsfrenzy /var/cache/dnsfrenzy /var/log/dnsfrenzy
cp -r src/* /opt/dnsfrenzy/
chmod +x /opt/dnsfrenzy/dnsfrenzy.sh /opt/dnsfrenzy/lib/*.sh /opt/dnsfrenzy/tui/dashboard.py
[[ ! -f /opt/dnsfrenzy/config.json ]] && cp config.json.example /opt/dnsfrenzy/config.json
cp systemd/dnsfrenzy.service /etc/systemd/system/
cp systemd/dnsfrenzy.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dnsfrenzy.timer
cat > /usr/local/bin/dnsfrenzy << 'CMD'
#!/bin/bash
if [[ $# -gt 0 ]]; then exec /opt/dnsfrenzy/dnsfrenzy.sh "$@"; else exec python3 /opt/dnsfrenzy/tui/dashboard.py; fi
CMD
chmod +x /usr/local/bin/dnsfrenzy
echo "==> Installation complete. Run 'sudo dnsfrenzy' to launch."
