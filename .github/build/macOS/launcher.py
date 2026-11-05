"""Keep user settings outside the signed macOS application bundle."""

import sys
from FlashGBX.FlashGBX import main

if __name__ == "__main__":
    sys.exit(main(portableMode=False))
