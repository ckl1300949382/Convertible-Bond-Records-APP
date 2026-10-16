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
