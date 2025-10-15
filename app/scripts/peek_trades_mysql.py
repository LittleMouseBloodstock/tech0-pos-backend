from __future__ import annotations

import argparse
import os
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from ..models import Trade
from .migrate_sqlite_to_mysql import _normalize_mysql_connect_args


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dst", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    if not args.dst:
        print("Provide --dst or set DATABASE_URL")
        return 2
    url, ca = _normalize_mysql_connect_args(args.dst)
    e: Engine = create_engine(url, connect_args=ca, future=True)
    with e.connect() as conn:
        rows = conn.execute(select(Trade.__table__.c.TRD_ID)).fetchall()
        ids = [r[0] for r in rows]
        print("trade ids:", ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

