"""sales 表仓储：参数化 SQL、明确事务边界（文档 §5.1/§5.2）。

按文档 §2.3：不对业务字段建立唯一约束，手工新增允许完全重复；
默认排序为最新日期在前，同日期按 id 降序（§3.3 稳定次序）。
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from decimal import Decimal

from bond_profit.domain.models import RecordQuery, SaleRecord
from bond_profit.domain.money import cents_to_yuan, yuan_to_cents

_SELECT_COLUMNS = (
    "id, bond_name, bond_code, sale_date, sale_price_cents, "
    "quantity, note, created_at, updated_at"
)
_INSERT_SQL = (
    "INSERT INTO sales "
    "(bond_name, bond_code, sale_date, sale_price_cents, quantity, note, "
    " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
_UPDATE_SQL = (
    "UPDATE sales SET bond_name = ?, bond_code = ?, sale_date = ?, "
    "sale_price_cents = ?, quantity = ?, note = ?, updated_at = ? "
    "WHERE id = ?"
)
# 排序白名单：只允许按这三列排序，防止 SQL 注入（§3.3 日期/价格/收益）。
# sale_price_cents 为每张单价（分），成本固定 100 元/张（§2.2），
# 收益分 = (单价分 − 10000) × 张数，SQL 内整数运算无精度问题。
_SORT_EXPRS = {
    "date": "sale_date",
    "price": "sale_price_cents",
    "profit": "((sale_price_cents - 10000) * quantity)",
}


class RepositoryError(Exception):
    """数据库操作失败。message 面向用户（中文），技术细节通过日志记录。"""


class SalesRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ---- 写入 -------------------------------------------------------------

    def add(self, record: SaleRecord) -> SaleRecord:
        """插入一条记录，返回带 id 与时间戳的新对象。

        允许业务字段完全相同的多条记录（§2.3）。
        """
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._conn:  # 事务：成功提交，异常自动回滚
                cursor = self._conn.execute(
                    _INSERT_SQL,
                    (
                        record.bond_name,
                        record.bond_code,
                        record.sale_date.isoformat(),
                        yuan_to_cents(record.sale_price),
                        record.quantity,
                        record.note,
                        now,
                        now,
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("数据库写入失败，记录未保存") from exc
        return SaleRecord(
            bond_name=record.bond_name,
            bond_code=record.bond_code,
            sale_date=record.sale_date,
            sale_price=record.sale_price,
            quantity=record.quantity,
            note=record.note,
            id=cursor.lastrowid,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def add_many(self, records: list[SaleRecord]) -> list[SaleRecord]:
        """单事务批量写入（§4.3 Excel 导入）：任一条失败全部回滚。"""
        if not records:
            return []
        now = datetime.now().isoformat(timespec="seconds")
        added: list[SaleRecord] = []
        try:
            with self._conn:  # 同一事务：异常自动回滚（XLS-05）
                for record in records:
                    cursor = self._conn.execute(
                        _INSERT_SQL,
                        (
                            record.bond_name,
                            record.bond_code,
                            record.sale_date.isoformat(),
                            yuan_to_cents(record.sale_price),
                            record.quantity,
                            record.note,
                            now,
                            now,
                        ),
                    )
                    added.append(
                        SaleRecord(
                            bond_name=record.bond_name,
                            bond_code=record.bond_code,
                            sale_date=record.sale_date,
                            sale_price=record.sale_price,
                            quantity=record.quantity,
                            note=record.note,
                            id=cursor.lastrowid,
                            created_at=datetime.fromisoformat(now),
                            updated_at=datetime.fromisoformat(now),
                        )
                    )
        except sqlite3.Error as exc:
            raise RepositoryError("数据库写入失败，本次导入未保存任何记录") from exc
        return added

    def update(self, record: SaleRecord) -> SaleRecord:
        """按 id 更新记录；记录不存在时抛出 RepositoryError。"""
        if record.id is None:
            raise RepositoryError("缺少记录 id，无法更新")
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._conn:
                cursor = self._conn.execute(
                    _UPDATE_SQL,
                    (
                        record.bond_name,
                        record.bond_code,
                        record.sale_date.isoformat(),
                        yuan_to_cents(record.sale_price),
                        record.quantity,
                        record.note,
                        now,
                        record.id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise RepositoryError("记录不存在或已被删除")
        except sqlite3.Error as exc:
            raise RepositoryError("数据库写入失败，修改未保存") from exc
        return SaleRecord(
            bond_name=record.bond_name,
            bond_code=record.bond_code,
            sale_date=record.sale_date,
            sale_price=record.sale_price,
            quantity=record.quantity,
            note=record.note,
            id=record.id,
            created_at=record.created_at,
            updated_at=datetime.fromisoformat(now),
        )

    def delete(self, record_id: int) -> None:
        """删除记录；记录不存在时抛出 RepositoryError。"""
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM sales WHERE id = ?", (record_id,)
                )
        except sqlite3.Error as exc:
            raise RepositoryError("数据库删除失败，记录未删除") from exc
        if cursor.rowcount == 0:
            raise RepositoryError("记录不存在或已被删除")

    # ---- 读取 -------------------------------------------------------------

    def get_by_id(self, record_id: int) -> SaleRecord | None:
        cursor = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM sales WHERE id = ?", (record_id,)
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_all(self) -> list[SaleRecord]:
        """全部记录，最新日期在前，同日期按 id 降序（§3.3）。"""
        cursor = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM sales "
            "ORDER BY sale_date DESC, id DESC"
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def count_filtered(self, query: RecordQuery) -> int:
        """符合搜索/筛选条件的记录总数（用于分页计算）。"""
        where, params = _build_where(query)
        cursor = self._conn.execute(f"SELECT COUNT(*) FROM sales {where}", params)
        return cursor.fetchone()[0]

    def list_page(
        self, query: RecordQuery, offset: int, limit: int
    ) -> list[SaleRecord]:
        """分页读取符合搜索/筛选条件的记录（§3.3 每页 20 条）。

        排序键走白名单；同排序键按 id 降序保证结果稳定（UI-01）。
        """
        where, params = _build_where(query)
        order_expr = _SORT_EXPRS.get(query.sort_key, "sale_date")
        direction = "DESC" if query.descending else "ASC"
        cursor = self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM sales {where} "
            f"ORDER BY {order_expr} {direction}, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def distinct_years(self) -> list[int]:
        """数据库中出现过的卖出年份，降序（用于年份筛选下拉）。"""
        cursor = self._conn.execute(
            "SELECT DISTINCT CAST(substr(sale_date, 1, 4) AS INTEGER) AS y "
            "FROM sales ORDER BY y DESC"
        )
        return [row[0] for row in cursor.fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]

    # ---- 内部 -------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: tuple) -> SaleRecord:
        return SaleRecord(
            id=row[0],
            bond_name=row[1],
            bond_code=row[2],
            sale_date=date.fromisoformat(row[3]),
            sale_price=cents_to_yuan(row[4]),
            quantity=row[5],
            note=row[6],
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
        )


def _build_where(query: RecordQuery) -> tuple[str, list]:
    """把搜索/筛选条件编译为 WHERE 子句与参数，全部走参数化绑定。"""
    clauses: list[str] = []
    params: list = []

    if query.keyword:
        # LIKE 通配符转义，避免用户输入 %/_ 被当成通配符
        escaped = (
            query.keyword.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        like = f"%{escaped}%"
        clauses.append(
            r"(bond_name LIKE ? ESCAPE '\' OR bond_code LIKE ? ESCAPE '\')"
        )
        params.extend([like, like])

    if query.year is not None:
        start_year = query.year
        start_month = query.month if query.month is not None else 1
        end_month = query.month if query.month is not None else 12
        last_day = calendar.monthrange(query.year, end_month)[1]
        clauses.append("sale_date >= ? AND sale_date <= ?")
        params.extend(
            [
                f"{start_year:04d}-{start_month:02d}-01",
                f"{query.year:04d}-{end_month:02d}-{last_day:02d}",
            ]
        )

    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params
