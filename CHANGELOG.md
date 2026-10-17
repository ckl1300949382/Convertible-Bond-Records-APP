# 变更日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
程序版本采用 `MAJOR.MINOR.PATCH`，数据库 schema_version 独立递增（阶段 1 起）。

## [未定版] - UI V2.0 修复：日历弹层深色对比度（分支 ui-v2）

修复已知问题「QDateEdit 日历弹层星期表头深色对比度偏弱」。校验/保存逻辑零改动；无新增依赖。

- ui/theme.py：
  - 新增 apply_calendar_formats()——星期表头（Qt 内部 weekdayTextFormat 绘制，不走 QSS）按主题显式配色：周一~周五弱化文字色、周六/周日用主题红（中国日历休息日习惯，深浅主题各调亮度）
  - apply_theme() 新增全局 QPalette 文字角色同步（WindowText/ButtonText/Text）——QSS 不更新 QPalette，日历导航栏月/年按钮为 Qt 内部自绘（QCalToolButton），按全局调色板绘制文字，深色下黑字低对比；仅同步文字类角色，背景/强调色仍以 QSS 为准
  - 排查过程：先后验证控件调色板、组件级 QSS、headerTextFormat 均不可达（内部自绘绕过），最终以全局调色板方案收敛
- ui/record_dialog.py：创建日期控件（calendarPopup）时调用 apply_calendar_formats
- 测试：新增 tests/unit/test_theme.py::test_apply_calendar_formats_follows_theme；全量 pytest 真实执行 240 passed
- 视觉取证：docs/ui_v2_preview/fix_calendar_dark.png、fix_calendar_light.png
- 备注：日历导航栏深色对比度问题一并修复，已知问题清单中该项关闭

## [未定版] - UI V2.0 阶段 8（分支 ui-v2）

回归与发布。业务规则、数据库结构、Excel 规则、备份恢复逻辑零改动；无新增依赖。

- docs/版本说明.txt：新增「界面焕新（UI V2.0）」条目（随包发布）
- 回归：全量 pytest 真实执行 239 passed（阶段 0 基线 230 → 新增 widgets 5 项 + 主题断言扩展；业务测试零语义改动）
- 打包验证：scripts/build_release.ps1 实际执行通过——PyInstaller onedir 构建完成、构建冒烟通过（进程存活并正常响应关闭）、压缩产物 dist\可转债收益记录_v1.0.0_win64.zip（约 52 MB）
- 阶段 0~8 视觉取证汇总：docs/ui_v2_preview/（phase2~phase7 深浅主题截图）
- 已知问题（汇总）：
  - QT_QPA_PLATFORM=offscreen 缺 CJK 字体（截图取证改用真实 Windows 平台）
  - QDateEdit 日历弹层星期表头颜色由 Qt 内部格式控制，深色模式对比度可能偏弱
  - 月度图负值柱较矮时数值标签与类别标签间距较近（阶段 5 布局规则所致）
  - 阶段 7 高 DPI 为 QT_SCALE_FACTOR 渲染核验，未做物理显示器实测

## [未定版] - UI V2.0 阶段 7（分支 ui-v2）

动效与高 DPI。导航信号语义、页面切换行为、偏好存储零改动（无 prefs 新键）；无新增依赖。

- ui/main_window.py：左侧导航切换页面时新增约 120ms 透明度淡入（QGraphicsOpacityEffect + QVariantAnimation，OutCubic）；动画结束即移除特效，避免常驻渲染开销；窗口不可见（含全部测试场景）时跳过动画直接切页
- 高 DPI 核验：以 QT_SCALE_FACTOR=1.25 / 1.5 渲染截图（docs/ui_v2_preview/phase7_dpi125.png、phase7_dpi15.png），文字/按钮/表格/卡片无裁切无重叠（注：为渲染因子核验，非物理显示器实测）
- 测试：全量 pytest 真实执行 239 passed（无测试改动）
- 已知问题：月度图负值柱较矮时数值标签与类别标签间距较近（阶段 5 布局规则所致，非本次引入）

## [未定版] - UI V2.0 阶段 6（分支 ui-v2）

数据管理页与备份恢复页美化。信号、Excel 流程、备份/恢复/校验逻辑零改动；无新增依赖。

- ui/data_management.py：页标题/两处提示去掉内联样式，改 objectName（#pageTitle/#pageHint）+ QSS；「从 Excel 导入…」设为 accent 主操作；页边距/间距接入令牌（SPACE_XL/SPACE_L）
- ui/backup_page.py：标题/提示同样改 objectName + QSS；「手动备份到…」设为 accent 主操作；备份表开启斑马纹与行悬浮（与总览表格一致）；未通过验证行的错误红着色保留（item.setForeground 不受影响）；页边距/间距接入令牌
- ui/theme.py：新增 #pageTitle / #pageHint 样式节
- 测试：全量 pytest 真实执行 239 passed（无测试改动）
- 视觉取证：docs/ui_v2_preview/phase6_data_dark.png、phase6_data_light.png、phase6_backup_dark.png、phase6_backup_light.png（含一条未通过验证的模拟备份行）

## [未定版] - UI V2.0 阶段 5（分支 ui-v2）

图表视觉升级。绘制规则（盈红/亏绿/零中性不画柱、带符号数值标签、负值向下延伸）逐条保持；对外接口 items / set_data / set_label_color / apply_mode 不变；无新增依赖。

- ui/bar_chart.py：
  - 圆角柱（半径 3px，圆角只留在自由端：正值柱圆顶、负值柱圆底）+ 纵向渐变（自由端微亮、靠零轴为基色）
  - 淡网格：零轴上下各一条半程虚线（取色 chart_grid 令牌，弱于零轴线）
  - 悬浮高亮（柱体提亮 112%）+ 数值提示（QToolTip：类别：±金额 元）
  - 入场生长动画约 200ms（QVariantAnimation + OutCubic）；数据未变化时不重播，避免搜索逐键刷新闪烁；不可见（含测试场景）直接落定完整柱高
  - 内部新增 _color_grid（默认取 _LIGHT_COLORS["grid"]），apply_mode 随主题同步
- 测试：全量 pytest 真实执行 239 passed（tests/ui/test_bar_chart.py 零改动，冒烟断言全部通过）
- 视觉取证：docs/ui_v2_preview/phase5_dark.png、phase5_light.png（正负混合 + 跨年数据，独立临时数据库模拟）

## [未定版] - UI V2.0 阶段 4（分支 ui-v2）

表格与弹窗美化。信号、排序/分页/搜索/校验/保存逻辑零改动；无新增依赖。

- ui/main_window.py：记录表格开启斑马纹（setAlternatingRowColors，QSS 交替行底色阶段 1 已备）与行悬浮高亮（setMouseTracking + QSS item:hover）
- ui/record_dialog.py：「保存」按钮设为 accent 主操作样式；弹窗表单列间距接入间距令牌（SPACE_L）
- ui/theme.py：新增表格行悬浮底色规则；新增默认按钮（`:default`，弹窗/消息框确认键）强调色文字与描边——规则置于 [accent] 与 :disabled 之前，accent 主按钮与禁用态样式优先不受影响；消息框外观沿用阶段 1 全局 QSS
- 测试：全量 pytest 真实执行 239 passed（无测试改动）
- 视觉取证：docs/ui_v2_preview/phase4_dark.png、phase4_light.png、phase4_dialog_dark.png、phase4_dialog_light.png（独立临时数据库模拟数据）

## [未定版] - UI V2.0 阶段 3（分支 ui-v2）

统计卡与空状态改版。统计口径（STA-01 全局值）、刷新时机、空状态行为零改动；无新增依赖。

- ui/widgets.py（新增）：StatCard 统计卡组件——标题 + 大号数值（20px/600）；金额按盈亏着色（盈利红/亏损绿/零收益中性，色值随主题令牌）；金额「可见且变化」时做 180ms count-up（QVariantAnimation，无新依赖），窗口隐藏（含全部测试场景）时直接落定最终文本，保证文本随时可断言；笔数卡中性色无动画
- ui/main_window.py：四张统计卡换用 StatCard（total_profit_value 等值标签属性名保持不变）；累计收益为主卡；空状态新增副标题「点击下方按钮，记下第一笔转债卖出」（empty_title 文本不变）
- ui/theme.py：新增 statCard / statCardMain / statCardTitle / statCardValue 与 emptyTitle / emptyHint 样式节（主卡 = 纵向渐变微光底 + 强调色描边）
- 测试：新增 tests/unit/test_widgets.py 5 项（文本格式、盈亏着色双主题、笔数卡、隐藏即落定）；全量 pytest 真实执行 239 passed
- 视觉取证：docs/ui_v2_preview/phase3_dark.png、phase3_light.png、phase3_empty.png（独立临时数据库模拟数据）

## [未定版] - UI V2.0 阶段 2（分支 ui-v2）

侧边导航与顶部操作区改版。信号、快捷键、导航与筛选逻辑零改动；无新增依赖。

- ui/theme.py：新增侧边导航 `#navSidebar` 专属 QSS——选中项强调色 3px 左侧指示条 + 染色底 + 加粗，文字位置经 padding 补偿不偏移；通用 QListWidget 规则保持不变（不影响其他列表）
- ui/main_window.py：
  - 侧边导航设置 objectName（navSidebar），宽度 140 → 148
  - 「新增记录」与空状态「新增第一条记录」设为 accent 主按钮（复用阶段 1 备好的 `QPushButton[accent="true"]` 样式）
  - 总览页根布局边距/间距接入间距令牌（SPACE_L/SPACE_M），工具栏同组按钮间距收紧（SPACE_S）
- 测试：全量 pytest 真实执行 234 passed（无测试语义改动）
- 视觉取证：docs/ui_v2_preview/phase2_dark.png、phase2_light.png（独立临时数据库模拟数据）

## [未定版] - UI V2.0 阶段 0+1（分支 ui-v2）

视觉改版第一批：设计令牌与双主题 QSS 基座。业务规则、数据库结构、Excel 规则、备份恢复逻辑零改动；无新增第三方依赖。

- 阶段 0（基线与回退保障）：
  - 建立分支 ui-v2；全量 pytest 基线：230 passed（真实执行）
- 阶段 1（Design Tokens + 双主题 QSS + 字体排版）：
  - ui/tokens.py（新增）：Design Tokens 集中定义——深色=深海蓝黑背景+冰蓝紫强调，浅色=珍珠白背景+雾紫蓝强调；盈红/亏绿（中国金融习惯，浅深各调亮度保证对比度）、错误色、提醒色、表格网格线/选中色/斑马纹、图表色；字体（Microsoft YaHei UI）、字号、间距、圆角令牌。约定界面代码不再硬编码十六进制色值
  - ui/theme.py（重写）：浅/深两套完整定制 QSS 由令牌生成（浅色不再是 Qt 默认空样式），分节书写便于按节回退；覆盖输入控件、下拉弹层、微调框自绘箭头、按钮（含 accent 主按钮备用态）、表格、滚动条、导航列表、菜单/消息框/状态栏、日历弹层；新增 active_mode() 记录当前主题，chart_colors() 与 profit_color()/loss_color()/error_color()/warning_color()/error_qss() 主题感知取色接口
  - ui/bar_chart.py：新增 apply_mode()——盈红/亏绿柱、零轴线、标签色随主题切换；保留 set_label_color() 旧接口兼容
  - ui/main_window.py：主题切换改走 apply_mode() 并刷新收益列；单笔收益列按盈利红/亏损绿/零中性着色（仅显示层，收益计算与数据不变）
  - ui/record_dialog.py、ui/import_preview_dialog.py、ui/backup_page.py：硬编码错误色（#c62828 / rgb(200,0,0) / Qt red）与重复跳过琥珀色全部接入主题令牌
  - 测试：tests/unit/test_theme.py 更新（浅色现为完整 QSS、新增令牌/语义色/active_mode 断言）；tests/ui/test_main_window.py 主题断言改为双主题特征色判断。全量 pytest 真实执行：234 passed
  - 视觉取证：docs/ui_v2_preview/ 三张截图（浅/深总览 + 深色记录弹窗，独立临时数据库模拟数据）
- 已知问题：
  - QT_QPA_PLATFORM=offscreen 离屏渲染缺 CJK 字体（截图取证改用真实 Windows 平台）
  - QDateEdit 日历弹层星期表头颜色由 Qt 内部格式控制，深色模式对比度可能偏弱，后续阶段复核

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
