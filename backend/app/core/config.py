from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


# Ubicación de la raíz del proyecto.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """
    Configuración de la aplicación.

    Lee las variables de entorno y valida sus tipos.
    """

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_sslmode: str | None = None
    postgres_channel_binding: str | None = None

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:

        query: dict[str, str] = {}

        if self.postgres_sslmode:
            query["sslmode"] = self.postgres_sslmode

        if self.postgres_channel_binding:
            query["channel_binding"] = self.postgres_channel_binding

        """Construye la URL de conexión a PostgreSQL."""

        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            query=query,
        )


settings = Settings()