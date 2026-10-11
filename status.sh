#!/usr/bin/env bash
# Read-only diagnostics; safe to run from Fish with: bash status.sh
set -Eeuo pipefail

state() {
  local level="$1" name="$2"
  if [[ "$level" == user ]]; then
    if systemctl --user is-active --quiet "$name"; then echo 'running'; else echo 'not running'; fi
    printf '  enabled: '; systemctl --user is-enabled "$name" 2>/dev/null || echo 'unknown'
  else
    if systemctl is-active --quiet "$name"; then echo 'running'; else echo 'not running'; fi
    printf '  enabled: '; systemctl is-enabled "$name" 2>/dev/null || echo 'unknown'
  fi
}

printf '=== SC-Game status ===\n'
printf 'Bluetooth: '; state system bluetooth.service
printf 'SC Controller: '; state user scc-daemon.service
printf 'SSP switcher: '; state system btsspsw.service

if command -v bluetoothctl >/dev/null 2>&1; then
  printf '\nBluetooth controllers (connected):\n'
  bluetoothctl devices Connected 2>/dev/null || true
  printf '\nBluetooth controllers (paired):\n'
  bluetoothctl devices Paired 2>/dev/null || true
fi

printf '\nVirtual Xbox input devices (event numbers may change):\n'
found=0
for path in /sys/class/input/event*/device/name; do
  [[ -r "$path" ]] || continue
  IFS= read -r name < "$path" || true
  if [[ "$name" == *'Microsoft X-Box 360 pad'* ]]; then
    printf '  %s: %s\n' "${path%/device/name}" "$name"
    found=$((found + 1))
  fi
done
printf 'Total virtual Xbox devices: %s\n' "$found"

if command -v btmgmt >/dev/null 2>&1; then
  printf '\nBluetooth adapter current settings (SSP shown only if enabled):\n'
  btmgmt info 2>/dev/null | grep 'current settings:' || true
fi
printf '\nTo test button presses: sudo evtest\n'
