from __future__ import annotations

"""
SQLite -> MySQL data migration for POS Lv2.

- Copies data for tables defined in app.models (products, trades, trade_details)
- Creates missing tables on the destination
- Inserts rows in safe order (products -> trades -> trade_details)
- Skips conflicting rows (logs and continues) to make repeated runs resilient

Usage examples:
  # Dry-run (no writes):
  py -3.11 -m app.scripts.migrate_sqlite_to_mysql

  # Apply changes using env DATABASE_URL for MySQL:
  py -3.11 -m app.scripts.migrate_sqlite_to_mysql --apply

  # Specify explicit source/destination:
  py -3.11 -m app.scripts.migrate_sqlite_to_mysql --apply \
      --src sqlite:///./serendigo.db \
      --dst mysql+pymysql://user:pass@host:3306/dbname

Notes:
- Destination should be MySQL (pymysql driver). SSL is used if configured by env.
- Source defaults to ./serendigo.db in the repo root.
"""

import argparse
import os
from typing import Iterable, Sequence, Tuple

from sqlalchemy import create_engine, insert, select, func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ..models import Base, Product, Trade, TradeDetail
from ..core.config import get_settings
from .. import db as app_db


def _normalize_mysql_connect_args(url: str) -> Tuple[str, dict]:
    """Return (url, connect_args) with SSL settings when targeting MySQL."""
    u = url.strip()
    # Ensure sync driver
    if "+aiomysql" in u:
        u = u.replace("+aiomysql", "+pymysql", 1)

    connect_args: dict = {}
    if u.startswith("mysql"):
        # Try to honor SSL_CA_PATH or fallback to the repo certificate used by the app
        ca_from_env = os.getenv("SSL_CA_PATH")
        if ca_from_env and os.path.exists(ca_from_env):
            connect_args = {"ssl": {"ssl_ca": ca_from_env}}
        else:
            # Same logic as the app's db.py (keep paths relative stable)
            fallback = os.path.join(os.path.dirname(__file__), "../../DigiCertGlobalRootCA.crt.pem")
            if os.path.exists(fallback):
                connect_args = {"ssl": {"ssl_ca": fallback}}
    elif u.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return u, connect_args


def _chunked(rows: Iterable[dict], size: int = 500) -> Iterable[list[dict]]:
    buf: list[dict] = []
    for r in rows:
        buf.append(r)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def _ensure_tables(dest: Engine) -> None:
    Base.metadata.create_all(bind=dest)


def _table_row_count(e: Engine, table) -> int:
    with e.connect() as conn:
        stmt = select(func.count()).select_from(table)
        return int(conn.execute(stmt).scalar() or 0)


def _fetch_all_as_dicts(e: Engine, table) -> Iterable[dict]:
    with e.connect() as conn:
        result = conn.execute(select(table))
        for row in result:
            yield dict(row._mapping)


def _copy_table(src: Engine, dst: Engine, table, apply: bool) -> Tuple[int, int, int]:
    """Copy rows from src to dst for given table.

    Returns (src_count, inserted, skipped_conflicts)
    """
    src_count = _table_row_count(src, table)
    inserted = 0
    skipped = 0
    if not apply:
        return src_count, inserted, skipped

    with dst.begin() as dest_conn:
        for batch in _chunked(_fetch_all_as_dicts(src, table), size=500):
            try:
                dest_conn.execute(insert(table), batch)
                inserted += len(batch)
            except IntegrityError:
                # Fallback to row-by-row to skip conflicts while continuing
                for row in batch:
                    try:
                        dest_conn.execute(insert(table).values(**row))
                        inserted += 1
                    except IntegrityError:
                        skipped += 1
                # continue with next batch
    return src_count, inserted, skipped


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to MySQL")
    parser.add_argument("--src", default="sqlite:///./serendigo.db", help="Source SQLite URL or path (default: ./serendigo.db)")
    parser.add_argument("--dst", default=None, help="Destination DB URL (default: env DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="Actually write to destination (default: dry-run)")
    args = parser.parse_args(argv)

    settings = get_settings()

    # Resolve source URL
    src_url = args.src
    if os.path.sep in src_url and not src_url.startswith("sqlite"):
        # treat as file path
        src_url = f"sqlite:///{src_url}"
    src_url, src_connect_args = _normalize_mysql_connect_args(src_url)
    src_engine = create_engine(src_url, connect_args=src_connect_args, future=True)

    # Resolve destination URL (prefer CLI arg, then env via app settings)
    dst_url = args.dst or (settings.database_url or "")
    if not dst_url:
        print("ERROR: Destination URL is not provided. Set DATABASE_URL or pass --dst.")
        return 2
    dst_url, dst_connect_args = _normalize_mysql_connect_args(dst_url)
    if not dst_url.startswith("mysql"):
        print(f"ERROR: Destination must be MySQL. Got: {dst_url}")
        return 2
    dest_engine = create_engine(dst_url, connect_args=dst_connect_args, future=True)

    # Prepare destination schema
    _ensure_tables(dest_engine)

    plan = [
        (Product.__table__, "products"),
        (Trade.__table__, "trades"),
        (TradeDetail.__table__, "trade_details"),
    ]

    print("Source:", src_url)
    print("Destination:", dst_url)
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")

    totals = {"src": 0, "inserted": 0, "skipped": 0}
    for table, name in plan:
        src_count = _table_row_count(src_engine, table)
        if not args.apply:
            print(f"- {name}: src rows={src_count}")
            totals["src"] += src_count
            continue
        sc, ins, sk = _copy_table(src_engine, dest_engine, table, apply=True)
        totals["src"] += sc
        totals["inserted"] += ins
        totals["skipped"] += sk
        print(f"- {name}: src={sc}, inserted={ins}, skipped_conflicts={sk}")

    if args.apply:
        print(
            "Done.",
            f"Totals: src={totals['src']}, inserted={totals['inserted']}, skipped={totals['skipped']}",
        )
    else:
        print(f"Dry-run complete. Total rows discoverd at source: {totals['src']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
