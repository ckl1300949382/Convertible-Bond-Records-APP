# 可转债收益记录 App

个人使用的可转债打新卖出收益记录桌面软件。准确录入、编辑、查询、统计、导入导出和备份交易记录。

- **技术栈**：Python 3.12 + PySide6 + SQLite
- **平台**：Windows 11 本地离线运行，绿色版发布
- **需求基线**：[可转债收益记录App_V1.6_完整工程开发文档.md](可转债收益记录App_V1.6_完整工程开发文档.md)

## 当前状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 0 | 工程骨架、最小窗口、日志、测试、打包 | 进行中 |
| 阶段 1 | 记录核心与持久化 | 未开始 |
| 阶段 2 | 首页与统计交互 | 未开始 |
| 阶段 3 | Excel 导入导出 | 未开始 |
| 阶段 4 | 备份恢复与迁移 | 未开始 |
| 阶段 5 | Windows 发布与综合验收 | 未开始 |

## 开发环境搭建

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

## 常用命令

```powershell
# 开发运行（最小窗口）
.venv\Scripts\python -m bond_profit

# 运行测试
.venv\Scripts\python -m pytest -v

# 打包绿色版（产物 dist/BondProfit/BondProfit.exe）
.venv\Scripts\python scripts\build_windows.py
```

## 数据与日志位置

- 日志：`%LOCALAPPDATA%\ConvertibleBondProfit\logs\app.log`（滚动保留 5 份）
- 数据库（阶段 1 起）：`%LOCALAPPDATA%\ConvertibleBondProfit\data\app.db`
- 上述目录均不在仓库内，且已被 `.gitignore` 排除（数据库/备份/日志不入 Git）
