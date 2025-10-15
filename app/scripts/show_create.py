from __future__ import annotations

import argparse
import os
from sqlalchemy import create_engine, text
from .migrate_sqlite_to_mysql import _normalize_mysql_connect_args


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dst", default=os.getenv("DATABASE_URL", ""))
    args = p.parse_args()
    if not args.dst:
        print("Provide --dst or set DATABASE_URL")
        return 2
    url, ca = _normalize_mysql_connect_args(args.dst)
    e = create_engine(url, connect_args=ca, future=True)
    with e.connect() as c:
        print("DESCRIBE trade_details:")
        for row in c.execute(text("DESCRIBE trade_details")):
            print(tuple(row))
        print("\nSHOW CREATE TABLE trade_details:")
        row = c.execute(text("SHOW CREATE TABLE trade_details")).fetchone()
        print(row[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

