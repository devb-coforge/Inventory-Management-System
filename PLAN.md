# Implementation Plan

## Database

- `suppliers`: supplier ID and required name. Stores supplier details.
- `products`: product ID, unique required SKU, name, category, supplier ID, unit price in cents, stock quantity, and reorder level. Required fields cannot be null; price, stock, and reorder level cannot be negative.
- `sales`: sale ID and required timestamp. Groups items purchased together.
- `sale_items`: item ID, sale ID, product ID, positive quantity, and nonnegative price in cents. Saves the price charged at the time of sale. Each product appears once per sale.
- `stock_movements`: movement ID, product ID, signed quantity change, reason, and timestamp. Reasons are limited to restock, adjustment, or sale.

A supplier has many products. A sale has many sale items. Each sale item belongs to a product. Each stock movement belongs to a product. Foreign keys protect these relationships and prevent deleting products with sales history.

Use STRICT tables, enable foreign keys on every connection, and make schema creation safe to repeat. Add an index on `sale_items.product_id` for sales lookups. Use placeholders for all supplied values.

## Sample data

Create 4 suppliers, 12 products across at least 3 categories, and 5 sales with 12 sale items total. Include at least 2 never-sold products and 2 products at or below their reorder level. Start with no stock movements.

The seed script will create the schema, insert sample data using placeholders and executemany, and print each table's row count.

## Public functions

Database functions accept a connection so tests can use an in-memory database. Prices are integer cents. Report and search functions return rows readable by column name.

- `connect(db_path=None)`: return a connection with foreign keys enabled and named rows. Resolve the default path from INVENTORY_DB or a file beside the code.
- `seed_database(connection)`: create the schema and load sample data; return nothing.
- `add_product(connection, sku, name, category, supplier_id, unit_price, quantity, reorder_level)`: return the new product ID.
- `get_product(connection, product_id)`: return a product row with its supplier name, or None.
- `change_price(connection, product_id, unit_price)`: return whether a product was updated.
- `delete_product(connection, product_id)`: return whether a product was deleted; reject products with sales history.
- `search_products(connection, text, category=None, max_price=None, in_stock_only=False, low_stock_only=False)`: return matching products sorted by name.
- `stock_value_by_supplier(connection)`: return supplier names and stock values, highest value first.
- `low_stock(connection)`: return products at or below their reorder level and the units short.
- `sales_by_product(connection)`: return each product's units sold and revenue, highest revenue first.
- `never_sold(connection)`: return products with no sale items.
- `restock(connection, product_id, quantity, timestamp=None)`: increase stock and log a movement; return nothing.
- `adjust_stock(connection, product_id, change, timestamp=None)`: adjust stock and log a movement; return nothing.
- `record_sale(connection, items, timestamp=None)`: accept product ID and quantity pairs; return the new sale ID.
- `backup_database(connection, destination)`: create a backup using SQLite's backup function; return nothing.
- `main()`: run the terminal menu; return nothing.

Invalid operations raise specific errors that the menu translates into friendly messages. Stock operations default to the current time when no timestamp is supplied.

## Transactions

Each stock operation uses one transaction. Helpers inside it never commit independently.

- Restock: require a positive amount and an existing product, increase stock, and insert a restock movement. Undo both writes if either fails.
- Adjust: check the product and resulting stock, update stock, and insert an adjustment movement. Reject negative resulting stock and undo all writes on failure.
- Sale: reject empty input, nonpositive quantities, and duplicate products. Create the sale, check each product and available stock, save each line at its current price, reduce stock, and insert a negative sale movement. Any failure undoes the sale, all items, stock updates, and movements.

Close connections with contextlib.closing and catch specific exceptions.

## Build order

Write tests before each feature. Use a fresh in-memory database per test and at least 23 tests overall. Run pytest and Ruff in CI before merging each PR.

1. `feature/database-and-seed`: schema, connection helper, seed data, and CI setup.
2. `feature/products-and-search`: product operations, joined lookup, and safe filtered search.
3. `feature/reports`: four reports with known expected results.
4. `feature/stock-and-sales`: atomic stock operations and rollback tests.
5. `feature/menu-and-container`: input handling, backup, Docker, and container tests in CI.
6. `feature/low-stock-banner`: startup banner showing the number of low-stock products.

Use a separate PR for each branch, describe the changes and testing, merge after CI passes, and delete the branch afterward.

## Releases and documentation

- Release 1.0.0 after the menu and container are ready, with Git tag v1.0.0 and Docker image tag 1.0.0.
- Add the low-stock banner, then release Git tag v1.1.0 and Docker image tag 1.1.0.
- Keep an entry for each version in CHANGELOG.md.
- Pin the Python image version and store the database in a persistent Docker volume.
- Add a docker-build CI job that builds the image and runs tests inside it.
- Verify persistence across containers and rollback from 1.1.0 to 1.0.0 with the same data.
- Verify backups with PRAGMA integrity_check and matching row counts; document restoration.
- Add setup and usage instructions, expected report results, a failed-sale example, real verification output, and a short self-review to the README as the work is completed.
