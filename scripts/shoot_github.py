# shoot_github.py
# Скриншоты публичных страниц запусков GitHub Actions (headless Edge).
# Запуск: python scripts/shoot_github.py <имя> <url> [ширина] [высота]

import pathlib
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

name, url = sys.argv[1], sys.argv[2]
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1400
height = int(sys.argv[4]) if len(sys.argv) > 4 else 1100
with tempfile.TemporaryDirectory() as tmp:
    shot = pathlib.Path(tmp) / "shot.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--screenshot={shot}", f"--window-size={width},{height}",
                    "--virtual-time-budget=15000", "--force-device-scale-factor=1", f"--user-data-dir={tmp}", url],
                   check=True, capture_output=True, timeout=120)
    Image.open(shot).convert("RGB").save(ROOT / "screenshots" / f"{name}.png")
print("saved", name)
