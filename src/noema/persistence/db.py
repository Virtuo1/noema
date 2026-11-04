"""Database engine, SQLite connection pragmas, and session management."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from noema.config import DEFAULT_OWNER_DISPLAY_NAME, DEFAULT_OWNER_USER_ID, get_settings


class Base(DeclarativeBase):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_id(prefix: str = "") -> str:
    uid = str(uuid4())
    return f"{prefix}_{uid}" if prefix else uid


def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()


_engine_cache: dict[str, Engine] = {}
_sessionmaker_cache: dict[str, sessionmaker[Session]] = {}


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    if url not in _engine_cache:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            file_path = url.replace("sqlite:///", "", 1)
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(url, connect_args=connect_args, future=True)
        if url.startswith("sqlite"):
            event.listen(engine, "connect", _configure_sqlite_connection)
        _engine_cache[url] = engine
        _sessionmaker_cache[url] = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _engine_cache[url]


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_settings().database_url
    get_engine(url)
    return _sessionmaker_cache[url]


@contextmanager
def session_scope(database_url: str | None = None) -> Generator[Session, None, None]:
    factory = get_session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_fts_and_local_owner(engine: Engine) -> None:
    """Ensure FTS5 virtual table and the default local principal exist."""
    from noema.persistence.models import AISettingsModel, AppUserModel

    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            fk_status = conn.execute(text("PRAGMA foreign_keys;")).scalar()
            if fk_status != 1:
                raise RuntimeError("SQLite foreign_keys pragma is not enabled.")
            conn.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS search_documents_fts USING fts5(
                        document_id UNINDEXED,
                        owner_user_id UNINDEXED,
                        kind UNINDEXED,
                        text,
                        tokenize = 'unicode61'
                    );
                    """
                )
            )

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as session:
        user = session.get(AppUserModel, DEFAULT_OWNER_USER_ID)
        now = utc_now_iso()
        if user is None:
            session.add(
                AppUserModel(
                    id=DEFAULT_OWNER_USER_ID,
                    created_at=now,
                    display_name=DEFAULT_OWNER_DISPLAY_NAME,
                )
            )
            session.flush()
        ai_cfg = session.get(AISettingsModel, DEFAULT_OWNER_USER_ID)
        if ai_cfg is None:
            session.add(
                AISettingsModel(
                    owner_user_id=DEFAULT_OWNER_USER_ID,
                    conversation_provider="local_heuristic",
                    conversation_model="noema-local-chat-v1",
                    extraction_provider="local_heuristic",
                    extraction_model="noema-local-extractor-v1",
                    embedding_provider="local_heuristic",
                    embedding_model="noema-local-embed-v1",
                    hosted_data_consent=0,
                    local_endpoint_url="http://127.0.0.1:11434/v1",
                    context_budget_tokens=1600,
                    updated_at=now,
                )
            )
        session.commit()


def init_db(database_url: str | None = None) -> Engine:
    """Create schema (for tests or bootstrap) and verify SQLite FTS5 & foreign keys."""
    import noema.persistence.models  # noqa: F401

    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    ensure_fts_and_local_owner(engine)
    return engine
