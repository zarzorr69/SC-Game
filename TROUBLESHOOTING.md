# Troubleshooting

These notes reflect a tested dual-DS4 setup on CachyOS + Ryoku Hyprland. Do not blindly change Bluetooth security or overwrite game prefixes.

## Controller connects briefly then switches off

Confirm it is paired, bonded and trusted:

```bash
bluetoothctl devices Paired
bluetoothctl info AA:BB:CC:DD:EE:FF
```

If BlueZ emits `br-connection-create-socket` or `profiles/input/device.c:control_connect_cb() ... Function not implemented (38)`, inspect the Bluetooth journal:

```bash
sudo journalctl -u bluetooth -b --since '5 minutes ago' --no-pager | tail -80
```

On some BlueZ/controller combinations, `sudo btmgmt -i hci0 ssp off` temporarily makes a controller stable, but **SSP off weakens adapter-wide Bluetooth Classic pairing security**. A successful 30-second connection under this setting is only a compatibility clue, not a permanent security fix. To restore normal behavior:

```bash
sudo btmgmt -i hci0 ssp on
```

Only if needed, `bash install.sh --with-ssp-workaround` uses [btsspsw](https://github.com/VHSgunzo/btsspsw) to manage this workaround persistently. It turns SSP on for discovery and off otherwise. It's not PS4-specific and affects other Bluetooth devices.

## QuickShell Bluetooth menu can't pair

Use `blueman-manager` or `bluetoothctl` to pair *once* instead. Pairing is stored by BlueZ, not by the desktop menu. Press **PS** for reconnection after pairing; don't press Share + PS unless entering pairing mode again.

## SC Controller GUI opens, but no Xbox devices appear

```bash
systemctl --user status scc-daemon.service --no-pager
journalctl --user -u scc-daemon.service -b -n 80 --no-pager
bash status.sh
```

SC Controller's *Restart Emulation* button is not a substitute for a running background daemon. `scc-daemon debug` is useful while diagnosing, but stop that manual process before starting the systemd user unit so that only one daemon owns the devices. In the GUI, choose the plain **XBox Controller** profile for each DS4.

## Linux reports four Xbox gamepads for two PS4 controllers

Compare device names while Steam is running and after you fully **Steam → Exit**:

```bash
grep -Hi 'Microsoft X-Box' /sys/class/input/event*/device/name
```

If two extra devices appear with Steam running, disable Steam Input globally for PlayStation/Xbox/generic controllers: **Steam → Settings → Controller → Advanced Settings**. Restart Steam and recheck. Steam may still list both real DS4 devices and two virtual Xbox pads; that UI is not the same as four virtual Xbox input devices.

Use `sudo evtest` to verify that each SC Controller virtual Xbox device responds only to its own physical pad. Linux event numbers are assigned dynamically, so don't hardcode `event30`, `event263`, etc.

## Controller works in Steam but not in Lutris/Proton

Open **Lutris → game → Wine tools dropdown beside Play → Wine Control Panel → Game Controllers → XInput**.

Check which XInput **User #0** through **User #3** slots actually respond. Many games favor User #0. A recorded case had DS4 #1 at #2 and DS4 #2 at #1 because additional, inactive virtual devices had been present earlier. After removing those extra virtual devices and restarting the game's Wine server, the pads appeared at #0 and #1 and both worked in Soulframe.

In Lutris's global Wine runner (gear icon), keep **Autoconfigure joypads** off. It is not necessary to copy another game's Wine prefix to a new game.

When restarting Wine, make sure the game and Wine Control Panel are **closed first**. Closing the Lutris app window alone does not necessarily stop Wine processes.

**Do not assume** the Fish alias `wineserver='/usr/bin/umu-run wineserver'` works for management commands: that can treat `wineserver` as a Windows executable and emit `Executable not found: wineserver`. Also, a zero exit status from `umu-run wineboot -k` does not alone prove that it reset device enumeration. Prefer Lutris's own prefix tools or a correctly scoped Wine/Proton wineserver binary, and confirm by reopening the XInput tester.

## Verify service autostart after reboot

```bash
systemctl --user is-enabled scc-daemon.service
systemctl is-enabled btsspsw.service
bash status.sh
```

Press PS after logging in. Services being enabled does not prove the controller will reconnect after every reboot; verify on your own hardware. Note that `btsspsw.service` only exists if that optional workaround was installed.
