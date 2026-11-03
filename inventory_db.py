import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def connect(db_path=None):
    """Open a database with foreign keys enabled."""
    if db_path is None:
        db_path = os.environ.get("INVENTORY_DB") or Path(__file__).with_name(
            "inventory.db"
        )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def add_product(
    connection, sku, name, category, supplier_id, unit_price, quantity, reorder_level
):
    """Save a product and return its ID; invalid fields raise IntegrityError."""
    with connection:
        cursor = connection.execute(
            """INSERT INTO products
               (sku, name, category, supplier_id, unit_price, quantity, reorder_level)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sku, name, category, supplier_id, unit_price, quantity, reorder_level),
        )
    return cursor.lastrowid


def get_product(connection, product_id):
    """Return a product with its supplier name, or None when it is missing."""
    return connection.execute(
        """SELECT p.*, s.name AS supplier_name
           FROM products p JOIN suppliers s ON s.id = p.supplier_id
           WHERE p.id = ?""",
        (product_id,),
    ).fetchone()


def change_price(connection, product_id, unit_price):
    """Save a price in cents; return False if the product does not exist."""
    with connection:
        cursor = connection.execute(
            "UPDATE products SET unit_price = ? WHERE id = ?",
            (unit_price, product_id),
        )
    return cursor.rowcount > 0


def delete_product(connection, product_id):
    """Delete a product, returning False if missing; history blocks deletion."""
    with connection:
        cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    return cursor.rowcount > 0


def search_products(
    connection,
    text,
    category=None,
    max_price=None,
    in_stock_only=False,
    low_stock_only=False,
):
    """Find literal text in names, SKUs, or suppliers with combinable filters.

    Empty text matches all products. Prices are cents, category matches exactly,
    and SQLite LIKE provides case-insensitive matching for ASCII text.
    """
    escaped_text = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped_text}%"
    conditions = [
        """(p.name LIKE ? ESCAPE '\\'
            OR p.sku LIKE ? ESCAPE '\\'
            OR s.name LIKE ? ESCAPE '\\')"""
    ]
    parameters = [pattern, pattern, pattern]
    if category is not None:
        conditions.append("p.category = ?")
        parameters.append(category)
    if max_price is not None:
        conditions.append("p.unit_price <= ?")
        parameters.append(max_price)
    if in_stock_only:
        conditions.append("p.quantity > 0")
    if low_stock_only:
        conditions.append("p.quantity <= p.reorder_level")
    query = (
        "SELECT p.*, s.name AS supplier_name "
        "FROM products p JOIN suppliers s ON s.id = p.supplier_id WHERE "
        + " AND ".join(conditions)
        + " ORDER BY p.name, p.id"
    )
    return connection.execute(query, parameters).fetchall()


def stock_value_by_supplier(connection):
    """Return each supplier's current stock value in cents, highest first."""
    return connection.execute(
        """SELECT s.id AS supplier_id, s.name AS supplier_name,
                  COALESCE(SUM(p.unit_price * p.quantity), 0) AS stock_value
           FROM suppliers s LEFT JOIN products p ON p.supplier_id = s.id
           GROUP BY s.id, s.name
           ORDER BY stock_value DESC"""
    ).fetchall()


def low_stock(connection):
    """Return products at or below reorder level with units_short, sorted by name."""
    return connection.execute(
        """SELECT p.*, p.reorder_level - p.quantity AS units_short
           FROM products p
           WHERE p.quantity <= p.reorder_level
           ORDER BY p.name"""
    ).fetchall()


def sales_by_product(connection):
    """Return product IDs, SKUs, names, units_sold, and revenue in cents."""
    return connection.execute(
        """SELECT p.id, p.sku, p.name,
                  COALESCE(SUM(si.quantity), 0) AS units_sold,
                  COALESCE(SUM(si.quantity * si.unit_price), 0) AS revenue
           FROM products p LEFT JOIN sale_items si ON si.product_id = p.id
           GROUP BY p.id, p.sku, p.name
           ORDER BY revenue DESC"""
    ).fetchall()


def never_sold(connection):
    """Return products without any sale items, sorted by product name."""
    return connection.execute(
        """SELECT p.* FROM products p
           WHERE NOT EXISTS (SELECT 1 FROM sale_items si WHERE si.product_id = p.id)
           ORDER BY p.name"""
    ).fetchall()


def _change_stock(connection, product_id, change, reason, timestamp):
    """Write stock and its movement together"""
    product = connection.execute(
        "SELECT quantity, unit_price FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        raise ValueError(f"Product {product_id} does not exist.")
    if product["quantity"] + change < 0:
        raise ValueError(
            f"Insufficient stock: Product {product_id} has {product['quantity']} units; "
            f"cannot remove {-change}."
        )
    connection.execute(
        "UPDATE products SET quantity = quantity + ? WHERE id = ?",
        (change, product_id),
    )
    connection.execute(
        """INSERT INTO stock_movements (product_id, change, reason, occurred_at)
           VALUES (?, ?, ?, ?)""",
        (product_id, change, reason, timestamp),
    )
    return product


def restock(connection, product_id, quantity, timestamp=None):
    """Increase stock by a positive amount and log a restock movement."""
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("Restock quantity must be a positive integer.")
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()
    with connection:
        _change_stock(connection, product_id, quantity, "restock", timestamp)


def adjust_stock(connection, product_id, change, timestamp=None):
    """Apply a signed change and log it; refuse a negative resulting stock."""
    if type(change) is not int:
        raise ValueError("Stock adjustment must be an integer.")
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()
    with connection:
        _change_stock(connection, product_id, change, "adjustment", timestamp)


def record_sale(connection, items, timestamp=None):
    """Record a list of product/quantity pairs atomically and return the sale ID."""
    if not items:
        raise ValueError("A sale must contain at least one product.")
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()
    with connection:
        cursor = connection.execute(
            "INSERT INTO sales (sold_at) VALUES (?)", (timestamp,)
        )
        sale_id = cursor.lastrowid
        seen = set()
        for product_id, quantity in items:
            if type(quantity) is not int or quantity <= 0:
                raise ValueError("Sale quantity must be a positive integer.")
            if product_id in seen:
                raise ValueError(
                    f"Duplicate product: Product {product_id} appears more than once in the sale."
                )
            seen.add(product_id)
            product = _change_stock(
                connection, product_id, -quantity, "sale", timestamp
            )
            connection.execute(
                """INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                   VALUES (?, ?, ?, ?)""",
                (sale_id, product_id, quantity, product["unit_price"]),
            )
    return sale_id


def backup_database(connection, destination):
    """Copy the database to a new file using SQLite's backup API."""
    if connection.in_transaction:
        raise ValueError("Finish the current transaction before creating a backup.")
    if Path(destination).exists():
        raise FileExistsError("Choose a new backup file; that file already exists.")
    with closing(connect(destination)) as backup:
        connection.backup(backup)
