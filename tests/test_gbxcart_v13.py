"""Protocol regression tests; these do not replace testing a physical reader."""

import configparser
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zipfile

from FlashGBX.hw_GBxCartRW import GbxDevice, GBxCartSerial


class L1Serial:
    """Small serial peer for the existing L1 wire protocol, without USB hardware."""

    def __init__(self, port, baudrate, timeout=0.1, exclusive=True, *, official=0):
        self.port, self.baudrate, self.timeout = port, baudrate, timeout
        self.is_open = True
        self.official = official
        self.pending = bytearray()
        self.writes = []
        self.variables = {}
        self.write_command = None
        self.rom = bytes(range(256)) * 1024
        self.ram = bytearray((i * 7) & 255 for i in range(0x10000))

    @property
    def in_waiting(self):
        return len(self.pending)

    def isOpen(self):
        return self.is_open

    def close(self):
        self.is_open = False

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.pending.clear()

    def reset_output_buffer(self):
        pass

    def read(self, count=1):
        result = bytes(self.pending[:count])
        del self.pending[:count]
        return result

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        if self.write_command is not None:
            addr = self.variables[(4, 0)]
            self.ram[addr:addr + len(data)] = data
            self.variables[(4, 0)] += len(data)
            self.write_command = None
            self.pending += b"\x01"
        elif data == b"h":  # PCB revision
            self.pending += b"\x04"
        elif data == b"V":  # Official version: zero identifies LK firmware
            self.pending += bytes([self.official])
        elif data == b"\xa1":
            self.pending += b"\x08" + struct.pack(">cHBI", b"L", 1, 4, 1709317610)
        elif data[0] == 0xA6:
            _, size, key, value = struct.unpack(">BBII", data)
            self.variables[(size, key)] = value
        elif data in (b"\xb1", b"\xc1", b"\xc3"):
            addr = self.variables[(4, 0)]
            size = self.variables[(2, 0)]
            ram = data == b"\xc3" or (data == b"\xb1" and self.variables.get((1, 1)) == 3)
            if not ram and data == b"\xc1":
                addr *= 2
            source = self.ram if ram else self.rom
            self.pending += source[addr:addr + size]
            self.variables[(4, 0)] += size // 2 if data == b"\xc1" else size
        elif data in (b"\xb3", b"\xc4"):
            self.write_command = data
        elif data == b"C":  # Reset LEDs
            self.pending += b"\x01"
        elif data in (b"\xa2", b"\xa3", b"\xa4", b"\xa5"):
            pass  # L1 mode/voltage commands have no ACK
        else:
            raise AssertionError("Unexpected L1 command: " + data.hex())
        return len(data)


def firmware(pcb=4, version=1, timestamp=1709317610, identifier="L"):
    return dict(pcb_ver=pcb, pcb_name="GBxCart RW", cfw_id=identifier,
                fw_ver=version, fw_ts=timestamp, fw_dt="2024-03-01", ofw_ver=0)


class FirmwarePolicyTests(unittest.TestCase):
    def test_bundled_l1_is_allowed(self):
        dev = GbxDevice()
        dev.FW = firmware()
        self.assertFalse(dev.FirmwareUpdateAvailable())
        self.assertIs(dev.FW_UPDATE_REQ, False)

    def test_official_firmware_requires_l1_instead_of_discontinuation(self):
        dev = GbxDevice()
        dev.FW = firmware(version=0, timestamp=0, identifier="")
        dev.FW["ofw_ver"] = 31
        self.assertTrue(dev.FirmwareUpdateAvailable())
        self.assertIs(dev.FW_UPDATE_REQ, True)

    def test_stale_or_unknown_v13_firmware_requires_update(self):
        for fw in (firmware(timestamp=0), firmware(identifier="X"), firmware(version=2)):
            with self.subTest(fw=fw):
                dev = GbxDevice()
                dev.FW = fw
                self.assertTrue(dev.FirmwareUpdateAvailable())
                self.assertIs(dev.FW_UPDATE_REQ, True)

    def test_other_discontinued_boards_remain_blocked(self):
        for pcb in (2, 90, 100):
            with self.subTest(pcb=pcb):
                dev = GbxDevice()
                dev.FW = firmware(pcb=pcb)
                self.assertTrue(dev.FirmwareUpdateAvailable())
                self.assertEqual(dev.FW_UPDATE_REQ, 2)

    def test_modern_firmware_policy_is_unchanged(self):
        for pcb in (5, 6):
            with self.subTest(pcb=pcb):
                dev = GbxDevice()
                dev.FW = firmware(pcb, 16, dev.DEVICE_LATEST_FW_TS[pcb])
                self.assertFalse(dev.FirmwareUpdateAvailable())
                self.assertIs(dev.FW_UPDATE_REQ, False)
                dev.FW["uart_ack"] = False
                self.assertTrue(dev.FirmwareUpdateAvailable())
                self.assertIs(dev.FW_UPDATE_REQ, False)

    def test_bundled_v13_firmware_timestamp_matches_policy(self):
        path = Path(__file__).resolve().parents[1] / "FlashGBX/res/fw_GBxCart_RW_v1_3.zip"
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("cfw.hex", archive.namelist())
            ini = configparser.ConfigParser()
            ini.read_string(archive.read("fw.ini").decode("utf-8"))
        self.assertEqual(ini.getint("Firmware", "cfw_buildts"), GbxDevice.DEVICE_LATEST_FW_TS[4])


class L1ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.dev = GbxDevice()
        self.dev.FW_VAR = {}
        self.dev.INFO = {"action": None}
        self.dev.CANCEL = self.dev.ERROR = False
        self.dev.NO_PROG_UPDATE = True
        self.peer = L1Serial("test-v13", 1000000)
        with patch.object(self.dev, "_OpenSerial", return_value=self.peer):
            self.assertEqual(self.dev.Initialize(flashcarts={"DMG": {}, "AGB": {}}, port="test-v13"), [])

    def tearDown(self):
        self.dev.Close()

    def test_discovery_connects_l1_at_one_megabaud(self):
        self.assertTrue(self.dev.IsConnected())
        self.assertEqual(self.dev.GetPCBVersion(), "v1.3")
        self.assertEqual(self.dev.GetFirmwareVersion(), "L1")
        self.assertEqual(self.dev.BAUDRATE, 1000000)
        self.assertIs(self.dev.FW_UPDATE_REQ, False)
        self.assertLessEqual(self.dev.MAX_BUFFER_WRITE, 0x100)

    def test_l1_capability_limits_and_new_commands(self):
        self.assertEqual(self.dev.GetSupportedModes(), ["DMG", "AGB"])
        self.assertFalse(self.dev.CanPowerCycleCart())
        self.assertFalse(self.dev.IsClkConnected())
        self.assertFalse(self.dev.SupportsBootloaderReset())
        start = len(self.peer.writes)
        self.dev.SetAutoPowerOff(1500)
        self.dev.SetAGBReadMethod(2)
        self.dev.SetDMGReadMethod(1)
        self.dev.SetFlowControl(True)
        self.assertEqual(self.peer.writes[start:], [])
        # Even when the transport supports ACK, a v1.3 must never negotiate it.
        with patch.object(self.dev, "DEVICE", spec=GBxCartSerial) as transport:
            self.dev._ConfigureACKTransport()
            transport.ConfigureACK.assert_not_called()

    def test_dmg_and_agb_rom_reads_across_block_boundary(self):
        for mode in ("DMG", "AGB"):
            with self.subTest(mode=mode):
                self.dev.SetMode(mode)
                self.assertEqual(self.dev.ReadROM(0x120, 0x201, max_length=0x100), self.peer.rom[0x120:0x321])
                self.assertEqual(self.dev.ReadROM(0, 1), self.peer.rom[:1])

    def test_dmg_and_agb_save_round_trip_with_partial_last_block(self):
        payload = bytearray((i * 11) & 255 for i in range(0x201))
        for mode in ("DMG", "AGB"):
            with self.subTest(mode=mode):
                self.dev.SetMode(mode)
                self.dev.WriteRAM(0x40, payload)
                self.assertEqual(self.dev.ReadRAM(0x40, len(payload), max_length=0x100), payload)

    def test_official_firmware_is_detected_for_gui_updater(self):
        peer = L1Serial("official-v13", 1000000, official=31)
        with patch.object(self.dev, "_OpenSerial", return_value=peer):
            self.dev.Initialize(port=peer.port)
        self.assertEqual(self.dev.GetFirmwareVersion(), "R31")
        self.assertIs(self.dev.FW_UPDATE_REQ, True)


if __name__ == "__main__":
    unittest.main()
