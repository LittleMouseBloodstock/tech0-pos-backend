from __future__ import annotations

"""
SQLite schema doctor for POS Lv2.

- Detects differences between the current SQLite DB and SQLAlchemy models.
- Safely applies minimal fixes:
  - Create missing tables
  - Add missing columns (added as NULLable for safety)
  - Ensure unique index on trade_details (TRD_ID, DTL_NO)

Usage:
  py -3.11 -m app.scripts.fix_sqlite_schema           # dry run (no changes)
  py -3.11 -m app.scripts.fix_sqlite_schema --apply   # apply changes

Notes:
  - Only supports SQLite URLs (sqlite:///...)
  - Does NOT drop or alter existing columns; it prints warnings instead.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import argparse
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ..models import Base, Product, Trade, TradeDetail
from ..db import engine as app_engine


@dataclass
class ColumnSpec:
    name: str
    type_sql: str
    nullable: bool


def _sqlite_type(col) -> str:
    # Map common SQLAlchemy types to SQLite type names used in PRAGMA
    t = col.type.__class__.__name__.lower()
    if "integer" in t:
        return "INTEGER"
    if "string" in t or "varchar" in t or "text" in t:
        return "TEXT"
    if "datetime" in t or "date" in t:
        return "DATETIME"
    return "TEXT"


def expected_schema() -> Dict[str, List[ColumnSpec]]:
    mapping: Dict[str, List[ColumnSpec]] = {}
    md = Base.metadata
    for tbl_name in (Product.__tablename__, Trade.__tablename__, TradeDetail.__tablename__):
        t = md.tables[tbl_name]
        cols: List[ColumnSpec] = []
        for c in t.columns:
            cols.append(ColumnSpec(name=c.name, type_sql=_sqlite_type(c), nullable=bool(c.nullable)))
        mapping[tbl_name] = cols
    return mapping


def table_exists(e: Engine, name: str) -> bool:
    insp = inspect(e)
    return insp.has_table(name)


def fetch_existing_columns(e: Engine, table: str) -> Dict[str, Tuple[str, int]]:
    # Returns mapping: name -> (type, notnull)
    with e.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info('{table}')"))
        result: Dict[str, Tuple[str, int]] = {}
        for r in rows:
            # row: cid, name, type, notnull, dflt_value, pk
            result[str(r[1])] = (str(r[2]).upper(), int(r[3]))
        return result


def ensure_unique_index_trade_details(e: Engine, apply: bool) -> List[str]:
    actions: List[str] = []
    table = TradeDetail.__tablename__
    with e.connect() as conn:
        idx_rows = conn.execute(text(f"PRAGMA index_list('{table}')")).fetchall()
        found = False
        for idx in idx_rows:
            # Each row: seq, name, unique, origin, partial
            name = str(idx[1])
            unique = int(idx[2]) == 1
            if not unique:
                continue
            cols = conn.execute(text(f"PRAGMA index_info('{name}')")).fetchall()
            col_names = [str(c[2]).upper() for c in cols]
            if col_names == ["TRD_ID", "DTL_NO"]:
                found = True
                break
        if not found:
            stmt = "CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_detail_per_trade ON trade_details(TRD_ID, DTL_NO)"
            actions.append(stmt)
            if apply:
                conn.execute(text(stmt))
                actions.append("(applied)")
    return actions


def add_missing_columns(e: Engine, table: str, expected: List[ColumnSpec], existing: Dict[str, Tuple[str, int]], apply: bool) -> List[str]:
    actions: List[str] = []
    for col in expected:
        if col.name not in existing:
            # Add as NULLable for safety; SQLite allows without default
            stmt = f"ALTER TABLE {table} ADD COLUMN {col.name} {col.type_sql}"
            actions.append(stmt)
            if apply:
                with e.connect() as conn:
                    conn.execute(text(stmt))
                    actions.append(f"(applied) {table}.{col.name}")
        else:
            # Compare type and nullability; warn only
            typ, notnull = existing[col.name]
            if typ and typ != col.type_sql:
                actions.append(f"WARN type mismatch {table}.{col.name}: db={typ}, expected={col.type_sql}")
            if notnull and col.nullable:
                actions.append(f"WARN nullability mismatch {table}.{col.name}: db NOT NULL, expected NULLable")
    return actions


def ensure_tables_and_columns(e: Engine, apply: bool) -> List[str]:
    md = Base.metadata
    exp = expected_schema()
    actions: List[str] = []
    for tbl_name in (Product.__tablename__, Trade.__tablename__, TradeDetail.__tablename__):
        if not table_exists(e, tbl_name):
            actions.append(f"CREATE TABLE {tbl_name}")
            if apply:
                md.tables[tbl_name].create(bind=e)
                actions.append(f"(applied) table {tbl_name}")
        else:
            existing = fetch_existing_columns(e, tbl_name)
            actions.extend(add_missing_columns(e, tbl_name, exp[tbl_name], existing, apply))
    # Ensure unique index on trade_details
    actions.extend(ensure_unique_index_trade_details(e, apply))
    return actions


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix SQLite schema to match models (safe ops)")
    parser.add_argument("--apply", action="store_true", help="Apply changes (without this, dry-run)")
    args = parser.parse_args(argv)

    e = app_engine
    if not str(e.url).startswith("sqlite"):
        print(f"This tool supports SQLite only. Current URL: {e.url}")
        return 1

    actions = ensure_tables_and_columns(e, apply=args.apply)
    if not actions:
        print("No actions needed.")
    else:
        print("Planned actions:")
        for a in actions:
            print(" -", a)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

