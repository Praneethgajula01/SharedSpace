# SharedSpace — Learning Notes

## Step 1: Environment & Project Scaffolding
- Virtual environments isolate Python packages so our project dependencies don't clash with system-wide packages.
- `.env` files keep secrets and database credentials local and out of Git via `.gitignore`.
- Setting a flexible `DATABASE_URL` abstraction lets our code seamlessly connect to SQLite for local tests and PostgreSQL for production.

## Step 2: Database Engine & Session Management
- SQLAlchemy translates Python objects to SQL commands, allowing our codebase to switch between SQLite and PostgreSQL without code changes.
- In SQLite, foreign keys are turned off by default; we enable them using an engine connect listener with `PRAGMA foreign_keys=ON`.
- Context managers (`with get_db_session() as session:`) guarantee that database transactions commit on success, roll back on errors, and always close cleanly.
