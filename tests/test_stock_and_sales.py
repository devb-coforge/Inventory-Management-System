import sqlite3
from datetime import UTC, datetime

import pytest

from inventory_db import (
    adjust_stock,
    change_price,
    get_product,
    record_sale,
    restock,
    sales_by_product,
)
from seed_db import seed_database

TIMESTAMP = "2026-10-30T12:00:00Z"


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


def test_restock_increases_stock_and_records_movement(seeded_db):
    assert restock(seeded_db, 7, 8, TIMESTAMP) is None
    assert get_product(seeded_db, 7)["quantity"] == 8
    movement = seeded_db.execute("SELECT * FROM stock_movements").fetchone()
    assert dict(movement) == {
        "id": 1,
        "product_id": 7,
        "change": 8,
        "reason": "restock",
        "occurred_at": TIMESTAMP,
    }
    assert not seeded_db.in_transaction


@pytest.mark.parametrize("change", [5, -5, -20])
def test_adjustment_records_signed_change(seeded_db, change):
    assert adjust_stock(seeded_db, 1, change, TIMESTAMP) is None
    assert get_product(seeded_db, 1)["quantity"] == 20 + change
    movement = seeded_db.execute("SELECT * FROM stock_movements").fetchone()
    assert (movement["change"], movement["reason"], movement["occurred_at"]) == (
        change,
        "adjustment",
        TIMESTAMP,
    )
    assert not seeded_db.in_transaction


def test_sale_saves_current_prices_reduces_stock_and_records_movements(seeded_db):
    sale_id = record_sale(seeded_db, [(1, 2), (2, 30)], TIMESTAMP)
    sale = seeded_db.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    assert sale["sold_at"] == TIMESTAMP
    items = seeded_db.execute(
        "SELECT product_id, quantity, unit_price FROM sale_items WHERE sale_id = ?",
        (sale_id,),
    ).fetchall()
    assert [tuple(row) for row in items] == [(1, 2, 1299), (2, 30, 599)]
    assert get_product(seeded_db, 1)["quantity"] == 18
    assert get_product(seeded_db, 2)["quantity"] == 0
    assert [
        tuple(row)
        for row in seeded_db.execute(
            "SELECT product_id, change, reason, occurred_at FROM stock_movements"
        )
    ] == [(1, -2, "sale", TIMESTAMP), (2, -30, "sale", TIMESTAMP)]
    assert not seeded_db.in_transaction

    change_price(seeded_db, 1, 2000)
    row = next(row for row in sales_by_product(seeded_db) if row["id"] == 1)
    assert (row["units_sold"], row["revenue"]) == (5, 3797 + 2 * 1299)


@pytest.mark.parametrize("operation", [restock, adjust_stock, record_sale])
def test_default_timestamp_is_current_utc_and_shared_by_sale_writes(
    seeded_db, operation
):
    before = datetime.now(UTC)
    if operation is record_sale:
        sale_id = operation(seeded_db, [(1, 1), (2, 1)])
        timestamp = seeded_db.execute(
            "SELECT sold_at FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()[0]
    else:
        operation(seeded_db, 1, 1)
        timestamp = seeded_db.execute(
            "SELECT occurred_at FROM stock_movements"
        ).fetchone()[0]
    after = datetime.now(UTC)
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.utcoffset().total_seconds() == 0
    assert before <= parsed <= after
    assert all(
        row[0] == timestamp
        for row in seeded_db.execute("SELECT occurred_at FROM stock_movements")
    )


@pytest.mark.parametrize("quantity", [0, -1])
def test_restock_rejects_invalid_quantities_without_changes(seeded_db, quantity):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError):
        restock(seeded_db, 1, quantity)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("operation", [restock, adjust_stock, record_sale])
def test_missing_product_raises_specific_error_and_leaves_no_changes(
    seeded_db, operation
):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError, match="999"):
        if operation is record_sale:
            operation(seeded_db, [(1, 1), (999, 1)])
        else:
            operation(seeded_db, 999, 1)
    assert list(seeded_db.iterdump()) == before
    assert not seeded_db.in_transaction


def test_adjustment_rejects_negative_result_without_changes(seeded_db):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError, match="1"):
        adjust_stock(seeded_db, 1, -21)
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize(
    "items",
    [
        [],
        [(1, 0)],
        [(1, -1)],
        [(1, 2), (1, 1)],
        [(1, 2), (2, 31)],
    ],
)
def test_invalid_sale_rolls_back_every_change(seeded_db, items):
    before = list(seeded_db.iterdump())
    with pytest.raises(ValueError):
        record_sale(seeded_db, items, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before
    assert not seeded_db.in_transaction


@pytest.mark.parametrize("operation", [restock, adjust_stock, record_sale])
def test_movement_failure_rolls_back_every_write(seeded_db, operation):
    seeded_db.execute(
        """CREATE TRIGGER reject_movement BEFORE INSERT ON stock_movements
           WHEN NEW.product_id = 2
           BEGIN SELECT RAISE(ABORT, 'movement rejected'); END"""
    )
    before = list(seeded_db.iterdump())
    with pytest.raises(sqlite3.IntegrityError, match="movement rejected"):
        if operation is record_sale:
            operation(seeded_db, [(1, 2), (2, 3)], TIMESTAMP)
        else:
            operation(seeded_db, 2, 3, TIMESTAMP)
    assert list(seeded_db.iterdump()) == before
    assert not seeded_db.in_transaction
