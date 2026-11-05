# GBxCart RW v1.3 test build

This fork restores the v1.3 support disabled in upstream FlashGBX 5.2.1. It is based on upstream commit `5b2398b` and retains the existing L1 protocol implementation and original firmware archive. No new device firmware was developed.

**Physical v1.3 hardware has not been tested for this release.** Automated serial-peer tests check firmware detection, the connection policy, mode selection, ROM reads and SRAM read/write transfers. The real Qt firmware updater is also tested. Each Mac package is checked for architecture, resources, ad hoc signature, command-line help and GUI startup. These checks cannot establish electrical behavior, USB timing or cartridge compatibility.

## Install on a Mac

1. Download the DMG for your Mac from [this fork's releases](https://github.com/borjaburgos/FlashGBX/releases): `arm64` for Apple silicon (M1 or newer), `x86_64` for Intel. The packaged builds target macOS 15 or newer, as upstream does. No Python installation is needed.
2. Open the DMG and drag FlashGBX to Applications. Quit other programs using the reader. Settings are stored in your user configuration directory, outside the signed app; use the app's configuration-directory menu item to find them.
3. The app is ad hoc signed, without an Apple Developer ID or notarization. If macOS blocks it, use System Settings → Privacy & Security → Open Anyway after attempting to open it. Only for this downloaded app, if needed, run `xattr -dr com.apple.quarantine /Applications/FlashGBX.app` in Terminal, then open it again.
4. Optional: verify the download in Terminal using `shasum -a 256 -c FlashGBX-5.2.1.post1_macOS-arm64.dmg.sha256` (substitute `x86_64` for Intel). Keep the DMG and its checksum file together.

## Connect a v1.3

1. With the reader unplugged, insert a known-good licensed GB/GBC cartridge. Connect the reader and choose Connect in FlashGBX.
2. A v1.3 already running the bundled **LK L1 firmware updated 2024-03-01** should connect directly. Confirm the connected device says **GBxCart RW v1.3** and **L1**.
3. A stock reader running official R firmware will be detected but requires the existing v1.3 firmware updater. Choose the **LK firmware L1** option, which is selected by default. Leave the device connected until the updater finishes, then reconnect in FlashGBX. The official R31 option does not enable FlashGBX cartridge operations. L1 is not compatible with insideGadgets' official interface software; its original R31 firmware can be restored through the same updater if needed.
4. Do not insert or remove cartridges while the reader is connected. v1.3 lacks software cartridge power control. Disconnect USB first. Always select the correct platform mode: Game Boy for GB/GBC (5 V), Game Boy Advance for GBA (3.3 V).

## First hardware checks

Start with backups on cartridges you own. Keep original save backups separately.

1. Select Game Boy mode and confirm the cartridge title and header. Back up its ROM twice to different files. Compare the files with `shasum -a 256`; hashes should match, and a recognized clean dump should match the database when available.
2. Back up save data twice and compare it too. Check the file has the expected size. Reconnect and repeat one backup to check the connection is repeatable.
3. Unplug USB before changing cartridges. Repeat ROM and save backups with a known-good GBA cartridge in Game Boy Advance mode, if available. Different save memory types need separate physical coverage.
4. Only after consistent backups, optionally restore a verified save to a cartridge whose save can be replaced, then back it up and compare. Test ROM writing only on an expendable compatible flash cartridge, using a homebrew ROM and verification. Flashcart support still depends on the existing L1 capability checks.

The v1.3 stays at 1,000,000 baud, with conservative 256-byte transfers. ACK/compressed flow control, automatic power-off, software power cycling, and features requiring newer firmware or a connected CLK pin remain unavailable. L1's older flashcart restrictions still apply. Other discontinued board revisions have not been enabled.

## Report results

Include the Mac model/CPU, macOS version, app version, PCB marking, displayed firmware, cartridge title/mapper/save type, operation, file sizes and hashes, and any exact error message. FlashGBX's configuration directory and debug log are accessible through its interface. Review logs for personal paths before sharing. Report problems in [this fork](https://github.com/borjaburgos/FlashGBX/issues), since this is an unofficial compatibility build.

## Rebuild and verify

From a Python environment with the project dependencies and PySide6 installed:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

The macOS workflow is manually dispatched with version `5.2.1.post1` and builds separately on native Apple silicon and Intel runners. It runs the tests before packaging and produces a DMG and SHA-256 file for each architecture. Release assets are published after both builds succeed. Build provenance is linked in the release notes.
