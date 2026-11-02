from logging.config import fileConfig

from alembic import context

from app.core.base import Base
from app.core.config import settings
from app.core.database import engine
from app.models import User  # noqa: F401 -- register models in Base.metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Metadata que Alembic utilizará para detectar
# las tablas de nuestros modelos SQLAlchemy.
target_metadata = Base.metadata


def run_migrations_offline():
    """
    Permite generar SQL de migraciones sin
    establecer una conexión con PostgreSQL.
    """

    context.configure(
        url=settings.database_url.render_as_string(
            hide_password=False
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Ejecuta las migraciones conectándose
    directamente a PostgreSQL.
    """

    # Tests supply their own connection, never the application/development DB.
    connection = config.attributes.get("connection")
    if connection is not None:
        configure_connection(connection)
    else:
        with engine.connect() as connection:
            configure_connection(connection)


def configure_connection(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
