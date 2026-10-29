# El Dockerfile es una receta para construir una imagen de nuestra aplicación.

# Imagen base con Python 3.13
FROM python:3.13-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /workspace/backend

# Configuración de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalamos las dependencias
COPY backend/requirements.txt ./requirements.txt

RUN python -m pip install --no-cache-dir -r requirements.txt

# Copiamos el código y la configuración de migraciones
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini

# Puerto donde escuchará FastAPI
EXPOSE 8000

# Iniciamos el servidor
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# FROM	Selecciona Python 3.13 como base
# WORKDIR	Define el directorio de trabajo
# COPY	Copia archivos del proyecto a la imagen
# RUN	Instala las dependencias
# EXPOSE	Documenta el puerto utilizado
# CMD	Define cómo iniciar FastAPI