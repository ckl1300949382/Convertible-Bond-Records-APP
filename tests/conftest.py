"""测试全局隔离。

背景（2026-10-28 修正）：界面测试构造 MainWindow 时多数没有传 settings_path，
于是读写的是本机真实 QSettings（注册表 HKCU\\Software\\BondProfit\\BondProfit）。
用例关闭窗口时 closeEvent 会把当时的排序写回注册表，下一条用例启动就继承了
上一条留下的排序，造成「同一份代码两次结果不同」，也污染了用户的真实偏好。

这里统一把「未显式指定路径」的偏好存储重定向到当前用例的临时 ini；
显式传 settings_path 的用例行为不变。
"""

from __future__ import annotations

import pytest

from bond_profit.ui import prefs


@pytest.fixture(autouse=True)
def isolate_qsettings(tmp_path, monkeypatch):
    """把默认 QSettings 重定向到临时 ini，返回该 ini 路径供用例复用。"""
    ini = tmp_path / "qsettings.ini"
    real_open_settings = prefs.open_settings

    def open_settings(ini_path=None):
        return real_open_settings(str(ini_path) if ini_path is not None else str(ini))

    monkeypatch.setattr(prefs, "open_settings", open_settings)
    yield ini
