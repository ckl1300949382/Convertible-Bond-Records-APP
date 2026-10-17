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

---

# 阶段 3 验收清单（版本 0.4.0）

范围：§4.1–4.5 Excel 模板/解析/去重/预览/导入事务/导出、§3.1 导航、§9 阶段 3 里程碑、§10.3 测试矩阵 XLS-01～10。

## 自动验证（Agent 已执行，174 passed in 5.44s）

| # | 验收项 | 对应测试 | 实际结果 | 是否通过 |
|---|---|---|---|---|
| E1 | XLS-01：六字段重复的两行 | test_xls01_in_file_duplicates_skip | 首行「可导入」，后行「重复跳过」，预计新增 1 笔 | 通过 |
| E2 | XLS-02：与数据库完全相同 | test_xls02_existing_db_duplicate_skips | 跳过且不计入净收益变化 | 通过 |
| E3 | XLS-03：空备注/空串/纯空格去重 | test_xls03_note_blank_variants_same_key | 备注空值统一后视为相同 | 通过 |
| E4 | XLS-04：任一行错误整批禁止 | test_xls04_any_error_blocks_commit、test_xls04_field_error_reasons | 逐行中文原因+真实 Excel 行号；commit_import 对 has_errors 抛「存在错误行」拒绝 | 通过 |
| E5 | XLS-05：数据库异常全部回滚 | test_xls05_failed_write_rolls_back_all（quantity=0 触发 CHECK） | RepositoryError 后库内无任何记录 | 通过 |
| E6 | XLS-06：列顺序打乱按列名匹配 | test_xls06_shuffled_column_order | 正确识别；缺必需列报中文错误（test_missing_required_column_raises） | 通过 |
| E7 | XLS-07：Excel 日期单元格与 YYYY-MM-DD 文本 | test_preview_valid_rows_both_date_forms | 均识别；完全空白行跳过且行号真实 | 通过 |
| E8 | XLS-08：数值单元格丢失前导零 | test_xls08_lost_leading_zero_rejected | 拒绝猜测补零，提示改为文本格式修正源文件 | 通过 |
| E9 | XLS-09：筛选导出全集跨页 | test_export_filtered_full_set、test_export_all_with_profit_column | 关键词全集不受分页限制；收益列正确、代码文本格式保留前导零 | 通过 |
| E10 | XLS-10：含亏损批次净收益 | test_xls10_loss_batch_net_profit | +300.00 −15.00 → 净收益变化 +285.00，仅计新增 | 通过 |
| E11 | 导入事务全有或全无 + 提交前重查去重 | test_commit_success、test_commit_rechecks_duplicates_after_preview | 单事务提交；预览后库内新增同键记录仍正确跳过 | 通过 |
| E12 | 导入预览 UI（§4.4） | test_import_preview_dialog 4 项、test_data_management 7 项 | 统计行/逐行状态/错误行禁用「开始导入」/提交成功与失败保持打开均符合；导航「总览/数据管理」切换正常 | 通过 |

## 人工抽检（openpyxl 与真实 Excel 兼容性，建议复核）

| # | 操作步骤 | 预期结果 | 备注 |
|---|---|---|---|
| F1 | 数据管理页下载模板 → 用 Excel/WPS 打开 → 手工填写含代码 012345 的行 → 导入 | 模板含「填写说明」页；代码前导零保留；预览显示可导入 | 文件对话框与真实 Excel 交互留人工 |
| F2 | 导出全部记录 → 用 Excel 打开 | 七列（六字段+收益）；代码列文本；日期/金额显示格式正确 | 视觉格式人工确认 |
| F3 | 导入成功后查看总览 | 卡片/图表/表格自动刷新 | 信号已自动化验证，视觉效果人工确认 |
| F4 | 预览对话框观察颜色 | 错误行红色、重复跳过琥珀色、错误行「开始导入」置灰 | 颜色人工确认 |

## 已知问题

- 导出收益列为 Excel 数值（Decimal→float 序列化，仅展示；两位小数显示格式），导入时不读取该列。
- 预览对话框业务列以文本单元格展示，不支持行内排序/筛选（文档未要求）。
- 模板预设前 200 行代码列文本格式；超出后需用户自行设置单元格格式为文本。
- 导入文件级错误（打不开/缺列）与错误行的原因展示均为中文，技术细节仅写日志。

# 阶段 4 验收清单（版本 0.5.0）

范围：§5.3 版本迁移、§6.1–6.5 备份/恢复/异常处理、§9 阶段 4 里程碑、§10.4 测试矩阵 BAK-01～06 / RES-01～03 / MIG-01～03。

## 自动验证（Agent 已执行，224 passed in 7.10s）

| # | 验收项 | 对应测试 | 实际结果 | 是否通过 |
|---|---|---|---|---|
| A1 | BAK-01：当天首次成功后不再更新自动备份 | test_first_run_backs_up_once_per_day | 当天第二次检查返回 None、仍 1 份 | 通过 |
| A2 | BAK-02：跨天保持运行且有变更 → 新备份 | test_cross_day_backup_after_changes | 次日检查生成第 2 份 | 通过 |
| A3 | BAK-03：备份失败不计当天成功次数、可重试 | test_failed_backup_keeps_state_and_retries、test_auto_check_failure_shows_status_message | 状态不变（未记日期/仍脏）；重试成功计数；UI 状态栏提示不阻断 | 通过 |
| A4 | BAK-04：第 31 份成功后只清理最旧自动备份 | test_prune_removes_only_oldest、test_auto_backup_keeps_30_after_31st | 显式 mtime 确定性删除最旧一份（含 manifest）；31→30 且最新存活 | 通过 |
| A5 | BAK-05：备份失败不删除旧备份、无临时残留 | test_failed_backup_keeps_old_backups | 目录内容与失败前一致，无 .tmp 文件 | 通过 |
| A6 | BAK-06：手动/升级/恢复保护备份不参与自动清理 | test_protected_and_manual_never_pruned | 各 35 份无一被删 | 通过 |
| A7 | 备份快照一致性与 manifest | test_backup_creates_verified_snapshot、test_manifest_metadata | 快照内容与源库一致；元数据（类型/记录数/库版本）正确 | 通过 |
| A8 | 列表以实际文件检查为准（§6.3） | test_list_reads_actual_file_over_manifest、test_corrupt_file_reported_unverified | manifest 记录数被篡改仍显示实际值；损坏文件标记「未通过」 | 通过 |
| A9 | RES-01：损坏备份拒绝恢复 | test_restore_rejects_corrupt_backup | RestoreError；原数据不变；未创建保护备份（校验先行） | 通过 |
| A10 | RES-02：过新版本备份拒绝恢复 | test_restore_rejects_newer_version_backup | 提示先升级程序；原数据不变 | 通过 |
| A11 | RES-03：恢复中断原数据可恢复、保护副本存在 | test_failed_restore_keeps_protection_and_live_data | 保护副本 1 份；当前数据未改动；修复后重试成功 | 通过 |
| A12 | 恢复成功替换数据 + 三重校验 | test_restore_replaces_active_data | 记录数、收益汇总（20000 分）与备份一致后写回；列表/表格/状态同步 | 通过 |
| A13 | MIG-01：旧版数据库升级成功、记录不丢 | test_old_db_migrates_successfully | user_version 1→2；2 条记录保留；新列生效 | 通过 |
| A14 | MIG-02：迁移失败停止升级、原数据保留 | test_migration_failure_stops_and_preserves_data | 版本号不变、记录保留、成功执行过的 DDL 已整体回滚 | 通过 |
| A15 | MIG-03：旧程序打开过新数据库拒绝写入 | test_too_new_db_refused_without_writes、app 预检分支 | DatabaseTooNewError；数据与版本号不变；任何写操作在版本检查之后 | 通过 |
| A16 | 损坏库启动保护（§6.5） | test_corrupt_db_refuses_to_open_and_file_preserved | 拒绝打开；文件字节级未改动；不静默建空库 | 通过 |
| A17 | 自动备份策略门控 | test_no_backup_across_days_without_changes、test_manual_backup_clears_dirty、test_state_store_corrupt_falls_back_to_safe_defaults | 无变更跨天不备份；手动备份后清脏；状态文件损坏按安全默认 | 通过 |
| A18 | 备份 UI（§6 / §9 第 9 项） | tests/ui/test_backup_page.py 14 项 | 手动备份全流程、列表列与类型映射、恢复确认 Yes/No、恢复成功后总览刷新、30 分钟定时器启动 | 通过 |

## 人工抽检（真实环境行为，建议复核）

| # | 操作步骤 | 预期结果 | 备注 |
|---|---|---|---|
| G1 | 备份与恢复页 → 手动备份到其他磁盘目录 | 目录中出现 app_*.db + manifest；列表与提示正常 | 文件对话框交互留人工 |
| G2 | 录入几条记录 → 重启程序 | 启动时自动备份当天一份；当天再改再重启不重复生成 | 依赖真实 %LOCALAPPDATA% 目录 |
| G3 | 备份列表选择一份旧备份 → 恢复 → 查看总览 | 确认对话框含替换警告；恢复后表格/卡片/图表刷新为备份时点数据 | 恢复目标建议用测试数据 |
| G4 | 状态栏观察自动备份提示 | 备份完成/失败均有 10 秒提示，不影响录入操作 | BAK-03 视觉确认 |

## 已知问题

- 自动备份仅在启动时与每 30 分钟检查一次（§6.1 建议 30 分钟）；数据变更后到下一次检查之间存在无备份窗口，属文档允许范围。
- 手动备份文件存放在用户自选目录，不出现在「备份与恢复」列表中（已批准默认决策②）；如需恢复需将该文件放入 backups/auto 或 backups/protected 目录，或按文档 §6.4 由用户自选路径导入（当前版本通过放置目录实现）。
- 迁移注册表当前为空（schema_version=1 为唯一版本）；迁移路径由测试注入假步骤验证（MIG-01/02），真实迁移将在未来版本发布时登记。
- 备份/恢复的完整性校验使用 SQLite integrity_check；极端磁盘故障（备份文件与源库同时损坏）不在防护范围内，请按文档建议将手动备份存放到其他磁盘。

# 阶段 5 验收清单（版本 1.0.0）

范围：§9 阶段 5 里程碑、§10.4 PKG-01～03、§10.5 验收证据、§11 发布规范、§12 用户操作与人工验收清单。

## 自动验证（Agent 已执行）

| # | 验收项 | 对应测试/脚本 | 实际结果 | 是否通过 |
|---|---|---|---|---|
| A1 | 全套回归（§10.5 测试报告） | `.venv\Scripts\python.exe -m pytest -q`（Windows 11，Python 3.12.10，PySide6 6.12） | 230 passed，0 failed（批次 19 定版后复跑见下） | 通过 |
| A2 | PKG-01 本机部分：打包后双击启动 | scripts/build_release.ps1 冒烟 | exe 启动 → 6 秒存活 → 正常关闭；期间自动初始化数据目录/日志/启动备份 | 通过 |
| A3 | 发布包内容（§11.1） | 构建脚本拷入 | dist/可转债收益记录/ 含 exe、_internal、版本说明.txt、使用说明.txt；压缩为 dist/可转债收益记录_v1.0.0_win64.zip | 通过 |
| A4 | 全局异常兜底 | tests/unit/test_error_hook.py 4 项 | 未捕获异常写 CRITICAL 日志 + 中文提示；提示失败不影响兜底；可恢复原钩子 | 通过 |
| A5 | 日志复制入口 | tests/ui/test_main_window.py 2 项 | 「打开日志」打开日志文件夹；无日志目录时友好提示不崩溃 | 通过 |
| A6 | 中文文案巡检 | 全 UI 模块英文残留扫描 | 窗口标题/按钮/占位符/弹窗零英文残留 | 通过 |
| A7 | 版本与标题联动 | main_window 标题动态引用 `bond_profit.__version__` | 1.0.0 定版后窗口标题自动显示 v1.0.0 | 通过 |

## 人工验收清单（§12 逐项展开，交付时复核）

| # | 操作步骤 | 预期结果 | 实际结果 | 是否通过 | 备注 |
|---|---|---|---|---|---|
| H1 | 在干净目录首次启动程序 | 空白欢迎状态、默认主题跟随系统、新增入口可见 | 待人工 | 待定 | 对应阶段 1 清单 S1；测试覆盖 tests/ui/test_main_window.py 空状态 |
| H2 | 新增记录：填代码、名称、日期、价格、数量并保存 | 表单实时显示自动收益；保存后列表与统计刷新 | 待人工 | 待定 | tests/ui/test_record_dialog.py、test_main_window.py 已覆盖逻辑 |
| H3 | 手动新增完全相同的记录 | 两条均保留（允许重复） | 待人工 | 待定 | tests 验证 repository 不去重 |
| H4 | 编辑记录的日期、价格、数量 | 对应统计（卡片/图表）随之变化 | 待人工 | 待定 | tests/ui/test_main_window.py 编辑联动 |
| H5 | 删除：先点取消、再确认删除 | 取消不变；确认后列表与统计同步减少 | 待人工 | 待定 | REC-03，test_main_window.py 覆盖两分支 |
| H6 | 名称/代码搜索、年月筛选、各排序切换、翻页 | 结果正确；每页 20 条 | 待人工 | 待定 | tests/unit/test_repository.py 分页/筛选/排序 |
| H7 | 图表切换年份、观察空月份、负收益柱 | 切换正常、空月无柱、负收益柱向下（红） | 待人工 | 待定 | tests/ui/test_bar_chart.py 覆盖正负着色 |
| H8 | 下载模板→填入合法与非法行→导入预览→导出筛选结果 | 非法行阻止整批导入；预览逐行显示原因；导出含收益列 | 待人工 | 待定 | XLS-01～10 自动验证见阶段 3 清单 A1～A12 |
| H9 | 手动备份→查看自动备份列表→选备份恢复并核对统计 | 备份/恢复成功；恢复后统计与备份时点一致 | 待人工 | 待定 | BAK/RES 自动验证见阶段 4 清单 A1～A18 |
| H10 | 切换主题并重启程序；检查窗口尺寸与排序偏好 | 主题、窗口状态、排序被记住；搜索/筛选不被记住 | 待人工 | 待定 | tests/ui/test_prefs.py 覆盖偏好读写 |
| H11 | 依次按 Ctrl+N / Ctrl+S / Ctrl+F / Esc | 分别触发新增、保存当前编辑、定位搜索框、关闭弹窗 | 待人工 | 待定 | QShortcut 对合成键事件不响应为已知限制，测试用 emit 接线验证 |
| H12 | 发布：无 Python 的 Windows 11、断网运行；从新版目录沿用旧数据 | 离线全功能可用；旧数据自动沿用；版本过新时拒绝并提示升级 | 待人工 | 待定 | 本机冒烟已通过（A2）；干净机验证需用户在目标机器执行 |

## 已知问题

- 测试环境限制（非产品缺陷）：QShortcut 与 QTableWidget 双击对 pytest 合成键事件不响应，测试以信号 emit 接线验证，人工按 H11 抽检。
- 自动备份每天最多一份、每 30 分钟检查一次；数据变更到下次检查之间存在无备份窗口（文档 §6.1 允许）。
- 手动备份文件存放于用户自选目录，不出现在备份列表（已批准默认决策②）。
- 打包冒烟会使用真实 %LOCALAPPDATA% 数据目录：冒烟期间可能触发一次真实的启动自动备份，属预期行为、无副作用。
- 无应用图标（文档未要求）；后续版本可补充 .ico。


