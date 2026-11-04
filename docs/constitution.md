# Constitución — Notifications Challenge

Este take-home debe poder mantenerlo alguien que empieza a programar.
Los siguientes seis principios son obligatorios.

## 1. Stack simple y estable
- Conservar FastAPI, SQLAlchemy síncrono, PostgreSQL y Alembic; frontend previsto: React, TypeScript y Vite.
- Toda nueva dependencia, servicio o capa requiere justificación escrita y aprobación; no se agregan por anticipación.

## 2. Spec, código y contrato coherentes
- Cada cambio funcional parte de una spec breve aprobada: alcance, comportamiento y criterios de aceptación.
- Código y tests deben cumplir esa spec; los cambios de contrato actualizan también la spec y OpenAPI.
- Las funcionalidades planeadas no se documentan como implementadas.

## 3. Lógica separada de la interfaz
- Routers y frontend manejan entrada y presentación; los servicios contienen las reglas de negocio.
- El acceso a datos pertenece a repositorios; los servicios no dependen de HTTP.
- Los routers reciben servicios mediante Depends; no construyen servicios ni repositorios.

## 4. Tests con las herramientas existentes
- No agregar dependencias de testing; usar pytest, TestClient y unittest.mock disponibles.
- Cada cambio de comportamiento incluye pruebas de éxito, errores y límites relevantes.
- Probar lógica aislada con unitarios y persistencia con PostgreSQL de testing y rollback.
- Ejecutar ./up_test.sh antes de dar el cambio por terminado; informar cualquier bloqueo sin afirmar que pasó.

## 5. Datos del usuario protegidos
- Validar entradas y exigir autenticación y autorización sobre cada recurso privado; documentar las excepciones públicas.
- Guardar contraseñas únicamente como hashes Argon2id y configurar secretos mediante variables de entorno.
- No guardar secretos en Git ni registrar contraseñas o tokens; las respuestas no exponen contraseñas ni hashes.
- Los tests nunca usan datos reales ni bases de desarrollo o producción.

## 6. Idiomas consistentes
- Nuevos identificadores, comentarios, rutas, claves JSON y códigos de error se escriben en inglés.
- Nuevos textos dirigidos al usuario, especificaciones y documentación explicativa se escriben en español.
- Traducir textos existentes requiere un cambio explícito; no hacer traducciones masivas como efecto secundario.
