"""销售记录服务：校验 → 事务写入的协调层。

UI 层只与本模块对话，不直接访问仓储；
数据库失败在此转为面向用户的中文提示并记录日志（文档 §5.2）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from bond_profit.domain.models import SaleRecord
from bond_profit.domain.validation import normalize, validate_record
from bond_profit.infrastructure.repository import RepositoryError, SalesRepository

logger = logging.getLogger(__name__)


@dataclass
class ServiceResult:
    ok: bool
    errors: list[str] = field(default_factory=list)  # 字段校验错误
    record: SaleRecord | None = None
    failure: str | None = None  # 数据库失败时的用户提示


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

    def list_records(self) -> list[SaleRecord]:
        return self._repository.list_all()

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
