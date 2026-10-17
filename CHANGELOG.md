# 变更日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
程序版本采用 `MAJOR.MINOR.PATCH`，数据库 schema_version 独立递增（阶段 1 起）。

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
