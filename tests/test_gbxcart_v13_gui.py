"""Exercise the actual Qt v1.3 updater without touching a serial port."""

import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from FlashGBX.hw_GBxCartRW import GbxDevice, FirmwareUpdaterWindowV13
from FlashGBX.pyside import QtWidgets
from FlashGBX.FlashGBX_GUI import FlashGBX_GUI, qt_app
from test_gbxcart_v13 import firmware, L1Serial


class V13UpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_app

    def test_main_window_connects_l1_without_discontinued_dialog(self):
        path = Path(__file__).resolve().parents[1] / "FlashGBX"
        dev = GbxDevice()
        dev.FW_VAR = {}
        dev.INFO = {"action": None, "last_action": None, "dump_info": {}}
        peer = L1Serial("test-v13", 1000000)
        with tempfile.TemporaryDirectory() as config_path:
            args = dict(config_path=config_path, app_path=str(path),
                        flashcarts={"DMG": {}, "AGB": {}}, config_ret=[],
                        argparsed=SimpleNamespace(device_port=None))
            with patch.object(FlashGBX_GUI, "FindDevices"), patch.object(FlashGBX_GUI, "UpdateCheck"):
                window = FlashGBX_GUI(args)
            with patch.object(dev, "_OpenSerial", return_value=peer):
                dev.Initialize(flashcarts=args["flashcarts"], port=peer.port)
            window.DEVICES = {"v13": dev}
            window.cmbDevice.clear()
            window.cmbDevice.addItem("v13")
            with patch.object(QtWidgets.QMessageBox, "exec", side_effect=AssertionError("Unexpected firmware dialog")):
                window.ConnectDevice(connection_messages=[])
            self.assertIs(window.CONN, dev)
            self.assertTrue(window.optDMG.isEnabled())
            self.assertTrue(window.optAGB.isEnabled())
            self.assertFalse(window.actGBxCartFlowControl.isEnabled())
            window.DisconnectDevice()
            window.deleteLater()
            self.app.processEvents()

    def test_stock_firmware_routes_to_bundled_l1_updater(self):
        dev = GbxDevice()
        dev.FW = firmware(version=0, timestamp=0, identifier="")
        dev.FW["ofw_ver"] = 31
        dev.PORT = "test-v13"
        self.assertIs(dev.FirmwareUpdateAvailable(), True)
        self.assertEqual(dev.GetFirmwareUpdaterClass(), (None, FirmwareUpdaterWindowV13))
        parent = QtWidgets.QWidget()
        path = Path(__file__).resolve().parents[1] / "FlashGBX"
        window = FirmwareUpdaterWindowV13(parent, str(path), device=dev)
        self.assertTrue(window.optCFW.isChecked())
        self.assertIn("L1", window.optCFW.text())
        self.assertIn("R31", window.lblDeviceFWVerResult.text())
        self.assertEqual(window.lblDevicePCBVerResult.text(), "v1.3")
        window.deleteLater()
        parent.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
