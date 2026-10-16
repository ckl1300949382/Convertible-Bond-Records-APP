# 变更日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。
程序版本采用 `MAJOR.MINOR.PATCH`，数据库 schema_version 独立递增（阶段 1 起）。

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
