import sqlite3
from contextlib import closing

import pytest

from inventory_db import backup_database, connect, restock
from seed_db import ROW_COUNTS, seed_database


def test_backup_preserves_all_data_and_passes_integrity_check(db, tmp_path):
    seed_database(db)
    restock(db, 1, 3)
    before = list(db.iterdump())
    destination = tmp_path / "backup.db"

    assert backup_database(db, destination) is None

    with closing(connect(destination)) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not backup.execute("PRAGMA foreign_key_check").fetchall()
        assert list(backup.iterdump()) == before
        for query in ROW_COUNTS.values():
            assert (
                backup.execute(query).fetchone()[0] == db.execute(query).fetchone()[0]
            )
    assert list(db.iterdump()) == before
    assert not db.in_transaction


def test_backup_refuses_to_overwrite_an_existing_file(db, tmp_path):
    destination = tmp_path / "existing.db"
    destination.write_bytes(b"keep this file")
    with pytest.raises(FileExistsError):
        backup_database(db, destination)
    assert destination.read_bytes() == b"keep this file"


def test_backup_cannot_target_the_live_database(tmp_path):
    destination = tmp_path / "live.db"
    with closing(connect(destination)) as db:
        seed_database(db)
        before = list(db.iterdump())
        with pytest.raises(FileExistsError):
            backup_database(db, destination)
        assert list(db.iterdump()) == before


def test_backup_rejects_pending_transaction_without_committing(db, tmp_path):
    destination = tmp_path / "backup.db"
    db.execute("INSERT INTO suppliers (name) VALUES (?)", ("Pending",))
    with pytest.raises(ValueError, match="transaction"):
        backup_database(db, destination)
    assert db.in_transaction
    assert not destination.exists()


def test_backup_missing_parent_reports_error(db, tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        backup_database(db, tmp_path / "missing" / "backup.db")
