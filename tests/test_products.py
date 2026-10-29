import sqlite3

import pytest

from inventory_db import add_product, change_price, delete_product, get_product
from seed_db import seed_database


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


def test_add_product_returns_id_and_persists_fields(seeded_db):
    product_id = add_product(seeded_db, "NEW-001", "New Tool", "Tools", 1, 1250, 7, 2)
    product = get_product(seeded_db, product_id)
    assert dict(product) == {
        "id": product_id,
        "sku": "NEW-001",
        "name": "New Tool",
        "category": "Tools",
        "supplier_id": 1,
        "unit_price": 1250,
        "quantity": 7,
        "reorder_level": 2,
        "supplier_name": "Forge Tools",
    }
    assert not seeded_db.in_transaction


@pytest.mark.parametrize(
    "overrides",
    [
        {"sku": "HAM-001"},
        {"supplier_id": 999},
        {"unit_price": -1},
        {"quantity": -1},
        {"reorder_level": -1},
        {"name": None},
    ],
)
def test_add_product_rejects_invalid_values_without_changes(seeded_db, overrides):
    values = {
        "sku": "NEW-001",
        "name": "New Tool",
        "category": "Tools",
        "supplier_id": 1,
        "unit_price": 1250,
        "quantity": 7,
        "reorder_level": 2,
    }
    values.update(overrides)
    before = list(seeded_db.iterdump())
    with pytest.raises(sqlite3.IntegrityError):
        add_product(seeded_db, **values)
    assert list(seeded_db.iterdump()) == before


def test_add_product_accepts_zero_price_stock_and_reorder_level(seeded_db):
    product_id = add_product(seeded_db, "ZERO", "Free", "Tools", 1, 0, 0, 0)
    assert get_product(seeded_db, product_id)["quantity"] == 0


def test_get_product_joins_supplier_name(seeded_db):
    product = get_product(seeded_db, 1)
    assert product["name"] == "Claw Hammer"
    assert product["supplier_name"] == "Forge Tools"


def test_get_missing_product_returns_none(seeded_db):
    assert get_product(seeded_db, 999) is None


def test_change_price_updates_product_without_changing_sale_history(seeded_db):
    before = list(seeded_db.execute("SELECT * FROM sale_items"))
    assert change_price(seeded_db, 1, 1500) is True
    assert get_product(seeded_db, 1)["unit_price"] == 1500
    assert list(seeded_db.execute("SELECT * FROM sale_items")) == before
    assert not seeded_db.in_transaction


def test_change_price_accepts_zero(seeded_db):
    assert change_price(seeded_db, 1, 0) is True
    assert get_product(seeded_db, 1)["unit_price"] == 0


def test_change_price_missing_product_returns_false(seeded_db):
    assert change_price(seeded_db, 999, 1500) is False


def test_change_price_rejects_negative_price_without_changes(seeded_db):
    with pytest.raises(sqlite3.IntegrityError):
        change_price(seeded_db, 1, -1)
    assert get_product(seeded_db, 1)["unit_price"] == 1299


def test_delete_never_sold_product(seeded_db):
    assert delete_product(seeded_db, 11) is True
    assert get_product(seeded_db, 11) is None
    assert not seeded_db.in_transaction


def test_delete_sold_product_is_rejected_without_changes(seeded_db):
    before = list(seeded_db.iterdump())
    with pytest.raises(sqlite3.IntegrityError):
        delete_product(seeded_db, 1)
    assert list(seeded_db.iterdump()) == before


def test_delete_missing_product_returns_false(seeded_db):
    assert delete_product(seeded_db, 999) is False
