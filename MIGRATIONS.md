# Database Migrations with Alembic

This project uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations.
Alembic tracks every schema change and applies them incrementally — no manual SQL, no data loss.

## Setup (already done)

Alembic is initialized and the current schema is stamped as `head`.
The configuration lives in `alembic/env.py` and reads the database URL from `app/config.py`.

---

## Workflow for every schema change

### Step 1 — Edit the SQLAlchemy model

Add, remove, or modify a column in the relevant `models.py` file.

```python
# Example: app/analysis/models.py
salary_min = Column(Integer, nullable=True)
```

### Step 2 — Generate the migration

Alembic compares the Python models against the live database and generates a migration file.

```bash
.venv/bin/alembic revision --autogenerate -m "short_description_of_change"
```

A new file is created in `alembic/versions/`. **Always review it before applying** — Alembic
may miss renames or complex constraints, which you must fix manually.

### Step 3 — Apply the migration

```bash
.venv/bin/alembic upgrade head
```

---

## Useful commands

| Command | Description |
|---------|-------------|
| `alembic current` | Show the current migration revision applied to the DB |
| `alembic history` | List all migrations in order |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +1` | Apply the next migration only |
| `alembic downgrade -1` | Roll back the last migration |
| `alembic downgrade base` | Roll back all migrations (empty DB) |
| `alembic upgrade head --sql` | Print the SQL that would be executed, without applying it |

> Prefix commands with `.venv/bin/` if you are not inside the virtual environment.

---

## What Alembic may miss (review carefully)

- **Column renames** — detected as a drop + add; set `compare_type=True` or edit manually
- **Server defaults** — not always detected
- **Check constraints** — partially supported on SQLite

When in doubt, inspect the generated file in `alembic/versions/` and adjust the `upgrade()` /
`downgrade()` functions before running `upgrade head`.

---

## Example end-to-end

```bash
# 1. Add a column to the model
#    app/analysis/models.py → salary_min = Column(Integer, nullable=True)

# 2. Generate migration
.venv/bin/alembic revision --autogenerate -m "add_salary_min_to_analyses"

# 3. Review the generated file in alembic/versions/

# 4. Apply
.venv/bin/alembic upgrade head

# 5. Verify
.venv/bin/alembic current
```