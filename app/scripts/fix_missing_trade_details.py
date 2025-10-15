from __future__ import annotations

"""
Fix migration gaps for trade_details where source has NULL DTL_NO but
destination (MySQL) requires NOT NULL.

Strategy:
- For each TRD_ID that has trade_details with NULL DTL_NO in source (SQLite),
  compute sequential line numbers starting at 1, skipping any numbers already
  used in destination for that TRD_ID.
- Insert the missing rows into MySQL with computed DTL_NO.

Usage:
  py -3.11 -m app.scripts.fix_missing_trade_details --apply \
      --src sqlite:///./serendigo.db --dst mysql+pymysql://...
"""

import argparse
import os
from typing import Sequence

from sqlalchemy import create_engine, select, insert
from sqlalchemy.engine import Engine

from ..models import TradeDetail
from .migrate_sqlite_to_mysql import _normalize_mysql_connect_args


def _fetch_src_nulls(src: Engine) -> dict[int, list[dict]]:
    with src.connect() as conn:
        rows = conn.execute(
            select(TradeDetail.__table__).where(TradeDetail.__table__.c.DTL_NO.is_(None)).order_by(
                TradeDetail.__table__.c.TRD_ID.asc(), TradeDetail.__table__.c.DTL_ID.asc()
            )
        )
        result: dict[int, list[dict]] = {}
        for r in rows:
            d = dict(r._mapping)
            result.setdefault(d["TRD_ID"], []).append(d)
        return result


def _fetch_used_line_nos(dst: Engine) -> dict[int, set[int]]:
    with dst.connect() as conn:
        rows = conn.execute(
            select(TradeDetail.__table__.c.TRD_ID, TradeDetail.__table__.c.DTL_NO)
        )
        used: dict[int, set[int]] = {}
        for trd_id, line_no in rows:
            if line_no is None:
                continue
            used.setdefault(int(trd_id), set()).add(int(line_no))
        return used


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Insert missing trade_details with computed DTL_NO")
    p.add_argument("--src", default="sqlite:///./serendigo.db")
    p.add_argument("--dst", default=os.getenv("DATABASE_URL", ""))
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)

    src_url = args.src
    if os.path.sep in src_url and not src_url.startswith("sqlite"):
        src_url = f"sqlite:///{src_url}"
    src_url, src_ca = _normalize_mysql_connect_args(src_url)
    dst_url = args.dst
    if not dst_url:
        print("Provide --dst or set DATABASE_URL")
        return 2
    dst_url, dst_ca = _normalize_mysql_connect_args(dst_url)

    src = create_engine(src_url, connect_args=src_ca, future=True)
    dst = create_engine(dst_url, connect_args=dst_ca, future=True)

    src_nulls = _fetch_src_nulls(src)
    used = _fetch_used_line_nos(dst)

    total_planned = 0
    for trd_id, rows in src_nulls.items():
        used_set = used.get(trd_id, set())
        next_no = 1
        for row in rows:
            while next_no in used_set:
                next_no += 1
            row_to_insert = dict(row)
            row_to_insert["DTL_NO"] = next_no
            total_planned += 1
            if args.apply:
                with dst.begin() as conn:
                    conn.execute(insert(TradeDetail.__table__).values(**row_to_insert))
            print(
                f"Insert TRD_ID={trd_id} DTL_ID={row['DTL_ID']} as DTL_NO={next_no} (PRD_CODE={row['PRD_CODE']}, QTY={row['QTY']})"
            )
            used_set.add(next_no)
            next_no += 1

    print(f"Planned inserts: {total_planned} ({'APPLIED' if args.apply else 'DRY-RUN'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

