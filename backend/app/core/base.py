from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
  """
  Clase base para los modelos ORM.

  Los futuros modelos de SQLAlchemy heredarán
  de esta clase para registrar sus tablas.
  """
  pass