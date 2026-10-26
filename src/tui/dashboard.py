#!/usr/bin/env python3
import curses, json, subprocess, time, os

CONFIG = "/opt/dnsfrenzy/config.json"
CACHE = "/var/cache/dnsfrenzy/best.json"
HEALTH = "/var/cache/dnsfrenzy/health.json"
MODE = "/var/cache/dnsfrenzy/mode.json"
STATE = "/var/cache/dnsfrenzy/state.json"

def load_json(path, default=None):
    if default is None: default = {}
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def run_cmd(cmd):
    try: return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except: return ""

def safe_addstr(stdscr, y, x, text, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if y >= max_y or x >= max_x: return
    max_len = max_x - x
    if y == max_y - 1 and x + max_len >= max_x: max_len -= 1
    stdscr.addstr(y, x, text[:max_len], attr)

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLUE, -1)
    curses.init_pair(2, curses.COLOR_WHITE, -1)
    curses.init_pair(3, curses.COLOR_CYAN, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)

    while True:
        config = load_json(CONFIG, {"servers": [], "refresh_interval": 1000})
        delay_ms = max(100, min(10000, int(config.get("refresh_interval", 1000))))
        stdscr.timeout(delay_ms)

        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        if max_y < 15 or max_x < 60:
            safe_addstr(stdscr, 0, 0, "Terminal too small (min 60x15)", curses.color_pair(4))
            stdscr.refresh(); time.sleep(0.5); continue

        cache = load_json(CACHE, {"server": "None", "time": "N/A"})
        mode_data = load_json(MODE, {"mode": "auto"})
        state = load_json(STATE, {})
        
        is_auto = (mode_data.get("mode") == "auto")
        current_dns = cache.get("server", "None")
        current_time = cache.get("time", "N/A")
        is_locked = state.get("locked", False)
        
        vpn = "tun" in run_cmd("ip link show") or "throne-tun" in run_cmd("ip link show")
        service = run_cmd("systemctl is-active --quiet dnsfrenzy.timer && echo active") == "active"
        status = "STOPPED"
        if service: 
            if vpn: status = "STANDBY (VPN)"
            elif is_auto: status = "AUTO"
            else: status = "MANUAL"

        safe_addstr(stdscr, 0, 0, "+" + "-" * (max_x - 2), curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 1, 0, "|", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 1, 2, " DNSFrenzy v3.1 ", curses.color_pair(1) | curses.A_BOLD)
        status_str = f"[{status}{' [LOCKED]' if is_locked else ''}]"
        safe_addstr(stdscr, 1, max_x - len(status_str) - 2, status_str, curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 1, max_x - 1, "|", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 2, 0, "+" + "-" * (max_x - 2), curses.color_pair(1) | curses.A_BOLD)

        mode_label = "(AUTO)" if is_auto else "(MANUAL)"
        dns_display = f"{current_dns} ({current_time} ms) {mode_label}"
        if current_dns == "None": dns_display = "Evaluating... (AUTO)"
        safe_addstr(stdscr, 3, 2, f"Active DNS: {dns_display}", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 0, "+" + "-" * (max_x - 2), curses.color_pair(1))

        safe_addstr(stdscr, 5, 2, "Configured Servers (Click row)", curses.color_pair(1) | curses.A_BOLD)
        health_data = load_json(HEALTH, {})
        visible_servers = []
        row = 6
        
        for srv in config.get("servers", []):
            if not srv.get("enabled", True): continue
            visible_servers.append(srv)
            ip = srv.get("primary", "0.0.0.0")
            name = srv.get("name", "Unknown")[:15].ljust(15)
            h = health_data.get(ip, {})
            rate = int(h.get("success_rate", 0))
            avg = int(h.get("avg_time", 0))
            is_selected = (ip == current_dns)
            color = 3 if is_selected else 2
            marker = ">" if is_selected else "o"
            bar_len = 10; filled = int(rate / 10)
            bar = "#" * filled + "." * (bar_len - filled)
            line = f" {marker} {name} {ip:<15} [{bar}] {rate:>3}% {avg:>3}ms"
            safe_addstr(stdscr, row, 2, line, curses.color_pair(color) | (curses.A_BOLD if is_selected else 0))
            row += 1
            
        safe_addstr(stdscr, row, 0, "+" + "-" * (max_x - 2), curses.color_pair(1))
        iface = run_cmd("ip route show default | awk '{print $5}' | head -1")
        ping = "ONLINE" if run_cmd("ping -c 1 -W 1 1.1.1.1 > /dev/null 2>&1") else "OFFLINE"
        safe_addstr(stdscr, row + 1, 2, f" Network: {iface} | Internet: {ping} | Delay: {delay_ms}ms ", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, row + 2, 0, "+" + "-" * (max_x - 2), curses.color_pair(1))

        controls = "[q]uit [a]uto [c]onfig [+]Delay [-]Delay [l]ock [r]efresh [s]ervice"
        pad = (max_x - len(controls)) // 2
        safe_addstr(stdscr, row + 3, pad, controls, curses.color_pair(2))
        safe_addstr(stdscr, max_y - 2, 0, "+" + "-" * (max_x - 2), curses.color_pair(1))
        stdscr.refresh()

        try: key = stdscr.getch()
        except: key = -1

        if key == ord('q') or key == ord('Q'): break
        elif key == curses.KEY_RESIZE:
            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
            continue 
        elif key == ord('a') or key == ord('A'):
            new_mode = "manual" if is_auto else "auto"
            save_json(MODE, {"mode": new_mode})
        elif key == ord('+') or key == ord('='):
            config["refresh_interval"] = min(10000, delay_ms + 500)
            save_json(CONFIG, config)
        elif key == ord('-') or key == ord('_'):
            config["refresh_interval"] = max(100, delay_ms - 500)
            save_json(CONFIG, config)
        elif key == ord('l') or key == ord('L'):
            state["locked"] = not state.get("locked", False)
            save_json(STATE, state)
        elif key == ord('r') or key == ord('R'):
            os.system("/opt/dnsfrenzy/dnsfrenzy.sh > /dev/null 2>&1")
        elif key == ord('s') or key == ord('S'):
            if service: os.system("systemctl stop dnsfrenzy.timer")
            else: os.system("systemctl start dnsfrenzy.timer")
        elif key == ord('c') or key == ord('C'):
            curses.endwin(); os.system("nano /opt/dnsfrenzy/config.json")
        elif key == curses.KEY_MOUSE:
            try:
                _, x, y, z, bstate = curses.getmouse()
                if bstate & curses.BUTTON1_CLICKED:
                    if 6 <= y < row and 2 <= x < max_x - 2:
                        clicked_idx = y - 6
                        if 0 <= clicked_idx < len(visible_servers):
                            target_ip = visible_servers[clicked_idx].get("primary")
                            save_json(CACHE, {"server": target_ip, "time": "manual", "timestamp": int(time.time())})
                            save_json(MODE, {"mode": "manual"})
                            os.system(f"bash -c 'source /opt/dnsfrenzy/lib/applier.sh && apply_dns {target_ip} 0 Manual'")
            except: pass

curses.wrapper(main)
