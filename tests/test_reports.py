import pytest

from inventory_db import (
    low_stock,
    never_sold,
    sales_by_product,
    stock_value_by_supplier,
)
from seed_db import seed_database


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


def test_stock_value_by_supplier_matches_seed_totals(seeded_db):
    assert [dict(row) for row in stock_value_by_supplier(seeded_db)] == [
        {"supplier_id": 1, "supplier_name": "Forge Tools", "stock_value": 57435},
        {"supplier_id": 2, "supplier_name": "Bright Electric", "stock_value": 41373},
        {"supplier_id": 4, "supplier_name": "Fixings Depot", "stock_value": 20257},
        {"supplier_id": 3, "supplier_name": "Flow Plumbing", "stock_value": 13247},
    ]


def test_stock_value_keeps_suppliers_separate_and_includes_empty_suppliers(seeded_db):
    seeded_db.execute("INSERT INTO suppliers VALUES (?, ?)", (5, "Forge Tools"))
    seeded_db.execute(
        """INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (13, "EXTRA", "Extra Tool", "Tools", 5, 100, 2, 0),
    )
    seeded_db.execute("INSERT INTO suppliers VALUES (?, ?)", (6, "Empty Supplier"))
    rows = stock_value_by_supplier(seeded_db)
    assert [(row["supplier_id"], row["stock_value"]) for row in rows][-2:] == [
        (5, 200),
        (6, 0),
    ]


def test_low_stock_matches_seed_products_and_units_short(seeded_db):
    rows = low_stock(seeded_db)
    assert [(row["id"], row["name"], row["units_short"]) for row in rows] == [
        (7, "Copper Pipe", 5),
        (10, "Wood Screw Pack", 5),
    ]
    assert rows[0]["quantity"] == 0
    assert rows[0]["reorder_level"] == 5


def test_low_stock_includes_exact_reorder_level_and_zero_threshold(seeded_db):
    seeded_db.execute("UPDATE products SET quantity = reorder_level WHERE id = 1")
    seeded_db.execute(
        "UPDATE products SET quantity = 0, reorder_level = 0 WHERE id = 2"
    )
    rows = low_stock(seeded_db)
    assert [(row["id"], row["units_short"]) for row in rows] == [
        (1, 0),
        (7, 5),
        (2, 0),
        (10, 5),
    ]


def test_low_stock_returns_no_rows_when_all_stock_is_above_reorder(seeded_db):
    seeded_db.execute("UPDATE products SET quantity = reorder_level + 1")
    assert low_stock(seeded_db) == []


def test_sales_by_product_matches_seed_totals_including_unsold_products(seeded_db):
    rows = sales_by_product(seeded_db)
    assert {row["id"]: (row["units_sold"], row["revenue"]) for row in rows} == {
        1: (3, 3797),
        7: (3, 3297),
        4: (6, 2394),
        5: (1, 1499),
        9: (4, 1396),
        2: (2, 1198),
        10: (2, 998),
        3: (1, 899),
        6: (2, 498),
        8: (2, 398),
        12: (0, 0),
        11: (0, 0),
    }
    assert [row["revenue"] for row in rows] == sorted(
        (row["revenue"] for row in rows), reverse=True
    )
    assert rows[0]["name"] == "Claw Hammer"
    assert rows[0]["sku"] == "HAM-001"


def test_sales_revenue_uses_historical_prices_and_ignores_current_stock(seeded_db):
    before = [dict(row) for row in sales_by_product(seeded_db)]
    seeded_db.execute("UPDATE products SET unit_price = 999999, quantity = 0")
    assert [dict(row) for row in sales_by_product(seeded_db)] == before


def test_never_sold_matches_seed_products_sorted_by_name(seeded_db):
    rows = never_sold(seeded_db)
    assert [(row["id"], row["name"], row["sku"]) for row in rows] == [
        (12, "Bolt Pack", "BLT-001"),
        (11, "Hex Nut Pack", "NUT-001"),
    ]
    assert rows[0]["quantity"] == 16


def test_free_sale_counts_as_sold(seeded_db):
    seeded_db.execute(
        """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
           VALUES (?, ?, ?, ?)""",
        (1, 12, 2, 0),
    )
    assert [row["id"] for row in never_sold(seeded_db)] == [11]
    row = next(row for row in sales_by_product(seeded_db) if row["id"] == 12)
    assert (row["units_sold"], row["revenue"]) == (2, 0)


def test_products_without_sales_are_reported_with_zero_totals(seeded_db):
    seeded_db.execute("DELETE FROM sale_items")
    rows = sales_by_product(seeded_db)
    assert len(rows) == 12
    assert all(row["units_sold"] == row["revenue"] == 0 for row in rows)
    assert len(never_sold(seeded_db)) == 12


@pytest.mark.parametrize(
    "report", [stock_value_by_supplier, low_stock, sales_by_product, never_sold]
)
def test_report_returns_no_rows_for_empty_database(db, report):
    assert report(db) == []


@pytest.mark.parametrize(
    "report", [stock_value_by_supplier, low_stock, sales_by_product, never_sold]
)
def test_report_leaves_database_and_pending_transaction_unchanged(seeded_db, report):
    seeded_db.execute("UPDATE products SET quantity = 0 WHERE id = 1")
    before = list(seeded_db.iterdump())
    report(seeded_db)
    assert list(seeded_db.iterdump()) == before
    assert seeded_db.in_transaction
    seeded_db.rollback()
    assert (
        seeded_db.execute("SELECT quantity FROM products WHERE id = 1").fetchone()[0]
        == 20
    )
