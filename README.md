# SC-Game 🎮

**DualShock 4 → virtual Xbox 360 gamepads across Steam, Lutris/Proton, Wine/UMU, and native Linux games.**

A small Bash installer for **Arch Linux / CachyOS**, including Hyprland/Ryoku. Based on a tested two-controller setup using BlueZ, the [SC Controller](https://github.com/C0rn3j/sc-controller) GUI/backend, and an optional [btsspsw](https://github.com/VHSgunzo/btsspsw) Bluetooth workaround.

This project is an *installer/configuration helper*, not a controller driver or a replacement for either upstream project.

## Quick start

**One-line installer (Fish or Bash, Arch/CachyOS):**

```bash
curl -fsSLo sc-game-install.sh https://raw.githubusercontent.com/zarzorr69/SC-Game/master/install.sh && bash sc-game-install.sh
```

This downloads `install.sh` into the current directory before running it, so you can inspect it first. It also keeps standard input available for interactive prompts (unlike piping directly into `bash`). **Do not run the installer with `sudo`**; it requests elevated permissions only when needed.

**Optional SSP reconnect workaround:** If your DualShock 4 pairs but immediately disconnects, use the installer downloaded above and explicitly opt in:

```bash
bash sc-game-install.sh --with-ssp-workaround
```

This requires typing `I ACCEPT` to acknowledge the adapter-wide Bluetooth security reduction. The `--yes` flag can bypass prompts for unattended installations; do not use it without understanding the implications.

**Alternatively, clone the entire project** (including the status and uninstall scripts):

```bash
git clone https://github.com/zarzorr69/SC-Game.git
cd SC-Game
bash install.sh
```

The one-liner only downloads the installer. Clone the repository if you also want to run `bash status.sh`, `bash uninstall.sh`, or review all documentation locally.

### Why SSP opt-in matters

[btsspsw](https://github.com/VHSgunzo/btsspsw) toggles Bluetooth **Secure Simple Pairing (SSP)** adapter-wide: SSP ON while discovery is enabled, SSP OFF while discovery is disabled. The latter weakens Bluetooth Classic security for other devices as well. Only enable this if needed; revisit it after updates to BlueZ/kernel/controller firmware. The installer does not enable it by default.

## After installation (one-time GUI setup)

1. Pair each PS4 controller **once** in Blueman (`blueman-manager`) or `bluetoothctl`. Trust each pairing (`bluetoothctl trust <MAC>`). In Ryoku/QuickShell, a problematic Bluetooth sidebar can be bypassed with Blueman. After pairing, press **PS** to reconnect.
2. Run `sc-controller`. In **Settings → Controllers**, ensure *Enable DualShock 4 support* is checked. Do **not** register a DS4 manually—it is natively supported.
3. Select **XBox Controller** (the plain profile, not “High Precision Camera”) for **each** detected controller; SC Controller remembers controller profiles. For fixed controller identity across different connect orders, use the serial-number setting if supported by the installed version.
4. In **Steam → Settings → Controller → Advanced Settings**, set **PlayStation Controller Support** to **Not Enabled**, and turn **off Steam Input for Xbox controllers** and **generic controllers**. Restart Steam. The aim is to avoid Steam creating extra virtual Xbox pads on top of SC Controller's existing pads. If a specific Steam title requires Steam Input, configure an override for that title.
5. In Lutris, use **Runners → Wine → gear icon → Runner options (Advanced)**: leave *Autoconfigure joypads* **Off**. Game-level overrides can supersede this. New Wine prefixes do not need copying from an existing game's prefix.
6. Verify with `bash status.sh` and `sudo evtest`. With **two connected DS4s**, expect two responsive Xbox pads. Games need their own gamepad support.

### The flow

```text
DS4 #1 + DS4 #2 over Bluetooth
         │
        BlueZ ── optional btsspsw compatibility workaround
         │
    SC Controller user service (starts on login)
         │
 Virtual Xbox pad #1 + Virtual Xbox pad #2
         │
  Steam / Lutris / Wine / other compatible launchers
```

**Note:** The installer cannot guarantee fixed XInput player numbers (#0/#1) for all games or Wine versions. Those slots depend on enumeration/connection order. If a Wine game sees extra or empty slots, fully exit Steam when diagnosing, then retest with only SC Controller's two virtual pads. A clean Wine process restart can also help; do not copy an entire game prefix merely to copy controller configuration.

## Commands

```bash
bash status.sh                            # Read-only diagnostics
systemctl --user status scc-daemon.service
sc-controller                             # GUI for profiles
sudo evtest                               # Button/axis tests
bash uninstall.sh                         # Uninstall only project-managed settings
```

The `scc-daemon.service` user unit is enabled with `WantedBy=default.target` and:

```ini
ExecStart=/usr/bin/scc-daemon --foreground --alone start
Restart=on-failure
RestartSec=3
```

The GUI is optional after profiles are selected. Neither controller pairing nor Steam settings are modified by the installer.

## Name and migration

SC-Game is the new name for the original DualShock Anywhere installer. If you installed the previous release, the current installer recognizes its systemd service marker and the uninstaller recognizes its old state marker. Existing controller profiles, pairings, and game prefixes are not renamed or reset.

## Safety and reversibility

- **No automatic modification** of Steam VDF files, Lutris configs, existing Wine prefixes, Hyprland/QuickShell settings, or current Bluetooth pairings.
- **No forced overwrite** of an unfamiliar existing `scc-daemon.service`. A compatible user unit is preserved; otherwise installation stops and asks for manual review.
- `uninstall.sh` removes the project-created service only. If the SSP service was newly enabled by this installer, it also disables it and requests `btmgmt ssp on`; an SSP service previously enabled by the user is preserved. Installed packages remain because other apps may use them.
- Bluetooth SSP changes can break or weaken security for other devices. For manual recovery: `sudo systemctl disable --now btsspsw.service` then `sudo btmgmt -i hci0 ssp on` (adapt adapter index).
- Running the installation may do a full Arch package upgrade **if any required packages are missing** (`pacman -Syu --needed`). Resolve mirror issues in your distribution's mirror configuration rather than hardcoding a server.
- AUR dependencies come from a third party. Review `btsspsw-bin`'s PKGBUILD. The repo does not vendor external binaries or patches.

For the exact Bluetooth, Steam, and Wine/XInput errors encountered during testing, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Known limitations

- Tested setup: CachyOS/Hyprland (Ryoku), BlueZ 5.87, two Bluetooth DS4s, SC Controller 1.0.6, Steam and Lutris 0.5.22 with Proton-CachyOS/UMU. This repo hasn't been executed on every supported distribution or hardware model.
- `systemd --user` is required. Gamepad emulation starts after user login, not at the system login screen.
- XInput slot numbers may vary; different Wine/Proton builds may enumerate devices differently.
- Sandboxed launchers may need access to input devices. Individual games that only support keyboard/mouse may require their own SC Controller profile.
- SC Controller's automatic per-window profile switching is not generally available on Wayland; manually select profiles when necessary.

## Upstream projects

- [SC Controller (C0rn3j)](https://github.com/C0rn3j/sc-controller)
- [btsspsw (VHSgunzo)](https://github.com/VHSgunzo/btsspsw)

Licensed MIT for the scripts and documentation in this repository. Upstream applications retain their own licenses.
