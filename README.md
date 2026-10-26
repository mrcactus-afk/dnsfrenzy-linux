# DNSFrenzy

Fully automated, modular DNS switching daemon for Linux with real latency testing and network-change detection.

## Installation
curl -fsSL https://raw.githubusercontent.com/mrcactus-afk/dnsfrenzy-linux/main/install.sh | sudo bash

## Usage
sudo dnsfrenzy

## TUI Controls
q = quit
a = toggle auto/manual mode
+ / - = change refresh delay
l = lock current DNS
r = force refresh
s = start/stop service
c = edit config
mouse click = select server

## Uninstall
sudo ./uninstall.sh
