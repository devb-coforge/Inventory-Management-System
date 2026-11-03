import sqlite3
from datetime import UTC, datetime

import pytest

from inventory_db import adjust_stock, get_product, record_sale, restock
from seed_db import seed_database

TIMESTAMP = "2026-11-02T10:00:00Z"


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


def test_restock_increases_stock_and_logs_movement(seeded_db):
    assert restock(seeded_db, 1, 4, TIMESTAMP) is None
    assert get_product(seeded_db, 1)["quantity"] == 24
    movement = seeded_db.execute("SELECT * FROM stock_movements").fetchone()
    assert dict(movement) == {
        "id": 1,
        "product_id": 1,
        "change": 4,
        "reason": "restock",
        "occurred_at": TIMESTAMP,
    }
    assert not seeded_db.in_transaction


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2", None])
def test_restock_rejects_invalid_quantity_without_changes(seeded_db, quantity):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError, match="positive integer"):
        restock(seeded_db, 1, quantity, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("change", [4, -4, -20, 0])
def test_adjust_stock_changes_quantity_and_logs_movement(seeded_db, change):
    assert adjust_stock(seeded_db, 1, change, TIMESTAMP) is None
    assert get_product(seeded_db, 1)["quantity"] == 20 + change
    movement = seeded_db.execute(
        "SELECT product_id, change, reason, occurred_at FROM stock_movements"
    ).fetchone()
    assert tuple(movement) == (1, change, "adjustment", TIMESTAMP)
    assert not seeded_db.in_transaction


@pytest.mark.parametrize("change", [-21, 1.5, True, "2", None])
def test_invalid_adjustment_leaves_database_unchanged(seeded_db, change):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError):
        adjust_stock(seeded_db, 1, change, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("operation", [restock, adjust_stock])
def test_stock_change_for_unknown_product_leaves_database_unchanged(
    seeded_db, operation
):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError, match="Product 999 does not exist"):
        operation(seeded_db, 999, 2, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("operation", [restock, adjust_stock])
def test_stock_change_rolls_back_when_movement_insert_fails(seeded_db, operation):
    seeded_db.executescript(
        """CREATE TRIGGER reject_movement BEFORE INSERT ON stock_movements
           BEGIN SELECT RAISE(ABORT, 'Movement rejected'); END;"""
    )
    before = list(seeded_db.iterdump())
    with pytest.raises(sqlite3.IntegrityError, match="Movement rejected"):
        operation(seeded_db, 1, 2, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before


def test_sale_saves_current_prices_stock_and_movements(seeded_db):
    with seeded_db:
        seeded_db.execute("UPDATE products SET unit_price = 1500 WHERE id = 1")
    sale_id = record_sale(seeded_db, [(1, 2), (4, 3)], TIMESTAMP)
    assert sale_id == 6
    assert tuple(
        seeded_db.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    ) == (6, TIMESTAMP)
    lines = seeded_db.execute(
        """SELECT product_id, quantity, unit_price FROM sale_items
           WHERE sale_id = ? ORDER BY product_id""",
        (sale_id,),
    )
    assert [tuple(row) for row in lines] == [(1, 2, 1500), (4, 3, 399)]
    assert get_product(seeded_db, 1)["quantity"] == 18
    assert get_product(seeded_db, 4)["quantity"] == 37
    movements = seeded_db.execute(
        """SELECT product_id, change, reason, occurred_at
           FROM stock_movements ORDER BY id"""
    )
    assert [tuple(row) for row in movements] == [
        (1, -2, "sale", TIMESTAMP),
        (4, -3, "sale", TIMESTAMP),
    ]
    assert not seeded_db.in_transaction


def test_sale_can_use_all_stock_and_zero_price(seeded_db):
    with seeded_db:
        seeded_db.execute("UPDATE products SET unit_price = 0 WHERE id = 1")
    sale_id = record_sale(seeded_db, [(1, 20)], TIMESTAMP)
    assert get_product(seeded_db, 1)["quantity"] == 0
    assert (
        seeded_db.execute(
            "SELECT unit_price FROM sale_items WHERE sale_id = ?", (sale_id,)
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "items, message",
    [
        ([], "at least one"),
        ([(1, 2), (4, 41)], "Insufficient stock"),
        ([(1, 2), (999, 1)], "Product 999 does not exist"),
        ([(1, 2), (1, 3)], "Duplicate product"),
        ([(1, 2), (4, 0)], "positive integer"),
        ([(1, 2), (4, -1)], "positive integer"),
        ([(1, 2), (4, 1.5)], "positive integer"),
        ([(1, 2), (4, True)], "positive integer"),
        ([(1, 2), (4, "2")], "positive integer"),
        ([(1, 2), (4, None)], "positive integer"),
    ],
)
def test_failed_sale_leaves_entire_database_unchanged(seeded_db, items, message):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError, match=message):
        record_sale(seeded_db, items, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before
    assert not seeded_db.in_transaction


def test_sale_rolls_back_when_second_movement_insert_fails(seeded_db):
    seeded_db.executescript(
        """CREATE TRIGGER reject_second_movement BEFORE INSERT ON stock_movements
           WHEN NEW.product_id = 4
           BEGIN SELECT RAISE(ABORT, 'Movement rejected'); END;"""
    )
    before = list(seeded_db.iterdump())
    with pytest.raises(sqlite3.IntegrityError, match="Movement rejected"):
        record_sale(seeded_db, [(1, 2), (4, 3)], TIMESTAMP)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("operation", [restock, adjust_stock, record_sale])
def test_stock_operations_default_to_current_utc_time(seeded_db, operation):
    before = datetime.now(UTC)
    if operation is record_sale:
        sale_id = operation(seeded_db, [(1, 1)])
        saved_time = seeded_db.execute(
            "SELECT sold_at FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()[0]
    else:
        operation(seeded_db, 1, 1)
        saved_time = seeded_db.execute(
            "SELECT occurred_at FROM stock_movements"
        ).fetchone()[0]
    timestamp = datetime.fromisoformat(saved_time)
    assert before <= timestamp <= datetime.now(UTC)
    assert (
        seeded_db.execute("SELECT occurred_at FROM stock_movements").fetchone()[0]
        == saved_time
    )
