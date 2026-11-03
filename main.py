import sqlite3
from contextlib import closing

from inventory_db import (
    add_product,
    backup_database,
    connect,
    get_product,
    low_stock,
    never_sold,
    record_sale,
    restock,
    sales_by_product,
    search_products,
    stock_value_by_supplier,
    low_stock_product_count,
)

MENU = """
Inventory Management
 1. Search products with filters
 2. Look up a product
 3. Add a product
 4. Restock a product
 5. Record a sale
 6. Stock value by supplier
 7. Low stock report
 8. Sales by product
 9. Never sold report
10. Back up database
 0. Exit
"""
MONEY_COLUMNS = {"unit_price", "stock_value", "revenue"}


def _required_text(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field is required.")


def _integer(prompt, minimum=1, optional=False):
    while True:
        value = input(prompt).strip()
        if optional and not value:
            return None
        try:
            number = int(value)
            if number >= minimum:
                return number
        except ValueError:
            pass
        print(f"Enter a whole number of at least {minimum}.")


def _yes_no(prompt):
    while True:
        value = input(prompt).strip().lower()
        if value in {"y", "yes"}:
            return True
        if value in {"", "n", "no"}:
            return False
        print("Enter y or n.")


def _money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def _print_rows(rows):
    if not rows:
        print("No results.")
        return
    columns = rows[0].keys()
    print(" | ".join(column.replace("_", " ").title() for column in columns))
    for row in rows:
        print(
            " | ".join(
                _money(row[column]) if column in MONEY_COLUMNS else str(row[column])
                for column in columns
            )
        )


def _search(connection):
    text = input("Search text (blank for all): ").strip()
    category = input("Category (blank for any): ").strip() or None
    max_price = _integer(
        "Maximum price in cents (blank for any): ", minimum=0, optional=True
    )
    in_stock = _yes_no("In stock only? [y/N]: ")
    low_only = _yes_no("Low stock only? [y/N]: ")
    rows = search_products(connection, text, category, max_price, in_stock, low_only)
    _print_rows(rows)


def _lookup(connection):
    product_id = _integer("Product ID: ")
    product = get_product(connection, product_id)
    if product is None:
        print(f"Product {product_id} was not found.")
    else:
        _print_rows([product])


def _add(connection):
    sku = _required_text("SKU: ")
    name = _required_text("Name: ")
    category = _required_text("Category: ")
    suppliers = connection.execute(
        "SELECT id, name FROM suppliers ORDER BY name"
    ).fetchall()
    _print_rows(suppliers)
    supplier_id = _integer("Supplier ID: ")
    price = _integer("Unit price in cents: ", minimum=0)
    quantity = _integer("Initial stock: ", minimum=0)
    reorder = _integer("Reorder level: ", minimum=0)
    product_id = add_product(
        connection, sku, name, category, supplier_id, price, quantity, reorder
    )
    print(f"Product added: {product_id}")


def _restock(connection):
    product_id = _integer("Product ID: ")
    quantity = _integer("Quantity to add: ")
    restock(connection, product_id, quantity)
    print(f"Restocked product {product_id} by {quantity} units.")


def _sale(connection):
    print(
        "Enter each product once. Leave Product ID blank to finish or cancel an empty sale."
    )
    items = []
    while True:
        product_id = _integer("Product ID (blank to finish): ", optional=True)
        if product_id is None:
            break
        items.append((product_id, _integer("Quantity: ")))
    if not items:
        print("Sale cancelled.")
        return
    sale_id = record_sale(connection, items)
    print(f"Sale recorded: {sale_id}")


def run_menu(connection):
    """Run the required menu actions, reporting errors without exiting."""
    actions = {
        "1": _search,
        "2": _lookup,
        "3": _add,
        "4": _restock,
        "5": _sale,
    }
    reports = {
        "6": stock_value_by_supplier,
        "7": low_stock,
        "8": sales_by_product,
        "9": never_sold,
    }
    try:
        while True:
            print(MENU)
            choice = input("Choose an option: ").strip()
            if choice == "0":
                break
            try:
                if choice in actions:
                    actions[choice](connection)
                elif choice in reports:
                    _print_rows(reports[choice](connection))
                elif choice == "10":
                    destination = _required_text("Backup file path (new file): ")
                    backup_database(connection, destination)
                    print(f"Backup saved: {destination}")
                else:
                    print("Choose a listed option.")
            except sqlite3.IntegrityError as error:
                if "products.sku" in str(error):
                    print("That SKU already exists. Use a unique SKU.")
                elif "FOREIGN KEY" in str(error):
                    print("Unknown supplier. Choose an existing supplier ID.")
                else:
                    print(f"Database rejected the change: {error}")
            except sqlite3.Error as error:
                print(f"Database error: {error}")
            except (ValueError, OSError) as error:
                print(f"Could not complete action: {error}")
            except OverflowError:
                print("That number is too large for the database.")
    except (EOFError, KeyboardInterrupt):
        print()
    print("Goodbye.")

def print_menu_low_stock(connection):
    print("=" * 100)
    print(f"Low Stock Report: {low_stock_product_count(connection)} products below reorder level")
    print("=" * 100)

def main():
    """Open the configured database and close it when the menu exits."""
    try:
        with closing(connect()) as connection:
            connection.execute("SELECT 1 FROM products LIMIT 1")
            print_menu_low_stock(connection)
            run_menu(connection)
    except sqlite3.Error as error:
        print(f"Database error: {error}. Check INVENTORY_DB and run seed_db.py first.")


if __name__ == "__main__":
    main()
