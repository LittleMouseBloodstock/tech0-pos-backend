from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, conint
from fastapi import Body
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


@router.get("/purchase/ping")
def ping() -> dict:
    return {"ok": True}

@router.post("/purchase")
def create_purchase(payload: dict = Body(...), db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    import traceback
    try:
        items = payload.get("items") or []
        if not items:
            return PurchaseResponse(id=0, status="empty", success=False, subtotal=0, total=0)

        subtotal = 0
        details: list[TradeDetail] = []
        for idx, it in enumerate(items, start=1):
            code = str(it.get("product_code") or "").strip()
            qty = int(it.get("quantity") or 0)
            unit_price = it.get("unit_price")
            prd = db.query(Product).filter(Product.code == code).first()
            price = int(unit_price) if unit_price is not None else (int(prd.price) if prd else 0)
            subtotal += price * qty
            details.append(
                TradeDetail(
                    line_no=idx,
                    prd_id=prd.id if prd else None,
                    prd_code=code,
                    prd_name=prd.name if prd else code,
                    prd_price=price,
                    qty=qty,
                    tax_cd="10",
                )
            )

        tax = subtotal // 10
        total = subtotal + tax

        emp_cd = (str(payload.get("cashier_code") or "").strip() or "9999999999")
        store_cd = (str(payload.get("store_code") or "").strip() or "30")
        pos_no = (str(payload.get("pos_id") or "").strip() or "90")

        trade = Trade(
            subtotal=subtotal,
            total=total,
            emp_cd=emp_cd,
            store_cd=store_cd,
            pos_no=pos_no,
        )
        db.add(trade)
        db.flush()

        for d in details:
            d.trade_id = trade.id
            db.add(d)

        # Try commit here to surface DB errors inside this handler
        try:
            db.commit()
        except Exception as ce:
            tb = traceback.format_exc()
            try:
                with open("purchase_error.log", "a", encoding="utf-8") as fp:
                    fp.write(tb + "\n")
            except Exception:
                pass
            return JSONResponse({"error": str(ce)}, status_code=500)

        return PurchaseResponse(id=trade.id, status="accepted", success=True, subtotal=subtotal, total=total)
    except Exception as e:
        tb = traceback.format_exc()
        try:
            with open("purchase_error.log", "a", encoding="utf-8") as fp:
                fp.write(tb + "\n")
        except Exception:
            pass
        return JSONResponse({"error": str(e)}, status_code=500)
