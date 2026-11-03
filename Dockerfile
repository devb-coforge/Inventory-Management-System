FROM python:3.13.7-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    INVENTORY_DB=/data/inventory.db
WORKDIR /app

# Install dependencies before copying application code to preserve this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-cache
COPY inventory_db.py main.py seed_db.py schema.sql ./
COPY conftest.py ./
COPY tests/ ./tests/
RUN mkdir /data

CMD [".venv/bin/python", "main.py"]
