#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

echo "Ejecutando tests dentro de Docker..."

# Construye y ejecuta el contenedor de testing.
docker compose -f docker-compose.test.yml run --rm --build tests

echo "Todos los tests finalizaron correctamente."