# Project Architecture

This application is built with **FastAPI** for the HTTP layer and uses
**SQLAlchemy** models with **Alembic** for schema migrations. Asynchronous
endpoints interact with a PostgreSQL database, and background tasks run via
`worker.py`.

## Main components

- `app/api` – REST API routes and dependency wiring  
- `app/services` – business logic and third-party integrations  
- `app/db/models` – SQLAlchemy ORM models  
- `alembic` – database migration scripts  

API routes must return data via the helper `success_response()` from
`app.utils.response_wrapper` so JSON envelopes stay consistent across the
codebase.

See `architecture.puml` for a high-level diagram that can be rendered with
PlantUML.
