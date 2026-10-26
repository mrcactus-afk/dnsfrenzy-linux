#!/bin/bash
is_vpn_active() {
    ip link show 2>/dev/null | grep -qE 'tun[0-9]*|throne-tun|wg[0-9]+|zt[0-9]+|ovpn|ppp[0-9]+' && return 0
    local def_if=$(ip route show default 2>/dev/null | awk '/default/ {print $5}')
    [[ "$def_if" =~ ^(tun|wg|zt|ppp|ovpn) ]] && return 0
    return 1
}
