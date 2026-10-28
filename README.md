# 可转债收益记录 App

个人使用的可转债打新卖出收益记录桌面软件。准确录入、编辑、查询、统计、导入导出和备份交易记录。

- **技术栈**：Python 3.12 + PySide6 + SQLite
- **平台**：Windows 11 本地离线运行，绿色版发布
- **需求基线**：[可转债收益记录App_V1.6_完整工程开发文档.md](可转债收益记录App_V1.6_完整工程开发文档.md)

## 当前状态

程序版本 **1.0.0**，数据库 `schema_version = 1`。阶段 0—5 全部完成，已产出 Windows 绿色版发布包。

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 0 | 工程骨架、最小窗口、日志、测试、打包 | 已完成 |
| 阶段 1 | 记录核心与持久化 | 已完成 |
| 阶段 2 | 首页与统计交互 | 已完成 |
| 阶段 3 | Excel 导入导出 | 已完成 |
| 阶段 4 | 备份恢复与版本迁移 | 已完成 |
| 阶段 5 | Windows 发布与综合验收 | 已完成 |

> 进度与逐批次变更以 [CHANGELOG.md](CHANGELOG.md) 为准；模块职责与关键设计决策见 [ARCHITECTURE.md](ARCHITECTURE.md)；验收记录见 [docs/ACCEPTANCE_CHECKLIST.md](docs/ACCEPTANCE_CHECKLIST.md)。

## 开发环境搭建

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

## 常用命令

```powershell
# 开发运行
.venv\Scripts\python -m bond_profit

# 运行测试
.venv\Scripts\python -m pytest -v

# 打包正式绿色版（产物 dist\可转债收益记录\ 与 dist\可转债收益记录_v{版本}_win64.zip）
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

> 打包只保留 `scripts/build_release.ps1` 一套。阶段 0 的早期脚本 `build_windows.py` 已删除（其产物 `dist/BondProfit/` 作废）。

## 数据与日志位置

- 日志：`%LOCALAPPDATA%\ConvertibleBondProfit\logs\app.log`（滚动保留 5 份）
- 数据库（阶段 1 起）：`%LOCALAPPDATA%\ConvertibleBondProfit\data\app.db`
- 上述目录均不在仓库内，且已被 `.gitignore` 排除（数据库/备份/日志不入 Git）
