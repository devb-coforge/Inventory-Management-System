from pathlib import Path

from seed_db import seed_database


def test_schema_creates_five_strict_tables(db):
    tables = {
        row["name"]: row["strict"]
        for row in db.execute("PRAGMA table_list")
        if not row["name"].startswith("sqlite_")
    }
    assert tables == {
        "suppliers": 1,
        "products": 1,
        "sales": 1,
        "sale_items": 1,
        "stock_movements": 1,
    }


def test_schema_can_run_again_without_losing_data(db):
    seed_database(db)
    before = list(db.iterdump())
    schema = Path(__file__).resolve().parents[1] / "schema.sql"
    db.executescript(schema.read_text())
    assert list(db.iterdump()) == before


def test_connection_enables_foreign_keys_and_named_rows(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.execute("SELECT 42 AS answer").fetchone()["answer"] == 42
