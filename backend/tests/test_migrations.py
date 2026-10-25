"""Gap 8: Alembic owns the schema, for new and pre-existing databases."""
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

import db.models  # noqa: F401  (registers tables)
from db.database import BACKEND_DIR, Base, async_database_url, sync_database_url
from helpers import override

USER_ID = "0123456789abcdef0123456789abcdef"
SUBJECT_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOPIC_ID = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


def test_fresh_database_matches_the_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    with override(DATABASE_URL=url):
        command.upgrade(_config(), "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    # SQLite can't add the quiz_sets.subject_id FK to an existing table (it is created on Postgres)
    diff = [d for d in diff if not (d[0] == "add_fk" and d[1].parent.name == "quiz_sets")]
    assert diff == []


def test_database_from_before_migrations_is_adopted_with_its_data(tmp_path):
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    with override(DATABASE_URL=url):
        command.upgrade(_config(), "0001")  # the same tables the old create_all startup made
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))  # i.e. never migrated
            connection.execute(text(f"INSERT INTO users (id, email, hashed_password) VALUES ('{USER_ID}', 'old@user.dev', 'x')"))
            connection.execute(text(f"INSERT INTO subjects (id, user_id, name) VALUES ('{SUBJECT_ID}', '{USER_ID}', 'Old subject')"))
            connection.execute(text(f"INSERT INTO topics (id, subject_id, title, index_order) VALUES ('{TOPIC_ID}', '{SUBJECT_ID}', 'T', 0)"))
            connection.execute(text(f"INSERT INTO quiz_sets (id, topic_id, quiz_type, questions) VALUES ('{'c' * 32}', '{TOPIC_ID}', 'mcq', '[]')"))

        command.upgrade(_config(), "head")

        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
            assert connection.execute(text("SELECT email FROM users")).scalar() == "old@user.dev"
            assert connection.execute(text("SELECT subject_id FROM quiz_sets")).scalar() == SUBJECT_ID  # backfilled
        engine.dispose()


def test_database_url_drivers():
    cases = {
        "sqlite:///./test.db": ("sqlite+aiosqlite:///./test.db", "sqlite:///./test.db"),
        "sqlite+aiosqlite:///./test.db": ("sqlite+aiosqlite:///./test.db", "sqlite:///./test.db"),
        "postgresql://u:p@db:5432/one01": ("postgresql+asyncpg://u:p@db:5432/one01", "postgresql+psycopg2://u:p@db:5432/one01"),
        "postgres://u:p@db/one01": ("postgresql+asyncpg://u:p@db/one01", "postgresql+psycopg2://u:p@db/one01"),
    }
    for raw, (expected_async, expected_sync) in cases.items():
        with override(DATABASE_URL=raw):
            assert (async_database_url(), sync_database_url()) == (expected_async, expected_sync), raw
