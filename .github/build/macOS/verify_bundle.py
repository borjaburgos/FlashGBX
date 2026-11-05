"""Check the completed app, including launch, before distributing its DMG."""

from pathlib import Path
import os
import plistlib
import subprocess
import sys
import time
import zipfile

app = Path(sys.argv[1]).resolve()
arch = sys.argv[2]
executable = app / "Contents/MacOS/FlashGBX"
subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
architectures = subprocess.check_output(["lipo", "-archs", str(executable)], text=True).split()
assert architectures == [arch], architectures
with (app / "Contents/Info.plist").open("rb") as stream:
    info = plistlib.load(stream)
assert info["CFBundleIdentifier"] == "com.borjaburgos.FlashGBX"
resources = app / "Contents/MacOS/res"
for filename in ("config.zip", "fw_GBxCart_RW_v1_3.zip"):
    with zipfile.ZipFile(resources / filename) as archive:
        assert archive.testzip() is None
assert (resources / f"libmgba-macos-{arch}.dylib").is_file()
assert (app / "Contents/MacOS/locale").is_dir()

env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
help_result = subprocess.run([str(executable), "--help"], env=env, capture_output=True,
                             text=True, timeout=30, check=True)
assert "backup-rom" in help_result.stdout, help_result.stdout + help_result.stderr

# A missing Qt plugin or import failure exits immediately. Start the full GUI,
# allow Qt to initialize, then terminate it without interacting with hardware.
process = subprocess.Popen([str(executable)], env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
try:
    time.sleep(5)
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(f"Packaged GUI exited early ({process.returncode}):\n{stdout}\n{stderr}")
finally:
    if process.poll() is None:
        process.terminate()
    stdout, stderr = process.communicate(timeout=10)
    print(stdout)
    print(stderr, file=sys.stderr)
print(f"Verified {arch}: signature, architecture, resources, CLI help and GUI startup")
