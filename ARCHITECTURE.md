# 架构说明

对应需求文档 §7「推荐架构与工程目录」。分层职责，UI 与业务分离。

## 分层职责

| 层 | 位置 | 职责 | 禁止 |
|---|---|---|---|
| presentation/UI | `src/bond_profit/ui/` | 窗口、弹窗、表格模型、图表、主题 | 直接拼 SQL、业务计算 |
| application/services | `src/bond_profit/application/`（阶段 1 起） | 协调新增编辑、导入、恢复、统计刷新；定义事务边界 | 依赖具体 GUI 控件 |
| domain | `src/bond_profit/domain/`（阶段 1 起） | 记录模型、字段校验、金额计算、去重键、统计口径 | 依赖 GUI、数据库 |
| infrastructure/persistence | `src/bond_profit/infrastructure/` | SQLite 仓储、迁移、备份、设置、日志 | — |
| infrastructure/excel | `src/bond_profit/excel/`（阶段 3 起） | 模板、解析、预览、导入/导出适配 | — |

## 依赖方向

```
ui ──▶ application ──▶ domain
              │             ▲
              ▼             │
        infrastructure ◀────┘（domain 不反向依赖 infrastructure）
```

## 现有模块

- `app.py`：QApplication 装配与启动入口，仅装配不含业务
- `infrastructure/logging.py`：RotatingFileHandler 日志，目录可注入（测试用临时目录）
- `ui/main_window.py`：最小主窗口

## 关键设计决策

1. **金额精度**（阶段 1 实现）：数据库存定点整数分（`sale_price_cents`），业务层用 `Decimal`，禁止二进制浮点计算金钱。
2. **日志目录可注入**：`setup_logging(log_dir=None)` 默认写 `%LOCALAPPDATA%/ConvertibleBondProfit/logs/`，测试传 `tmp_path` 隔离，满足测试不碰真实数据红线。
3. **src 布局**：源码在 `src/`，通过 `pip install -e .` 可编辑安装，`python -m bond_profit` 运行。
4. **打包**：PyInstaller onedir + windowed，spec 与中间产物放 `build/`（不入 Git）。

## 数据库（阶段 1 起）

- 位置：`%LOCALAPPDATA%/ConvertibleBondProfit/data/app.db`
- 版本管理：`PRAGMA user_version`，迁移前强制保护备份
