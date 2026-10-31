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

Database setup, sample data, product operations, and filtered search are implemented. Reports, stock transactions, the terminal menu, and Docker support are planned.

See [PLAN.md](PLAN.md) for the implementation plan.

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

## Testing

Run the checks with:

```sh
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```
