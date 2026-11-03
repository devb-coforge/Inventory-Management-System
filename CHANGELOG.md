# Changelog

## 1.1.0 - 2026-11-03

- Show a startup banner with the number of products at or below their reorder level.

## 1.0.0 - 2026-11-03

- Add the SQLite schema, sample data, product management, filtered search, inventory reports, and transactional stock changes and sales.
- Add the terminal menu with filtered search, product operations, stock changes, sales, and all four reports.
- Validate numeric input and display friendly database errors; close the database on exit.
- Add SQLite backups with overwrite protection, integrity tests, and restore instructions.
- Add a pinned Docker image and a CI job that runs the tests inside it.
- Validate integer stock quantities and improve stock-operation error messages.
