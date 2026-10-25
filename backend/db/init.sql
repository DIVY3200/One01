-- One01 database bootstrap (runs once when the Postgres container is first created).
-- The schema itself is managed by Alembic migrations in backend/migrations and is
-- applied automatically when the backend starts.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
