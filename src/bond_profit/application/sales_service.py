"""销售记录服务：校验 → 事务写入的协调层。

UI 层只与本模块对话，不直接访问仓储；
数据库失败在此转为面向用户的中文提示并记录日志（文档 §5.2）。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal

from bond_profit.domain.models import RecordQuery, SaleRecord
from bond_profit.domain.statistics import (
    GlobalStatistics,
    global_statistics,
    monthly_profits,
    yearly_profits,
)
from bond_profit.domain.validation import normalize, validate_record
from bond_profit.infrastructure.repository import RepositoryError, SalesRepository

logger = logging.getLogger(__name__)


@dataclass
class ServiceResult:
    ok: bool
    errors: list[str] = field(default_factory=list)  # 字段校验错误
    record: SaleRecord | None = None
    failure: str | None = None  # 数据库失败时的用户提示


@dataclass
class PageResult:
    records: list[SaleRecord]
    total: int  # 符合条件的总数
    page: int  # 钳制后的实际页码（从 1 开始）


class SalesService:
    def __init__(self, repository: SalesRepository) -> None:
        self._repository = repository

    def create_record(self, record: SaleRecord) -> ServiceResult:
        """新增记录。校验失败或写入失败均不假装成功。"""
        return self._write(self._repository.add, record)

    def update_record(self, record: SaleRecord) -> ServiceResult:
        """更新记录。校验失败或写入失败均不假装成功。"""
        return self._write(self._repository.update, record)

    def delete_record(self, record_id: int) -> None:
        """删除记录；失败抛出 RepositoryError 由调用方提示。"""
        self._repository.delete(record_id)

    def add_many(self, records: list[SaleRecord]) -> list[SaleRecord]:
        """批量新增（§4.3 Excel 导入）：先标准化再单事务写入，全有或全无。"""
        return self._repository.add_many([normalize(r) for r in records])

    def list_records(self) -> list[SaleRecord]:
        return self._repository.list_all()

    def list_page(
        self, query: RecordQuery, page: int, page_size: int
    ) -> PageResult:
        """分页查询（§3.3）。页码超出范围时自动钳制，
        删除当前页最后一条后页码随之调整。"""
        total = self._repository.count_filtered(query)
        last_page = max(1, math.ceil(total / page_size))
        current = min(max(1, page), last_page)
        records = self._repository.list_page(
            query, offset=(current - 1) * page_size, limit=page_size
        )
        return PageResult(records=records, total=total, page=current)

    def list_filtered(self, query: RecordQuery) -> list[SaleRecord]:
        """筛选条件下的全部记录（§4.5 导出全集，不受分页限制）。"""
        return self._repository.list_filtered(query)

    def distinct_years(self) -> list[int]:
        return self._repository.distinct_years()

    def global_statistics(self) -> GlobalStatistics:
        """全局统计卡片（§3.2）：全量聚合，不经过搜索/筛选条件（STA-01）。"""
        return global_statistics(self._repository.list_all())

    def monthly_profits(self, year: int) -> list[Decimal]:
        """某年 1—12 月收益（§3.5），缺失月份为 0。"""
        return monthly_profits(self._repository.list_all(), year)

    def yearly_profits(self) -> list[tuple[int, Decimal]]:
        """各年份总收益（§3.5），年份升序。"""
        return yearly_profits(self._repository.list_all())

    # ---- 内部 -------------------------------------------------------------

    def _write(self, action, record: SaleRecord) -> ServiceResult:
        normalized = normalize(record)
        errors = validate_record(normalized)
        if errors:
            return ServiceResult(ok=False, errors=errors)
        try:
            saved = action(normalized)
        except RepositoryError as exc:
            logger.error("数据库写入失败：%s", exc, exc_info=True)
            return ServiceResult(ok=False, failure=str(exc))
        return ServiceResult(ok=True, record=saved)
