import asyncio
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from utils.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _normalized_url() -> str:
    url = settings.DATABASE_URL.strip()
    if url.startswith("postgres://"):  # Heroku/Render style
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _asyncpg_options(url: str) -> str:
    """Hosted Postgres URLs (Neon, Supabase) use libpq options that asyncpg rejects:
    it takes ssl=require instead of sslmode=require and has no channel_binding."""
    parsed = make_url(url)
    query = dict(parsed.query)
    if "sslmode" in query:
        query["ssl"] = query.pop("sslmode")
    query.pop("channel_binding", None)
    return parsed.set(query=query).render_as_string(hide_password=False)


def async_database_url() -> str:
    """DATABASE_URL with the async driver the app runs on (aiosqlite / asyncpg)."""
    url = _normalized_url()
    if url.startswith("sqlite:"):
        return "sqlite+aiosqlite:" + url[len("sqlite:"):]
    if url.startswith("postgresql:"):
        url = "postgresql+asyncpg:" + url[len("postgresql:"):]
    if url.startswith("postgresql+asyncpg:"):
        return _asyncpg_options(url)
    return url


def sync_database_url() -> str:
    """DATABASE_URL with a sync driver, used by Alembic migrations."""
    url = _normalized_url()
    if url.startswith("sqlite+aiosqlite:"):
        return "sqlite:" + url[len("sqlite+aiosqlite:"):]
    if url.startswith("postgresql+asyncpg:"):
        return "postgresql+psycopg2:" + url[len("postgresql+asyncpg:"):]
    if url.startswith("postgresql:"):
        return "postgresql+psycopg2:" + url[len("postgresql:"):]
    return url


engine = create_async_engine(
    async_database_url(),
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        # SQLite ignores ON DELETE CASCADE unless foreign keys are enabled per connection.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def run_migrations() -> None:
    """Upgrade the schema to the latest Alembic revision.

    The baseline migration only creates tables that are missing, so databases
    created before migrations existed are adopted without losing data.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["configure_logger"] = False  # keep the app's logging setup
    command.upgrade(config, "head")


async def init_db():
    """Apply database migrations (creates the schema on a fresh database)."""
    await asyncio.to_thread(run_migrations)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
