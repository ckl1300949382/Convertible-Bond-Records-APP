"""测试脚本：python scripts/run_tests.py"""

from __future__ import annotations

import sys

import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["-v"]))
