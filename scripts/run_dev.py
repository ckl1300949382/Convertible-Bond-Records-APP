"""开发环境启动脚本：python scripts/run_dev.py"""

from __future__ import annotations

import sys
from pathlib import Path

# 未执行 pip install -e . 时也能从 src 导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bond_profit.app import main

if __name__ == "__main__":
    raise SystemExit(main())
