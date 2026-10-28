import curses
import json
import os
import subprocess
import sys
import time

CONFIG = "/opt/dnsfrenzy/config.json"
CACHE = "/var/cache/dnsfrenzy/best.json"
MODE = "/var/cache/dnsfrenzy/mode.json"
STATE = "/var/cache/dnsfrenzy/state.json"


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if not callable(default) else default()


def run_cmd(cmd):
    try:
        return (
            subprocess.check_output(
                cmd, shell=True, stderr=subprocess.DEVNULL, timeout=2
            )
            .decode()
            .strip()
        )
    except Exception:
        return ""


def safe_addstr(stdscr, y, x, text, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x >= max_x or x < 0:
        return
    max_len = max_x - x
    if max_len <= 0:
        return
    try:
        stdscr.addstr(y, x, text[:max_len], attr)
    except curses.error:
        pass


def draw_box(stdscr, y, x, h, w, attr=0, double=False):
    if h < 2 or w < 2:
        return
    if double:
        tl, tr, bl, br, h_c, v_c = "╔", "╗", "╚", "╝", "═", "║"
    else:
        tl, tr, bl, br, h_c, v_c = "┌", "┐", "└", "┘", "─", "│"
    safe_addstr(stdscr, y, x, tl + h_c * (w - 2) + tr, attr)
    for i in range(1, h - 1):
        safe_addstr(stdscr, y + i, x, v_c, attr)
        safe_addstr(stdscr, y + i, x + w - 1, v_c, attr)
    safe_addstr(stdscr, y + h - 1, x, bl + h_c * (w - 2) + br, attr)


def _open_config_editor(config_path):
    import shutil

    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        input("Press Enter to continue...")
        return
    editor = None
    for candidate in [
        os.environ.get("EDITOR"),
        os.environ.get("VISUAL"),
        "sensible-editor",
        "nano",
        "vi",
        "vim",
    ]:
        if candidate and shutil.which(candidate):
            editor = candidate
            break
    if not editor:
        print("No editor found. Install nano: sudo apt-get install -y nano")
        input("Press Enter to continue...")
        return
    try:
        subprocess.run([editor, config_path])
    except Exception as e:
        print(f"Editor failed: {e}")
        input("Press Enter to continue...")


def _is_valid_ip(ip):
    """Basic IPv4 validation"""

    parts = ip.strip().split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False
    return True


def _text_input(stdscr, y, x, max_width, initial="", attr=0):
    """Interactive text input field. Returns (text, cancelled)."""
    text = list(initial)
    cursor = len(text)
    while True:
        # Render field
        field_width = max_width - 2
        display = "".join(text)
        if len(display) > field_width:
            display = display[-field_width:]
        for i in range(field_width):
            ch = display[i] if i < len(display) else " "
            safe_addstr(stdscr, y, x + i, ch, attr)
        safe_addstr(
            stdscr,
            y,
            x + min(cursor, field_width - 1),
            text[cursor] if cursor < len(text) and cursor < field_width else "_",
            attr | curses.A_REVERSE,
        )
        stdscr.refresh()

        key = stdscr.getch()
        if key == 27 or key == curses.KEY_CANCEL:  # ESC
            return ("".join(text), True)
        elif key in (10, 13, curses.KEY_ENTER):  # Enter
            return ("".join(text), False)
        elif key in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
            if cursor > 0:
                text.pop(cursor - 1)
                cursor -= 1
        elif key == curses.KEY_DC:  # Delete
            if cursor < len(text):
                text.pop(cursor)
        elif key == curses.KEY_LEFT:
            if cursor > 0:
                cursor -= 1
        elif key == curses.KEY_RIGHT:
            if cursor < len(text):
                cursor += 1
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = len(text)
        elif 32 <= key < 127 and len(text) < 100:
            text.insert(cursor, chr(key))
            cursor += 1


def _form_dialog(stdscr, title, fields, initial_values=None):
    """
    Render a form dialog.
    fields: list of (label, field_type) where field_type is 'text' or 'ip'
    initial_values: dict of field_name -> initial value
    Returns: (values_dict, cancelled)
    """
    max_y, max_x = stdscr.getmaxyx()
    form_h = 5 + len(fields) * 2
    form_w = min(60, max_x - 4)
    form_y = max(0, (max_y - form_h) // 2)
    form_x = max(0, (max_x - form_w) // 2)

    if initial_values is None:
        initial_values = {}

    values = {name: initial_values.get(name, "") for name, _ in fields}
    current_field = 0

    while True:
        stdscr.erase()

        # Draw form box
        draw_box(
            stdscr,
            form_y,
            form_x,
            form_h,
            form_w,
            curses.color_pair(5) | curses.A_DIM,
            double=True,
        )

        # Title
        title_text = f" {title} "
        title_x = form_x + (form_w - len(title_text)) // 2
        safe_addstr(
            stdscr, form_y, title_x, title_text, curses.color_pair(1) | curses.A_BOLD
        )

        # Fields
        field_y = form_y + 2
        for i, (label, field_type) in enumerate(fields):
            is_current = i == current_field
            label_attr = (
                curses.color_pair(1) | curses.A_BOLD
                if is_current
                else curses.color_pair(5)
            )
            field_attr = curses.color_pair(1) if is_current else curses.color_pair(5)

            safe_addstr(stdscr, field_y + i * 2, form_x + 2, label + ": ", label_attr)

            field_x = form_x + 2 + len(label) + 2
            field_width = form_w - len(label) - 6

            val = values.get(fields[i][0], "")
            if field_type == "ip" and val and not _is_valid_ip(val):
                field_attr |= curses.color_pair(4)  # Red for invalid

            if is_current:
                safe_addstr(
                    stdscr,
                    field_y + i * 2,
                    field_x - 1,
                    ">",
                    curses.color_pair(1) | curses.A_BOLD,
                )

            # Render current value
            display_val = val if val else "(empty)"
            val_attr = field_attr if val else (curses.color_pair(5) | curses.A_DIM)
            safe_addstr(
                stdscr, field_y + i * 2, field_x, display_val[:field_width], val_attr
            )

        # Buttons
        btn_y = form_y + form_h - 2
        save_label = "[Enter] Save"
        cancel_label = "[Esc] Cancel"
        safe_addstr(
            stdscr, btn_y, form_x + 2, save_label, curses.color_pair(2) | curses.A_BOLD
        )
        safe_addstr(
            stdscr,
            btn_y,
            form_x + form_w - len(cancel_label) - 2,
            cancel_label,
            curses.color_pair(4),
        )

        # Hint for IP fields
        if fields[current_field][1] == "ip":
            safe_addstr(
                stdscr,
                field_y + current_field * 2 + 1,
                form_x + 2,
                "  (format: 1.2.3.4)",
                curses.color_pair(3) | curses.A_DIM,
            )

        stdscr.refresh()

        # Handle input
        key = stdscr.getch()
        if key == 27 or key == curses.KEY_CANCEL:
            return (values, True)
        elif key in (10, 13, curses.KEY_ENTER):
            # Validate IP fields before saving
            valid = True
            for name, ftype in fields:
                if ftype == "ip" and values[name] and not _is_valid_ip(values[name]):
                    valid = False
                    break
            if valid:
                return (values, False)
            # If invalid, flash error
            safe_addstr(
                stdscr,
                btn_y,
                form_x + form_w // 2 - 10,
                " Invalid IP address! ",
                curses.color_pair(4) | curses.A_BOLD,
            )
            stdscr.refresh()
            time.sleep(1)
        elif key == curses.KEY_UP:
            current_field = (current_field - 1) % len(fields)
        elif key == curses.KEY_DOWN:
            current_field = (current_field + 1) % len(fields)
        elif key == curses.KEY_TAB or key == 9:
            current_field = (current_field + 1) % len(fields)
        elif (
            key in (curses.KEY_BACKSPACE, 127, 8)
            or (32 <= key < 127)
            or key
            in (
                curses.KEY_LEFT,
                curses.KEY_RIGHT,
                curses.KEY_DC,
                curses.KEY_HOME,
                curses.KEY_END,
            )
        ):
            # Pass through to text input
            name, ftype = fields[current_field]
            val, cancelled = _text_input(
                stdscr,
                field_y + current_field * 2,
                form_x + 2 + len(fields[current_field][0]) + 2,
                form_w - len(fields[current_field][0]) - 6,
                initial=values[name],
            )
            if not cancelled:
                values[name] = val


def _confirm_dialog(stdscr, message):
    """Show a confirmation dialog. Returns True if confirmed."""
    max_y, max_x = stdscr.getmaxyx()
    msg_w = min(len(message) + 10, max_x - 4)
    msg_h = 5
    msg_y = max(0, (max_y - msg_h) // 2)
    msg_x = max(0, (max_x - msg_w) // 2)

    draw_box(
        stdscr,
        msg_y,
        msg_x,
        msg_h,
        msg_w,
        curses.color_pair(5) | curses.A_DIM,
        double=True,
    )
    safe_addstr(stdscr, msg_y + 1, msg_x + 2, message, curses.color_pair(5))
    safe_addstr(
        stdscr,
        msg_y + 3,
        msg_x + 2,
        "[Y] Confirm",
        curses.color_pair(2) | curses.A_BOLD,
    )
    safe_addstr(
        stdscr, msg_y + 3, msg_x + msg_w - 12, "[N] Cancel", curses.color_pair(4)
    )
    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord("y"), ord("Y")):
            return True
        elif key in (ord("n"), ord("N"), 27):
            return False


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_RED, -1)
    curses.init_pair(5, curses.COLOR_WHITE, -1)

    CYAN = curses.color_pair(1)
    GREEN = curses.color_pair(2)
    YELLOW = curses.color_pair(3)
    RED = curses.color_pair(4)
    WHITE = curses.color_pair(5)
    GRAY = curses.color_pair(5) | curses.A_DIM

    while True:
        config = load_json(CONFIG, {"servers": [], "refresh_interval": 1000})
        delay_ms = max(100, min(10000, int(config.get("refresh_interval", 1000))))
        stdscr.timeout(delay_ms)

        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        if max_y < 15 or max_x < 60:
            safe_addstr(
                stdscr, 0, 0, "Terminal too small (min 60x15)", YELLOW | curses.A_BOLD
            )
            stdscr.refresh()
            time.sleep(0.5)
            continue

        cache = load_json(CACHE, {"server": "None", "time": "N/A", "latency": "N/A"})
        mode_data = load_json(MODE, {"mode": "auto"})
        state = load_json(STATE, {})

        is_auto = mode_data.get("mode") == "auto"
        current_dns = cache.get("server", "None")
        current_latency = cache.get("latency", "N/A")
        cache.get("time", "N/A")
        is_locked = state.get("locked", False)

        vpn_iface = run_cmd(
            "ip link show | grep -E 'tun|throne-tun' | head -1 | awk '{print $2}' | tr -d ':'"
        )
        vpn = bool(vpn_iface)
        service = (
            run_cmd("systemctl is-active --quiet dnsfrenzy.timer && echo active")
            == "active"
        )

        if not service:
            status_text, status_color = "STOPPED", RED
        elif vpn:
            status_text, status_color = "STANDBY", YELLOW
        elif is_auto:
            status_text, status_color = "AUTO", GREEN
        else:
            status_text, status_color = "MANUAL", YELLOW

        servers = config.get("servers", [])

        # HEADER (double border)
        header_h = 3
        draw_box(stdscr, 0, 0, header_h, max_x, GRAY, double=True)
        safe_addstr(stdscr, 1, 2, " DNSFrenzy ", CYAN | curses.A_BOLD)

        badge = f" {status_text} "
        if is_locked:
            badge += "[LOCKED] "
        safe_addstr(
            stdscr, 1, max_x - len(badge) - 2, badge, status_color | curses.A_BOLD
        )

        latency_str = f" {current_latency}ms " if current_latency != "N/A" else " -- "
        mid_x = max(20, (max_x - len(latency_str)) // 2)
        safe_addstr(stdscr, 1, mid_x, latency_str, WHITE)

        # INFO PANEL
        info_y = header_h + 1
        info_h = 4
        draw_box(stdscr, info_y, 0, info_h, max_x, GRAY)

        dns_display = current_dns if current_dns != "None" else "No active DNS"
        dns_color = GREEN if current_dns != "None" else YELLOW
        safe_addstr(stdscr, info_y + 1, 2, "Active: ", GRAY)
        safe_addstr(stdscr, info_y + 1, 10, dns_display, dns_color | curses.A_BOLD)

        iface = run_cmd("ip route | grep default | awk '{print $5}' | head -1") or "-"
        internet_ok = (
            run_cmd("ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1 && echo ok") == "ok"
        )
        net_status, net_color = ("OK", GREEN) if internet_ok else ("DOWN", RED)

        metrics = f"Interface: {iface}   Internet: "
        safe_addstr(stdscr, info_y + 2, 2, metrics, GRAY)
        m_len = len(metrics) + 2
        safe_addstr(stdscr, info_y + 2, m_len, net_status, net_color | curses.A_BOLD)
        m_len += len(net_status) + 3
        safe_addstr(stdscr, info_y + 2, m_len, f"Refresh: {delay_ms}ms", GRAY)

        # VPN STANDBY EXPLANATION
        if vpn:
            vpn_y = info_y + 3
            safe_addstr(stdscr, vpn_y, 2, "⚠ VPN Detected: ", YELLOW | curses.A_BOLD)
            safe_addstr(stdscr, vpn_y, 19, f"{vpn_iface}", YELLOW)
            safe_addstr(
                stdscr,
                vpn_y + 1,
                2,
                "  DNS switching paused. VPN handles DNS resolution.",
                GRAY,
            )
            info_h = 6  # Expand info panel
        else:
            info_h = 4

        # SERVER LIST
        list_y = info_y + info_h + 1
        list_h = max_y - list_y - 4
        if list_h < 5:
            list_h = 5
        draw_box(stdscr, list_y, 0, list_h, max_x, GRAY)

        safe_addstr(stdscr, list_y, 2, " DNS Servers ", CYAN | curses.A_BOLD)
        safe_addstr(stdscr, list_y, 15, "(click to select)", GRAY)

        col_y = list_y + 1
        safe_addstr(stdscr, col_y, 2, "Name", GRAY | curses.A_UNDERLINE)
        safe_addstr(stdscr, col_y, 24, "Primary", GRAY | curses.A_UNDERLINE)
        safe_addstr(stdscr, col_y, 42, "Latency", GRAY | curses.A_UNDERLINE)

        active_idx = -1
        for i, s in enumerate(servers):
            if s.get("primary") == current_dns or s.get("name") == current_dns:
                active_idx = i
                break

        row_start = col_y + 1
        visible_count = min(len(servers), list_h - 3)

        for i in range(visible_count):
            s = servers[i]
            row = row_start + i
            if row >= list_y + list_h - 1:
                break

            is_active = i == active_idx
            name = s.get("name", "?")
            primary = s.get("primary", "?")
            latency = s.get("latency", "N/A")

            if is_active:
                for col in range(1, max_x - 1):
                    safe_addstr(stdscr, row, col, " ", GREEN)
                safe_addstr(stdscr, row, 2, "► " + name, GREEN | curses.A_BOLD)
                safe_addstr(stdscr, row, 24, primary, GREEN)
                safe_addstr(stdscr, row, 42, f"{latency}ms", GREEN | curses.A_BOLD)
                if max_x > 60:
                    safe_addstr(stdscr, row, max_x - 8, "ACTIVE", GREEN | curses.A_BOLD)
            else:
                safe_addstr(stdscr, row, 2, "  " + name, WHITE)
                safe_addstr(stdscr, row, 24, primary, GRAY)
                safe_addstr(stdscr, row, 42, f"{latency}ms", WHITE)

        # FOOTER
        footer_y = max_y - 4
        draw_box(stdscr, footer_y, 0, 4, max_x, GRAY)

        controls = [
            ("a", "auto"),
            ("m", "manual"),
            ("l", "lock"),
            ("r", "refresh"),
            ("s", "svc"),
            ("c", "config"),
            ("n", "new"),
            ("e", "edit"),
            ("d", "delete"),
            ("+/-", "speed"),
            ("q", "quit"),
        ]
        cx = 2
        line = 0
        for key, label in controls:
            if cx + len(key) + len(label) + 2 > max_x - 2:
                line += 1
                cx = 2
                if line > 1:
                    break
            hint_text = f"[{key}]"
            safe_addstr(
                stdscr, footer_y + 1 + line, cx, hint_text, CYAN | curses.A_BOLD
            )
            cx += len(hint_text)
            safe_addstr(stdscr, footer_y + 1 + line, cx, f"{label} ", GRAY)
            cx += len(label) + 1

        stdscr.refresh()

        # INPUT
        key = stdscr.getch()
        if key == ord("q") or key == ord("Q"):
            break
        elif key == curses.KEY_RESIZE:
            stdscr.clear()
        elif key == ord("a") or key == ord("A"):
            mode_data["mode"] = "auto"
            try:
                with open(MODE, "w") as f:
                    json.dump(mode_data, f)
            except Exception:
                pass
        elif key == ord("m") or key == ord("M"):
            mode_data["mode"] = "manual"
            try:
                with open(MODE, "w") as f:
                    json.dump(mode_data, f)
            except Exception:
                pass
        elif key == ord("+") or key == ord("="):
            config["refresh_interval"] = max(100, delay_ms - 100)
            try:
                with open(CONFIG, "w") as f:
                    json.dump(config, f)
            except Exception:
                pass
        elif key == ord("-") or key == ord("_"):
            config["refresh_interval"] = min(10000, delay_ms + 100)
            try:
                with open(CONFIG, "w") as f:
                    json.dump(config, f)
            except Exception:
                pass
        elif key == ord("l") or key == ord("L"):
            state["locked"] = not state.get("locked", False)
            try:
                with open(STATE, "w") as f:
                    json.dump(state, f)
            except Exception:
                pass
        elif key == ord("r") or key == ord("R"):
            os.system("/opt/dnsfrenzy/dnsfrenzy.sh > /dev/null 2>&1")
        elif key == ord("s") or key == ord("S"):
            if service:
                os.system("systemctl stop dnsfrenzy.timer")
            else:
                os.system("systemctl start dnsfrenzy.timer")
        elif key == ord("c") or key == ord("C"):
            curses.endwin()
            _open_config_editor(CONFIG)
        elif key == ord("n") or key == ord("N"):
            fields = [("primary", "ip"), ("secondary", "ip")]
            vals, cancelled = _form_dialog(stdscr, "Add Server", fields)
            stdscr.clear()
            if not cancelled and vals.get("primary"):
                cfg = load_json(CONFIG, {"servers": []})
                if "servers" not in cfg:
                    cfg["servers"] = []
                cfg["servers"].append(
                    {
                        "primary": vals["primary"].strip(),
                        "secondary": vals.get("secondary", "").strip(),
                    }
                )
                try:
                    with open(CONFIG, "w") as f:
                        json.dump(cfg, f, indent=2)
                except Exception:
                    pass
        elif key == ord("e") or key == ord("E"):
            if servers and 0 <= selected_idx < len(servers):
                target = servers[selected_idx]
                fields = [("primary", "ip"), ("secondary", "ip")]
                init = {
                    "primary": target.get("primary", ""),
                    "secondary": target.get("secondary", ""),
                }
                vals, cancelled = _form_dialog(stdscr, "Edit Server", fields, init)
                stdscr.clear()
                if not cancelled and vals.get("primary"):
                    cfg = load_json(CONFIG, {"servers": []})
                    if "servers" in cfg and selected_idx < len(cfg["servers"]):
                        cfg["servers"][selected_idx] = {
                            "primary": vals["primary"].strip(),
                            "secondary": vals.get("secondary", "").strip(),
                        }
                        try:
                            with open(CONFIG, "w") as f:
                                json.dump(cfg, f, indent=2)
                        except Exception:
                            pass
        elif key == ord("d") or key == ord("D"):
            if servers and 0 <= selected_idx < len(servers):
                target = servers[selected_idx]
                ip = target.get("primary", "Unknown")
                if _confirm_dialog(stdscr, "Delete Server", f"Delete {ip}?"):
                    cfg = load_json(CONFIG, {"servers": []})
                    if "servers" in cfg and selected_idx < len(cfg["servers"]):
                        cfg["servers"].pop(selected_idx)
                        try:
                            with open(CONFIG, "w") as f:
                                json.dump(cfg, f, indent=2)
                        except Exception:
                            pass
                    if len(servers) > 1:
                        servers.pop(selected_idx)
                        if selected_idx >= len(servers):
                            len(servers) - 1
        elif key == curses.KEY_MOUSE:
            try:
                _, x, y, z, bstate = curses.getmouse()
                if bstate & curses.BUTTON1_CLICKED:
                    if row_start <= y < row_start + visible_count:
                        clicked_idx = y - row_start
                        if 0 <= clicked_idx < len(servers):
                            target = servers[clicked_idx]
                            try:
                                cache["server"] = target.get("primary")
                                cache["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                with open(CACHE, "w") as f:
                                    json.dump(cache, f)
                                mode_data["mode"] = "manual"
                                with open(MODE, "w") as f:
                                    json.dump(mode_data, f)
                            except Exception:
                                pass
            except Exception:
                pass


if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("Error: DNSFrenzy TUI requires a terminal.")
        print("Please run this from a terminal emulator (Konsole, xterm, etc.)")
        sys.exit(1)
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\nTUI interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error initializing TUI: {e}")
        print("This may occur if:")
        print("  - Not running in a terminal")
        print("  - Terminal too small (minimum 60x15)")
        print("  - Missing terminal capabilities")
        sys.exit(1)
