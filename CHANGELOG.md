# 变更日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
程序版本采用 `MAJOR.MINOR.PATCH`，数据库 schema_version 独立递增（阶段 1 起）。

## [未发布] - 2026-10-29 - UI 改版：提案 B「数字剧场」落地

视觉方向已由用户确认（三套静态提案中选 B）。业务规则、数据库 schema、测试数量（228）均不变。
改造分批进行，每批独立提交、独立回归。

- 批次 1（令牌层与样式层）：
  - 新增 `ui/tokens.py`：色值/字号/圆角/控件尺寸的唯一来源。`Palette` 双主题（浅色 `#ffffff` 画布、深色 `#121214`），含 `profit`/`loss` 两色（**涨红跌绿不变**）、字号阶（hero 62px / mini 19px / title 16px / base 13px / body 12px / small 11px）、圆角三级（卡 9 / 控件 7 / 芯片 5）、控件高 28、行高 30
  - `ui/tokens.py::apply_app_font`：全局字体 `Segoe UI Variable Display` + `Microsoft YaHei UI` 回退（本机实测均存在），并开启 `tnum` 等宽数字，让收益列纵向对齐；字体不支持该特性时静默跳过
  - `ui/theme.py` 重写：浅色不再「清空 QSS 退回 Qt 默认」，两套主题由同一份模板 + 令牌生成完整 QSS，覆盖窗口/按钮/输入框/表格/导航/滚动条/状态栏/提示/菜单/日历弹层
  - 强制 Fusion 风格（`theme.BASE_STYLE`）：原生 Windows style 会忽略圆角与扁平按钮，QSS 只能"看起来生效一半"。设一次即在 QApplication 上打标记，不重复重建风格对象
  - 规避已知坑：不再使用裸 `QWidget { }` 选择器（旧深色 QSS 第一行会污染所有子控件）；改用 `#root` objectName 与具体类型选择器
  - `ui/main_window.py`：central 加 `objectName("root")`；移除 4 张统计卡与 2 个图表容器的 `StyledPanel` 边框（旧的深灰凸起框与新风格冲突）
  - 测试更新 4 处（均为「旧视觉契约」而非行为变更）：`test_theme.py` 的「深色 QSS 含 #2b2b2b」改为读取令牌、`test_stylesheet_for_light_is_empty` 改为验证浅色也有完整 QSS 且与深色不同、`test_apply_theme_sets_and_clears_stylesheet` 改为验证切换不残留
  - 本机实测：全量 228 项通过；用 58 条虚构记录渲染真实窗口截图核对，浅色/深色均无黑字压深底、无深灰残留块
  - 补充：`test_main_window.py` 的主题切换断言收紧——不再以「浅色 = 空 QSS」为前提（该前提已被本批推翻，旧断言只是碰巧通过），改为「实际样式表 == 该主题应有样式表」

- 批次 2（图标层、组件层与侧栏重做）：
  - 新增 `ui/icons.py`：13 个内联 SVG 图标（总览/数据管理/备份/新增/编辑/删除/搜索/日/月/文件夹/刷新/勾/警告），`QSvgRenderer` 渲染，不引入图标库、保持完全离线；只缓存 SVG 字节串而不缓存 `QPixmap`（QPixmap 绑定 QApplication，测试重建 app 后旧位图会变悬空对象）
  - 新增 `ui/widgets.py`：`Sidebar`（品牌区 + 导航 + 底部状态行）、`BrandMark`、`StatusDot`（QSS 动态属性着色）、`IconButton`/`PrimaryButton`/`GhostButton`
  - 侧栏重做：140px 纯文字列表 → 196px 图标+文字侧栏；新增品牌区（「转」方块 + 转债账本 + 本地·离线）；底部新增「上次自动备份」状态行；主题按钮与日志按钮从工具栏移到侧栏底部
  - **测试契约不变**：`nav_list` 仍是 `QListWidget`（`count()`/`item(i).text()`/`currentRow()` 断言原样通过）；`theme_button`/`log_button` 仍是 `MainWindow` 的属性，`text()` 契约不变
  - 图标随主题重新着色：`Sidebar.refresh_icons(mode)`——QIcon 是预渲染位图，QSS 管不到，必须显式重新生成；当前主题记录在 `QApplication`（`theme.THEME_MODE_PROPERTY`）
  - 修复自绘图表深色下露浅灰底：QSS 不更新 QPalette（已知坑 5 的又一实例），`BarChart` 开启 `WA_StyledBackground` 并加 QSS `BarChart` 规则，背景随主题自动切换（探针实测深色 `#121214` / 浅色 `#ffffff`）
  - 本机实测：全量 228 项通过；真实窗口截图核对，侧栏三图标、选中高亮（盈利红图标 + 卡片底）、底部状态行在浅色/深色下均正常

- 批次 3（总览页迁出 + hero 数字排版）：
  - 新增 `ui/overview_page.py`：总览页整体（页标题、工具栏、hero 指标区、图表、表格、分页、空状态）从 `main_window.py` 迁出——此前 170 行 UI 构建堆在 `__init__`；页面只管外观，数据填充与业务编排留在 MainWindow
  - **属性转发**：`window.table` / `window.search_input` / `window.total_profit_value` 等约 20 个控件名原样保留，1798 行 UI 测试对控件的直接访问零改动
  - hero 排版：累计收益 62px 唯一主视觉（数字与「元」拆为两个标签，62px/15px），本年/本月/累计卖出降为 19px mini——旧版四张同权重卡片废除
  - 涨红跌绿扩展到 hero/mini：按数值正负切 QSS 动态属性（pos/neg），零为中性色；盈利/亏损语义色值不变
  - 新增 `QPushButton#primaryButton` 主按钮样式（深色实心胶囊，「新增记录」/空状态入口使用）
  - MainWindow 瘦身：删除 `_make_stat_card`，表格填充/分页刷新下沉到 `overview.fill_table` / `set_pager`；清理 9 个不再使用的 QtWidgets 导入
  - 测试更新（已批准的 4 处断言）：`total_profit_value` / `year_profit_value` / `month_profit_value` 的 `text()` 不再含「元」（`"+400.00 元"` → `"+400.00"`）；`total_count_value` 仍为 `"N 笔"`
  - 本机实测：全量 228 项通过；浅色/深色截图核对，hero 主次、主按钮胶囊、深色可读性均正常

- 批次 4（表格视觉与空状态）：
  - 表格列宽固定（94/1fr/84/92/76/100/1fr，名称与备注均分余量）——替代旧版 `ResizeToContents`，翻页时列宽不再随内容左右抖动
  - 行高 30px（`tokens.ROW_HEIGHT`）、表头高 26px；去网格（`setShowGrid(False)`），行间 1px 发丝线改由 `_RowHairlineDelegate` 绘制（QSS 的 item border 在 QTableWidget 上渲染不可靠）；开启鼠标跟踪 + `::item:hover` 行悬停高亮
  - 纵向滚动改 `ScrollPerPixel`，滚动手感更细腻
  - 分页栏升级：顶部发丝线（`#tfoot` border-top）、按钮换成 26px 图标箭头（`IconButton` + 新增 `chev-left/chev-right` 图标）；**page_label 文本契约不变**（仍为「第 N / M 页」，7 处测试断言原样通过）
  - 空状态图形化：46px 圆角图标底 + 22px 线性图标 + 标题 + 副文案「新增第一条后，这里会自动算出收益与走势」+ 主按钮；`empty_title.text()` 契约不变
  - `OverviewPage.refresh_theme()`：空状态图标随主题重新着色，挂入 `_apply_theme_mode`
  - 本机实测：全量 228 项通过；浅色表格（发丝线/固定列宽/弱化表头）、深色、空状态三态截图核对

## [未发布] - 2026-10-28 - 维护：测试隔离与文档修正

不含业务逻辑变更，程序版本号与数据库 schema_version 均不变。

- 界面行为变更（为后续 UI 改版让路）：
  - `ui/prefs.py` 只保留主题记忆；删除 `load_window_state` / `save_window_state` 与 `ui/window_geometry`、`ui/sort_key`、`ui/sort_desc` 三个键
  - `ui/main_window.py`：启动固定 1080×760、表格默认「日期降序」；移除 `closeEvent` 中的偏好写回（该方法无其他职责，一并删除）
  - 原因：改 UI 后按旧几何还原会挤压新布局甚至让窗口落到屏幕外；旧排序键也可能与新表格列对不上
  - 搜索/筛选条件本来就明确不记忆（§3.6），行为未变
  - 测试：`test_prefs.py` 删 2 项窗口状态用例；`test_window_geometry_and_sort_not_remembered` 改为验证「重开后回到默认」；全量 228 项通过

- 测试隔离（修正 230 项不再稳定通过）：
  - 新增 `tests/conftest.py`：autouse 夹具把「未显式传 `settings_path`」的偏好存储重定向到临时 ini。此前 `tests/ui/` 与 `tests/acceptance/` 共 40 处 `MainWindow(...)` 未传该参数，读写本机真实 QSettings（注册表 `HKCU\Software\BondProfit\BondProfit`）：用例关闭窗口时 `closeEvent` 把当时的排序写回注册表，下一条用例继承上一条的状态，导致同一份代码两遍结果不同（实测 227 通过/3 失败 与 228 通过/2 失败），并污染用户真实偏好（`ui/sort_key=price`）
  - `tests/unit/test_backup.py::test_list_sorted_newest_first`：原来把 manifest 的 `created_at` 写死为 `2026-10-17T23:59:59` 当作「更晚」，该日期成为过去后排序断言必然反转（定时炸弹）。改为基于第一份备份的真实 `created_at` 加 1 秒，与当前日期解耦
  - 本机实测：全量 230 项连跑两遍均 230 passed；跑完 76 项 UI 测试后真实偏好未被写入
- 依赖与文档：
  - `requirements.txt` 补 `openpyxl==3.1.5`（此前只在 pyproject 声明，照 README 装依赖会缺 Excel 库）
  - `README.md`：状态表由「阶段 0 进行中」更新为阶段 0–5 全部完成、版本 1.0.0；打包命令改为 `scripts/build_release.ps1`
  - 删除阶段 0 遗留的 `scripts/build_windows.py`（产物 `dist/BondProfit/` 作废；`build_release.ps1` 直接调用 PyInstaller，不依赖它，源码/测试零引用）
  - 新增 `docs/已知问题.md`：留档三项未修技术隐患（错误提示关键字归位、金额转换异常未兜底、界面引用数据层类型）与两项需求文档偏差（备注列默认展示、统计入口合并），评估结论为不影响使用、不改代码

## [1.0.0] - 2026-10-17 - 阶段 5：Windows 发布与综合验收

- 批次 19（收官定版）：
  - 版本号 0.5.0 → 1.0.0（§11.4 正式发布版本）；阶段 5 验收清单见 docs/ACCEPTANCE_CHECKLIST.md（§12 十二项人工清单逐项展开）
  - 全量回归通过后重建发布包：dist/可转债收益记录_v1.0.0_win64.zip
  - Git tag：v1.0.0（§11.4 发布关联 commit/tag）
- 批次 18（绿色版打包）：
  - scripts/build_release.ps1：一键构建——PyInstaller（onedir + windowed，正式中文名「可转债收益记录.exe」）→ 拷入版本说明与使用说明 → 启动冒烟（进程存活检查、单实例冲突提示）→ 压缩发布包；产物入 dist/、build/ 不入 Git（架构决策 6）；脚本必须 UTF-8 with BOM（PowerShell 5 按 ANSI 读无 BOM 文件会乱码）
  - scripts/run_app.py：打包入口（app.py 无 __main__ 守卫，不能直接作为 PyInstaller 目标）
  - docs/版本说明.txt、docs/使用说明.txt：随包分发的发布文档（§11.1），含数据/备份位置、升级说明与快速上手
  - 新增构建依赖 pyinstaller（[project.optional-dependencies].build，仅构建用，运行包零影响）；本机实测：干净启动、自动初始化数据目录/日志/备份（PKG-01 本机部分通过）
- 批次 17（稳定性与日志复制）：
  - ui/error_hook.py：全局未捕获异常兜底——写完整堆栈日志 + 中文弹窗提示（含「打开日志」指引），不强制退出；数据层受控异常不经此钩子
  - 主窗口工具栏「打开日志」按钮：直达日志文件夹，便于整包拷贝反馈；无日志目录时友好提示
  - 中文文案巡检：全部 UI 模块零英文残留，无需改动
  - 测试：异常钩子 4 项、日志入口 2 项；230 项通过

## [0.5.0] - 2026-10-17 - 阶段 4：备份、恢复与版本迁移

- 批次 16（备份 UI + 收官）：
  - ui/backup_page.py：备份与恢复页（手动备份到自选目录、备份列表含时间/类型/记录数/库版本/验证状态、恢复确认对话框含数据替换警告、立即检查自动备份作为失败重试入口）；按钮仅发射信号，由主窗口槽内调用服务（延续批次 11 信号式接线约定）
  - 主窗口：左侧导航「总览 / 数据管理 / 备份与恢复」；QTimer 每 30 分钟检查自动备份（§6.1），失败仅在状态栏提示不阻断录入（BAK-03）；恢复成功后 refresh_records 同步刷新表格/卡片/图表（§66）
  - 版本号 0.4.0 → 0.5.0；阶段 4 验收清单见 docs/ACCEPTANCE_CHECKLIST.md；全套 224 项测试通过
- 批次 15（恢复流程 + 版本迁移）：
  - database.py：MIGRATIONS 逐版本迁移注册表（显式 BEGIN 事务——Python sqlite3 隐式事务只覆盖 DML、DDL 会自动提交，不显式开事务无法整体回滚；失败抛 MigrationError 原数据保留）；inspect_database 只读预检；DatabaseTooNewError（MIG-03 旧程序拒绝写入新库，任何写操作都在版本检查之后）
  - backup_service.restore_from_backup（§6.4）：实际文件校验（RES-01 损坏拒绝 / RES-02 过新拒绝）→ 恢复前保护备份 → 临时位置恢复 → 按需迁移 → 完整性/记录数/收益汇总三重比对 → 官方备份 API 写回活动连接（SQLite 事务保证，中断自动回滚 RES-03）；成功后置脏并记录当日（次日生成新自动备份）
  - app.py 启动编排：预检 → 过新弹窗退出 → 迁移前先创建并验证升级前保护备份（失败停止启动）→ connect 三类异常分别中文提示
  - 测试：迁移 4 项（含 DDL 成功后中途失败整体回滚）、恢复 6 项；210 项通过
- 批次 14（自动备份策略 + 启动健康检查）：
  - infrastructure/backup_state.py：state.json 持久化脏标记与最近自动备份日期；缺失/损坏按安全默认（视为有变更，宁可多备不漏备）
  - application/backup_service.py：自动备份策略——当天已成功跳过（BAK-01）、无变更跳过（§6.1）、跨天且有变更生成（BAK-02）、失败状态不变可重试（BAK-03）；手动备份成功后清脏（数据已有有效快照）
  - database.py：启动时先 integrity_check 再写入；损坏抛 DatabaseCorruptError，原文件原样保留，不静默建空库（§6.5）
  - sales_service/excel_service 成功写入触发 on_change 回调驱动脏标记；回调异常只记日志不影响记录
  - app.py：装配备份服务与脏标记接线；启动自动备份失败仅告警
  - 测试：备份策略 7 项、数据库 3 项、回调 2 项；200 项通过
- 批次 13（备份核心层，无新增第三方依赖）：
  - infrastructure/backup.py：SQLite 官方备份 API 一致性快照 → 临时文件 → integrity_check + 记录数校验 → 同目录原子发布；文件名含时间与随机后缀；manifest JSON 元数据（读取列表以实际文件检查为准，损坏文件标记未通过）；保留策略仅清理 auto 目录——第 31 份成功落盘后才删最旧一份（含其 manifest），protected/manual 永不清理，不误删无关文件（BAK-04/05/06）
  - 测试：备份核心 13 项；187 项通过

## [0.4.0] - 2026-10-17 - 阶段 3：Excel 导入导出

- 批次 12：阶段 3 收尾——验收清单 XLS-01～10 逐项对照（docs/ACCEPTANCE_CHECKLIST.md）、ARCHITECTURE 更新、版本号 0.4.0
- 批次 11（导出，XLS-09）：
  - repository/sales_service 新增 list_filtered：按搜索/年月条件取全集，不受分页限制
  - excel_service.export_records：导出 .xlsx——六业务字段 + 软件计算的「收益」列（导入时不作为可信来源）；代码列文本格式保留前导零，日期 yyyy-mm-dd、金额 0.00 显示格式；无匹配记录时不写文件并提示
  - 数据管理页新增「导出全部记录」「导出当前筛选结果」；筛选导出按钮仅发射 export_filtered_requested 信号，由主窗口槽内提供当前查询条件（页面不持有主窗口引用，避免循环引用引发的对象生命周期崩溃）
  - 测试：导出单测 3 项、导出 UI 5 项、导出接线 1 项；全套 174 项通过
- 批次 10（导入 UI）：
  - 主窗口：左侧导航「总览 / 数据管理」（§3.1），页面栈切换，默认进入总览；MainWindow 构造新增必传 excel_service 参数
  - ui/data_management.py：数据管理页（模板下载、从 Excel 导入），导入完成发射 import_completed 信号驱动总览页刷新
  - ui/import_preview_dialog.py：导入预览（§4.4）——统计行（预计新增/重复跳过/错误/预计净收益变化）、逐行状态表（可导入/重复跳过/错误 + 错误原因，错误红、重复琥珀色）；存在错误行禁用「开始导入」；确认后单事务写入并展示实际新增/跳过/净收益
  - app.py 装配 ExcelService；excel_service 预览时重复行保留解析记录供对照展示
  - 测试：数据管理页 7 项（monkeypatch 文件对话框走全流程）、预览对话框 4 项、主窗口导航 3 项；全套 166 项通过
- 批次 9（逻辑层，无 UI 改动）：
  - 新增依赖 openpyxl>=3.1（已经用户批准）
  - application/excel_service.py：官方模板生成（§4.1，六列标准列名 + 填写说明页，数据区无示例行，代码列文本格式保留前导零）；解析与逐行校验（§4.2，Excel 日期单元格与 YYYY-MM-DD 文本均可识别，数值单元格代码视为前导零丢失并拒绝猜测补零，拒绝布尔/非法数值/不可识别日期，跳过完全空白行并保留真实 Excel 行号）；导入专用去重键（§4.3，标准化六字段，备注空值统一）；预览统计（§4.4，可导入/重复跳过/错误逐行状态 + 预计净收益变化，仅计新增、含负收益）
  - 提交事务（§4.3）：存在任一错误行时整批拒绝提交；提交前重新检查去重（预览后数据库变化以实际事务为准）；repository.add_many 单事务批量写入，任一条失败全部回滚（XLS-05）
  - 测试：tests/unit/test_excel_service.py 16 项覆盖 XLS-01～10；全套 152 项通过

## [0.3.0] - 2026-10-17

- 阶段 2：首页与统计交互完成（版本号随本阶段发布递增）
- 批次 8：
  - 主题（§3.6）：首次启动跟随 Windows 浅/深色（读注册表 AppsUseLightTheme），工具栏「主题」按钮手动切换并保存偏好；深色为精简 QSS 调色板，图表标签/轴线颜色随主题切换
  - 窗口状态（§3.6）：记住窗口大小/位置（saveGeometry）与表头排序；明确不记住搜索/筛选条件
  - 快捷键（§3.6）：Ctrl+N 新增记录、Ctrl+S 弹窗内保存（Ctrl+F/Esc 此前已支持）
  - 偏好存储：ui/prefs.py 集中 QSettings 读写，测试可注入 ini 文件路径隔离
  - 版本号 0.2.0 → 0.3.0；阶段 2 验收清单见 docs/ACCEPTANCE_CHECKLIST.md
  - 测试：主题 5 项、偏好 5 项、UI 4 项、弹窗 Ctrl+S 1 项；全套 136 项通过
- 批次 7：
  - 领域层：monthly_profits（某年固定 12 项、缺失补 0、可含负值）、yearly_profits（年份升序聚合）
  - 服务层：monthly_profits / yearly_profits 透传
  - UI：自绘 BarChart 柱状图组件（盈利红/亏损绿/零中性、数值带正负号、负值柱向零轴下方延伸，无 QtCharts 依赖）；首页月度图（可选年份下拉，默认最新年份）与年度图；增删改后卡片与图表经 refresh_records 同步刷新
  - 测试：月度/年度聚合 8 项、BarChart 3 项、图表联动 3 项；全套 121 项通过
- 批次 6：
  - 领域层：domain/statistics.py 全局统计聚合（累计收益/本年收益/本月收益/累计卖出笔数，Decimal 纯函数，today 可注入）
  - 服务层：global_statistics 全量聚合透传，不经过搜索/筛选条件（STA-01）
  - 主窗口：四张统计卡片（带正负号与单位）、空状态页（「还没有任何卖出记录」+「新增第一条记录」入口，不插入示例数据）、增删改后卡片同步刷新
  - 测试：统计聚合 7 项、服务层 3 项（含 REC-02 重新归属）、UI 5 项；全套 107 项通过
- 批次 5：
  - 数据层：RecordQuery 查询条件对象；SalesRepository 分页查询（list_page / count_filtered，关键词 LIKE 转义、年月筛选日期范围、排序白名单 date/price/profit、id 降序稳定次序）、distinct_years
  - 服务层：SalesService.list_page（页码超界自动钳制，删除当前页最后一条后页码随之调整）、distinct_years 透传
  - 主窗口：搜索框（名称/代码包含匹配，Ctrl+F 聚焦）、年份/月份下拉筛选（月份下拉在选定年份后启用）、表头点击排序（日期/卖出单价/单笔收益，指示器显示）、每页 20 条分页控件、筛选变更回第一页
  - 测试：数据层 12 项、服务层 4 项、UI 13 项；全套 93 项通过

## [0.2.0] - 2026-10-17

### 阶段 1：记录核心与持久化

- 批次 3：
  - 领域层：SaleRecord 模型、7 项中文字段校验与标准化、Decimal 收益计算（(单价−100.00)×张数）、元↔分金额转换
  - 数据层：SQLite 连接与 schema（sales 表 + CHECK 约束兜底 + user_version=1）、SalesRepository CRUD（参数化 SQL、事务边界、允许重复录入、默认排序）
- 批次 4：
  - 服务层：SalesService 校验→写入协调，数据库失败转为中文提示并记日志
  - 新增/编辑弹窗：紧凑双列、日期选择器（默认当天）、数量默认 10 张、输入框下方错误提示、保存失败保留输入、未保存修改关闭时确认放弃
  - 主窗口升级：记录表格（含单笔收益列）、新增/编辑/删除入口、删除确认弹窗
  - 单实例控制：QLocalServer/QLocalSocket，重复启动自动激活已有窗口
  - 版本号 0.2.0；文档同步（CHANGELOG、ARCHITECTURE、阶段 1 验收清单）

## [0.1.0] - 2026-10-16

### 阶段 0：工程骨架与开发环境

- 批次 1：
  - 建立目录分层（ui / infrastructure，application/domain 随阶段 1 引入）
  - `pyproject.toml` 项目元数据与 pytest 配置；`requirements.txt` 锁定依赖版本（PySide6 6.12.0、pytest 9.1.1、pytest-qt 4.5.0）
  - 最小 PySide6 主窗口与应用装配入口（`python -m bond_profit`）
  - RotatingFileHandler 日志（`%LOCALAPPDATA%/ConvertibleBondProfit/logs/app.log`，目录可注入）
  - pytest + pytest-qt 测试框架，冒烟与 UI 测试共 4 项
- 批次 2：
  - PyInstaller 打包脚本 `scripts/build_windows.py`，产出 onedir 无控制台绿色版
  - 开发辅助脚本 `scripts/run_dev.py`、`scripts/run_tests.py`
  - 项目文档：README、ARCHITECTURE、AGENTS、阶段 0 验收清单
