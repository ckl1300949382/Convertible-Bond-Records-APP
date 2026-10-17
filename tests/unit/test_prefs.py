"""用户偏好读写测试（§3.6）：ini 文件隔离，不碰真实偏好存储。"""

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


def test_window_state_roundtrip(tmp_path):
    from PySide6.QtCore import QByteArray

    settings = prefs.open_settings(str(tmp_path / "prefs.ini"))
    geometry, sort_key, descending = prefs.load_window_state(settings)
    assert geometry is None  # 无保存值
    assert sort_key == "date"
    assert descending is True

    settings.setValue("ui/window_geometry", QByteArray(b"fake-geometry"))
    settings.setValue("ui/sort_key", "price")
    settings.setValue("ui/sort_desc", False)
    geometry, sort_key, descending = prefs.load_window_state(settings)
    assert geometry == QByteArray(b"fake-geometry")
    assert sort_key == "price"
    assert descending is False


def test_window_state_invalid_sort_key_falls_back(tmp_path):
    settings = prefs.open_settings(str(tmp_path / "prefs.ini"))
    settings.setValue("ui/sort_key", "1; DROP TABLE sales")
    _, sort_key, _ = prefs.load_window_state(settings)
    assert sort_key == "date"
