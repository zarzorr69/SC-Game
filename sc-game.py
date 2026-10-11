#!/usr/bin/env python3
# SC-Game TUI (managed installation)
"""SC-Game terminal dashboard. Standard-library-only and no root required to launch."""

from __future__ import annotations

import argparse
import curses
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.1.0"
XBOX_NAME = "Microsoft X-Box 360 pad"


def run(argv: list[str], timeout: float = 5) -> tuple[int, str]:
    """Run a fixed argument vector. Never pass user input through a shell."""
    try:
        result = subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="replace", timeout=timeout, check=False,
        )
        return result.returncode, (result.stdout + ("\n" + result.stderr if result.stderr else "")).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def parse_devices(text: str) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^Device\s+((?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2})\s+(.+)$", line.strip())
        if match:
            devices.append((match.group(1).upper(), match.group(2).strip()))
    return devices


def parse_info(text: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(Paired|Bonded|Trusted|Connected):\s*(yes|no)\b", line)
        if match:
            result[match.group(1).lower()] = match.group(2) == "yes"
    return result


def service(name: str, *, user: bool = False) -> tuple[str, str]:
    prefix = ["systemctl", "--user"] if user else ["systemctl"]
    rc, active = run(prefix + ["is-active", name], 3)
    _rc, enabled = run(prefix + ["is-enabled", name], 3)
    if rc != 0:
        active = "unavailable" if "not-found" not in active else "not-found"
    return active.splitlines()[0] if active else "unknown", enabled.splitlines()[0] if enabled else "unknown"


@dataclass
class Controller:
    address: str
    name: str
    connected: bool = False
    paired: bool = False
    bonded: bool = False
    trusted: bool = False


@dataclass
class Snapshot:
    bluetooth: tuple[str, str] = ("unknown", "unknown")
    daemon: tuple[str, str] = ("unknown", "unknown")
    ssp_switcher: tuple[str, str] = ("unknown", "unknown")
    ssp_setting: str = "unknown"
    controllers: list[Controller] = field(default_factory=list)
    pads: list[tuple[str, str]] = field(default_factory=list)
    note: str = ""


def xbox_devices() -> list[tuple[str, str]]:
    pads = []
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            name = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if XBOX_NAME in name:
            event = Path(path).parents[1].name
            pads.append((event, name))
    return pads


def snapshot() -> Snapshot:
    s = Snapshot()
    s.bluetooth = service("bluetooth.service")
    s.daemon = service("scc-daemon.service", user=True)
    s.ssp_switcher = service("btsspsw.service")
    if shutil.which("btmgmt"):
        code, info = run(["btmgmt", "info"], 3)
        if code == 0:
            match = re.search(r"current settings:\s*(.*)", info)
            if match:
                s.ssp_setting = "enabled" if "ssp" in match.group(1).split() else "disabled"
    s.pads = xbox_devices()
    if not shutil.which("bluetoothctl"):
        s.note = "bluetoothctl not found; install bluez-utils"
        return s
    _rc, known = run(["bluetoothctl", "devices"], 4)
    _rc, connected = run(["bluetoothctl", "devices", "Connected"], 4)
    connected_addresses = {a for a, _n in parse_devices(connected)}
    raw_devices = parse_devices(known)
    # BlueZ may know other Bluetooth devices; only show game controllers.
    for address, name in raw_devices:
        if "controller" not in name.lower() and "gamepad" not in name.lower() and "dualshock" not in name.lower():
            continue
        item = Controller(address=address, name=name, connected=address in connected_addresses)
        _rc, detail = run(["bluetoothctl", "info", address], 3)
        flags = parse_info(detail)
        item.connected = flags.get("connected", item.connected)
        item.paired = flags.get("paired", False)
        item.bonded = flags.get("bonded", False)
        item.trusted = flags.get("trusted", False)
        s.controllers.append(item)
    return s


def plain_status(s: Snapshot) -> str:
    lines = [
        f"SC-Game {VERSION}",
        f"Bluetooth: {s.bluetooth[0]} (enabled: {s.bluetooth[1]})",
        f"SC Controller: {s.daemon[0]} (enabled: {s.daemon[1]})",
        f"btsspsw: {s.ssp_switcher[0]} (enabled: {s.ssp_switcher[1]})",
        f"Bluetooth SSP: {s.ssp_setting}",
        f"Detected gamepads: {len(s.controllers)}; virtual Xbox pads: {len(s.pads)}",
    ]
    for c in s.controllers:
        lines.append(f"  {c.name} {c.address}: {'connected' if c.connected else 'offline'}; paired={c.paired}; bonded={c.bonded}; trusted={c.trusted}")
    for event, name in s.pads:
        lines.append(f"  {event}: {name}")
    if s.note:
        lines.append(s.note)
    return "\n".join(lines)


class Dashboard:
    def __init__(self, window: curses.window):
        self.window = window
        self.data = Snapshot()
        self.selected = 0
        self.message = "Press R to refresh. Actions are never automatic."
        self.last_refresh = 0.0
        self.colors = False
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
            except curses.error:
                pass
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            self.colors = True
        self.window.keypad(True)
        self.window.timeout(900)
        self.refresh()

    def paint(self, y: int, x: int, text: str, style: int = 0) -> None:
        height, width = self.window.getmaxyx()
        if not (0 <= y < height and 0 <= x < width):
            return
        try:
            self.window.addnstr(y, x, text, max(0, width - x - 1), style)
        except curses.error:
            pass

    def color(self, status: str) -> int:
        if status in ("active", "enabled", "connected"):
            return curses.color_pair(2) if self.colors else curses.A_BOLD
        if status in ("inactive", "disabled", "offline", "failed"):
            return curses.color_pair(3) if self.colors else 0
        return 0

    def refresh(self) -> None:
        self.data = snapshot()
        self.last_refresh = time.monotonic()
        if self.selected >= len(self.data.controllers):
            self.selected = max(0, len(self.data.controllers) - 1)

    def draw(self) -> None:
        w = self.window
        w.erase()
        height, width = w.getmaxyx()
        if height < 17 or width < 55:
            self.paint(0, 1, "SC-GAME | Enlarge terminal (minimum 55x17)", curses.A_BOLD)
            self.paint(2, 1, "q quit   r refresh")
            w.refresh()
            return
        brand = curses.color_pair(1) if self.colors else curses.A_BOLD
        self.paint(0, 2, "SC-GAME   /   CONTROLLER CONTROL CENTER", brand | curses.A_BOLD)
        self.paint(1, 2, "=" * (width - 4), brand)
        services = [
            ("Bluetooth", self.data.bluetooth),
            ("SC Controller", self.data.daemon),
            ("SSP switcher", self.data.ssp_switcher),
        ]
        for n, (title, values) in enumerate(services):
            x = 2 + n * ((width - 4) // 3)
            self.paint(3, x, f"{title}", curses.A_BOLD)
            self.paint(4, x, f"{values[0]} / {values[1]}", self.color(values[0]))
        self.paint(6, 2, f"BLUETOOTH GAMEPADS ({len(self.data.controllers)})", brand | curses.A_BOLD)
        max_rows = max(1, min(len(self.data.controllers), height - 16))
        if not self.data.controllers:
            self.paint(7, 3, "No known game controllers. Pair using [B] Blueman.")
        else:
            start = max(0, self.selected - max_rows + 1)
            for row, idx in enumerate(range(start, min(start + max_rows, len(self.data.controllers)))):
                c = self.data.controllers[idx]
                prefix = ">" if idx == self.selected else " "
                state = "ONLINE" if c.connected else "OFFLINE"
                flags = "paired" if c.paired else "unpaired"
                flags += ", trusted" if c.trusted else ", not trusted"
                attr = curses.A_REVERSE if idx == self.selected else self.color("connected" if c.connected else "offline")
                self.paint(7 + row, 3, f"{prefix} {c.name} [{state}] {c.address} ({flags})", attr)
        y = 8 + max_rows
        self.paint(y, 2, f"VIRTUAL XBOX 360 PADS ({len(self.data.pads)})", brand | curses.A_BOLD)
        if not self.data.pads:
            self.paint(y + 1, 3, "No virtual pads. Check SC Controller daemon.")
        else:
            events = ", ".join(event for event, _name in self.data.pads)
            self.paint(y + 1, 3, events + "  (event numbers change after reconnect)")
        self.paint(y + 2, 2, f"Bluetooth SSP: {self.data.ssp_setting} (adapter-wide)")
        self.paint(height - 5, 2, "[B] Blueman   [G] SC GUI   [C] Connect selected   [T] Trust selected")
        self.paint(height - 4, 2, "[S] Start/enable   [X] Stop   [R] Restart/refresh   [E] evtest")
        self.paint(height - 3, 2, "[L] Logs   [?] Help   [Q] Quit   [UP/DOWN] Select controller")
        self.paint(height - 2, 2, "-" * (width - 4))
        self.paint(height - 1, 2, self.message)
        w.refresh()

    def prompt(self, message: str) -> bool:
        height, _width = self.window.getmaxyx()
        self.message = message + " (y/N)"
        self.draw()
        self.window.timeout(-1)
        try:
            key = self.window.getch()
        finally:
            self.window.timeout(900)
        return key in (ord("y"), ord("Y"))

    def operate(self, argv: list[str], label: str) -> None:
        rc, output = run(argv, 15)
        details = output.splitlines()[-1] if output else ("OK" if rc == 0 else "failed")
        self.message = f"{label}: {details[:100]}"
        self.refresh()

    def spawn(self, program: str) -> None:
        if not shutil.which(program):
            self.message = f"{program} not installed."
            return
        try:
            subprocess.Popen([program], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.message = f"Opened {program}. Return here to manage controllers."
        except OSError as exc:
            self.message = f"Cannot open {program}: {exc}"

    def selected_controller(self) -> Controller | None:
        if self.data.controllers:
            return self.data.controllers[self.selected]
        self.message = "No controller selected. Pair in Blueman first."
        return None

    def external(self, argv: list[str], title: str) -> None:
        if not shutil.which(argv[0]):
            self.message = f"Command unavailable: {argv[0]}"
            return
        curses.def_prog_mode()
        curses.endwin()
        try:
            print(f"\n== SC-Game: {title} ==\n")
            subprocess.run(argv, check=False)
            input("\nPress Enter to return to SC-Game...")
        except (KeyboardInterrupt, EOFError):
            pass
        except OSError as exc:
            print(f"Error: {exc}")
            try:
                input("Press Enter to return...")
            except EOFError:
                pass
        finally:
            curses.reset_prog_mode()
            self.window.clear()
            self.refresh()

    def help(self) -> None:
        curses.def_prog_mode()
        curses.endwin()
        try:
            print("\nSC-Game: keyboard shortcuts and troubleshooting\n")
            print("B: Open Blueman (pair each DualShock 4 once; trust afterwards).")
            print("G: Open SC Controller GUI. Select the plain 'XBox Controller' profile.")
            print("C: Reconnect selected paired controller; T: mark it trusted.")
            print("S: Enable and start the SC Controller user service.")
            print("X: Stop SC Controller (temporary; enabled at next login).")
            print("R: Restart SC Controller service and refresh. F: refresh only.")
            print("E: Select an input device with evtest. L: inspect SC Controller logs.")
            print("\nSteam: Controller > Advanced. Disable Steam Input for PlayStation,")
            print("Xbox and generic devices to avoid additional virtual controllers.")
            print("Lutris: Wine runner Advanced > Autoconfigure joypads OFF.")
            print("Two connected DS4 controllers should normally yield two responsive")
            print("virtual Xbox pads; XInput slot numbering can change by launch order.")
            print("\nSSP SECURITY: btsspsw intentionally weakens adapter-wide Classic")
            print("Bluetooth pairing security when discovery is OFF. This dashboard")
            print("only displays its state; use the installer to opt in deliberately.")
            input("\nPress Enter to return...")
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            curses.reset_prog_mode()
            self.window.clear()
            self.refresh()

    def loop(self) -> None:
        while True:
            # Refresh infrequently enough not to stall the keyboard on DBus.
            if time.monotonic() - self.last_refresh > 12:
                self.refresh()
            self.draw()
            key = self.window.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
            if key == curses.KEY_UP:
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN:
                self.selected = min(max(0, len(self.data.controllers) - 1), self.selected + 1)
            elif key in (ord("f"), ord("F")):
                self.refresh()
                self.message = "Status refreshed."
            elif key in (ord("b"), ord("B")):
                self.spawn("blueman-manager")
            elif key in (ord("g"), ord("G")):
                self.spawn("sc-controller")
            elif key in (ord("c"), ord("C")):
                controller = self.selected_controller()
                if controller and self.prompt(f"Connect {controller.address}?"):
                    self.operate(["bluetoothctl", "connect", controller.address], "Bluetooth connect")
            elif key in (ord("t"), ord("T")):
                controller = self.selected_controller()
                if controller and self.prompt(f"Trust {controller.address} persistently?"):
                    self.operate(["bluetoothctl", "trust", controller.address], "Bluetooth trust")
            elif key in (ord("s"), ord("S")):
                if self.prompt("Enable and start SC Controller service?"):
                    self.operate(["systemctl", "--user", "enable", "--now", "scc-daemon.service"], "Start SC Controller")
            elif key in (ord("x"), ord("X")):
                if self.prompt("Stop SC Controller emulation until next login/start?"):
                    self.operate(["systemctl", "--user", "stop", "scc-daemon.service"], "Stop SC Controller")
            elif key in (ord("r"), ord("R")):
                if self.prompt("Restart SC Controller? Games may lose controller input briefly."):
                    self.operate(["systemctl", "--user", "restart", "scc-daemon.service"], "Restart SC Controller")
            elif key in (ord("e"), ord("E")):
                self.external(["sudo", "evtest"], "Gamepad input test")
            elif key in (ord("l"), ord("L")):
                self.external(["journalctl", "--user", "-u", "scc-daemon.service", "-n", "50", "--no-pager"], "Last 50 SC Controller log lines")
            elif key in (ord("?"), ord("h"), ord("H")):
                self.help()
            elif key == curses.KEY_RESIZE:
                self.refresh()


def main() -> int:
    parser = argparse.ArgumentParser(description="SC-Game DS4 / virtual Xbox controller terminal dashboard")
    parser.add_argument("--status", action="store_true", help="Print read-only status without starting the TUI")
    parser.add_argument("--version", action="version", version=f"SC-Game {VERSION}")
    args = parser.parse_args()
    if args.status:
        print(plain_status(snapshot()))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty() or not os.environ.get("TERM"):
        print("Interactive TUI requires a terminal; use sc-game --status for text output.", file=sys.stderr)
        return 2
    try:
        curses.wrapper(lambda screen: Dashboard(screen).loop())
    except curses.error as exc:
        print(f"Terminal could not start curses UI: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
