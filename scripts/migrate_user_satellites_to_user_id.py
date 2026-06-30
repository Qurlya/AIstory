#!/usr/bin/env python3
"""
Normalize old user satellite rows after importing an old SQL dump.

Old schema stored users.<satellite>_id foreign-key columns. New schema expects every
user satellite row to have the same primary key as users.id. This script copies the
old referenced rows to rows whose id equals users.id and can optionally drop the old
users FK columns afterwards.
"""
from __future__ import annotations

import argparse
import os
from typing import Iterable

import pymysql
from dotenv import load_dotenv

SATELLITES = {
    "event_stats_id": "user_event_stats",
    "culture_stats_id": "user_culture_stats",
    "personality_stats_id": "user_personality_stats",
    "streak_id": "user_streaks",
    "rating_id": "user_ratings",
    "ad_stats_id": "user_ad_stats",
}

DEFAULT_SQL = {
    "last_update_info": "UTC_TIMESTAMP()",
    "last_activity": "'1970-01-01 00:00:00'",
    "ad_last_click_at": "NULL",
    "display_as": "1",
    "rating_year": "YEAR(UTC_TIMESTAMP())",
    "rating_month": "MONTH(UTC_TIMESTAMP())",
}


def q(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def fetch_column_names(cursor, database: str, table: str) -> list[str]:
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """,
        (database, table),
    )
    return [row[0] for row in cursor.fetchall()]


def column_exists(cursor, database: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        LIMIT 1
        """,
        (database, table, column),
    )
    return cursor.fetchone() is not None


def migrate_satellite(cursor, database: str, old_fk_column: str, table: str) -> None:
    child_columns = fetch_column_names(cursor, database, table)
    if not child_columns:
        print(f"[skip] table {table} does not exist")
        return

    data_columns = [column for column in child_columns if column != "id"]

    if column_exists(cursor, database, "users", old_fk_column):
        tmp_table = f"tmp_{table}_old_satellite"
        cursor.execute(f"DROP TEMPORARY TABLE IF EXISTS {q(tmp_table)}")
        cursor.execute(f"CREATE TEMPORARY TABLE {q(tmp_table)} AS SELECT * FROM {q(table)}")

        select_columns = ["u.id"] + [f"old.{q(column)}" for column in data_columns]
        insert_columns = ["id"] + data_columns
        update_clause = ", ".join(f"{q(column)} = VALUES({q(column)})" for column in data_columns)
        sql = f"""
            INSERT INTO {q(table)} ({', '.join(q(column) for column in insert_columns)})
            SELECT {', '.join(select_columns)}
            FROM users u
            JOIN {q(tmp_table)} old ON old.id = u.{q(old_fk_column)}
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        cursor.execute(sql)
        print(f"[copy] {table}: copied {cursor.rowcount} row changes from users.{old_fk_column}")
    else:
        print(f"[info] users.{old_fk_column} not found; only filling missing {table} rows")

    default_columns = ["id"] + data_columns
    default_select = ["u.id"] + [DEFAULT_SQL.get(column, "0") for column in data_columns]
    cursor.execute(
        f"""
        INSERT IGNORE INTO {q(table)} ({', '.join(q(column) for column in default_columns)})
        SELECT {', '.join(default_select)}
        FROM users u
        LEFT JOIN {q(table)} child ON child.id = u.id
        WHERE child.id IS NULL
        """
    )
    print(f"[fill] {table}: inserted {cursor.rowcount} default rows for users without satellite")


def drop_old_user_columns(cursor, database: str, columns: Iterable[str]) -> None:
    for column in columns:
        if column_exists(cursor, database, "users", column):
            cursor.execute(f"ALTER TABLE users DROP COLUMN {q(column)}")
            print(f"[drop] users.{column}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy old user satellite rows so child table ids equal users.id."
    )
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("DB_USER"))
    parser.add_argument("--password", default=os.getenv("DB_PASS"))
    parser.add_argument("--database", default=os.getenv("DB_NAME"))
    parser.add_argument(
        "--drop-old-user-columns",
        action="store_true",
        help="Drop old users.*_id columns after copying data. Make a backup first.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    missing = [name for name in ("user", "password", "database") if not getattr(args, name)]
    if missing:
        raise SystemExit(f"Missing DB connection args: {', '.join(missing)}")

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            for old_fk_column, table in SATELLITES.items():
                migrate_satellite(cursor, args.database, old_fk_column, table)

            if args.drop_old_user_columns:
                drop_old_user_columns(cursor, args.database, SATELLITES.keys())

        connection.commit()
        print("[done] user satellite ids now match users.id")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
