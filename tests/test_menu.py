import sqlite3
from contextlib import closing

import pytest

import main as menu
from inventory_db import connect, get_product
from seed_db import seed_database


@pytest.fixture
def seeded_db(db):
    seed_database(db)
    return db


def run_menu(monkeypatch, db, answers):
    answers = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    menu.run_menu(db)


def test_search_combines_filters_and_displays_money(seeded_db, monkeypatch, capsys):
    run_menu(monkeypatch, seeded_db, ["1", "forge", "Tools", "900", "y", "n", "0"])
    output = capsys.readouterr().out
    assert "Pliers" in output
    assert "Screwdriver" in output
    assert "Claw Hammer" not in output
    assert "8.99" in output
    assert "Forge Tools" in output


def test_search_blank_filters_and_no_results(seeded_db, monkeypatch, capsys):
    run_menu(monkeypatch, seeded_db, ["1", "no-match", "", "", "", "", "0"])
    assert "No results." in capsys.readouterr().out


def test_lookup_found_and_missing_product(seeded_db, monkeypatch, capsys):
    run_menu(monkeypatch, seeded_db, ["2", "1", "2", "999", "0"])
    output = capsys.readouterr().out
    assert "Claw Hammer" in output
    assert "12.99" in output
    assert "Forge Tools" in output
    assert "Product 999 was not found." in output


def test_add_product_and_restock(seeded_db, monkeypatch, capsys):
    run_menu(
        monkeypatch,
        seeded_db,
        ["3", "NEW", "New Tool", "Tools", "1", "29", "3", "1", "4", "13", "2", "0"],
    )
    product = get_product(seeded_db, 13)
    assert (product["unit_price"], product["quantity"]) == (29, 5)
    output = capsys.readouterr().out
    assert "Product added: 13" in output
    assert "Restocked product 13" in output


def test_sale_collects_multiple_lines_then_saves_once(seeded_db, monkeypatch, capsys):
    run_menu(monkeypatch, seeded_db, ["5", "1", "2", "2", "3", "", "0"])
    assert get_product(seeded_db, 1)["quantity"] == 18
    assert get_product(seeded_db, 2)["quantity"] == 27
    assert seeded_db.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 6
    assert "Sale recorded: 6" in capsys.readouterr().out


@pytest.mark.parametrize("second_line", [["7", "1"], ["999", "1"], ["1", "1"]])
def test_failed_sale_returns_to_menu_without_partial_writes(
    seeded_db, monkeypatch, capsys, second_line
):
    before = list(seeded_db.iterdump())
    run_menu(monkeypatch, seeded_db, ["5", "1", "2", *second_line, "", "0"])
    assert list(seeded_db.iterdump()) == before
    output = capsys.readouterr().out
    assert "Could not complete action:" in output
    assert "Goodbye." in output


def test_empty_sale_is_cancelled(seeded_db, monkeypatch, capsys):
    before = list(seeded_db.iterdump())
    run_menu(monkeypatch, seeded_db, ["5", "", "0"])
    assert list(seeded_db.iterdump()) == before
    assert "Sale cancelled." in capsys.readouterr().out


@pytest.mark.parametrize(
    "choice, expected",
    [("6", "574.35"), ("7", "Units Short"), ("8", "37.97"), ("9", "Hex Nut Pack")],
)
def test_reports_display_results(seeded_db, monkeypatch, capsys, choice, expected):
    run_menu(monkeypatch, seeded_db, [choice, "0"])
    assert expected in capsys.readouterr().out


def test_backup_menu_creates_a_readable_copy(seeded_db, monkeypatch, tmp_path, capsys):
    destination = tmp_path / "backup.db"
    run_menu(monkeypatch, seeded_db, ["10", str(destination), "0"])
    with closing(connect(destination)) as backup:
        assert list(backup.iterdump()) == list(seeded_db.iterdump())
    assert "Backup saved:" in capsys.readouterr().out


def test_bad_numeric_input_reprompts(seeded_db, monkeypatch, capsys):
    run_menu(
        monkeypatch,
        seeded_db,
        ["unknown", "2", "text", "1.5", "-1", "1", "0"],
    )
    output = capsys.readouterr().out
    assert "Choose a listed option." in output
    assert output.count("Enter a whole number") == 3
    assert "Claw Hammer" in output


@pytest.mark.parametrize(
    "answers, expected",
    [
        (
            ["3", "HAM-001", "Duplicate", "Tools", "1", "1", "0", "0"],
            "SKU already exists",
        ),
        (["3", "NEW", "New", "Tools", "999", "1", "0", "0"], "supplier"),
    ],
)
def test_constraint_errors_are_friendly_and_menu_continues(
    seeded_db, monkeypatch, capsys, answers, expected
):
    before = list(seeded_db.iterdump())
    run_menu(monkeypatch, seeded_db, [*answers, "0"])
    output = capsys.readouterr().out
    assert expected in output
    assert "Goodbye." in output
    assert list(seeded_db.iterdump()) == before


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_interrupted_sale_never_saves_partial_input(
    seeded_db, monkeypatch, capsys, error
):
    before = list(seeded_db.iterdump())
    answers = iter(["5", "1", "2"])

    def interrupted_input(prompt):
        try:
            return next(answers)
        except StopIteration:
            raise error from None

    monkeypatch.setattr("builtins.input", interrupted_input)
    menu.run_menu(seeded_db)
    assert "Goodbye." in capsys.readouterr().out
    assert list(seeded_db.iterdump()) == before


def test_database_errors_return_to_menu(db, monkeypatch, capsys):
    run_menu(monkeypatch, db, ["3", "NEW", "New", "Tools", "1", "1", "0", "0", "0"])
    assert "supplier" in capsys.readouterr().out


def test_operational_database_error_does_not_crash_menu(seeded_db, monkeypatch, capsys):
    def failed_report(connection):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(menu, "stock_value_by_supplier", failed_report)
    run_menu(monkeypatch, seeded_db, ["6", "0"])
    output = capsys.readouterr().out
    assert "Database error: database is locked" in output
    assert "Goodbye." in output


def test_backup_error_returns_to_menu(seeded_db, monkeypatch, tmp_path, capsys):
    destination = tmp_path / "existing.db"
    destination.write_bytes(b"keep")
    run_menu(monkeypatch, seeded_db, ["10", str(destination), "0"])
    assert "Could not complete action:" in capsys.readouterr().out
    assert destination.read_bytes() == b"keep"


def test_main_uses_configured_database_and_closes_it(monkeypatch, tmp_path, capsys):
    database = tmp_path / "inventory.db"
    connection = connect(database)
    seed_database(connection)
    monkeypatch.setenv("INVENTORY_DB", str(database))
    monkeypatch.setattr(menu, "connect", lambda: connection)
    monkeypatch.setattr("builtins.input", lambda prompt: "0")
    assert menu.main() is None
    assert "Goodbye." in capsys.readouterr().out
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")


def test_main_explains_uninitialized_database(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("INVENTORY_DB", str(tmp_path / "empty.db"))
    menu.main()
    assert "seed_db.py" in capsys.readouterr().out


def test_main_reports_database_open_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("INVENTORY_DB", str(tmp_path / "missing" / "inventory.db"))
    menu.main()
    assert "Database error:" in capsys.readouterr().out
