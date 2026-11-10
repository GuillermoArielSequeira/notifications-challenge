# Plan 002 — Envío de notificación

Estado: aprobado explícitamente por el usuario el 2026-11-09, según lo comunicado por el coordinador.

Referencia: [spec aprobada](spec.md), incluidas P1, P2, P3/P3b y P4, con respuesta «apruebo la spec» el 2026-11-08. Tras revisión documental con veredicto APROBADO técnico sin incumplimientos materiales, el usuario respondió «apruebo el plan» el 2026-11-09, según lo comunicado por el coordinador. Posteriormente aprobó todas las tareas de [tasks.md](tasks.md) y autorizó expresamente la ejecución agrupada, secuencial y sin pausas solo de T1–T6 de 002. T1–T6 se ejecutaron y su evidencia está registrada; no hay cierre autorizado.

Estado de validación: revisión final APROBADO técnico, sin hallazgos, comunicada por el coordinador el 2026-11-09. Lista para presentar al usuario; su conformidad expresa de cierre sigue pendiente. El reviewer no ejecutó comandos por instrucción y no sustituye con su veredicto la decisión del usuario.

## Punto de partida comprobado por lectura al redactar el plan
Esta sección conserva el contexto previo a T1; no describe el estado posterior a la implementación. Los resultados actuales figuran en la evidencia final y en [tasks.md](tasks.md).
- Existen CRUD autenticado, `NotificationCreateRequest`, `NotificationUpdateRequest`, `NotificationResponse`, `NotificationService`, `NotificationRepository` y `get_notification_service`. No existen estrategias, destinatario ni envío implementados.
- El router recibe servicio y usuario mediante Depends. `protected_api` ya protege las cuatro operaciones; no hace falta modificar autenticación ni el registro de rutas en `main.py`.
- La creación del repositorio hace `add → commit → refresh`. Solo los errores de SQLAlchemy dentro de `add/commit` activan su rollback; `refresh` es posterior a la confirmación. Se conservará esta interfaz y este comportamiento, compatibles con P3b.
- El modelo tiene únicamente `id`, `user_id`, `title`, `content`, `channel`; `content` admite 5000 y el CHECK de canal admite los tres actuales. No se añadirá destinatario, estado, fecha ni migración.
- Los tests actuales permiten POST sin destinatario y SMS de 5000: esas expectativas de creación deben cambiar por la ruptura aprobada. Las pruebas de persistencia directa, respuesta y PATCH con 5000 siguen siendo regresiones válidas.
- Se leyeron constitución, AGENTS, MEMORY, README, los tres documentos cerrados de 001, contratos, servicio, repositorio, router, dependencias, errores, modelo, fixtures, tests relacionados y requirements. Los nuevos componentes descritos abajo son propuestas, no código existente. 001 no se modifica.

## Enfoque y decisiones
Conservar Python/FastAPI, Pydantic, SQLAlchemy síncrono, PostgreSQL y Alembic. La simulación es local y síncrona, sin proveedor, red, colas, framework de plugins, dependencias, cambios de configuración ni nueva capa de persistencia. Frontend y verificación visual no aplican.

| Decisión | Justificación y alternativa descartada |
| --- | --- |
| Strategy pequeña por canal y registro explícito inyectado | Cada estrategia concentra validación específica, preparación y protección de destino. Evita `if/elif` por canal en schema, router, servicio y sender, que exigiría editar el flujo común al extenderlo |
| Un sender concreto y un `Protocol` de estrategia | El sender comparte selección, orden y eventos; el protocolo documenta tres operaciones distintas comprobables con mocks. No hacen falta jerarquía abstracta, interfaz adicional de sender/repositorio, contenedor DI ni descubrimiento automático |
| Validación básica en Pydantic; reglas de canal en estrategias | El contrato mantiene tipos/campos y las estrategias son la única fuente de formatos por canal. Validar todo con ramas de canal en un validador Pydantic duplicaría o centralizaría reglas que deben poder extenderse |
| Composición en `core/dependencies.py` | Reutiliza Depends y overrides actuales; los routers no construyen estrategias, loggers ni repositorios. El mapa cerrado es explícito y no hay fallback |
| Simular y registrar antes de `repository.create` | Garantiza ausencia de escritura ante validación/simulación/log fallidos. Simular después del commit violaría RF-6; dentro de una transacción no haría atómico el log con PostgreSQL |
| Conservar `commit → refresh` del repositorio | P3b acepta la fila confirmada ante fallo posterior. Sustituirlo por `flush`, materialización previa y commit exigiría cambiar responsabilidades o retorno para reducir un riesgo ya aceptado; no garantiza entrega de respuesta. No se introduce UoW, borrado compensatorio ni refactor de PATCH/DELETE |
| Preparar también la respuesta dentro del límite seguro de POST | El `response_model` automático valida/serializa después del retorno del router: un try solo alrededor del servicio no captura esos errores. La materialización explícita evita esa brecha sin handler global de 500 ni cambios de errores de otros endpoints |
| Reloj callable solo en el registrador | El timestamp UTC sí es requerido y debe probarse con una fecha fija. No se inyecta tiempo en CRUD, repositorio o estrategias ni se agrega un framework de reloj |
| Logging stdlib dedicado, síncrono y con datos permitidos | Permite verificar emisión y errores sin dependencia ni configuración global. No se promete auditoría durable, recepción real ni atomicidad con la base |

La extensión futura admite cambiar el registro, los contratos y el CHECK de persistencia para habilitar un canal, como permite RNF-4. No promete añadir canales sin tocar ningún archivo; promete no editar las reglas de otros canales ni la coordinación común.

## Archivos y responsabilidades previstos
Rutas relativas a la raíz; son alcance futuro sujeto a aprobación del plan y las tareas, no permisos para editarlas en esta fase.

| Archivo | Responsabilidad / cambio previsto |
| --- | --- |
| `backend/app/services/delivery/__init__.py` (nuevo) | Identificar el pequeño paquete de la funcionalidad; sin auto-registro ni efectos de envío al importar |
| `backend/app/services/delivery/sender.py` (nuevo) | `DeliveryStrategy` Protocol, excepciones seguras de validación/ejecución y `NotificationSender`; selección por mapa y coordinación sin ramas de canal |
| `backend/app/services/delivery/email.py` (nuevo) | `EmailDeliveryStrategy`: validar/normalizar email, preparar texto plano y ocultar destino |
| `backend/app/services/delivery/sms.py` (nuevo) | `SmsDeliveryStrategy`: validar número y límite SMS, conservar contenido y enmascarar número |
| `backend/app/services/delivery/push.py` (nuevo) | `PushDeliveryStrategy`: validar token, preparar payload y ocultar destino |
| `backend/app/services/delivery/logging.py` (nuevo) | `DeliveryRecorder`, reloj UTC por defecto y construcción del logger/handler local que propaga fallos detectables sin volcar excepciones |
| `backend/app/schemas/notification.py` | Añadir solo a creación `recipient` estricto/obligatorio/no nulo, `repr=False`, metadato `writeOnly`; describir formatos dependientes de canal y límite SMS. No añadirlo a respuesta ni PATCH |
| `backend/app/services/notifications.py` | Inyectar sender y ampliar solo `create` con destinatario; simular una vez antes de llamar al repositorio. Conservar consulta, edición y borrado |
| `backend/app/core/dependencies.py` | Componer mapa de las tres estrategias, registrador y sender, e inyectarlo en el servicio usando la sesión actual; ofrecer `get_notification_sender` para sustitución controlada en pruebas |
| `backend/app/routers/notifications.py` | Pasar destinatario al servicio; adaptar errores de validación de estrategia al 422 existente; capturar fallos de creación/preparación de respuesta y documentar 500. No coordinar canales |
| `backend/app/core/exception_handlers.py` | Añadir únicamente traducciones de códigos de validación de destino/SMS; reutilizar `validation_error_handler` y no alterar auth ni formato global |
| `backend/tests/test_notification_delivery.py` (nuevo) | Unitarios de estrategias, sender, reloj, redacción, handler y fallos de logging |
| `backend/tests/test_notification_service.py` | Adaptar constructor y creación; probar orden sender/repositorio y ausencia de simulación en el resto del CRUD |
| `backend/tests/test_notification_schemas.py` | Separar datos de POST/PATCH/respuesta; cubrir obligatoriedad/tipo de destinatario y preservar contratos anteriores no afectados |
| `backend/tests/test_notifications.py` | Adaptar creaciones y OpenAPI; integración de éxito, validaciones, fallos, privacidad y regresión con PostgreSQL |
| `backend/tests/test_validation_errors.py` | Cubrir nuevos códigos y ausencia de datos sensibles; mantener regresiones de registro/login y rutas anidadas |
| `README.md`, `AGENTS.md` | Cuando exista implementación, explicar POST incompatible, simulación frente a entrega real, PATCH sin reenvío y alcance efectivo; no anunciar frontend |
| `MEMORY.md` y documentos de 002 | Registrar fase/aprobaciones y evidencias reales. La trazabilidad permanece en este plan; T1–T6 de `tasks.md` están completadas técnicamente, pendientes de conformidad de cierre de la spec |

Sin cambios previstos en `models/`, migraciones, repositorio, `schemas/auth.py`, `schemas/errors.py`, `main.py`, requirements, fixtures globales o infraestructura. Los modelos de error existentes y la documentación de respuesta local bastan; no se necesita un nuevo modelo para un único `detail` de 500. Se reutilizan `db_session`, `db_test_client`, `authenticated_user_factory`, `auth_headers` y overrides existentes.

## Interfaces y límites entre componentes
- `DeliveryValidationError(field, code)` contiene únicamente nombres/códigos permitidos, nunca el valor recibido, una excepción de Pydantic ni su mensaje/contexto. No importa FastAPI. `DeliveryExecutionError` y el error de registro tienen mensajes constantes sin datos de entrada.
- `DeliveryStrategy` define `validate(recipient: str, content: str) -> str`, `prepare(title: str, content: str) -> str | dict[str, str]` y `protect_recipient(recipient: str) -> str`. `validate` devuelve el destinatario normalizado cuando corresponde, o señala campo/código seguros. Las estrategias no conocen HTTP, base de datos, usuario ni JWT.
- `NotificationSender(strategies: Mapping[str, DeliveryStrategy], recorder: DeliveryRecorder)` expone `simulate(channel, recipient, title, content) -> None`. Selecciona una estrategia, valida, prepara y registra. Utiliza el destinatario devuelto por `strategy.validate` (normalizado para email), no el original, para la protección del destino y su registro protegido posteriores. La representación preparada es local y transitoria; no se devuelve al cliente ni se almacena. Sus resultados exactos y su orden se verifican en unitarios.
- `DeliveryRecorder(logger, clock: Callable[[], datetime])` expone `record(channel, status, protected_recipient) -> None`. Recibe un destino ya protegido, construye exclusivamente los cinco campos aprobados y emite JSON mediante logging stdlib. No acepta un request, modelo, template, payload o excepción como argumento.
- `NotificationService(repository, sender).create(user_id, title, content, channel, recipient) -> Notification`: recibe cadenas ya verificadas por el contrato básico HTTP, llama a `sender.simulate(...)` y solo después a `repository.create(user_id, title, content, channel)`. Nunca pasa `recipient` al repositorio ni lo añade a una entidad. Se conservan sus otras interfaces y lista de campos modificables.
- `get_notification_sender()` compone estrategias y registrador; `get_notification_service(db, sender=Depends(get_notification_sender))` construye el servicio. El logger dedicado se construye una sola vez por proceso, sin añadir handlers por petición. Componer dependencias no ejecuta simulación, reloj, SQL ni escritura de logs.
- Un canal permitido por el contrato pero ausente del registro es un error de composición (500 seguro), no una selección alternativa ni una simulación exitosa. Un canal no permitido por HTTP mantiene el 422 actual.

## Validación sin ramificación central por canal
1. Pydantic conserva cadenas estrictas, título 1–200, contenido 1–5000/no blanco, `channel` Literal y `extra="forbid"`. Añade `recipient` como cadena estricta de longitud mínima 1; no aplica trim global, coerción ni un formato de proveedor. No impone un máximo global antes de la normalización de email.
2. Solo después de que el cuerpo básico sea válido, el servicio/sender invoca la estrategia seleccionada. Cada estrategia aplica sus propias reglas; el schema y el router no consultan registros ni importan estrategias concretas.
3. Email usa Pydantic `EmailStr` con `max_length=254` y minúsculas, mediante un adaptador local, reproduciendo el criterio de `EmailCredentials` sin importar un schema de autenticación ni refactorizarlo. Se preserva su normalización de espacios externos y no se consulta DNS. Los errores del adaptador se descartan y se convierten al código seguro. Un test de equivalencia con el contrato de registro evita desviaciones.
4. SMS valida primero con coincidencia completa de `\+[1-9][0-9]{7,14}`; no usar `\d` ni coincidencias que permitan un salto de línea final. Después comprueba `len(content) <= 160`, sobre puntos de código de Python, sin recortar, normalizar o contar el título. La no vaciedad/blancos ya fue comprobada en el contrato básico. `prepare` conserva exactamente `content`.
5. Push valida longitud 1–512 y que cada carácter esté en U+0021–U+007E; no trim, no controles, no Unicode fuera de ASCII visible. No analiza JWT ni valida credenciales de proveedor.
6. Email prepara exactamente `title + "\n\n" + content`. Push prepara exactamente `{"title": title, "body": content}`. Ningún formato incorpora el destino.

### Adaptación de errores y contrato
La ruta POST transforma únicamente `DeliveryValidationError` en `RequestValidationError` con ubicación `("body", field)` y código permitido, sin `input` ni contexto sensible. El handler existente produce `detail: [{type, field, message}]`. No se devuelve un 422 alternativo con `detail` textual. La validación específica sucede antes de preparar o registrar, por lo que este error no exige evento de envío.

| Condición | `type` público | `field` | Mensaje nuevo / criterio |
| --- | --- | --- | --- |
| Destino omitido | `required_field` | `recipient` | Mensaje existente |
| Destino null o no cadena | `invalid_type` | `recipient` | Mensaje existente, sin coerción |
| Cadena de destino vacía | `string_too_short` | `recipient` | Mensaje existente de mínimo 1 |
| Email inválido o fuera del máximo del contrato de email | `invalid_recipient_email` | `recipient` | `Ingresá un email destinatario válido de hasta 254 caracteres.` |
| Número SMS inválido | `invalid_recipient_sms` | `recipient` | `Ingresá un número con + y entre 8 y 15 dígitos, sin cero inicial.` |
| Token push inválido | `invalid_recipient_push` | `recipient` | `Ingresá un token de 1 a 512 caracteres ASCII visibles, sin espacios.` |
| SMS de 161–5000 puntos de código con número válido | `sms_too_long` | `content` | `El contenido SMS debe tener como máximo 160 caracteres.` |

Las validaciones generales siguen precediendo a las específicas: por ejemplo, contenido de 5001 devuelve el error de longitud existente sobre `content`, y número inválido no conduce a preparación aunque también exceda 160. No se garantiza acumular errores específicos de canal con errores básicos de Pydantic. Todos son 422 seguros; no hay dependencia de mensajes internos de librerías. PATCH conserva su contrato y 5000 incluso en SMS; `recipient` es `unexpected_field`.

OpenAPI conserva un único contrato de POST, ahora con los cuatro campos obligatorios y destinatario `writeOnly`, sin `recipient` en respuestas/PATCH. Descripciones de creación/campos detallan los tres formatos, normalización de email y máximo SMS condicional: el máximo general 5000 no debe presentarse como permiso de enviar SMS de 5000. Documentar 422 y el ejemplo exacto de 500, semántica de simulación y posible fila tras fallo posterior al commit. No introducir un `oneOf` discriminado que altere rutas de error ni fingir que JSON Schema expresa toda validación de `EmailStr`. Los tests comprobarán tanto metadatos como comportamiento.

## Orden de ejecución, transacción y respuesta segura
Flujo previsto, no desglose de tareas:

```text
autenticación existente y validación básica del cuerpo
  → servicio.create → sender: seleccionar → validar destino/contenido
  → preparar representación local → registrar status=simulated
  → repository.create: add → commit → refresh
  → router: validar NotificationResponse → convertir a JSON → construir respuesta 201
```

- Cualquier validación fallida detiene la creación antes de preparación, logs de éxito y acceso de escritura al repositorio. No se llama a otro canal.
- Un fallo de preparación o ejecución anterior al registro de éxito provoca, si el registrador funciona, un único evento `failed` seguro. No se ejecutan pasos posteriores ni repositorio. El sender convierte el fallo en `DeliveryExecutionError` sin propagar detalles sensibles como mensaje público.
- Si falla el propio registro `simulated`, no se llama al repositorio ni se intenta un segundo evento por ese mismo medio fallido. Si falla registrar `failed`, también se rechaza, sin bucle de registro ni enmascarar la causa como éxito. No hay `simulated` previo a terminar preparación ni un éxito emitido desde un `finally`.
- Si falla la escritura reversible antes del commit, el repositorio actual hace rollback de SQLAlchemy y la ruta devuelve el 500 seguro, sin nueva fila. Un fallo real de PostgreSQL se probará además de los mocks; no se alteran restricciones para provocarlo. No se prometerá el resultado de un commit de confirmación desconocida por pérdida de conexión.
- Si el commit terminó y falla `refresh`, validación de respuesta, serialización o construcción local de respuesta, la ruta devuelve el mismo 500; la fila confirmada permanece y el log anterior sigue describiendo únicamente la simulación. No se llama a delete, no se repite el sender ni se reintenta el commit.
- En POST, un único límite `try` cubre servicio y construcción explícita de respuesta: `NotificationResponse.model_validate(record)`, `model_dump(mode="json")` y `JSONResponse` 201. Se conserva `response_model=NotificationResponse` para OpenAPI; devolver una Response ya construida evita una segunda validación/serialización automática fuera del límite. Adaptar primero la excepción específica de validación; para el resto capturar `Exception` solo en este límite de creación y lanzar `HTTPException(500, detail="No se pudo completar la creación de la notificación.") from None`. No capturar `BaseException` ni envolver auth, otras rutas o todo el middleware.
- No registrar esas excepciones ni su traceback; la adaptación evita que datos de SQL, Pydantic o destinatarios lleguen a respuesta o al logger de errores por excepción no manejada. No usar `logger.exception`, `exc_info`, `str(error)` ni incluir request/modelos en logs. El cierre normal de sesión puede revertir lecturas pendientes, pero no deshace un commit exitoso.
- Una vez entregada la respuesta construida a ASGI no se promete revertir persistencia ni controlar fallos de transporte del cliente. No hay garantía distribuida de recepción de respuesta. POST repetidos continúan siendo creaciones distintas.

## Registro técnico protegido y verificable
- Emitir una línea JSON por evento con exactamente `event="notification_delivery"`, `channel`, `status` (`simulated`/`failed`), `timestamp` ISO 8601 UTC y `recipient` protegido. El reloj por defecto usa `datetime.now(timezone.utc)`; el registrador normaliza fechas aware a UTC y no interpreta fechas naive como hora local.
- `protect_recipient` devuelve `[redacted]` para email/push. SMS devuelve un `*` por cada carácter anterior a los últimos cuatro dígitos, incluido el signo `+`. Ejemplo: `+12345678901` → `********8901`. No hay identificador de usuario, JWT, título, contenido, template, payload o texto de excepción entre los campos del evento.
- Utilizar logger stdlib dedicado a esta funcionalidad, no propagado al root, con nivel INFO y un único handler síncrono a stderr que escribe únicamente el JSON preparado. No añadir handlers/configuración global de Uvicorn ni modificar despliegue. La captura del destino de salida en tests permite comprobar las líneas realmente emitidas, no solo llamadas a mocks.
- Un `StreamHandler` estándar puede consumir excepciones mediante `handleError` e imprimir el registro/traceback. El handler local debe sustituir ese comportamiento por una excepción de registro de mensaje constante, propagada al sender; no debe imprimir el error original. Probar fallo de escritura, formateo y flush del handler real con sustituciones stdlib, además del fallo del método del registrador. No cambiar `logging.raiseExceptions` global.
- El retorno normal de emisión confirma la operación local de logging, no retención ni entrega a un sistema de auditoría. Los fallos detectables del registrador, reloj o handler impiden guardar. Si falla el medio no se exige un evento alternativo ni se incorporan ficheros, tablas o servicios de auditoría. Un fallo de persistencia posterior no convierte `simulated` en `failed`: ese estado describe la simulación, no la transacción.

## Tests previstos y trazabilidad
Usar pytest, TestClient y `unittest.mock` disponibles; sin nuevas dependencias ni SQLite. Los unitarios usarán `create_autospec`, `patch` y fixtures locales. Los tests con persistencia usan exclusivamente PostgreSQL de testing y las fixtures existentes, con migraciones y aislamiento transaccional. No se escriben ni ejecutan en esta fase.

| RF/RNF y aceptación | Casos y comprobaciones previstas | Archivos de tests | Tareas propuestas |
| --- | --- | --- | --- |
| RF-1, RF-10; CA-1, CA-3, CA-6 | Destino requerido/estricto/no nulo, vacío y campos desconocidos/inmutables; canales exactos; título 1/200/201 y contenido vacío/blanco/1/5000/5001, conservación de textos; schema JSON y HTTP | `test_notification_schemas.py`, `test_notifications.py` | T4, T5, T6 |
| RF-2, RF-6; CA-1, CA-4 | Tres canales: elegir solo uno, orden validar/preparar/registrar/guardar, una llamada y ninguna alternativa; datos/propietario correctos; validación o fallo interrumpe pasos posteriores; repetir POST produce dos simulaciones/filas distintas | `test_notification_delivery.py`, `test_notification_service.py`, `test_notifications.py` | T3, T4, T5 |
| RF-3, RF-5, RF-8; CA-2 | Email igual al criterio actual de registro (normalización, sintaxis, máximo exacto 254/exceso); template exacto con blancos/saltos de línea. Push payload exacto y token excluido. Preparación posterior a validar; error no registra éxito ni guarda | `test_notification_delivery.py`, `test_notifications.py` | T1, T3, T4, T5 |
| RF-1, RF-4, RF-6, RF-10, RNF-2; CA-3 | SMS con 7/8/15/16 dígitos, cero inicial, signos, espacios, guiones, salto final y dígitos Unicode rechazados; SMS de 159/160/161, acentos, emoji, saltos/espacios y secuencias combinadas cuentan por puntos de código sin truncado. Token 0/1/512/513, extremos !/~, controles, DEL, espacio y no ASCII. Destinatarios no cadena; sin filas nuevas ni simulación al rechazar | `test_notification_delivery.py`, `test_notification_schemas.py`, `test_notifications.py` | T1, T3, T4, T5 |
| RF-6, RF-7; CA-4 | Forzar fallos en preparación, registro, SQL antes del commit, refresh posterior y construcción de respuesta. Comprobar 500 exacto, ausencia/presencia de fila según punto de confirmación, recuperación de sesión, otros recursos intactos, sin reenvío/delete/commit adicional. Provocar fallo reversible con PostgreSQL real mediante `flush` dentro del commit sustituido antes de levantar SQLAlchemyError; distinguir esta excepción inyectada de los errores reales de restricciones existentes, que también se conservan | `test_notification_delivery.py`, `test_notification_service.py`, `test_notifications.py` | T2, T3, T4, T5 |
| RNF-2, RNF-3; CA-4, CA-5 | 422 con `field=recipient`/`content` y solo tres propiedades, mensajes españoles y códigos fijados; excepciones con marcadores sensibles nunca aparecen en cuerpo/logs; capturar salida real, sin traceback ni plantilla/cuerpo/JWT. 500 comprobado con TestClient normal, sin ocultar excepciones inesperadas con `raise_server_exceptions=False` | `test_validation_errors.py`, `test_notification_delivery.py`, `test_notifications.py` | T1, T2, T3, T4, T5 |
| RF-3–RF-5, RNF-3; CA-5 | JSON con los cinco campos/valores exactos y reloj aware fijo, UTC ISO 8601; email/push totalmente ocultos, SMS solo últimos cuatro. Fallos de reloj/logger/handler cortan antes de persistir; error al emitir evento failed no produce recursión. Log simulated puede permanecer tras escritura fallida y no certifica persistencia | `test_notification_delivery.py`, `test_notification_service.py`, `test_notifications.py` | T1, T2, T3, T4, T5 |
| RF-8, RF-9, RNF-1; CA-5, CA-6 | Ausencia de destino/estados en POST/GET/PATCH y esquema SQL sin columnas nuevas; registros previos creados directamente mediante repositorio siguen consultables/editables/borrables. PATCH rechaza recipient, admite contenido SMS de 5000 y cambio a SMS de recurso largo, no reenvía; GET/DELETE tampoco. Propietarios aislados, 404 indistinguibles y 401 actual sin sender ni escritura (tokens ausente, inválido, vencido, usuario borrado/inexistente) | `test_notification_schemas.py`, `test_notification_service.py`, `test_notifications.py`; suite auth existente | T4, T5, T6 |
| RNF-4; CA-7 | Inyectar estrategia ficticia mínima solo como doble de prueba en mapa unitario de sender/servicio; comprobar selección y flujo común sin tocar estrategias reales. Revisar que schema/servicio/sender no añaden ramas por canal y que el alta real futura se limita a comportamiento, registro y contratos/CHECK. No habilitar un cuarto canal en API/base | `test_notification_delivery.py`, `test_notification_service.py`; revisión del diseño | T1, T3, T4, T6 |
| RNF-5; CA-6, CA-8 | Composición sin efectos y usando sesión/overrides; regresiones completas de auth, formato de errores, migraciones y CRUD; OpenAPI/README/AGENTS coherentes, sin nuevas dependencias ni invocaciones de red/proveedor en código de envío | `test_notification_service.py`, `test_notifications.py`, tests existentes y revisión | T1–T6 |

Adaptar los tests actuales de forma selectiva: no añadir `recipient` indiscriminadamente a `VALID_NOTIFICATION`/datos usados para construir modelos o comparar respuestas. Separar payload de creación (destino ficticio adecuado al canal) de campos persistidos/públicos; conservar independientes PATCH y pruebas SQL. Sustituir únicamente expectativas obsoletas de POST, no eliminar cobertura de 001 para conseguir verde. Las pruebas sin autenticación deberán usar un nuevo cuerpo válido para comprobar el 401 real y ausencia de envío. Reiniciar mocks de simulación después del POST de preparación al verificar operaciones que no reenvían.

Para P3b, el test de refresh fallido debe ejecutar realmente el commit previo, sustituir solo la lectura posterior y consultar la fila en PostgreSQL al salir del parche; un rollback de lectura posterior no debe borrar esa inserción. La fixture usa savepoints, por lo que esta comprobación verifica la frontera de commit de aplicación sin dejar datos tras el test. Probar por separado fallos de `NotificationResponse.model_validate`, serialización y construcción de `JSONResponse`; verificar que el 201 normal pasa por el contrato público validado aunque FastAPI reciba una Response ya construida.

Los identificadores corresponden a las [tareas aprobadas](tasks.md), cuya ejecución agrupada T1–T6 fue autorizada expresamente por el usuario. La trazabilidad no cambia el diseño aprobado; T6 contrasta finalmente todos los requisitos y criterios. No se autoriza cierre ni ampliación de alcance.

## Verificación prevista y aprobación requerida
- Antes de implementar, después de aprobar plan y tareas, ejecutar `./up_test.sh` desde la raíz para obtener línea base actual. Los 426 tests/99% del 2026-11-08 son evidencia histórica, no ejecución de este plan. Un fallo de Docker/PostgreSQL bloquea la verificación y no demuestra un test rojo de comportamiento.
- En implementación, tests primero y comprobación del fallo esperado antes del cambio mínimo. Para un caso enfocado desde la raíz: `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/<archivo>.py::<test>`. Elegir el identificador real del test creado/adaptado en los archivos de esta matriz; reconstruir es necesario porque las imágenes copian fuentes.
- Al finalizar, ejecutar `./up_test.sh` desde la raíz con Docker disponible, revisar resultados/cobertura generada y contrastar CA-1–CA-8, OpenAPI, documentación y límites de edición aprobados. No usar base de desarrollo/producción. No hay frontend ni herramientas de verificación visual aplicables.
- Antes de la ejecución, esta sección registraba solo lectura y edición documental; sus comandos previstos se ejecutaron y sus resultados actuales están en la evidencia final siguiente. No se presume árbol limpio ni se autoriza el cierre de 002.
- No se detectaron contradicciones de alcance que requieran cambiar la spec. Plan y tareas aprobados, con ejecución agrupada T1–T6 terminada; cualquier cambio posterior de requisitos vuelve primero a aprobación de spec y el cierre necesita conformidad expresa posterior.

## Evidencia final de ejecución y trazabilidad

El 2026-11-09, desde la raíz y exclusivamente contra PostgreSQL `notifications_test`, T6 añadió `test_notification_openapi_explains_delivery_contract_limits`. Su RED verificó una omisión documental real de OpenAPI (normalización del email y semántica P3b): `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/test_notifications.py tests/test_notification_schemas.py tests/test_validation_errors.py` terminó con **420 passed, 1 failed en 16.24 s**. Tras completar solo las descripciones de schema/router autorizadas y la documentación, el mismo comando terminó con **421 passed en 15.82 s**. La verificación final `./up_test.sh` terminó con **550 passed en 19.07 s** y **98%** de cobertura; se inspeccionó `coverage/coverage.xml` (593/604 líneas, `line-rate="0.9818"`).

| Requisito | Evidencia real identificable |
| --- | --- |
| RF-1, RF-10 | `test_create_requires_all_fields`, límites/estrictez de schema y `test_api_create_persists_public_values_and_authenticated_owner`; OpenAPI verifica los cuatro requeridos y los tres canales. |
| RF-2 | `test_notification_sender_selects_one_actual_strategy_in_order`, `test_service_create_simulates_before_persisting_without_recipient` y `test_api_two_posts_emit_two_protected_events_and_two_independent_rows`. |
| RF-3 | Tests de estrategia email, orden de sender y `test_api_preparation_failure_records_one_protected_failure_and_never_persists`. |
| RF-4 | Límites SMS, Unicode y formatos en `test_notification_delivery.py` y HTTP en `test_api_recipient_boundaries_and_sms_unicode_code_points_are_accepted`. |
| RF-5 | Tests de estrategia/payload push, selección y validación HTTP de push. |
| RF-6 | Errores de validación, preparación y registrador antes de persistir en `test_notifications.py` y sender/registrador unitarios. |
| RF-7 | `test_api_reversible_postgresql_write_failure_rolls_back_and_preserves_existing_rows` y `test_api_postcommit_response_failures_return_safe_500_and_keep_confirmed_row` distinguen PostgreSQL reversible de P3b. |
| RF-8 | Respuestas públicas, schema `writeOnly`, inspección de columnas y tests GET/PATCH prueban que no existe ni se expone destinatario/estado. |
| RF-9 | `test_api_patch_rejects_recipient_without_partial_changes`, `test_api_patch_allows_sms_content_of_5000_without_resending` y `test_api_rest_crud_after_post_never_resends_or_records_events`. |
| RNF-1 | Matriz de tokens y propietarios en `test_all_notification_operations_reject_invalid_tokens_without_mutations` y pruebas de 404 ajeno/inexistente. |
| RNF-2 | `test_validation_errors.py`, contratos de schema y respuestas HTTP seguras verifican los tres campos y mensajes españoles. |
| RNF-3 | `test_notification_delivery.py` y pruebas HTTP de logs verifican cinco claves, UTC y redacción sin secretos. |
| RNF-4 | `test_notification_sender_allows_a_fictional_strategy_registered_only_in_its_map` prueba extensión solo por registro; no habilita un cuarto canal HTTP/SQL. |
| RNF-5 | Revisión de `delivery/`, DI y dependencias, más suite Docker final: sin proveedor, red, colas, reintentos ni dependencias nuevas. |

| Criterio | Contraste final |
| --- | --- |
| CA-1 | POST por email/SMS/push, único sender, propiedad y representación pública: pruebas de creación, sender y dos POST. |
| CA-2 | Template email, payload push, orden y exclusión de datos sensibles: pruebas unitarias de estrategia/sender y logs. |
| CA-3 | Fronteras SMS/destinatario, Unicode y 422 sin filas: tests de delivery, schema y HTTP. |
| CA-4 | Fallos de preparación/registro, rollback PostgreSQL y frontera postcommit P3b: tests adversariales de HTTP arriba citados. |
| CA-5 | Redacción, JWT/propietarios y 401 sin sender: tests de logger, privacidad y autenticación. |
| CA-6 | CRUD/PATCH sin reenvío, OpenAPI y documentación: tests de regresión y OpenAPI, más README/AGENTS actualizados. |
| CA-7 | Doble de estrategia ficticia y mapa explícito del sender, sin canal adicional de producción. |
| CA-8 | pytest, TestClient, `unittest.mock`, PostgreSQL de testing y suite Docker final correctos; no se usó SQLite ni se añadieron dependencias. La conformidad expresa del usuario para cerrar sigue pendiente. |

La trazabilidad confirma la implementación técnica de T1–T6, no cierra la spec ni afirma envío real, despliegue o recepción. El coordinador comunicó también `git diff --check` correcto del implementador y el veredicto técnico final APROBADO, sin hallazgos; el reviewer no ejecutó comandos por instrucción. Los avisos anteriores de contenedores huérfanos de Docker fueron no bloqueantes y no motivaron eliminación de contenedores. No hay bloqueos funcionales o técnicos pendientes comunicados. El siguiente paso es que el coordinador presente evidencias y revisión final al usuario y solicite conformidad expresa antes de cambiar el estado de la spec. Esta actualización documental no repitió verificaciones.
