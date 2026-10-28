from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


# Engine: administra la conectividad con PostgreSQL
# y mantiene un pool de conexiones reutilizables.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# Factory: permite crear sesiones independientes.
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Proporciona una sesión de base de datos.

    FastAPI podrá inyectarla mediante Depends().
    La sesión se cierra al finalizar su uso.
    """

    with SessionLocal() as session:
        yield session