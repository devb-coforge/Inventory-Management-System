import os
import sqlite3
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
