from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, conint
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Product, Trade, TradeDetail


router = APIRouter()


class PurchaseItem(BaseModel):
    product_code: str = Field(..., min_length=1)
    quantity: conint(gt=0)  # type: ignore[valid-type]
    unit_price: Optional[int] = Field(default=None, ge=0)


class PurchaseRequest(BaseModel):
    cashier_code: Optional[str] = None
    store_code: Optional[str] = None
    pos_id: Optional[str] = None
    items: List[PurchaseItem] = Field(default_factory=list)


class PurchaseResponse(BaseModel):
    id: int
    status: str
    success: bool
    subtotal: int
    total: int


@router.post("/purchase", response_model=PurchaseResponse)
def create_purchase(payload: PurchaseRequest, db: Session = Depends(get_db)) -> PurchaseResponse:
    """Persist trade and details. Totals computed as: subtotal=sum(unit_price*qty), tax=10% floor.
    Returns generated trade id and status.
    """
    if not payload.items:
        return PurchaseResponse(id=0, status="empty", success=False, subtotal=0, total=0)

    # Compute totals (unit_price fallback to product.price)
    subtotal = 0
    details: list[TradeDetail] = []
    for idx, it in enumerate(payload.items, start=1):
        prd = db.query(Product).filter(Product.code == it.product_code).first()
        unit_price = it.unit_price if it.unit_price is not None else (prd.price if prd else 0)
        subtotal += unit_price * int(it.quantity)
        details.append(
            TradeDetail(
                line_no=idx,
                prd_id=prd.id if prd else None,
                prd_code=it.product_code,
                prd_name=prd.name if prd else it.product_code,
                prd_price=unit_price,
                qty=int(it.quantity),
                tax_cd="10",  # 消費税区分 '10' 固定（Lv2）
            )
        )

    tax = subtotal // 10  # 10% floor
    total = subtotal + tax

    # Defaults: cashier_code -> '9999999999' if blank, store_code -> '30' fixed
    emp_cd = (payload.cashier_code or "").strip() or "9999999999"
    store_cd = (payload.store_code or "").strip() or "30"
    # POS機IDは 90 固定（モバイルレジ）
    pos_no = "90"

    trade = Trade(
        subtotal=subtotal,
        total=total,
        emp_cd=emp_cd,
        store_cd=store_cd,
        pos_no=pos_no,
    )
    db.add(trade)
    db.flush()  # get trade.id
    for d in details:
        d.trade_id = trade.id
        db.add(d)

    return PurchaseResponse(id=trade.id, status="accepted", success=True, subtotal=subtotal, total=total)
