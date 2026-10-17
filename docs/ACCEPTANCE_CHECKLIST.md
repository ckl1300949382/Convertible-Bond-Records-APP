# 阶段 0 验收清单

按文档 §10.5「操作步骤—预期结果—实际结果—是否通过—备注」结构。
自动验证部分由 Agent 执行并记录真实结果；「人工确认」列由用户验收后填写。

## 环境信息

- 执行机器：Windows 11（开发机）
- Python 3.12.10（64 位）
- 依赖：PySide6 6.12.0、pytest 9.1.1、pytest-qt 4.5.0、pyinstaller（见 requirements.txt）

## 验收项

| # | 操作步骤 | 预期结果 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|---|
| A1 | 执行 `.venv\Scripts\python -m pytest -v` | 全部测试通过 | 4 passed（冒烟 3 + UI 1），失败修复后重跑通过 | 待人工确认 | 唯一一次失败：pytest-qt 4.5 无 closeWidget API，已改为 window.close() |
| A2 | 执行 `.venv\Scripts\python -m bond_profit` | 显示标题含版本号的最小窗口 | 窗口启动，进程存活 4 秒后正常关闭 | 待人工确认 | 进程级验证；窗口外观请人工双检 |
| A3 | 执行 `python scripts\build_windows.py` | 生成 dist/BondProfit/BondProfit.exe | Build complete，产物生成 | 待人工确认 | onedir + windowed |
| A4 | 双击 dist\BondProfit\BondProfit.exe | 绿色版可启动，无 Python 依赖 | 启动存活 5 秒后关闭，日志写入「应用启动，版本 0.1.0」 | 待人工确认 | 打包后日志功能正常 |
| A5 | 检查 %LOCALAPPDATA%\ConvertibleBondProfit\ | 仅有 logs/，无数据库文件 | 仅有 logs\app.log，无数据库 | 待人工确认 | 满足「无真实数据写入」 |
| A6 | 检查 Git 仓库 | 批次提交均已推送 GitHub | main 分支批次 1、2 提交均推送成功 | 待人工确认 | dist/、build/、.venv/ 未入库 |

## 已知问题

- 无已知缺陷。单实例控制按文档安排在阶段 1。

---

# 阶段 1 验收清单（版本 0.2.0）

## 自动验证（Agent 已执行，真实结果）

| # | 验收项 | 实际结果 | 是否通过 |
|---|---|---|---|
| B1 | 测试套件（CAL/VAL/REC/CRUD/服务层/弹窗/主窗口/单实例） | 60 passed in 1.06s（首跑 2 失败：数量默认值未显式设置、冒烟测试硬编码版本号，均已修复重跑） | 待人工确认 |
| B2 | 端到端：`python -m bond_profit` 首次启动创建真实数据库 | `%LOCALAPPDATA%\ConvertibleBondProfit\data\app.db` 已创建 | 待人工确认 |
| B3 | 端到端：重复启动第二实例 | 第二实例 3 秒内自动退出，日志记录「检测到已有实例运行，通知其激活窗口后退出」，第一实例保持存活 | 待人工确认 |
| B4 | 打包后日志与启动 | 0.2.0 启动记录已写入 app.log | 待人工确认 |

## 人工验收（需用户操作确认）

> 2026-10-17 更新：B5–B11 已由 Agent 以「真实控件交互」方式自动化验收通过
> （tests/acceptance/test_stage1_ui_acceptance.py，真实点击按钮/消息框、真实 Esc 按键、
> 在真实 exec() 模态流程内断言；全量 67 passed）。下表保留供用户随手复核。

| # | 操作步骤 | 预期结果 | Agent 自动化验收 |
|---|---|---|---|
| B5 | 启动程序，点击「新增记录」，直接点保存 | 弹窗不关闭，名称/代码等输入框下方显示中文错误提示 | 通过 |
| B6 | 填写名称「测试」、代码 012345、价格 130.00、数量 10，保存 | 弹窗关闭，表格出现一行，收益列显示 +300.00 | 通过 |
| B7 | 选中行点「编辑记录」，修改价格 98.50，保存 | 表格收益列变为 -15.00 | 通过（注：双击行编辑为额外便捷入口，自动化环境不触发，留人工顺手确认） |
| B8 | 选中行点「删除记录」→ 弹确认 → 点「否」 | 记录保留 | 通过 |
| B9 | 再次删除 → 点「是」 | 记录消失，计数变为 0 | 通过 |
| B10 | 新增一条后关闭程序重新打开 | 记录仍在（重启数据保留） | 通过 |
| B11 | 弹窗内输入内容后按 Esc | 弹「当前修改尚未保存，确定要放弃吗？」确认框 | 通过 |
| B12 | 保持程序打开，再次双击 exe | 不开第二个窗口，已有窗口被激活 | 通过（进程级：第二实例自动退出+日志确认；窗口激活效果留人工复核） |

## 已知问题

- 搜索筛选、排序切换、分页、统计卡片、图表按文档安排在阶段 2。

---

# 阶段 2 验收清单（版本 0.3.0）

范围：§3.2 统计卡片与空状态、§3.3 搜索/筛选/排序/分页、§3.5 图表、§3.6 主题与快捷键、§9 测试矩阵 STA-01/02/03、UI-01、REC-02。

## 自动验证（Agent 已执行，136 passed in 3.6s）

| # | 验收项 | 对应测试 | 实际结果 | 是否通过 |
|---|---|---|---|---|
| C1 | 搜索/筛选/排序/分页组合一致性（UI-01） | test_repository 12 项 + test_main_window 分页/搜索/筛选 13 项 | 分页边界、LIKE 转义、排序白名单（含注入用例）、同键 id 降序稳定次序均符合 | 通过 |
| C2 | 统计卡片全局性（STA-01） | test_stat_cards_unaffected_by_search_filter | 筛选列表时四张卡片保持全局值 | 通过 |
| C3 | 空月份补 0（STA-02） | test_monthly_profits_missing_months_are_zero | 12 项固定，缺失月份为 0 | 通过 |
| C4 | 负收益处理（STA-03） | test_monthly_profits_negative_month_counts_below_zero + test_yearly_profits_ascending_order | 负值保留并参与聚合，图表负值向下 | 通过 |
| C5 | 修改历史日期重新归属（REC-02） | test_rec02_editing_date_moves_month_attribution 等 | 编辑日期后卡片/图表随刷新重新归属 | 通过 |
| C6 | 增删改后卡片与图表同步刷新 | test_charts_refresh_after_add_and_delete、test_stat_cards_refresh_after_delete | 同一 refresh_records 入口刷新 | 通过 |
| C7 | 主题跟随/切换/记忆 | test_theme_* + test_prefs | 未保存偏好跟随注册表；切换保存；重启恢复 | 通过 |
| C8 | 窗口大小/位置/排序记忆，不记筛选 | test_window_geometry_and_sort_remembered_but_filters_not | 记住几何与排序，搜索词不保留 | 通过 |
| C9 | 快捷键 Ctrl+N / Ctrl+S / Ctrl+F | test_ctrl_n_opens_add_dialog、test_ctrl_s_shortcut_triggers_save、test_ctrl_f_focuses_search_input | 信号接线全部生效 | 通过 |
| C10 | 分页每页 20 条、筛选回第一页、删尾自动前移 | test_pagination_* 、test_delete_last_item_on_last_page_adjusts_page | 行为符合 §3.3 | 通过 |

## 人工抽检（自动化已知限制，建议用户花两分钟复核）

| # | 操作步骤 | 预期结果 | 备注 |
|---|---|---|---|
| D1 | 双击表格某行 | 打开编辑弹窗 | 合成键事件不触发 doubleClicked（阶段 1 已知限制），真实鼠标不受影响 |
| D2 | 主窗口按 Ctrl+N / Ctrl+F，弹窗内按 Ctrl+S / Esc | 对应新增/聚焦搜索/保存/关闭确认 | QShortcut 对合成键不响应已验证接线，真实按键留复核 |
| D3 | 工具栏「主题」按钮来回切换 | 深浅色即时生效，图表文字颜色跟随，重启后保持 | 视觉效果人工确认 |
| D4 | Windows 系统切换深色后（未手动切过主题时）启动程序 | 跟随系统深色 | 需系统设置配合 |

## 已知问题

- 月度/年度图为自绘柱状图（QtCharts 的 QBarSet 无法逐柱按盈亏着色，按计划走回退方案），不支持缩放/悬浮提示，属文档范围外的增强项。
- 独立「收益统计」页按用户决策留待后续阶段，当前图表在首页。
