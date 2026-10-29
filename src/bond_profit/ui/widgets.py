"""可复用界面组件：侧栏、按钮、分段控件、搜索框。

存在的理由：主线原本把导航、工具栏、统计卡全部内联写在 ``MainWindow.__init__``
里，改一个圆角要碰好几个地方。这里把「长得一样、行为一样」的控件收成类，
视觉只在 :mod:`bond_profit.ui.tokens` 与 :mod:`bond_profit.ui.theme` 改一次。

约束（与测试契约一致，不可违反）：
- ``Sidebar.nav_list`` 保持为 ``QListWidget``：测试直接断言 ``count()``、
  ``item(i).text()``、``currentRow()``，换成自绘控件会让断言全部失效。
- 按钮的 ``text()`` 是行为契约（主题按钮按文本判断当前主题），
  因此主题按钮保留文本，图标只是附加。

图标着色：QSS 管不到已经生成好的 ``QIcon``，所以主题切换后必须调用
:meth:`Sidebar.refresh_icons` 重新按新调色板生成图标。
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from bond_profit.ui import icons, theme, tokens


def _named(widget: QWidget, name: str) -> QWidget:
    """设 objectName 并返回自身，让 QSS 用 ``#name`` 精确定位（禁止裸 QWidget 选择器）。"""
    widget.setObjectName(name)
    return widget


def current_mode() -> str:
    """从 QApplication 取当前主题；尚未应用主题时按浅色处理。"""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    mode = app.property(theme.THEME_MODE_PROPERTY) if app is not None else None
    return str(mode) if mode else "light"


def set_flag(widget: QWidget, name: str, on: bool) -> None:
    """切换 QSS 用的动态属性（``[name="1"]``），并强制样式重新匹配。"""
    widget.setProperty(name, "1" if on else "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def apply_sign_property(widget: QWidget, value: float) -> None:
    """按数值正负打 ``pos`` / ``neg`` 动态属性，QSS 据此上色（涨红跌绿）。

    零为中性色。属性变化后必须 unpolish + polish，否则 QSS 不会重新匹配。
    """
    new = ("1" if value > 0 else "", "1" if value < 0 else "")
    if (widget.property("pos"), widget.property("neg")) == new:
        return
    widget.setProperty("pos", new[0])
    widget.setProperty("neg", new[1])
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Divider(QFrame):
    """1px 发丝分隔线：分组之间的唯一分隔手段（不用凸起边框）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("divider")
        self.setFixedHeight(1)


class Section(QFrame):
    """分组区块：小标题 + 弱化说明 + 横向内容区。

    数据管理的「导入 / 导出」、备份页的操作区都用它，保证各页
    标题与说明的层级一致；内容区是横向布局，调用方自行加 stretch。
    """

    def __init__(self, title: str, hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("section")
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        box.addWidget(_named(QLabel(title), "sectionTitle"))
        if hint:
            hint_label = _named(QLabel(hint), "sectionHint")
            hint_label.setWordWrap(True)
            box.addWidget(hint_label)
        self.body = QHBoxLayout()
        self.body.setSpacing(8)
        box.addLayout(self.body)


class MiniStat(QWidget):
    """mini 指标：小标签 + 19px 数字——统计条的基本单元（比总览 hero 低一级）。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        box.addWidget(_named(QLabel(title), "miniLabel"))
        self.value = _named(QLabel("0"), "miniValue")
        box.addWidget(self.value)

    def set_value(self, text: str, sign: float | None = None) -> None:
        """填数字；给了 sign 就按正负上色（不给则中性）。"""
        self.value.setText(text)
        apply_sign_property(self.value, 0.0 if sign is None else sign)


class RowHairlineDelegate(QStyledItemDelegate):
    """表格行间 1px 发丝线。

    QSS 的 ``::item { border-bottom }`` 在 QTableWidget 上渲染不可靠
    （部分 style 会丢），所以用 delegate 在每个单元格底部补一条线；
    颜色在绘制时实时取当前主题，主题切换无需手动刷新。
    """

    def paint(self, painter, option, index) -> None:  # noqa: N802 (Qt 命名)
        super().paint(painter, option, index)
        line = QColor(tokens.palette_for(current_mode()).line)
        rect = option.rect
        painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), line)


class BrandMark(QWidget):
    """侧栏顶部品牌区：圆角方块 + 应用名 + 「本地 · 离线」状态。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 0, 0)
        row.setSpacing(9)

        mark = _named(QLabel("转"), "brandMark")
        mark.setFixedSize(26, 26)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(mark)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        texts.addWidget(_named(QLabel("转债账本"), "brandName"))
        texts.addWidget(_named(QLabel("本地 · 离线"), "brandSub"))
        row.addLayout(texts)
        row.addStretch(1)


class StatusDot(QLabel):
    """状态圆点：正常用盈利红，未知/异常用弱色。

    状态通过 ``ok`` 动态属性交给 QSS 判断（``#statusDot[ok="true"]``），
    而不是在 Python 里拼 inline 样式——后者主题切换后不会重新求值。
    """

    def __init__(self, ok: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusDot")
        self.setFixedSize(6, 6)
        self._ok = ok
        self.set_ok(ok)

    def set_ok(self, ok: bool) -> None:
        self._ok = ok
        self.setProperty("ok", "true" if ok else "false")
        # 动态属性变化后必须重新 polish，QSS 才会重新匹配
        self.style().unpolish(self)
        self.style().polish(self)


class IconButton(QPushButton):
    """纯图标按钮：正方形，无文字，提示走 tooltip。"""

    def __init__(self, icon_name: str, tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self.setObjectName("iconButton")
        self.setFixedSize(tokens.CONTROL_HEIGHT, tokens.CONTROL_HEIGHT)
        if tooltip:
            self.setToolTip(tooltip)
        self.refresh_icon()

    def refresh_icon(self) -> None:
        palette = tokens.palette_for(current_mode())
        self.setIcon(icons.icon(self._icon_name, palette.text_2, size=15))


class PrimaryButton(QPushButton):
    """主操作按钮：深色实心胶囊，一个界面里只出现一次。"""

    def __init__(self, text: str, icon_name: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._icon_name = icon_name
        self.setObjectName("primaryButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_name:
            self.refresh_icon()

    def refresh_icon(self) -> None:
        if not self._icon_name:
            return
        palette = tokens.palette_for(current_mode())
        self.setIcon(icons.icon(self._icon_name, palette.accent_fg, size=13))


class GhostButton(QPushButton):
    """次要按钮：默认透明，悬停才出现底色——对应提案 B 的工具栏按钮。"""

    def __init__(self, text: str, icon_name: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_name:
            self.refresh_icon()

    def refresh_icon(self) -> None:
        if not self._icon_name:
            return
        palette = tokens.palette_for(current_mode())
        self.setIcon(icons.icon(self._icon_name, palette.text_2, size=14))


class Segmented(QWidget):
    """分段控件（Apple 风格）：N 个文字选项单选，选中项深色胶囊。

    替代两个并排的 QRadioButton/普通按钮组；选项少（2–3 个）时最轻量。
    """

    currentChanged = Signal(int)

    def __init__(self, options: list[str], current: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmented")
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        self._buttons: list[QPushButton] = []
        for i, text in enumerate(options):
            button = QPushButton(text)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setChecked(i == current)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, idx=i: self._select(idx))
            row.addWidget(button)
            self._buttons.append(button)
        self._apply_checked()

    def _select(self, index: int) -> None:
        changed = index != self.current
        for i, button in enumerate(self._buttons):
            button.setChecked(i == index)
        self._apply_checked()
        if changed:
            self.currentChanged.emit(index)

    def _apply_checked(self) -> None:
        # 动态属性切换后重新 polish，QSS 的选中态才会刷新
        for button in self._buttons:
            button.style().unpolish(button)
            button.style().polish(button)

    @property
    def current(self) -> int:
        for i, button in enumerate(self._buttons):
            if button.isChecked():
                return i
        return 0


class Sidebar(QFrame):
    """左侧导航：品牌 + 三个页面入口 + 底部（备份状态 / 主题 / 日志）。

    页面切换仍走 ``QListWidget.currentRowChanged``，``MainWindow`` 只负责把
    索引转发给 ``pages`` 栈——保持既有的「无路由框架」结构。
    """

    # (显示文字, 图标名)
    NAV_ITEMS = (
        ("总览", "overview"),
        ("数据管理", "data"),
        ("备份与恢复", "backup"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(tokens.SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        box = QVBoxLayout(self)
        box.setContentsMargins(10, 14, 10, 10)
        box.setSpacing(0)
        box.addWidget(BrandMark())
        box.addSpacing(14)

        # 导航列表：必须是 QListWidget（测试契约），靠 QSS + item icon 做成 Apple 侧栏
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("nav")
        self.nav_list.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for label, icon_name in self.NAV_ITEMS:
            QListWidgetItem(icons.icon(icon_name, "#000000"), label, self.nav_list)
        box.addWidget(self.nav_list, stretch=1)
        box.addSpacing(8)

        # ---- 底部：备份状态 + 主题/日志 ----
        foot = QVBoxLayout()
        foot.setContentsMargins(4, 0, 4, 0)
        foot.setSpacing(9)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_dot = StatusDot(ok=True)
        self.status_label = _named(QLabel("上次自动备份 —"), "sideMeta")
        status_row.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.status_label, stretch=1)
        foot.addLayout(status_row)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        # 文本保留"浅色/深色"：_on_toggle_theme 按文本判断当前主题
        self.theme_button = QPushButton("主题")
        self.theme_button.setObjectName("sideButton")
        self.log_button = IconButton("folder")
        actions.addWidget(self.theme_button, stretch=1)
        actions.addWidget(self.log_button)
        foot.addLayout(actions)

        box.addLayout(foot)

        self.nav_list.currentRowChanged.connect(lambda _row: self.refresh_icons())

    def refresh_icons(self, mode: str | None = None) -> None:
        """按当前主题重新生成导航图标：选中项用盈利红，其余用次要文字色。

        图标是预先渲染好的 ``QIcon``，QSS 改不了它的颜色，只能重新生成——
        这是自绘图标在双主题下的固定成本。
        """
        palette = tokens.palette_for(mode or current_mode())
        current = self.nav_list.currentRow()
        for row, (_label, icon_name) in enumerate(self.NAV_ITEMS):
            color = palette.profit if row == current else palette.text_2
            item = self.nav_list.item(row)
            if item is not None:
                item.setIcon(icons.icon(icon_name, color, size=16))
