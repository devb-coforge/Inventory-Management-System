import pytest

from inventory_db import add_product, search_products
from seed_db import seed_database


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


@pytest.mark.parametrize(
    "text, expected_ids",
    [("hAmMeR", [1]), ("hAm-0", [1]), ("fOrGe", [1, 3, 2])],
)
def test_search_matches_name_sku_and_supplier_ignoring_case(
    seeded_db, text, expected_ids
):
    assert [row["id"] for row in search_products(seeded_db, text)] == expected_ids


def test_empty_search_lists_all_products_sorted_by_name(seeded_db):
    rows = search_products(seeded_db, "")
    assert len(rows) == 12
    assert [row["name"] for row in rows] == sorted(row["name"] for row in rows)
    assert all(row["supplier_name"] for row in rows)


@pytest.mark.parametrize(
    "filters, expected_ids",
    [
        ({"category": "Tools"}, {1, 2, 3}),
        ({"max_price": 399}, {4, 6, 8, 9, 11}),
        ({"in_stock_only": True}, set(range(1, 13)) - {7}),
        ({"low_stock_only": True}, {7, 10}),
        ({"max_price": 0}, set()),
    ],
)
def test_search_individual_filters(seeded_db, filters, expected_ids):
    assert {row["id"] for row in search_products(seeded_db, "", **filters)} == (
        expected_ids
    )


def test_search_combines_text_and_all_filters(seeded_db):
    rows = search_products(
        seeded_db,
        "depot",
        category="Fixings",
        max_price=499,
        in_stock_only=True,
        low_stock_only=True,
    )
    assert [row["id"] for row in rows] == [10]


def test_search_applies_filters_to_all_search_fields(seeded_db):
    assert search_products(seeded_db, "hammer", category="Electrical") == []
    assert search_products(seeded_db, "HAM-001", max_price=100) == []


def test_low_stock_includes_stock_equal_to_reorder_level(seeded_db):
    product_id = add_product(seeded_db, "EQUAL", "Equal Stock", "Tools", 1, 0, 5, 5)
    rows = search_products(seeded_db, "", low_stock_only=True, in_stock_only=True)
    assert {row["id"] for row in rows} == {10, product_id}


@pytest.mark.parametrize("text", ["'; DROP TABLE products; --", "' OR 1=1 --"])
def test_search_injection_text_returns_nothing_and_changes_nothing(seeded_db, text):
    before = list(seeded_db.iterdump())
    assert search_products(seeded_db, text) == []
    assert list(seeded_db.iterdump()) == before


def test_search_category_is_parameterized(seeded_db):
    before = list(seeded_db.iterdump())
    assert search_products(seeded_db, "", category="' OR 1=1 --") == []
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("text", ["%", "_", "\\"])
def test_search_treats_like_wildcards_and_escape_as_literal_text(seeded_db, text):
    product_id = add_product(
        seeded_db, "SPECIAL", f"Special {text} Tool", "Tools", 1, 100, 1, 0
    )
    assert [row["id"] for row in search_products(seeded_db, text)] == [product_id]
