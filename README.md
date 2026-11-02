# Inventory Management System

A Python terminal app for managing a hardware store's inventory with SQLite.

## Planned features

- Manage products and suppliers.
- Search products with filters.
- Track restocks, adjustments, and sales.
- View stock value, low-stock, sales, and never-sold reports.
- Back up and restore the database.
- Run with Docker and persistent storage.

## Status

Database setup, sample data, product operations, filtered search, reports, and stock transactions are implemented. The terminal menu, backup support, and Docker support are planned.

See [PLAN.md](PLAN.md) for the implementation plan.

## Code layout

- `inventory_db.py`: opens SQLite connections and provides product operations, search, reports, stock changes, and sales.
- `seed_db.py`: creates the schema from `schema.sql` and loads sample data.
- `tests/`: tests each feature against the real database schema.

## Setup

Install uv and use Python 3.13. The project uses SQLite from the Python standard library.

```sh
uv sync --locked
```

## Create the sample database

```sh
uv run --locked python seed_db.py
```

The database defaults to `inventory.db` beside the code. Set `INVENTORY_DB` to use another location; its parent directory must already exist.

```sh
INVENTORY_DB=/tmp/inventory-demo.db uv run --locked python seed_db.py
```

Tests use a fresh in-memory database per test, with a temporary file for the seed command check. GitHub Actions runs these checks on pull requests and pushes to main.

## Products and search

The functions in `inventory_db.py` accept a connection from `connect()`:

- `add_product()` returns the new product ID. Prices are whole cents.
- `get_product()` returns a named row including `supplier_name`, or `None` for a missing ID.
- `change_price()` and `delete_product()` return whether a product was found. Database constraints reject invalid values and prevent deleting products with sales or stock movement history, raising `sqlite3.IntegrityError`.
- `search_products()` returns named rows sorted by product name. Text matches part of the name, SKU, or supplier name, ignoring ASCII case. Empty text lists all products; `%`, `_`, and backslashes are treated literally. Optional filters combine: exact category, inclusive maximum price in cents, positive stock, and stock at or below the reorder level.

## Reports

All 4 functions in `inventory_db.py` accept a connection and return lists of named rows. They leave the database and any pending transaction unchanged. Money values are integer cents.

- `stock_value_by_supplier()` returns `supplier_id`, `supplier_name`, and `stock_value` (current unit price × current quantity). Suppliers without products have zero value. Results sort by value descending; suppliers with the same name remain separate.
- `low_stock()` returns all product fields plus `units_short` (reorder level minus quantity) for products at or below their reorder level. A product exactly at its reorder level has zero units short.
- `sales_by_product()` returns product `id`, `sku`, `name`, `units_sold`, and `revenue`. Revenue uses prices saved in sale items, so later price changes do not rewrite history. Unsold products have zero units sold and revenue. Results sort by revenue descending.
- `never_sold()` returns all product fields for products with no sale items. A sale at zero price still counts as a sale. This report and the low-stock report sort by product name.

## Stock changes and sales

These functions in `inventory_db.py` accept a connection from `connect()`:

- `restock(connection, product_id, quantity, timestamp=None)` increases stock by a positive integer and records a `restock` movement. Returns `None`.
- `adjust_stock(connection, product_id, change, timestamp=None)` applies a signed integer change and records an `adjustment` movement. Zero is allowed and logged. Returns `None`.
- `record_sale(connection, items, timestamp=None)` accepts a list of `(product_id, quantity)` pairs and returns the new sale ID. It saves each item's current price in cents, reduces stock, and records negative `sale` movements. Later price changes leave this history intact.

Invalid amounts, missing products, insufficient stock, and duplicate sale products raise `ValueError` with an explanatory message. A sale cannot be empty. Database constraints enforce integer stock and sale quantities, nonnegative stock, and valid relationships.

Each operation uses one `with connection:` block to commit all its writes together or undo them all on failure. Timestamps default to the current UTC time in ISO 8601 format; supplied timestamps are stored as given. All writes in a sale share one timestamp.

Run this Python example with `uv run --locked python` to try a successful sale followed by a failed sale in a disposable database:

```python
from contextlib import closing

from inventory_db import (
    adjust_stock,
    connect,
    record_sale,
    restock,
)
from seed_db import seed_database


def show_state(connection, label):
    stock = connection.execute(
        "SELECT id, quantity FROM products WHERE id IN (1, 7) ORDER BY id"
    ).fetchall()
    counts = connection.execute(
        """SELECT (SELECT COUNT(*) FROM sales),
                  (SELECT COUNT(*) FROM sale_items),
                  (SELECT COUNT(*) FROM stock_movements)"""
    ).fetchone()
    print(f"{label} stock:", [tuple(row) for row in stock])
    print(f"{label} sales/items/movements:", tuple(counts))


with closing(connect(":memory:")) as connection:
    seed_database(connection)
    restock(connection, 7, 6)
    adjust_stock(connection, 7, -1)
    sale_id = record_sale(connection, [(1, 2), (7, 2)])
    print(f"Sale recorded: {sale_id}")

    show_state(connection, "Before")
    before = list(connection.iterdump())
    try:
        record_sale(connection, [(1, 1), (7, 4)])
    except ValueError as error:
        print(f"Sale rejected: {error}")
    assert list(connection.iterdump()) == before
    show_state(connection, "After")
```

Verified output:

```text
Sale recorded: 6
Before stock: [(1, 18), (7, 3)]
Before sales/items/movements: (6, 14, 4)
Sale rejected: Product 7 has 3 units; cannot remove 4.
After stock: [(1, 18), (7, 3)]
After sales/items/movements: (6, 14, 4)
```

The failed sale leaves no sale header, items, stock changes, or movements, including for the first product in the sale.

## Testing

Run the checks with:

```sh
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Stock and sales tests cover positive restocks, signed adjustments, current-price sales, fixed and default timestamps, and complete rollback for invalid sales or database write failures. Run the checks above to verify the results.

Implementation review: each stock operation uses one `with connection:` transaction, and no helper commits independently. Existing schema constraints protect stock and history; this feature needs no schema migration.
