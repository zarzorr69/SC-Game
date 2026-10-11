#!/usr/bin/env bash
# Remove only files/settings managed by SC-Game; leave packages/pairings alone.
set -Eeuo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/sc-game"
LEGACY_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/dualshock-anywhere"
UNIT_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/scc-daemon.service"
TUI_TARGET="$HOME/.local/bin/sc-game"

usage() {
  cat <<'USAGE'
Usage: bash uninstall.sh [--help]
Removes the SC Controller user service ONLY if installed by SC-Game.
Disables the SSP switcher ONLY if enabled by this installer's state marker.
Does not remove packages, controller profiles, Bluetooth pairing, Steam settings,
or other users' custom systemd units.
USAGE
}

case "${1:-}" in
  '') ;;
  -h|--help) usage; exit 0 ;;
  *) echo "Unknown argument: $1" >&2; exit 1 ;;
esac
(( EUID != 0 )) || { echo 'Run as normal user, not via sudo.' >&2; exit 1; }

if [[ -f "$UNIT_FILE" ]] && { grep -Fqx '# Managed by SC-Game' "$UNIT_FILE" || grep -Fqx '# Managed by DualShock Anywhere' "$UNIT_FILE"; }; then
  systemctl --user disable --now scc-daemon.service
  rm -f "$UNIT_FILE"
  systemctl --user daemon-reload
  echo 'Removed the installer-managed SC Controller user service.'
else
  echo 'No installer-managed SC Controller service found. Left any existing user service untouched.'
fi

if [[ -f "$STATE_DIR/ssp-enabled-by-installer" || -f "$LEGACY_STATE_DIR/ssp-enabled-by-installer" ]]; then
  sudo systemctl disable --now btsspsw.service
  if command -v btmgmt >/dev/null 2>&1; then
    if ! sudo btmgmt ssp on; then
      echo 'Could not restore SSP automatically; run sudo btmgmt -i hci0 ssp on (adjust hci index).' >&2
    fi
  else
    echo 'btmgmt not found: restore SSP manually after installing bluez-utils.' >&2
  fi
  rm -f "$STATE_DIR/ssp-enabled-by-installer" "$LEGACY_STATE_DIR/ssp-enabled-by-installer"
  echo 'Disabled installer-enabled btsspsw and requested restoration of Bluetooth SSP.'
else
  echo 'Existing btsspsw installation/service left untouched (not enabled by this installer).'
fi

if [[ -f "$STATE_DIR/tui-installed-by-installer" ]]; then
  if [[ -f "$TUI_TARGET" ]] && grep -Fq '# SC-Game TUI (managed installation)' "$TUI_TARGET"; then
    rm -f "$TUI_TARGET"
    echo 'Removed installer-managed sc-game terminal dashboard.'
  else
    echo 'TUI file has been changed or moved; preserved it.'
  fi
  rm -f "$STATE_DIR/tui-installed-by-installer"
fi

echo 'Packages, user-created SC profiles, paired devices, and Steam/Lutris settings were not changed.' 
