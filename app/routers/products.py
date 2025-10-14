from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Product


router = APIRouter()


@router.get("/products")
def get_products(
    code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return product matched by code (robust to UPC/EAN variants).
    - Tries exact match first.
    - If 12-digit, also tries '0' + code (UPC-A -> EAN-13 表現)。
    - If 13-digit and startswith '0', also tries without leading '0'.
    Response: { items: [{ code, name, price, prdId }]}.
    """
    if not code:
        return {"items": []}

    q = db.query(Product)
    p = q.filter(Product.code == code).first()

    if not p:
        digits = (code or "").strip().replace(" ", "")
        if digits.isdigit():
            if len(digits) == 12:
                alt = "0" + digits
                p = q.filter(Product.code == alt).first()
            elif len(digits) == 13 and digits.startswith("0"):
                alt = digits[1:]
                p = q.filter(Product.code == alt).first()

    if not p:
        return {"items": []}
    return {"items": [{"code": p.code, "name": p.name, "price": p.price, "prdId": p.id}]}


@router.post("/products/dev-seed")
def dev_seed(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """DEV ONLY: insert a sample product if table is empty.
    Returns count of products after seeding.
    """
    if db.query(Product).count() == 0:
        db.add_all(
            [
                Product(code="4901234567894", name="サンプルA", price=150),
                Product(code="4900000000001", name="サンプルB", price=300),
            ]
        )
    return {"count": db.query(Product).count()}


@router.post("/products/bulk")
def bulk_upsert(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Upsert products from JSON: { items: [{ code, name, price }] }.
    Returns { inserted: n, updated: m, count: total }.
    """
    items = payload.get("items") or []
    ins = upd = 0
    for it in items:
        code = str(it.get("code") or "").strip()
        if not code:
            continue
        name = str(it.get("name") or "")
        price = int(it.get("price") or 0)
        p = db.query(Product).filter(Product.code == code).first()
        if p:
            p.name = name or p.name
            p.price = price
            upd += 1
        else:
            db.add(Product(code=code, name=name or code, price=price))
            ins += 1
    return {"inserted": ins, "updated": upd, "count": db.query(Product).count()}
