"""Windows 绿色版打包脚本：python scripts/build_windows.py

产物：dist/BondProfit/BondProfit.exe（onedir + 无控制台窗口）。
spec 与工作目录放在 build/ 下（已被 .gitignore 忽略）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_NAME = "BondProfit"


def main() -> int:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name", APP_NAME,
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--paths", str(PROJECT_ROOT / "src"),
        str(PROJECT_ROOT / "src" / "bond_profit" / "__main__.py"),
    ]
    print("执行:", " ".join(args))
    result = subprocess.call(args)
    if result == 0:
        print(f"打包完成: {DIST_DIR / APP_NAME / (APP_NAME + '.exe')}")
    else:
        print(f"打包失败，退出码 {result}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
