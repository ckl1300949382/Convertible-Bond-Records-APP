"""用户偏好读写测试（§3.6）：只记主题；ini 文件隔离，不碰真实偏好存储。"""

from __future__ import annotations

from bond_profit.ui import prefs, theme


def test_open_settings_ini_isolated(tmp_path):
    settings = prefs.open_settings(str(tmp_path / "prefs.ini"))
    assert settings.fileName().endswith("prefs.ini")


def test_theme_roundtrip(tmp_path):
    settings = prefs.open_settings(str(tmp_path / "prefs.ini"))
    assert prefs.resolve_theme(settings) in ("light", "dark")  # 未保存时跟随 Windows

    prefs.save_theme(settings, "dark")
    assert prefs.resolve_theme(settings) == "dark"


def test_resolve_theme_unknown_value_follows_windows(tmp_path, monkeypatch):
    settings = prefs.open_settings(str(tmp_path / "prefs.ini"))
    settings.setValue("ui/theme", "auto")
    monkeypatch.setattr(theme, "detect_windows_theme", lambda: "dark")
    assert prefs.resolve_theme(settings) == "dark"
