# Inventory Management System

A Python terminal app for managing hardware-store products, searching inventory, recording stock changes and sales, running reports, and backing up a SQLite database. See [PLAN.md](PLAN.md) for the implementation plan.

## Setup and usage

Install uv and Python 3.13, then run:

```sh
uv sync --locked
uv run --locked python seed_db.py
uv run --locked python main.py
```

Seed once, before starting the menu. The database defaults to `inventory.db` beside the code. To choose another location, set `INVENTORY_DB` for both commands; its parent directory must exist.

Enter prices in whole cents (`1299` means 12.99). The menu displays money with two decimals. Blank search filters mean no restriction.

Seed output:

```text
suppliers: 4
products: 12
sales: 5
sale_items: 12
stock_movements: 0
```

## Testing

```sh
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Tests use fresh databases. CI runs these checks and builds the Docker image to run pytest inside it.

## Expected reports

On a fresh seed, stock value by supplier is:

```text
Forge Tools       574.35
Bright Electric   413.73
Fixings Depot     202.57
Flow Plumbing     132.47
```

Low stock contains Copper Pipe (stock 0, reorder level 5, short 5) and Wood Screw Pack (stock 5, reorder level 10, short 5). Never sold contains Bolt Pack and Hex Nut Pack.

Sales by product, using the prices saved in sale items:

```text
Product            Units  Revenue
Claw Hammer            3    37.97
Copper Pipe            3    32.97
LED Bulb               6    23.94
Extension Cable        1    14.99
Pipe Elbow             4    13.96
Screwdriver            2    11.98
Wood Screw Pack        2     9.98
Pliers                 1     8.99
Light Switch           2     4.98
Tap Washer Pack        2     3.98
Bolt Pack              0     0.00
Hex Nut Pack           0     0.00
```

The two zero-revenue products may appear in either order.

## Failed-sale example

With a freshly seeded connection `db`, this call sells one hammer before failing on an out-of-stock pipe:

```python
record_sale(db, [(1, 1), (7, 1)])
```

Verified output; stock entries are `(product_id, quantity)`:

```text
Before stock: [(1, 20), (7, 0)]; sales/items/movements: (5, 12, 0)
Insufficient stock: Product 7 has 0 units; cannot remove 1.
After stock: [(1, 20), (7, 0)]; sales/items/movements: (5, 12, 0)
```

The transaction rolls back the entire sale, including the hammer's stock change.

## Docker

```sh
docker build -t inventory-management:dev .
docker volume create inventory-data
docker run --rm -v inventory-data:/data inventory-management:dev .venv/bin/python seed_db.py
docker run --rm -it -v inventory-data:/data inventory-management:dev
```

The image pins Python to `3.13.7-slim-bookworm`. Its default database is `/data/inventory.db`. Seed the volume once and keep using that volume when replacing containers. Override the path with `-e INVENTORY_DB=/data/store.db` if needed.

Run container tests with:

```sh
docker run --rm inventory-management:dev .venv/bin/pytest -q
```

Actual build output (excerpt):

```text
#16 naming to docker.io/library/inventory-management:dev done
#16 unpacking to docker.io/library/inventory-management:dev 0.1s done
#16 DONE 0.6s
```

Persistence was verified using the separate volume `inventory-menu-check-20261102`: a menu session restocked product 1 by two units, then a replacement container read stock 22.

## Backup and restore

Menu option 10 uses SQLite's backup API. Choose a new file, such as `inventory-backup.db`, in an existing directory. In Docker, use a path inside the volume, such as `/data/backup.db`.

The backup test checks `PRAGMA integrity_check`, foreign keys, matching row counts, and matching data:

```sh
uv run --locked pytest tests/test_backup.py -q
```

Seed output:

```text
Persisted stock: 22
Backup integrity: ok
suppliers: 4 / 4
products: 12 / 12
sales: 5 / 5
sale_items: 12 / 12
stock_movements: 1 / 1
Restored stock: 22
```

To restore locally, stop the app, copy the backup to a new filename, and use that file:

```sh
cp inventory-backup.db restored.db
INVENTORY_DB=restored.db uv run --locked python main.py
```

For Docker, copy the backup within the volume and restart with `-e INVENTORY_DB=/data/restored.db` and the same volume.

## Releases

The low-stock startup banner and releases 1.0.0/1.1.0 are pending. After both images exist, rollback means stopping the 1.1.0 container and starting 1.0.0 with the same volume. Actual version-to-version rollback output will be added when verified.

## Self-review

The menu calls the database functions, keeping input handling separate from SQL. SQLite constraints enforce the product rules, and each stock operation uses one transaction. Helpers do not commit separately. Failed-sale tests verify that stock, sale items, and movement history remain unchanged after an error. Connections are closed when the menu exits.

If rebuilding this, I would use a clearer file structure. Schema, products, search, reports, stock changes, sales, and backup all live in one file, `inventory_db.py`, while the menu lives in `main.py`. Splitting those concerns into separate modules would make each part easier to follow. I would also decide on a consistent report display earlier and keep the input prompts shorter. The current display uses returned column names and values, which is sufficient for this assignment but can be wide. Entering prices as whole cents keeps validation straightforward and avoids rounding during input.
I would ask a reviewer to check the database error messages, particularly how duplicate SKUs and unknown suppliers are translated for the menu.