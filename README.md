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

Database setup and sample data are implemented. Product operations, reports, stock transactions, the terminal menu, and Docker support are planned.

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
