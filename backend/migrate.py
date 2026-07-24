"""One-off, idempotent SQLite migration.

Adds any columns that were introduced after a table was first created — SQLAlchemy's
create_all() only creates missing *tables*, never alters existing ones, so a DB built by
an earlier version can be missing newer columns (e.g. checkins.face_stress).

Safe to run repeatedly. Run from the backend/ dir:  python migrate.py
"""

import sqlite3

DB_PATH = "app.db"

# table -> {column: SQLite type} that must exist. Add future columns here.
REQUIRED_COLUMNS = {
    "checkins": {
        "journal": "VARCHAR(500)",
        "face_stress": "FLOAT",
    },
}


def main() -> None:
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    existing_tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    for table, columns in REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            print(f"- {table}: table absent (create_all will build it on next startup) — skipping")
            continue
        have = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
        for col, coltype in columns.items():
            if col in have:
                print(f"- {table}.{col}: already present")
            else:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                print(f"- {table}.{col}: ADDED ({coltype})")

    db.commit()
    db.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
