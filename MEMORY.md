# MEMORY.md — Notifications Challenge

Shared project memory for AI development sessions. Keep it concise and focused on current progress, relevant decisions, known issues, and next steps.

## Current Status

- Backend infrastructure is complete: FastAPI, SQLAlchemy, PostgreSQL, Alembic, Docker, and pytest.
- GitHub Actions runs automated tests and uploads coverage to Coveralls.
- El repositorio conserva referencias históricas de Render y Neon; esta memoria no afirma disponibilidad ni versión desplegada.
- Database migrations run automatically before FastAPI starts.
- User registration, JSON login with JWT access tokens, and `/api/v1/users/me` are implemented alongside diagnostic endpoints.
- API routes require a bearer token except registration, login, `/health`, and documentation. Future protected routers belong under `protected_api` in `app/main.py`.
- El CRUD HTTP de notificaciones propias está implementado con autenticación JWT, edición parcial, borrado definitivo y aislamiento entre propietarios. POST ejecuta simulación local síncrona por email/SMS/push antes de guardar; no usa proveedor/red ni acredita recepción, y el destinatario es efímero. El frontend sigue pendiente. No se afirma despliegue de estos cambios.
- Última verificación backend registrada: ejecución final del implementador el 2026-11-09, `./up_test.sh`: 550 passed en 19.07 s, 98% de cobertura; `coverage/coverage.xml`: 593/604 líneas, `line-rate="0.9818"`. Enfocada final: 421 passed en 15.82 s tras corregir la omisión documental de OpenAPI demostrada por el RED de T6. `git diff --check` pasó, según lo comunicado por el coordinador. No se repitieron comandos ni tests en esta actualización documental; las evidencias por tarea están en [tasks.md](specs/002-notification-delivery/tasks.md).

## Trabajo activo
- Spec activa: [002 — Envío de notificación](specs/002-notification-delivery/spec.md).
- Fase: validación técnica de T1–T6 completada y revisión final APROBADO técnico, sin hallazgos, según lo comunicado por el coordinador. Pendiente conformidad expresa del usuario para cerrar 002. [Plan](specs/002-notification-delivery/plan.md) y [tareas](specs/002-notification-delivery/tasks.md) aprobados; la spec conserva el estado aprobada, no implementada ni cerrada.
- Aprobaciones comunicadas por el coordinador: spec 002 aprobada el 2026-11-08, incluidas P1, P2, P3/P3b y P4; plan aprobado el 2026-11-09 con «apruebo el plan», tras revisión documental APROBADO técnico. Después, el 2026-11-09 el usuario respondió exactamente «si apruebo todas las tareas, ejecutalas todas y avisame cuando termines»: aprueba todas las tareas y autoriza ejecución agrupada, secuencial y sin pausas exclusivamente de T1–T6 de 002, con informe al terminar. No autoriza cierre de spec, cambios de alcance ni otras fases. Es autorización propia de 002, no una extensión de la ejecución agrupada histórica de 001, cuyo cierre y evidencias se conservan.
- Revisión final comunicada por el coordinador (2026-11-09): reviewer emitió APROBADO técnico, sin hallazgos y con evidencia suficiente para presentar al usuario. No ejecutó comandos por instrucción; el veredicto se apoya en revisión y evidencias del implementador, no en una nueva ejecución. No constituye conformidad del usuario ni autorización de cierre.
- Próximo paso: el coordinador debe presentar la finalización técnica de T1–T6, sus evidencias y el veredicto final, y pedir conformidad expresa del usuario para cerrar 002; no cambiar el estado de la spec antes de recibirla. No hay nuevas fases autorizadas.
- Verificación T1 (2026-11-09, raíz): tras restaurar Docker, la línea base `./up_test.sh` pasó 426 tests; el RED enfocado falló correctamente por ausencia de `app.services.delivery`; el GREEN enfocado pasó 33 tests y la suite completa `./up_test.sh` pasó 459 tests con 99% de cobertura. Se crearon estrategias aisladas sin HTTP/SQL/red/logging ni dependencias nuevas.
- Verificación T2 (2026-11-09, raíz): el RED `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/test_notification_delivery.py` falló durante recolección por ausencia de `app.services.delivery.logging` (0 tests, 1 error, 0.08 s). Tras el cambio mínimo, el mismo comando pasó 44 tests en 0.09 s y `./up_test.sh` pasó 470 tests en 14.92 s, con 99% de cobertura. Las ejecuciones enfocadas advirtieron contenedores huérfanos sin afectar los resultados; no se eliminaron. Se implementó logging aislado, sin conectar sender, CRUD, DI o HTTP.
- Verificación T3 (2026-11-09, raíz): el RED `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/test_notification_delivery.py` falló durante recolección por ausencia de `NotificationSender` (0 tests, 1 error, 0.10 s). Tras implementar el sender mínimo, el mismo comando pasó 58 tests en 0.12 s y `./up_test.sh` pasó 484 tests en 14.83 s, con 98% de cobertura. Persistió la advertencia de contenedores huérfanos sin impacto y no se eliminaron. El sender selecciona desde el mapa inyectado, usa el destinatario validado para proteger/registrar y no reintenta registros; sigue aislado de CRUD, DI y HTTP.
- Verificación T4 (2026-11-09, raíz): tras escribir tests de integración, el RED Docker enfocado recolectó 432 pruebas y falló en colección por ausencia de `get_notification_sender` (1 error, 0.25 s). Después de integrar schema/servicio/DI/router/handler y corregir una expectativa obsoleta de POST SMS de 5000, el comando enfocado pasó 463 pruebas en 12.85 s; `./up_test.sh` pasó 511 pruebas en 15.46 s, con 98% de cobertura. La advertencia de contenedores huérfanos apareció en el RED sin afectar el resultado y no se eliminaron. POST exige `recipient` efímero y write-only, simula antes de persistir y devuelve 422/500 seguros; PATCH/GET/DELETE no envían y no persisten ni exponen el destino.
- Verificación T5 (2026-11-09, raíz): los nuevos tests adversariales se ejecutaron primero. El Docker enfocado falló con 11 fallos y 485 pases en 16.17 s: nueve fueron dobles de test que anulaban indebidamente la validación real de destinatarios, uno esperaba que datos de preparación no confirmados sobrevivieran al rollback y uno reveló que el logger dedicado retenía handlers ajenos. Se corrigieron esas dos premisas de test y, para el defecto real, `create_delivery_logger` elimina handlers no locales para conservar uno solo. El mismo comando pasó 496 pruebas en 15.84 s; `./up_test.sh` pasó 549 en 19.46 s, 98%. Los tests con PostgreSQL `notifications_test` verifican el rollback tras flush, la fila retenida tras refresh/model_validate/model_dump/JSONResponse postcommit, logs protegidos, autenticación, privacidad y regresiones CRUD. No se modificaron persistencia, auth, modelo, migraciones, main, fixtures, configuración ni dependencias.
- Verificación T6 (2026-11-09, raíz): el nuevo test OpenAPI se ejecutó primero. El comando enfocado de T6 tuvo un RED documental real (420 pases, 1 fallo, 16.24 s) por no describir normalización de email/P3b; tras completar descripciones de schema/router, README y AGENTS, pasó 421 pruebas en 15.82 s. `./up_test.sh` pasó 550 pruebas en 19.07 s con 98%; `coverage/coverage.xml` confirma 593/604 líneas (0.9818). La documentación incluye ejemplos ficticios por canal, ruptura POST, destino efímero, simulación/logs protegidos, P3b y PATCH sin reenvío/5000. T6 está marcada completa; no cierra 002.
- Bloqueos: sin bloqueos funcionales o técnicos pendientes comunicados; únicamente falta conformidad expresa del usuario para el cierre. El fallo inicial de socket Docker de T1 fue de infraestructura y quedó resuelto antes de la línea base correcta; no fue un RED funcional.
- Advertencia histórica no bloqueante: ejecuciones Docker enfocadas previas mostraron contenedores huérfanos; no se eliminaron por no estar autorizado. No invalida las ejecuciones correctas ni el veredicto técnico final, y no implica un bloqueo actual.

## Decisions and Rationale

### Adopción de SDD
- **Decisión:** Usar la skill local `sdd` y una sola carpeta por funcionalidad con spec, plan y tareas; conservar la constitución y las skills de Python, sin incorporar Superpowers ni dependencias nuevas.
- **Motivo:** Mantener aprobaciones explícitas, trazabilidad entre requisitos y tests y ejecución de una tarea por vez, con un proceso entendible para quien empieza a programar. La adopción no crea specs retrospectivas ni modifica la aplicación.

### Constitución del proyecto
- **Decisión:** Se aprobó `docs/constitution.md` y se enlazó desde `AGENTS.md`.
- **Motivo:** Mantener criterios verificables de alcance, sencillez y seguridad para que alguien que empieza a programar pueda mantener el challenge, sin refactorizar lo existente como parte de esta adopción.

### Deployment migrations
- **Decision:** Execute Alembic migrations during application startup using `backend/start.sh`.
- **Reason:** The current deployment uses a single Render instance on the free plan. This provides a simple automated migration process without requiring a separate deployment job.
- **Revisit when:** Moving to multiple application instances or a production deployment requiring independent migration execution.

### Project-local agent skills
- **Decision:** Install `python-anti-patterns`, `python-error-handling`, and `python-testing-patterns` from `wshobson/agents` in `.agents/skills/`, with installation metadata in `skills-lock.json`. `python-project-structure` remains optional and is not installed.
- **Reason:** Add review, error-handling, and testing guidance for this repository without a global skill installation or application refactor.

## Known Issues and Learnings

- Docker development images do not use source bind mounts. Code changes require rebuilding the image.
- Database fixtures apply Alembic migrations through an explicit test connection, then isolate each test with an outer transaction and savepoints so application commits can be rolled back. Only the local `notifications_test` database is accepted.
- A random `JWT_SECRET_KEY` of at least 32 characters is now required before API startup, including Render deployment. `.env.example` deliberately leaves it empty; tests supply their own key. Token TTL defaults to 30 minutes.

### Authentication decisions
- **Decision:** Use Argon2id (`pwdlib`) for passwords and HS256 JWT access tokens (`PyJWT`) with mandatory subject, issue time, and expiration. No refresh/revocation flow in this scope.
- **Reason:** Keep the challenge implementation small while avoiding custom cryptography; checking that the subject user still exists also rejects deleted-user tokens.
- **Decision:** Normalize validated emails to lowercase and enforce uniqueness in PostgreSQL, handling constraint violations rather than relying on a pre-check.
- **Reason:** Case-insensitive account identity and safe duplicate handling even with concurrent registration requests.
- **Decision:** Use HTTP bearer authentication with JSON login rather than an OAuth2 password form.
- **Reason:** Match the requested email/password API without a form-parser dependency; Swagger still supports bearer authorization.
- **Decision:** Assemble `AuthService` in `get_auth_service` (`app/core/dependencies.py`) and inject it into auth endpoints using `AuthServiceDependency`.
- **Reason:** Keep service/repository construction out of HTTP handlers and allow service overrides for database-free router tests. This remains a pragmatic layered architecture; no repository interfaces or separate domain entities were introduced.

### Validation error responses
- **Decision:** Keep HTTP 422 and the `detail` list, but expose only `type`, `field`, and a Spanish `message` per validation error. Whole-body errors use a null field; nested paths retain their indices. HTTP 401 and 409 formats remain unchanged.
- **Reason:** Provide clear, machine-readable errors without leaking submitted values or internal validator messages. `app/core/exception_handlers.py` formats errors and `app/schemas/errors.py` defines the shared response/OpenAPI contract.

### Notificaciones propias
- **Decisión:** Buscar conjuntamente por UUID y propietario antes de editar/borrar y usar la misma excepción/404 para recursos ajenos e inexistentes, para no revelar su existencia. Los routers reciben el servicio inyectado y no construyen repositorios.
- **Decisión:** Extraer PATCH con `model_dump(exclude_unset=True)` tras validar con Pydantic; el servicio mantiene la lista de campos permitidos. Así se conservan omisiones sin aceptar null, cambios de identidad o asignación arbitraria de atributos desde HTTP.

## Next Steps
- Presentar evidencias finales y veredicto APROBADO técnico de 002; solicitar conformidad expresa del usuario para cerrar. No asumirla por completar tareas ni por la revisión técnica.
- Before production use, address rate limiting, email verification, password recovery, and token lifecycle requirements.
