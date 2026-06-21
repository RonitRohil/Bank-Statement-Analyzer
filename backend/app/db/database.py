from sqlmodel import SQLModel, create_engine, Session

from app.config.settings import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def create_db_and_tables():
    """Called at startup to create all tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency — yields a SQLModel Session."""
    with Session(engine) as session:
        yield session
