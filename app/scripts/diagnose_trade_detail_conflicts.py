from __future__ import annotations

"""
Diagnose duplicate conflicts for trade_details between SQLite source and MySQL destination.

Reports rows that would conflict by primary key (DTL_ID) or unique (TRD_ID, DTL_NO).

Usage:
  py -3.11 -m app.scripts.diagnose_trade_detail_conflicts \
    --src sqlite:///./serendigo.db \
    --dst mysql+pymysql://user:pass@host:3306/dbname
"""

import argparse
import os
from typing import Iterable, Sequence, Tuple

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine

from ..models import TradeDetail
from .migrate_sqlite_to_mysql import _normalize_mysql_connect_args


def _fetch_trade_details(e: Engine) -> list[dict]:
    with e.connect() as conn:
        result = conn.execute(
            select(
                TradeDetail.__table__.c.DTL_ID,
                TradeDetail.__table__.c.TRD_ID,
                TradeDetail.__table__.c.DTL_NO,
                TradeDetail.__table__.c.PRD_CODE,
                TradeDetail.__table__.c.PRD_NAME,
                TradeDetail.__table__.c.PRD_PRICE,
                TradeDetail.__table__.c.QTY,
            )
        )
        return [dict(row._mapping) for row in result]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose trade_details conflicts between SQLite and MySQL")
    parser.add_argument("--src", default="sqlite:///./serendigo.db", help="Source SQLite URL or file path")
    parser.add_argument("--dst", required=False, default=os.getenv("DATABASE_URL", ""), help="Destination MySQL URL")
    args = parser.parse_args(argv)

    src_url = args.src
    if os.path.sep in src_url and not src_url.startswith("sqlite"):
        src_url = f"sqlite:///{src_url}"
    src_url, src_connect_args = _normalize_mysql_connect_args(src_url)
    dst_url = args.dst
    if not dst_url:
        print("ERROR: --dst or env DATABASE_URL is required")
        return 2
    dst_url, dst_connect_args = _normalize_mysql_connect_args(dst_url)

    src_engine = create_engine(src_url, connect_args=src_connect_args, future=True)
    dst_engine = create_engine(dst_url, connect_args=dst_connect_args, future=True)

    s_rows = _fetch_trade_details(src_engine)
    d_rows = _fetch_trade_details(dst_engine)

    d_by_pk = {r["DTL_ID"]: r for r in d_rows}
    d_by_uq = {(r["TRD_ID"], r["DTL_NO"]): r for r in d_rows}

    pk_conflicts: list[tuple[dict, dict]] = []
    uq_conflicts: list[tuple[dict, dict]] = []
    missing: list[dict] = []

    for s in s_rows:
        pk = s["DTL_ID"]
        uq = (s["TRD_ID"], s["DTL_NO"])
        if pk in d_by_pk:
            pk_conflicts.append((s, d_by_pk[pk]))
        elif uq in d_by_uq:
            uq_conflicts.append((s, d_by_uq[uq]))
        else:
            missing.append(s)

    print("Source rows:", len(s_rows))
    print("Dest rows:", len(d_rows))
    print("Missing in dest (would insert):", len(missing))
    print("Conflicts by PK (DTL_ID):", len(pk_conflicts))
    print("Conflicts by Unique (TRD_ID,DTL_NO):", len(uq_conflicts))

    if pk_conflicts:
        print("\n-- PK conflicts (showing all) --")
        for s, d in pk_conflicts:
            print(
                f"DTL_ID={s['DTL_ID']}: src(TRD_ID={s['TRD_ID']}, DTL_NO={s['DTL_NO']}, PRD_CODE={s['PRD_CODE']}, QTY={s['QTY']})",
                f"; dst(TRD_ID={d['TRD_ID']}, DTL_NO={d['DTL_NO']}, PRD_CODE={d['PRD_CODE']}, QTY={d['QTY']})",
            )

    if uq_conflicts:
        print("\n-- Unique (TRD_ID,DTL_NO) conflicts (showing all) --")
        for s, d in uq_conflicts:
            print(
                f"(TRD_ID,DTL_NO)=({s['TRD_ID']},{s['DTL_NO']}): src(DTL_ID={s['DTL_ID']}, PRD_CODE={s['PRD_CODE']}, QTY={s['QTY']})",
                f"; dst(DTL_ID={d['DTL_ID']}, PRD_CODE={d['PRD_CODE']}, QTY={d['QTY']})",
            )

    if missing:
        print("\n-- Example missing rows (up to 10) --")
        for s in missing[:10]:
            print(
                f"DTL_ID={s['DTL_ID']}, (TRD_ID,DTL_NO)=({s['TRD_ID']},{s['DTL_NO']}), PRD_CODE={s['PRD_CODE']}, QTY={s['QTY']}"
            )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

