# Plan 001 — Gestión de notificaciones propias

Estado: aprobado explícitamente por el usuario en la conversación.
Spec de referencia: [spec.md](spec.md), implementada con cierre autorizado.

Este documento registra las decisiones técnicas aprobadas. El desglose de [tasks.md](tasks.md) también fue aprobado; T1–T7 están completadas y verificadas. El 2026-11-08 se autorizó explícitamente ejecutar T4–T7 sin pausas, informando solo el resultado final. Posteriormente el usuario dio conformidad expresa para cerrar 001 y comenzar la fase de spec de 002, según lo comunicado por el coordinador. El cierre es documental y usa las evidencias históricas registradas; no se ejecutaron nuevamente las verificaciones.

## Enfoque y límites
- Mantener FastAPI, SQLAlchemy síncrono, PostgreSQL y Alembic, sin dependencias nuevas, cambios de despliegue ni refactors de autenticación.
- Seguir el flujo existente router → servicio → repositorio → modelo. Inyectar el servicio desde `app/core/dependencies.py` y registrar el router bajo `protected_api`.
- No implementar envíos, destinatarios, estados, fechas de programación, filtros, paginación ni consulta individual. No agregar marcas temporales: la spec no las requiere.

## Contrato HTTP aprobado
Base: `/api/v1/notifications`. Todas las operaciones requieren bearer token.

| Método y ruta | Entrada | Respuesta correcta |
| --- | --- | --- |
| `POST /api/v1/notifications` | `title`, `content`, `channel`, obligatorios | 201 con la notificación creada |
| `GET /api/v1/notifications` | Sin filtros | 200 con un arreglo de notificaciones propias; `[]` si no hay |
| `PATCH /api/v1/notifications/{notification_id}` | Uno o más campos modificables | 200 con la notificación actualizada |
| `DELETE /api/v1/notifications/{notification_id}` | Identificador | 204 sin cuerpo |

- Representación pública: `id`, `title`, `content`, `channel`. No exponer datos del usuario ni aceptar el propietario desde el cliente.
- Identificadores UUID, coherentes con los usuarios existentes. Un UUID mal formado produce 422; uno válido pero inexistente o ajeno produce 404.
- Valores de `channel`: `email`, `sms`, `push`, en minúsculas y sin normalización automática. Email, SMS y Push son sus nombres de presentación.
- Conservar HTTP 401 y el mecanismo actual de autenticación. Para 404, devolver el mismo `{"detail": "Notificación no encontrada."}` en recursos ajenos e inexistentes.
- Conservar HTTP 422 con `detail: [{type, field, message}]`, sin valores enviados ni mensajes internos en la respuesta.

## Validación y modificación parcial
- Crear `NotificationCreateRequest`, `NotificationUpdateRequest` y `NotificationResponse` con Pydantic. La respuesta usa `from_attributes=True` como las respuestas existentes.
- Validar longitudes 1–200 y 1–5000 sobre las cadenas recibidas, sin `strip` ni conversiones de tipo. Comprobar con `strip` únicamente si todo el texto es blanco; devolver el texto original.
- Validar un único canal mediante un conjunto cerrado de valores. Rechazar tipos incorrectos, valores nulos y propiedades desconocidas en los cuerpos de notificaciones.
- En PATCH, distinguir entre campo omitido y campo enviado con null: omitir conserva el valor; null devuelve 422. Reflejarlo también en OpenAPI.
- Rechazar el objeto vacío. Extraer únicamente los campos efectivamente enviados y validados; nunca copiar arbitrariamente el cuerpo al modelo.
- Rechazar `id` y `user_id` en creación y edición para evitar asignaciones de propietario o cambios de identidad.
- Extender el formateador existente solo para los errores necesarios: texto en blanco, canal inválido, tipo/UUID inválido, campo no permitido, null explícito y modificación vacía. Mantener mensajes en español y los contratos previos de autenticación.

## Persistencia y autorización
- Crear `notifications` con `id` UUID como clave primaria, `user_id` UUID como clave foránea a `users.id`, `title` de hasta 200 caracteres, `content` de hasta 5000 y `channel` limitado a los tres valores admitidos. Todos son no nulos.
- Añadir un índice sobre `user_id` y una restricción CHECK de canales. No introducir un tipo ENUM nativo de PostgreSQL ni modificar la tabla de usuarios.
- Registrar el modelo en los metadatos existentes y añadir una migración posterior a `8c6c2ab17d42`; no modificar revisiones anteriores.
- El repositorio recibe siempre el `user_id` autenticado. Listar filtra por propietario; buscar para editar o eliminar filtra simultáneamente por `id` y `user_id`.
- El servicio lanza `NotificationNotFoundError` si la búsqueda no devuelve un recurso propio; no hace una segunda consulta para distinguir un recurso ajeno.
- El repositorio confirma cada operación de escritura y hace rollback si falla. Una edición valida todos los cambios antes de persistirlos, sin commits intermedios.

Flujo de edición:
```text
validar los campos enviados
buscar por identificador y usuario autenticado
si no existe un recurso propio, señalar no encontrado
aplicar solo los campos modificables enviados
confirmar una vez y devolver el resultado persistido
```

## Archivos y responsabilidades
Las rutas siguientes son relativas a la raíz del repositorio.

| Archivo | Cambio previsto |
| --- | --- |
| `backend/app/models/notification.py` | Nuevo modelo de persistencia y restricciones de la tabla |
| `backend/app/models/__init__.py` | Registrar y exportar el nuevo modelo junto a `User` |
| `backend/migrations/env.py` | Hacer explícito el registro del modelo para Alembic |
| `backend/migrations/versions/a4d2e7f9136b_create_notifications.py` | Nueva migración de tabla, índice y restricciones, implementada y comprobada en T2 |
| `backend/app/schemas/notification.py` | Contratos de creación, edición y respuesta; validaciones compartidas y canales admitidos |
| `backend/app/repositories/notifications.py` | Lecturas por propietario y persistencia transaccional |
| `backend/app/services/notifications.py` | Casos de uso de creación, consulta, edición y eliminación; excepción de recurso no encontrado |
| `backend/app/core/dependencies.py` | Proveedor `get_notification_service` y alias `NotificationServiceDependency` |
| `backend/app/routers/notifications.py` | Traducción HTTP de los cuatro casos de uso, sin acceso SQL directo |
| `backend/app/main.py` | Registrar el router bajo el grupo protegido |
| `backend/app/core/exception_handlers.py` | Mensajes seguros para las nuevas validaciones, sin cambiar la forma de los errores |
| `backend/tests/test_notification_schemas.py` | Nuevos tests unitarios de validación y edición parcial |
| `backend/tests/test_notification_service.py` | Nuevos tests del servicio con repositorio sustituido por `unittest.mock` |
| `backend/tests/test_notifications.py` | Nuevos tests de API y PostgreSQL real, incluyendo dos propietarios |
| `backend/tests/conftest.py` | Reutilizar aislamiento y añadir apoyo para autenticar dos usuarios distintos |
| `backend/tests/test_auth.py` | Adaptar la comprobación de la revisión vigente para que no dependa del hash de la migración de usuarios |
| `backend/tests/test_validation_errors.py` | Cubrir nuevas traducciones y comprobar regresiones de las existentes |
| `README.md` y `AGENTS.md` | Documentar endpoints y alcance real cuando estén implementados, no antes |
| `MEMORY.md` | Actualizar fase, aprobaciones, verificaciones y bloqueos sin duplicar requisitos |

## Interfaces entre capas
- `NotificationRepository(session)` expone `create(user_id, title, content, channel)`, `list_by_user(user_id)`, `get_by_id_and_user(notification_id, user_id)`, `update(notification, changes)` y `delete(notification)`.
- `NotificationService(repository)` expone `create(user_id, title, content, channel)`, `list_own(user_id)`, `update(user_id, notification_id, changes)` y `delete(user_id, notification_id)`.
- `changes` solo contiene `title`, `content` y/o `channel` ya validados. El servicio mantiene esa lista permitida; nunca permite cambiar `id` o `user_id`.
- El proveedor usa la sesión inyectada existente. Los routers obtienen `CurrentUser` y `NotificationServiceDependency`, pasan `user.id` al servicio y no construyen repositorios.
- Mantener servicios sin importaciones HTTP ni dependencias de los esquemas de petición; reciben UUID, cadenas y cambios validados.

## Decisiones y alternativas
| Decisión | Motivo y alternativa descartada |
| --- | --- |
| PATCH en lugar de PUT | La spec aprobó cambios parciales; PUT exigiría reemplazar el recurso completo |
| Borrado definitivo | Es el comportamiento aprobado; un borrado lógico agregaría recuperación y estados fuera de alcance |
| UUID como identificador | Sigue el modelo de usuarios; no se necesita otra estrategia de identificadores |
| Cadena y CHECK para el canal | Mantiene restricciones en PostgreSQL sin el ciclo de creación/eliminación de un ENUM nativo |
| Consulta conjunta por recurso y propietario | Evita leer o revelar recursos ajenos; descartar la búsqueda global seguida de una autorización tardía |
| Sin abstracciones nuevas de repositorio ni unidad de trabajo | Reutiliza el estilo existente y mantiene el challenge pequeño; no se requiere un segundo backend de persistencia |
| Sin orden de listado garantizado | La spec no requiere orden; los tests comparan resultados sin depender del orden físico |

## Estrategia de tests y trazabilidad
No añadir dependencias. Los tests unitarios usan pytest y `unittest.mock`; los de integración usan `db_test_client` y PostgreSQL de testing con migraciones y rollback existentes.

| Requisitos | Cobertura verificada al completar T7 | Tareas |
| --- | --- | --- |
| RF-1 | Crear con cada canal; comprobar UUID, valores persistidos y propietario obtenido del token | T2, T3, T4, T5 |
| RF-2, RF-3 | Título con 1/200/201 caracteres, contenido con 1/5000/5001; cadenas vacías y en blanco, incluidos tabulaciones/saltos de línea; campos ausentes, null y tipos incorrectos; canal desconocido; conservar texto y espacios significativos | T1, T5, T6 |
| RF-4, RF-5 | PATCH de cada campo y de varios; omitidos conservados; null y cuerpo vacío rechazados; combinar un campo válido y otro inválido sin cambios persistidos | T1, T3, T4, T6 |
| RF-6 | Borrado real comprobado en base y listado; segunda eliminación responde 404 | T3, T4, T6 |
| RF-7 | Lista vacía, varios recursos propios y exclusión completa de los de un segundo usuario; comparar sin exigir orden | T3, T4, T5 |
| RF-8, RNF-3 | PATCH/DELETE ajenos e inexistentes con el mismo 404 y mensaje; el recurso ajeno permanece intacto | T3, T4, T6 |
| RF-9 | Rechazar `id`/`user_id` y propiedades desconocidas sin crear ni modificar recursos; comprobar que el cliente no puede asignar otro propietario | T1, T4, T5, T6 |
| RNF-1 | Rechazar las cuatro operaciones sin token o con token inválido, usando peticiones con formato válido | T4, T5, T6 |
| RNF-2 | Errores 422 con solo `type`, `field`, `message`, mensajes españoles sin valores sensibles y documentación OpenAPI consistente; UUID mal formado | T1, T5, T6, T7 |
| RNF-4 | Reutilizar las fixtures y probar con dos usuarios de testing; no cambiar bases ni datos de desarrollo o producción | T2, T3, T5, T6 |
| Criterios de finalización | Suite completa, regresiones de autenticación, migración aplicada y coincidencia entre metadatos y esquema | T7 |

Los identificadores corresponden a [tasks.md](tasks.md), aprobado independientemente. La aprobación no equivale a ejecución ni autoriza continuar automáticamente entre tareas.

## Verificación y punto de partida
- Línea base previa a T1, verificada y repetida el 2026-11-04: `./up_test.sh` pasó 74 tests con Python 3.13.18 y PostgreSQL 17, con 99% de cobertura.
- Tras T1, `./up_test.sh` pasó 211 tests y la verificación enfocada de esquemas y errores pasó 158. Hay contratos y validaciones probados, todavía sin persistencia ni endpoints de notificaciones; las evidencias están en `tasks.md`.
- Tras T2, el 2026-11-06, la suite pasó 235 tests y la verificación ampliada de modelo/migraciones pasó 25, con 99% de cobertura global. La migración se aplicó solo a `notifications_test`; el modelo y el esquema coinciden. Repositorio y endpoints aún no están implementados.
- Tras T3, el 2026-11-06, el repositorio filtrado por propietario pasó 45 tests enfocados y la suite completa pasó 256, con 99% de cobertura global y 100% en el repositorio. Se comprobaron confirmación única, edición parcial, borrado definitivo y rollback con recuperación de sesión. Servicio y endpoints siguen pendientes; evidencias y límites en `tasks.md`.
- Tras T4–T7, el 2026-11-08, `./up_test.sh` pasó 426 tests con Python 3.13.18 y PostgreSQL 17, 99% de cobertura global y 100% en los módulos de notificaciones. Servicio, inyección y las cuatro rutas protegidas están implementados; OpenAPI y documentación reflejan el contrato. Reporte XML, formato y enlaces comprobados. Evidencias por tarea y contraste final en `tasks.md`; sin cambios de alcance, dependencias ni despliegue.
- Para validaciones puntuales locales, desde `backend/`: `python -m pytest -v tests/test_notification_schemas.py` y `python -m pytest -v tests/test_notification_service.py`.
- Para integración, desde la raíz: `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/test_notifications.py`.
- Al finalizar: `./up_test.sh`, comprobación de `coverage/coverage.xml`, comparación de metadatos y revisión de OpenAPI/documentación. Informar resultados observados, no solo cobertura.
- T2 reemplazó la revisión fija del test de migraciones por el head obtenido de Alembic, conservando la comparación real de metadatos y versión en la base de testing.

## Cierre y continuidad
La spec, este plan y [tasks.md](tasks.md) fueron aprobados. T1–T7 están completadas y verificadas técnicamente; el usuario autorizó expresamente el cierre el 2026-11-08. No quedan tareas ni aprobación de cierre pendientes en 001. La nueva funcionalidad se describe por separado en [002 — Envío de notificación](../002-notification-delivery/spec.md), todavía en borrador y sin plan ni tareas.
