from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column("PRD_ID", Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column("CODE", String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column("NAME", String(255))
    price: Mapped[int] = mapped_column("PRICE", Integer, default=0)

    __table_args__ = (
        # 価格は0以上
        CheckConstraint("PRICE >= 0", name="ck_products_price_nonneg"),
        # CODEの長さ（SQLiteでも動く簡易チェック）。
        # 正確なフォーマット（EAN-13/英数字）はアプリ側バリデーションで保証。
        CheckConstraint("length(CODE) >= 1 AND length(CODE) <= 64", name="ck_products_code_len"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column("TRD_ID", Integer, primary_key=True, autoincrement=True)
    datetime: Mapped[datetime] = mapped_column("DATETIME", DateTime, default=datetime.utcnow)
    emp_cd: Mapped[str | None] = mapped_column("EMP_CD", String(32), nullable=True)
    store_cd: Mapped[str | None] = mapped_column("STORE_CD", String(32), nullable=True)
    pos_no: Mapped[str | None] = mapped_column("POS_NO", String(32), nullable=True)
    subtotal: Mapped[int] = mapped_column("TTL_AMT_EX_TAX", Integer, default=0)
    total: Mapped[int] = mapped_column("TOTAL_AMT", Integer, default=0)

    details: Mapped[list[TradeDetail]] = relationship(back_populates="trade", cascade="all, delete-orphan")


class TradeDetail(Base):
    __tablename__ = "trade_details"

    id: Mapped[int] = mapped_column("DTL_ID", Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column("TRD_ID", ForeignKey("trades.TRD_ID"))
    # 取引ごと採番（1〜）。TRD_ID + DTL_NO の複合一意
    line_no: Mapped[int] = mapped_column("DTL_NO", Integer, default=1)
    prd_id: Mapped[int | None] = mapped_column("PRD_ID", Integer, nullable=True)
    prd_code: Mapped[str] = mapped_column("PRD_CODE", String(64))
    prd_name: Mapped[str] = mapped_column("PRD_NAME", String(255))
    prd_price: Mapped[int] = mapped_column("PRD_PRICE", Integer)
    tax_cd: Mapped[str | None] = mapped_column("TAX_CD", String(8), nullable=True)
    qty: Mapped[int] = mapped_column("QTY", Integer, default=1)

    trade: Mapped[Trade] = relationship(back_populates="details")

    __table_args__ = (UniqueConstraint("TRD_ID", "DTL_NO", name="uq_trade_detail_per_trade"),)
