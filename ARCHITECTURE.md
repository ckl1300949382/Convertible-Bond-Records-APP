# 架构说明

对应需求文档 §7「推荐架构与工程目录」。分层职责，UI 与业务分离。

## 分层职责

| 层 | 位置 | 职责 | 禁止 |
|---|---|---|---|
| presentation/UI | `src/bond_profit/ui/` | 窗口、弹窗、表格模型、图表、主题 | 直接拼 SQL、业务计算 |
| application/services | `src/bond_profit/application/`（阶段 1 起） | 协调新增编辑、导入、恢复、统计刷新；定义事务边界 | 依赖具体 GUI 控件 |
| domain | `src/bond_profit/domain/`（阶段 1 起） | 记录模型、字段校验、金额计算、去重键、统计口径 | 依赖 GUI、数据库 |
| infrastructure/persistence | `src/bond_profit/infrastructure/` | SQLite 仓储、迁移、备份、设置、日志 | — |
| application/excel | `src/bond_profit/application/excel_service.py`（阶段 3 起） | Excel 模板、解析校验、去重、预览、导入事务、导出（openpyxl） | 依赖 GUI 控件 |

## 依赖方向

```
ui ──▶ application ──▶ domain
              │             ▲
              ▼             │
        infrastructure ◀────┘（domain 不反向依赖 infrastructure）
```

## 现有模块

- `app.py`：装配入口 + 单实例控制（QLocalServer/QLocalSocket，§3.6）
- `application/sales_service.py`：校验→事务写入协调层，UI 唯一入口；数据库失败转中文提示并记日志；分页查询（页码钳制）、筛选全集 list_filtered（§4.5 导出）与统计聚合透传；add_many 批量写入；成功写入后触发 on_change 回调（阶段 4 供备份脏标记）
- `application/excel_service.py`：官方模板生成（六列+说明页，代码列文本格式）；preview_import 逐行校验（真实 Excel 行号、中文原因、前导零拒绝猜测补零）+ 标准化六字段去重键；commit_import 存在错误整批拒绝、提交前重查去重；export_records（六业务字段+收益列）
- `application/backup_service.py`：自动备份策略（当天一次/脏标记/失败可重试）、手动备份（成功后清脏）、restore_from_backup 恢复编排（校验→保护备份→临时恢复→按需迁移→三重比对→官方 API 写回活动连接）、list_backups
- `domain/`：models（SaleRecord、RecordQuery）、validation（7 项校验+标准化）、calculations（收益+格式化）、money（元↔分）、statistics（全局卡片/月度/年度聚合，纯函数 Decimal）
- `infrastructure/database.py`：SQLite 连接、建表、user_version=1、路径可注入；启动预检 inspect_database（只读完整性+版本识别）；DatabaseCorruptError（损坏拒绝、保留原文件）、DatabaseTooNewError（MIG-03）、MIGRATIONS 逐版本迁移注册表（显式 BEGIN，失败整体回滚）
- `infrastructure/backup.py`：备份核心——官方备份 API 快照→临时文件→校验→原子发布；manifest 元数据（读取以实际文件检查为准）；保留清理仅 auto 目录（成功落盘后删最旧）；backup_dirs 标准目录布局
- `infrastructure/backup_state.py`：state.json 持久化脏标记与最近自动备份日期；缺失/损坏按安全默认（视为有变更）
- `infrastructure/repository.py`：sales 表 CRUD、分页查询（关键词转义/年月筛选/排序白名单）、list_filtered 全集、distinct_years、add_many 单事务批量写入（失败全回滚）、参数化 SQL、事务边界、允许重复录入
- `infrastructure/logging.py`：RotatingFileHandler 日志，目录可注入（测试用临时目录）
- `ui/main_window.py`：左侧导航（总览/数据管理/备份与恢复）+ 页面栈、统计卡片、月度/年度图表、记录表格（搜索/筛选/排序/分页）、空状态、主题与窗口状态记忆、Ctrl+N/Ctrl+F；筛选导出槽 `_on_export_filtered`；30 分钟 QTimer 自动备份检查（失败状态栏提示不阻断）；恢复成功后 refresh_records 同步刷新
- `ui/data_management.py`：数据管理页——模板下载、导入入口（ImportPreviewDialog 确认后发 import_completed 驱动总览刷新）、导出全部/筛选（筛选经 export_filtered_requested 信号由主窗口提供查询条件）
- `ui/import_preview_dialog.py`：导入预览（统计行、逐行状态表错误红/重复琥珀、错误行禁用导入、提交结果展示）
- `ui/backup_page.py`：备份与恢复页——手动备份、备份列表（时间/类型/记录数/库版本/验证状态）、恢复确认（数据替换警告）、立即检查/刷新；按钮仅发射信号由主窗口槽内调服务
- `ui/record_dialog.py`：新增/编辑弹窗（校验提示、失败保留输入、Esc 确认放弃、Ctrl+S）
- `ui/bar_chart.py`：自绘柱状图（盈红/亏绿/零中性、数值带正负号、负值向零轴下方）
- `ui/theme.py`：Windows 主题检测 + 深色 QSS 调色板
- `ui/prefs.py`：QSettings 偏好读写（主题/窗口几何/排序；不记筛选），ini 路径可注入

## 关键设计决策

1. **金额精度**：数据库存定点整数分（`sale_price_cents`），业务层用 `Decimal`（`domain/money.py` 转换），禁止二进制浮点计算金钱。
2. **重复录入**（§2.3）：不对业务字段建唯一约束，两条完全相同记录均可保存；数据库 CHECK 约束与应用层校验互补兜底。
3. **日志目录可注入**：`setup_logging(log_dir=None)`；测试传 `tmp_path` 隔离。
4. **数据库路径可注入**：`connect(db_path=None)` 默认 `%LOCALAPPDATA%/ConvertibleBondProfit/data/app.db`；测试全部用临时路径。
5. **src 布局**：源码在 `src/`，`pip install -e .` 可编辑安装，`python -m bond_profit` 运行。
6. **打包**：PyInstaller onedir + windowed，spec 与中间产物放 `build/`（不入 Git）。
7. **Excel 去重键**（§4.3）：标准化后「名称/代码/日期/价格分/数量/备注」六字段元组；备注空单元格、空串、纯空格统一为空；仅约束导入，手工新增仍允许重复（§2.3）。
8. **导入事务**（§4.3）：先全文件解析校验，存在任一错误整批拒绝；提交前重新检查去重；`repository.add_many` 单事务写入，任一条失败全部回滚。
9. **导出收益列**：由软件按 §2.2 计算写入，仅展示用；导入不读取收益列（不可信来源）。
10. **UI 组件间传参**：子组件不持有主窗口绑定方法引用（循环引用会引发对象生命周期问题）；跨组件回调一律用 Qt 信号，由主窗口槽内即时提供数据（如筛选导出条件）。
11. **备份一致性**（§6.1–6.3）：快照用 SQLite 官方备份 API（不直接复制运行中的库文件）；临时文件校验通过后同目录原子发布；读取列表以实际文件检查为准（manifest 仅辅助）；保留清理只在 auto 目录、且新备份成功落盘后才删最旧（失败宁可多留不误删）。
12. **恢复安全**（§6.4）：校验（损坏/过新拒绝）→ 恢复前保护备份 → 独立临时位置恢复 → 按需迁移 → 完整性/记录数/收益汇总比对 → 官方备份 API 写回活动连接（SQLite 事务保证，中断自动回滚）；任何失败不覆盖当前有效数据库。恢复成功后置脏并记录当日已备份（次日生成新自动备份）。
13. **版本迁移**（§5.3）：MIGRATIONS 注册表逐版本迁移，显式 BEGIN 事务（Python sqlite3 隐式事务只覆盖 DML，DDL 自动提交，不显式开事务无法整体回滚）；升级前先创建并验证保护备份；旧程序遇到新库拒绝写入（MIG-03），任何写操作都在版本检查之后。
14. **脏标记持久化**：state.json 记录最近自动备份日期与脏标记，缺失/损坏按安全默认（视为有变更，宁可多备不漏备）；手动备份成功清脏，恢复成功置脏。
