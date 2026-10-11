#!/usr/bin/env bash
set -Eeuo pipefail
repo="$(pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home" "$tmp/bin" "$tmp/config" "$tmp/state"
cat > "$tmp/bin/systemctl" <<'MOCK'
#!/usr/bin/env bash
case "$*" in
  *show-environment*|*is-active*|*enable*|*disable*|*restart*|*stop*|*daemon-reload*|*cat*) exit 0 ;;
  *is-enabled*) echo enabled; exit 0 ;;
  *status*) echo 'active (running)'; exit 0 ;;
esac
exit 0
MOCK
cat > "$tmp/bin/pacman" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == '-Q' ]]; then exit 0; fi
exit 0
MOCK
cat > "$tmp/bin/scc-daemon" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
cat > "$tmp/bin/sc-controller" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
cat > "$tmp/bin/sudo" <<'MOCK'
#!/usr/bin/env bash
"$@"
MOCK
cat > "$tmp/bin/pgrep" <<'MOCK'
#!/usr/bin/env bash
exit 1
MOCK
chmod +x "$tmp/bin/"*
export HOME="$tmp/home" XDG_STATE_HOME="$tmp/state" XDG_CONFIG_HOME="$tmp/config" PATH="$tmp/bin:$PATH"
[[ "$EUID" != '0' ]] || { echo 'Run test under unprivileged user'; exit 77; }
bash "$repo/install.sh" >/dev/null
[[ -x "$HOME/.local/bin/sc-game" ]]
[[ -f "$tmp/state/sc-game/tui-installed-by-installer" ]]
[[ -f "$tmp/config/systemd/user/scc-daemon.service" ]]
bash "$repo/install.sh" >/dev/null
"$HOME/.local/bin/sc-game" --version | grep -q 'SC-Game'
bash "$repo/uninstall.sh" >/dev/null
[[ ! -e "$HOME/.local/bin/sc-game" ]]
[[ ! -e "$tmp/config/systemd/user/scc-daemon.service" ]]
echo 'PASS: mocked install/reinstall/uninstall'
