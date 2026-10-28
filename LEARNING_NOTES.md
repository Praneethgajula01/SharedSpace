# SharedSpace — Learning Notes

## Step 1: Environment & Project Scaffolding
- Virtual environments isolate Python packages so our project dependencies don't clash with system-wide packages.
- `.env` files keep secrets and database credentials local and out of Git via `.gitignore`.
- Setting a flexible `DATABASE_URL` abstraction lets our code seamlessly connect to SQLite for local tests and PostgreSQL for production.
