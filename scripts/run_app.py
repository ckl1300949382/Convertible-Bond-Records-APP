"""绿色版打包入口（阶段 5）：PyInstaller 以此文件为构建目标。"""

from __future__ import annotations

import sys

from bond_profit.app import main

if __name__ == "__main__":
    sys.exit(main())
