#!/usr/bin/env bash
# SC-Game: persistent DualShock 4 -> virtual Xbox controllers on Arch/CachyOS.
set -Eeuo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/sc-game"
LEGACY_MARKER="# Managed by DualShock Anywhere"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_FILE="$UNIT_DIR/scc-daemon.service"
WITH_SSP=false
ASSUME_YES=false

usage() {
  cat <<'USAGE'
Usage: bash install.sh [--with-ssp-workaround] [--yes] [--help]

Installs SC Controller and configures its daemon as a systemd *user* service.
Does NOT edit your Steam settings, game prefixes, or Bluetooth pairings.

  --with-ssp-workaround  Opt in to btsspsw: turns off adapter-wide Bluetooth
                         Classic Secure Simple Pairing while discovery is off.
                         Less secure; only use if DS4 reconnects otherwise fail.
  --yes                  Noninteractive acknowledgement of the SSP security
                         warning and AUR package installation (if requested).
  -h, --help             Show this help.

Run as your NORMAL user from Bash (works when invoked from Fish), not via sudo.
USAGE
}

log()  { printf '\033[1;36m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

while (($#)); do
  case "$1" in
    --with-ssp-workaround) WITH_SSP=true ;;
    --yes) ASSUME_YES=true ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1 (try --help)" ;;
  esac
  shift
done

(( EUID != 0 )) || die 'Run without sudo; this installer invokes sudo only where needed.'
command -v pacman >/dev/null || die 'This installer supports pacman-based Arch/CachyOS systems only.'
command -v systemctl >/dev/null || die 'Requires systemd.'
command -v sudo >/dev/null || die 'Requires sudo.'
systemctl --user show-environment >/dev/null 2>&1 || die 'A running systemd user session is required. Log into your desktop and retry.'

log 'Checking packages (this may perform a complete pacman system upgrade if dependencies are missing)...'
missing=()
for package in bluez bluez-utils sc-controller evtest; do
  pacman -Q "$package" >/dev/null 2>&1 || missing+=("$package")
done
if ((${#missing[@]})); then
  log "Installing missing packages: ${missing[*]}"
  sudo pacman -Syu --needed "${missing[@]}"
else
  log 'All required repository packages are already installed.'
fi

command -v scc-daemon >/dev/null || die 'scc-daemon not found after package installation.'
command -v sc-controller >/dev/null || die 'SC Controller GUI not found after package installation.'
DAEMON_BIN="$(command -v scc-daemon)"
[[ "$DAEMON_BIN" == /* && -x "$DAEMON_BIN" ]] || die "Invalid scc-daemon executable: $DAEMON_BIN"

log 'Enabling the existing BlueZ Bluetooth service (pairing is left untouched)...'
sudo systemctl enable --now bluetooth.service

if [[ "$WITH_SSP" == true ]]; then
  printf '\n'
  warn 'SECURITY: btsspsw disables Bluetooth Classic SSP on the ENTIRE adapter whenever discovery is off.'
  warn 'This weakens pairing security for other Bluetooth Classic devices, not just gamepads.'
  warn 'Only use the workaround when your controller fails with normal SSP enabled.'
  if [[ "$ASSUME_YES" == false ]]; then
    [[ -t 0 ]] || die 'Noninteractive installation requires --yes with --with-ssp-workaround.'
    read -r -p 'Type I ACCEPT to continue with the SSP workaround: ' answer
    [[ "$answer" == 'I ACCEPT' ]] || die 'SSP workaround declined. No SSP settings were changed.'
  fi

  if ! command -v btsspsw >/dev/null 2>&1 || ! systemctl cat btsspsw.service >/dev/null 2>&1; then
    if command -v paru >/dev/null 2>&1; then
      log 'Installing optional AUR package btsspsw-bin with paru.'
      if [[ "$ASSUME_YES" == true ]]; then paru -S --needed --noconfirm btsspsw-bin; else paru -S --needed btsspsw-bin; fi
    elif command -v yay >/dev/null 2>&1; then
      log 'Installing optional AUR package btsspsw-bin with yay.'
      if [[ "$ASSUME_YES" == true ]]; then yay -S --needed --noconfirm btsspsw-bin; else yay -S --needed btsspsw-bin; fi
    else
      die 'No btsspsw installation found. Install paru/yay, review the AUR PKGBUILD, and rerun. Existing SC Controller remains installed.'
    fi
  fi
  systemctl cat btsspsw.service >/dev/null 2>&1 || die 'btsspsw.service is missing after installation.'
  mkdir -p "$STATE_DIR"
  if ! systemctl is-enabled --quiet btsspsw.service; then
    : > "$STATE_DIR/ssp-enabled-by-installer"
  fi
  sudo systemctl enable --now btsspsw.service
  log 'SSP switcher enabled. Discovery OFF normally means SSP OFF.'
else
  log 'SSP workaround not requested: Bluetooth security settings are unchanged.'
fi

mkdir -p "$UNIT_DIR"
tmp_unit="$(mktemp)"
trap 'rm -f "$tmp_unit"' EXIT
cat > "$tmp_unit" <<UNIT
# Managed by SC-Game
[Unit]
Description=SC Controller Xbox Gamepad Emulation
After=graphical-session.target

[Service]
Type=simple
ExecStart=$DAEMON_BIN --foreground --alone start
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT

if [[ -e "$UNIT_FILE" ]] && ! grep -Fqx '# Managed by SC-Game' "$UNIT_FILE" && ! grep -Fqx "$LEGACY_MARKER" "$UNIT_FILE"; then
  # Respect users who already have the same working daemon service.
  if grep -Fqx "ExecStart=$DAEMON_BIN --foreground --alone start" "$UNIT_FILE" &&
     grep -Fqx 'WantedBy=default.target' "$UNIT_FILE"; then
    log 'An equivalent user service already exists; preserving it unchanged.'
  else
    die "Existing $UNIT_FILE is different. Back it up/review it manually; refusing to overwrite it."
  fi
else
  install -m 0644 "$tmp_unit" "$UNIT_FILE"
  log "Installed systemd user unit: $UNIT_FILE"
fi

# A foreground user service needs exclusive daemon ownership. Stop a manually
# launched daemon only when this service itself is not already running.
if ! systemctl --user is-active --quiet scc-daemon.service; then
  if pgrep -u "$(id -u)" -f '(^|[ /])scc-daemon([[:space:]]|$)' >/dev/null 2>&1; then
    log 'Stopping a manually started scc-daemon to avoid duplicate instances...'
    "$DAEMON_BIN" stop || warn 'Could not stop manually started daemon. Verify no duplicate daemon remains.'
  fi
fi

systemctl --user daemon-reload
systemctl --user enable --now scc-daemon.service
sleep 3
if ! systemctl --user is-active --quiet scc-daemon.service; then
  systemctl --user status scc-daemon.service --no-pager || true
  die 'SC Controller service failed to stay running. Inspect: journalctl --user -u scc-daemon.service -b -n 80'
fi

printf '\n'
log 'Installed and active! SC Controller service will start with your user session.'
log 'Connect each DS4 through Blueman (blueman-manager) or bluetoothctl, then trust it.'
log 'Open: sc-controller  |  Enable DS4 support; select the XBox Controller profile for EACH controller.'
log 'Steam: Settings > Controller > Advanced Settings; disable Steam Input for PlayStation, Xbox and Generic.'
log 'Lutris: Wine runner advanced setting "Autoconfigure joypads" should be OFF.'
log 'Run: bash status.sh   |   Only two virtual Xbox pads should appear for two connected DS4s.'
log 'XInput slots may change with device connection order; the installer does not pin slots.'
