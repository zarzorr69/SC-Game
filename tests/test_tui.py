"""Offline, standard-library tests for the SC-Game terminal dashboard."""

import importlib.util
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sc_game", ROOT / "sc-game.py")
sc_game = importlib.util.module_from_spec(spec)
import sys
sys.modules["sc_game"] = sc_game
spec.loader.exec_module(sc_game)


class TestParsing(unittest.TestCase):
    def test_devices_only_valid_macs(self):
        data = """Device 5B:02:99:64:58:1B Wireless Controller
Device CD:28:19:FD:66:94 Wireless Controller
AdvertisementMonitor path registered
"""
        self.assertEqual(sc_game.parse_devices(data), [
            ("5B:02:99:64:58:1B", "Wireless Controller"),
            ("CD:28:19:FD:66:94", "Wireless Controller"),
        ])

    def test_info_only_primary_fields(self):
        flags = sc_game.parse_info("Paired: yes\nBonded: yes\nTrusted: yes\nConnected: no\nBREDR.Connected: yes\n")
        self.assertEqual(flags, {"paired": True, "bonded": True, "trusted": True, "connected": False})

    def test_empty_list(self):
        self.assertEqual(sc_game.parse_devices("No default controller available"), [])

    def test_status_format(self):
        example = sc_game.Snapshot(
            bluetooth=("active", "enabled"), daemon=("active", "enabled"),
            controllers=[sc_game.Controller("CD:28:19:FD:66:94", "Wireless Controller", connected=True)],
            pads=[("event30", sc_game.XBOX_NAME)],
        )
        output = sc_game.plain_status(example)
        self.assertIn("virtual Xbox pads: 1", output)
        self.assertIn("event30", output)

    def test_no_shell_argument_expansion(self):
        with patch.object(sc_game.subprocess, "run") as execute:
            execute.return_value.returncode = 0
            execute.return_value.stdout = "ok"
            execute.return_value.stderr = ""
            sc_game.run(["bluetoothctl", "info", "CD:28:19:FD:66:94"])
            execute.assert_called_once()
            self.assertEqual(execute.call_args.args[0], ["bluetoothctl", "info", "CD:28:19:FD:66:94"])
            self.assertNotIn("shell", execute.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
