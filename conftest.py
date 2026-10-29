from contextlib import closing
from pathlib import Path

import pytest

from inventory_db import connect


@pytest.fixture
def db():
    """Create an empty in-memory database with the real schema."""
    with closing(connect(":memory:")) as connection:
        schema = Path(__file__).with_name("schema.sql").read_text()
        connection.executescript(schema)
        yield connection
