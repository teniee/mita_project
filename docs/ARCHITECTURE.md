# Project Architecture

This application is built with **FastAPI** for the HTTP layer and uses
**SQLAlchemy** models with **Alembic** for schema migrations. Asynchronous
endpoints interact with a PostgreSQL database and background tasks run via
`worker.py`.

Main components:

- `app/api` – REST API routes and dependency wiring
- `app/services` – business logic and integrations
- `app/db/models` – SQLAlchemy ORM models
- `alembic` – database migration scripts

API routes should return data using the helper
`success_response()` from `app.utils.response_wrapper` so responses are
consistent across the codebase.

See `architecture.puml` for a high-level diagram that you can render with PlantUML.
