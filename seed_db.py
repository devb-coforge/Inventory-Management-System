import sqlite3
from contextlib import closing
from pathlib import Path

from inventory_db import connect

SUPPLIERS = [
    (1, "Forge Tools"),
    (2, "Bright Electric"),
    (3, "Flow Plumbing"),
    (4, "Fixings Depot"),
]

# Quantities represent current stock after the historical sample sales.
PRODUCTS = [
    (1, "HAM-001", "Claw Hammer", "Tools", 1, 1299, 20, 5),
    (2, "DRV-001", "Screwdriver", "Tools", 1, 599, 30, 8),
    (3, "PLR-001", "Pliers", "Tools", 1, 899, 15, 4),
    (4, "BLB-001", "LED Bulb", "Electrical", 2, 399, 40, 10),
    (5, "CBL-001", "Extension Cable", "Electrical", 2, 1599, 12, 3),
    (6, "SWI-001", "Light Switch", "Electrical", 2, 249, 25, 6),
    (7, "PIP-001", "Copper Pipe", "Plumbing", 3, 1099, 0, 5),
    (8, "TAP-001", "Tap Washer Pack", "Plumbing", 3, 199, 35, 10),
    (9, "ELB-001", "Pipe Elbow", "Plumbing", 3, 349, 18, 5),
    (10, "SCR-001", "Wood Screw Pack", "Fixings", 4, 499, 5, 10),
    (11, "NUT-001", "Hex Nut Pack", "Fixings", 4, 299, 22, 5),
    (12, "BLT-001", "Bolt Pack", "Fixings", 4, 699, 16, 4),
]

SALES = [
    (1, "2026-10-01T10:00:00Z"),
    (2, "2026-10-02T11:00:00Z"),
    (3, "2026-10-03T12:00:00Z"),
    (4, "2026-10-04T13:00:00Z"),
    (5, "2026-10-05T14:00:00Z"),
]

SALE_ITEMS = [
    (1, 1, 1, 1199),
    (1, 2, 2, 599),
    (1, 3, 1, 899),
    (2, 4, 4, 399),
    (2, 5, 1, 1499),
    (3, 6, 2, 249),
    (3, 7, 3, 1099),
    (4, 8, 2, 199),
    (4, 9, 4, 349),
    (4, 10, 2, 499),
    (5, 1, 2, 1299),
    (5, 4, 2, 399),
]

ROW_COUNTS = {
    "suppliers": "SELECT COUNT(*) FROM suppliers",
    "products": "SELECT COUNT(*) FROM products",
    "sales": "SELECT COUNT(*) FROM sales",
    "sale_items": "SELECT COUNT(*) FROM sale_items",
    "stock_movements": "SELECT COUNT(*) FROM stock_movements",
}


def seed_database(connection):
    """Create tables and seed an empty database"""
    if connection.in_transaction:
        raise ValueError("Seed requires a connection with no active transaction.")
    connection.executescript(Path(__file__).with_name("schema.sql").read_text())
    with connection:
        if any(
            connection.execute(query).fetchone()[0] for query in ROW_COUNTS.values()
        ):
            raise ValueError(
                "Seed requires an empty database; existing data was left unchanged."
            )
        connection.executemany(
            "INSERT INTO suppliers (id, name) VALUES (?, ?)", SUPPLIERS
        )
        connection.executemany(
            """INSERT INTO products
               (id, sku, name, category, supplier_id, unit_price, quantity, reorder_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            PRODUCTS,
        )
        connection.executemany("INSERT INTO sales (id, sold_at) VALUES (?, ?)", SALES)
        connection.executemany(
            """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)""",
            SALE_ITEMS,
        )


def main():
    """Seed the configured database and print its table row counts."""
    with closing(connect()) as connection:
        seed_database(connection)
        for table, query in ROW_COUNTS.items():
            print(f"{table}: {connection.execute(query).fetchone()[0]}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as error:
        raise SystemExit(f"Could not seed database: {error}") from None
