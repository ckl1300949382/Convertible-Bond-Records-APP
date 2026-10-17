"""自绘柱状图组件测试：数据存储与渲染冒烟（§3.5）。"""

from __future__ import annotations

from decimal import Decimal

from bond_profit.ui.bar_chart import BarChart


def test_set_data_stores_items(qtbot):
    chart = BarChart()
    qtbot.addWidget(chart)

    data = [("1 月", Decimal("300.00")), ("2 月", Decimal("-15.00")), ("3 月", Decimal("0"))]
    chart.set_data(data)
    assert chart.items == data


def test_paint_smoke_with_mixed_values(qtbot):
    """正/负/零混合渲染不崩溃（盈利红/亏损绿/零中性在 paintEvent 内）。"""
    chart = BarChart()
    chart.resize(400, 200)
    qtbot.addWidget(chart)
    chart.show()
    qtbot.waitExposed(chart)

    chart.set_data(
        [
            ("1 月", Decimal("300.00")),
            ("2 月", Decimal("-15.00")),
            ("3 月", Decimal("0")),
            ("4 月", Decimal("0")),
        ]
    )
    chart.grab()  # 强制渲染，异常即失败


def test_paint_smoke_empty_and_single_value(qtbot):
    chart = BarChart()
    chart.resize(400, 200)
    qtbot.addWidget(chart)
    chart.show()
    qtbot.waitExposed(chart)

    chart.set_data([])  # 空数据显示「暂无数据」
    chart.grab()

    chart.set_data([("2026", Decimal("-510.00"))])  # 全负值：零轴在顶部
    chart.grab()

    chart.set_data([("2026", Decimal("510.00"))])  # 全正值：零轴在底部
    chart.grab()
