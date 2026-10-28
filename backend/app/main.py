from fastapi import FastAPI
from app.routers import system

from app.routers import system

# Instancia principal de FastAPI.
# Genera automáticamente la documentación OpenAPI y Swagger UI.
app = FastAPI(
  title="Notification API",
  description="Full Stack Take Home Challenge",
  version="0.1.0"
)
# Registra los endpoints definidos en el router de system.
# prefix: agrega /api/v1 a todas las rutas de ese router.
# tags: agrupa sus endpoints bajo "System" en Swagger.
app.include_router(
    system.router,
    prefix="/api/v1",
    tags=["System"],
)


@app.get("/")
def root():
  return {"message": "Hello World"}

@app.get("/health")
def health():
  return {"status": "ok"}