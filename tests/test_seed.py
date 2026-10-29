from seed_db import main, seed_database


def test_seed_contains_required_rows(db):
    seed_database(db)
    counts = {
        "suppliers": db.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "sales": db.execute("SELECT COUNT(*) FROM sales").fetchone()[0],
        "sale_items": db.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0],
        "stock_movements": db.execute(
            "SELECT COUNT(*) FROM stock_movements"
        ).fetchone()[0],
    }
    assert counts == {
        "suppliers": 4,
        "products": 12,
        "sales": 5,
        "sale_items": 12,
        "stock_movements": 0,
    }
    assert (
        db.execute("SELECT COUNT(DISTINCT category) FROM products").fetchone()[0] >= 3
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM products WHERE quantity <= reorder_level"
        ).fetchone()[0]
        >= 2
    )
    assert (
        db.execute(
            """SELECT COUNT(*) FROM products p WHERE NOT EXISTS
           (SELECT 1 FROM sale_items si WHERE si.product_id = p.id)"""
        ).fetchone()[0]
        >= 2
    )
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_seed_script_creates_database_and_prints_counts(monkeypatch, tmp_path, capsys):
    path = tmp_path / "seed.db"
    monkeypatch.setenv("INVENTORY_DB", str(path))
    main()
    assert path.exists()
    assert capsys.readouterr().out.splitlines() == [
        "suppliers: 4",
        "products: 12",
        "sales: 5",
        "sale_items: 12",
        "stock_movements: 0",
    ]
