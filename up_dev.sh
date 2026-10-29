#!/usr/bin/env bash

# Detiene el script si ocurre un error,
# se utiliza una variable indefinida o falla un comando del pipeline.
set -euo pipefail

# Nos ubicamos en el directorio donde está el script.
cd "$(dirname "$0")"

echo "Levantando FastAPI y PostgreSQL..."

# Construye la imagen y levanta los servicios.
docker compose -f docker-compose.yml up -d --build api

# Muestra el estado de los contenedores.
docker compose -f docker-compose.yml ps

echo "API disponible en http://localhost:8000/docs"