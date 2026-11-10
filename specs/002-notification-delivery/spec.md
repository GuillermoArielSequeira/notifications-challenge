# Spec 002 — Envío de notificación

Estado: aprobada

Aprobación: el 2026-11-08 el usuario respondió expresamente «apruebo la spec» al resumen y enlace de este documento, incluidas P1, P2, P3/P3b y P4 revisadas técnicamente, según lo comunicado por el coordinador. Posteriormente aprobó el plan y la ejecución agrupada de T1–T6; las seis tareas tienen evidencia técnica en [tasks.md](tasks.md) y [plan.md](plan.md). La spec sigue **aprobada**, no implementada ni cerrada: su cierre requiere conformidad expresa posterior del usuario.

Validación técnica final: el 2026-11-09 el coordinador comunicó el veredicto APROBADO técnico del reviewer, sin hallazgos y con evidencia suficiente para presentar al usuario. El reviewer no ejecutó comandos por instrucción; no es conformidad del usuario ni cierre de la spec. Sin bloqueos funcionales o técnicos pendientes comunicados; próximo paso: presentar evidencias y solicitar conformidad expresa de cierre.

## Contexto y objetivo
Al inicio de esta spec, el backend implementaba autenticación y CRUD de notificaciones propias, cerrado en [001](../001-notifications/spec.md), y POST solo guardaba `title`, `content` y `channel`. El usuario dispone de email de cuenta, pero no de teléfono ni token de dispositivo. Esta implementación añade la simulación local con destinatario efímero; el frontend sigue pendiente.

Se busca que cada creación válida ejecute una simulación de envío según el canal elegido, con sus validaciones, preparación del mensaje y registro técnico. Una creación solo será exitosa si la simulación y el guardado terminan correctamente. La solución debe permitir incorporar canales sin reescribir el comportamiento de los existentes ni la lógica común de creación/envío. Se aplica [la constitución](../../docs/constitution.md); el diseño se decidirá en el plan.

### Decisiones expresamente confirmadas
- Cerrar 001 y comenzar 002, únicamente en planificación y comenzando por la spec.
- El destinatario se proporciona en POST según el canal; no se deduce del perfil.
- SMS con más de 160 caracteres rechaza la creación, sin truncar, guardar ni enviar.
- Los registros son logs técnicos con protección de datos sensibles, sin historial consultable por API.
- La validación o simulación fallida rechaza la creación sin dejar una notificación guardada.

### Precisiones aprobadas
Las marcas **P1–P4** identifican las precisiones incluidas en la aprobación explícita de la spec; se conservan como referencias de sus requisitos y criterios.

- **P1 — Destinatario efímero:** un único campo JSON obligatorio `recipient`, de tipo cadena, interpretado según `channel`. Solo se usa para la simulación de esa creación; no se persiste ni se incluye en respuestas. Evita almacenar datos sensibles sin necesidad de historial o reenvío. Formatos definidos en Definiciones.
- **P2 — Resto del CRUD intacto:** PATCH no acepta `recipient`, no envía ni reenvía y conserva sus campos actuales. El límite SMS de 160 se aplica únicamente al contenido enviado al crear; PATCH conserva el límite general de 5000, incluso para un recurso cuyo canal sea SMS. Esto permite editar un SMS a más de 160 o cambiar a SMS un recurso largo, pero no lo envía; también preserva notificaciones previas. Aplicar el límite al estado resultante de PATCH sería un cambio de comportamiento adicional que necesita decisión expresa.
- **P3 — Errores:** entrada inválida devuelve el 422 seguro existente. Un fallo de ejecución de la simulación, de escritura o de preparación de la respuesta devuelve 500 con `{"detail":"No se pudo completar la creación de la notificación."}`, sin detalles internos ni datos de entrada. No se agregan fallos aleatorios ni valores especiales del destinatario para provocar errores; estos se verifican mediante sustituciones controladas en pruebas.
  - **P3b — Alcance de la garantía:** validación o simulación fallidas nunca dejan una notificación guardada, conforme a lo confirmado por el usuario. Si falla la escritura antes de su confirmación y es reversible, no queda una fila nueva. Si el guardado ya se confirmó correctamente y falla un paso posterior necesario para preparar la respuesta, la fila puede existir aunque se devuelva el 500 seguro; no se borra compensatoriamente ni se vuelve a simular automáticamente. Una respuesta HTTP de error no demuestra por sí sola ausencia de fila. El repositorio actual confirma la escritura antes de una lectura final; las alternativas para evitar operaciones posteriores a la confirmación se evaluarán en el plan, sin imponer aquí un refactor ni garantías distribuidas entre guardado y respuesta.
- **P4 — Preparación y logs mínimos:** las representaciones y campos mínimos definidos en Definiciones hacen comprobable la simulación sin exponer destinatarios ni representaciones adicionales del template/payload en la API. Las respuestas correctas conservan los campos públicos actuales, incluidos `title` y `content`; no se ocultan esos textos. Un log de simulación no certifica recepción real ni, por sí solo, persistencia.

## Usuarios
- Usuario autenticado que crea notificaciones propias y especifica un destino para el canal elegido.
- Persona que mantiene el backend y necesita distinguir la simulación de cada canal sin acceder a datos sensibles en logs.

## Historias de usuario
- **HU-1:** Como usuario autenticado, quiero que crear una notificación simule su envío al destinatario indicado para comprobar el comportamiento del canal.
- **HU-2:** Como usuario, quiero que una creación con entrada inválida o simulación fallida no deje una notificación guardada para evitar registros que aparenten éxito.
- **HU-3:** Como persona que mantiene el sistema, quiero incorporar otro canal sin modificar las reglas de los canales existentes ni el flujo común de creación/envío.

## Definiciones
- **Envío simulado:** ejecución local de validación, preparación y registro, sin proveedor ni comunicación de red. No demuestra recepción real y no genera estados públicos de entrega.
- **Destinatario (P1):** `recipient` no admite null, omisión, coerción de tipos ni valores vacíos. No exige que exista una cuenta registrada para ese destino.
  - `email`: dirección con el mismo criterio sintáctico y máximo de 254 caracteres que el registro actual, incluida su normalización de espacios externos y minúsculas; sin comprobar existencia del buzón ni consultar DNS. Ejemplo ficticio: `recipient@example.com`.
  - `sms`: signo `+` seguido de 8–15 dígitos ASCII, con primer dígito distinto de cero; sin espacios, guiones ni normalización. Ejemplo ficticio: `+12345678901`. Es una convención sintáctica de la simulación, no una comprobación de país, operador o número real.
  - `push`: token simulado de 1–512 caracteres ASCII visibles (U+0021 a U+007E); sin espacios ni caracteres de control y sin normalización. Ejemplo ficticio: `device-token-demo`. No se exige formato ni validez de un proveedor real; no es el JWT de autenticación.
- **Longitud SMS:** se cuenta solo `content` recibido, incluidos espacios y saltos de línea, en puntos de código Unicode; no bytes, grafemas, codificación GSM ni segmentos. No se recorta ni normaliza el contenido. El título no forma parte del texto SMS.
- **Template email (P4):** representación de texto plano con el título, dos saltos de línea y el contenido, preservando ambos textos. No incluye HTML ni plantillas aportadas por el usuario.
- **Payload push (P4):** representación con `title` igual al título y `body` igual al contenido; el token sirve de destino y no se incorpora a esos campos.
- **Registro técnico (P4):** evento con claves `event`, `channel`, `status`, `timestamp` y `recipient`; `event` vale `notification_delivery`, `status` vale `simulated` al completar la simulación o `failed` si falla su ejecución, y `timestamp` expresa fecha y hora UTC en ISO 8601. `recipient` vale `[redacted]` para email/push; para SMS conserva solo los últimos cuatro dígitos y sustituye cada carácter anterior por `*`. Nunca contiene el token push, ni siquiera parcialmente.
  - El registro de éxito se refiere únicamente a la simulación completada; un fallo posterior al guardar puede dejar ese log técnico, pero no permite devolver 201. No se promete una transacción atómica entre logs y base de datos ni un historial durable de auditoría.
  - Validación rechazada no exige un evento de envío; nunca se registra como simulación exitosa. Un fallo anterior a completar la simulación tampoco produce un evento con `status=simulated`.
  - Si falla el propio registro técnico, la creación se rechaza sin fila nueva; no se exige poder emitir un segundo evento de error por el mismo medio fallido.

## Requisitos funcionales
- **RF-1:** CUANDO un usuario autenticado solicite crear una notificación mediante `POST /api/v1/notifications`, EL SISTEMA exigirá título, contenido, un canal entre `email`, `sms` y `push`, y un destinatario correspondiente a ese canal; no utilizará un destino implícito del perfil. La forma `recipient` y sus formatos corresponden a P1.
- **RF-2:** CUANDO la entrada de creación sea válida, EL SISTEMA ejecutará una única simulación del canal elegido durante esa solicitud y devolverá 201 únicamente después de completar correctamente simulación y guardado, con la notificación asociada al usuario autenticado. No ejecutará los otros canales.
- **RF-3:** CUANDO se cree una notificación por email, EL SISTEMA validará la dirección destinataria, generará el template con título y contenido y registrará la simulación de envío, en ese orden; no realizará pasos posteriores si falla uno anterior. Formato del template y del registro según P4.
- **RF-4:** CUANDO se cree una notificación por SMS, EL SISTEMA validará el número, verificará que el contenido tenga entre 1 y 160 caracteres y registrará el número protegido y la fecha/hora de simulación. SI el contenido excede 160 caracteres, ENTONCES EL SISTEMA rechazará la creación sin truncarlo, guardarlo ni simular el envío. Formato del número según P1 y registro según P4.
- **RF-5:** CUANDO se cree una notificación push, EL SISTEMA validará el token de dispositivo, formateará el payload y registrará el estado de la simulación, en ese orden; no realizará pasos posteriores si falla uno anterior. Validación sintáctica según P1 y payload/registro según P4.
- **RF-6:** SI falla cualquier validación o la ejecución de la simulación, ENTONCES EL SISTEMA rechazará la creación sin dejar una notificación nueva persistida, sin cambiar notificaciones existentes y sin responder éxito. El código y cuerpo para fallos de ejecución se definen en P3.
- **RF-7 (P3/P3b):** SI falla una escritura reversible antes de confirmarse el guardado, ENTONCES EL SISTEMA rechazará la operación sin dejar una fila nueva. SI el guardado ya se confirmó correctamente y falla un paso posterior de preparación de la respuesta, ENTONCES EL SISTEMA devolverá el 500 seguro, pudiendo existir la fila confirmada, sin borrarla compensatoriamente ni volver a simular automáticamente. En ninguno de esos fallos responderá 201 ni reintentará automáticamente la simulación; los logs mantienen la semántica definida en P4. Esta precisión aprobada no reduce la garantía confirmada de RF-6.
- **RF-8 (P1):** EL SISTEMA utilizará el destinatario únicamente para la simulación de creación, sin persistirlo ni devolverlo en POST, GET o PATCH; mantendrá la representación pública `id`, `title`, `content`, `channel` sin añadir estados de entrega.
- **RF-9 (P2):** CUANDO se consulten, modifiquen o eliminen notificaciones, EL SISTEMA conservará el comportamiento de 001 y no ejecutará envíos; PATCH rechazará `recipient` como campo no permitido y mantendrá el límite general de contenido de 5000. Las notificaciones previas sin destinatario seguirán disponibles sin migración de destinatarios ni envío retroactivo.
- **RF-10:** EL SISTEMA conservará para la creación las validaciones actuales de título de 1–200 caracteres y contenido no vacío ni compuesto solo por blancos, de hasta 5000 para email/push y hasta 160 para SMS; conservará los textos recibidos y rechazará campos desconocidos, identificador o propietario aportados por el cliente.

## Requisitos no funcionales
- **RNF-1:** EL SISTEMA conservará la autenticación JWT y el aislamiento entre propietarios de 001; ante token ausente o inválido responderá 401 y no ejecutará la simulación ni guardará datos. Editar/borrar recursos ajenos e inexistentes conservará el mismo 404 sin revelar su existencia.
- **RNF-2:** SI la entrada es inválida, ENTONCES EL SISTEMA devolverá 422 con `detail` y errores que contengan solo `type`, `field`, `message`, con mensajes nuevos en español y sin valores recibidos. Para `recipient` inválido se señalará `recipient`; para exceso SMS se señalará `content`. Los códigos de error se concretarán en el plan; P3 define la respuesta a fallos de ejecución.
- **RNF-3:** EL SISTEMA evitará registrar destinatarios en claro, JWT, contraseñas, tokens push, título, contenido, template o payload en los logs de esta funcionalidad, incluidos sus errores; no incluirá cuerpos completos ni mensajes de excepciones que puedan contener esos datos. La representación protegida del número SMS y los campos permitidos se definen en P4.
- **RNF-4:** EL SISTEMA permitirá añadir el comportamiento de un canal nuevo sin modificar las reglas de los canales existentes ni la lógica común que coordina creación y envío. El alta podrá requerir registro del canal y ampliación explícita de contratos, validaciones y restricciones de persistencia: el catálogo actual está cerrado en varias partes del código. Esta spec admite solo los tres canales actuales; no requiere aceptar canales arbitrarios ni implementar un cuarto canal.
- **RNF-5:** EL SISTEMA realizará la simulación sin proveedores externos, llamadas de red, colas, reintentos automáticos ni nuevas dependencias; conservará el stack y las herramientas de verificación establecidos por la constitución.

## Compatibilidad y casos límite
- **Cambio incompatible de POST:** clientes actuales que solo envían `title`, `content`, `channel` deberán añadir el destinatario. Omitirlo producirá 422; no habrá fallback al email de cuenta. Esta ruptura ya fue implementada técnicamente en T4; el cierre de la spec sigue pendiente de conformidad expresa del usuario.
- SMS de 159 y 160 caracteres válido frente a 161 rechazado; contar también espacios, saltos de línea, caracteres acentuados y secuencias Unicode compuestas según la definición anterior.
- Destinatario ausente, null, vacío, tipo incorrecto o incompatible con el canal; teléfono con 7/8/15/16 dígitos, cero inicial o caracteres no permitidos; token con 0/1/512/513 caracteres, espacios o controles; email inválido o que exceda 254.
- Canal desconocido, mayúsculas o espacios en el canal siguen rechazándose; no se invoca un canal alternativo ante error.
- Título o contenido inválidos se rechazan antes de ejecutar la simulación. Un campo válido junto a uno inválido no produce guardado parcial ni log de éxito.
- Fallo durante generación de template, formateo de payload o registro de la simulación: comprobar rechazo, seguridad de errores y ausencia de filas nuevas. Bajo P3b, comprobar también ausencia de fila si falla una escritura reversible antes de confirmar el guardado; las notificaciones existentes de ambos propietarios se conservan.
- Bajo P3b, si el guardado se confirmó y falla la preparación posterior de la respuesta, comprobar el 500 seguro y que la fila confirmada puede seguir existiendo, sin borrado compensatorio, repetición automática de la simulación ni cambios en otras notificaciones. No interpretar todo error HTTP como creación no guardada ni prometer atomicidad distribuida entre base de datos y respuesta.
- Solicitudes POST repetidas son creaciones distintas, como actualmente; no se introduce idempotencia ni garantía de exactamente una vez entre solicitudes. Cada ejecución exitosa genera su propia simulación.
- Bajo P2, cambiar título/contenido/canal mediante PATCH no representa lo enviado originalmente ni provoca reenvío; la notificación sigue siendo un recurso editable, no un comprobante histórico de entrega.

## Fuera de alcance
- Envíos reales, proveedores, SDK, consultas DNS o comprobación de entrega, teléfono o dispositivo reales.
- Endpoint de envío independiente, reenvíos por PATCH, programación, procesamiento asíncrono, colas, reintentos, idempotencia y garantías distribuidas de entrega.
- Historial de envíos en API/base de datos, estados públicos de entrega/lectura, métricas, plataforma de auditoría o cambios de retención de logs.
- Modificar perfiles para guardar teléfonos/tokens, contactos, destinatarios múltiples, plantillas configurables, HTML, adjuntos, segmentación de SMS o truncado.
- Nuevos canales, frontend, UI o comprobación visual; refactors ajenos, despliegue, configuración y dependencias nuevas.

## Criterios de finalización
Estos criterios están aprobados, incluidas las precisiones P1–P4; definen la aceptación, no son por sí mismos resultados. Las evidencias técnicas están registradas en el plan y las tareas; la conformidad expresa del usuario exigida para cerrar sigue pendiente.

| Criterio | Comprobación de aceptación | Requisitos |
| --- | --- | --- |
| CA-1 — Creación por canal | Para cada canal, una solicitud autenticada válida devuelve 201, una fila propia con los textos intactos, una sola simulación del canal elegido y ningún otro canal; respuesta sin destinatario ni estado | RF-1–RF-5, RF-8, RF-10 |
| CA-2 — Email y push | Verificar validación antes de preparación y preparación antes del registro; template y payload contienen exactamente los datos definidos y no se registran en logs ni se añaden como representaciones a la API. Las respuestas correctas conservan `title` y `content` actuales | RF-3, RF-5, RF-8, RNF-3 |
| CA-3 — SMS y destinatarios | Aceptar límites exactos de número/token y SMS de 160; rechazar 161 y todos los formatos/tipos/omisiones inválidos con 422 seguro, sin simulación exitosa ni filas nuevas; conservar contenido, sin truncado | RF-1, RF-4, RF-6, RF-10, RNF-2 |
| CA-4 — Fallos controlados | Forzar fallos de preparación y ejecución/registro de la simulación: verificar respuesta no exitosa conforme a P3, ausencia de filas nuevas y ningún paso posterior de simulación tras el fallo. Bajo P3b, distinguir una escritura reversible fallida antes de confirmar (sin fila nueva) de un fallo de preparación de respuesta después de un guardado confirmado (500 seguro, la fila confirmada puede existir y no se borra compensatoriamente). Comprobar ausencia de repetición automática de la simulación y de cambios en notificaciones existentes en ambos casos. No inferir ausencia de fila de todo error HTTP ni confundir un log de simulación completada con confirmación de guardado | RF-2–RF-7, RNF-2, RNF-3 |
| CA-5 — Seguridad y logs | Capturar logs de éxito/error: canal/estado/fecha verificables, teléfono enmascarado, email/token ocultos y ausencia de título, contenido, template, payload, JWT y errores internos sensibles; dos usuarios no acceden ni afectan recursos ajenos; 401 no simula ni guarda | RNF-1–RNF-3 |
| CA-6 — Regresión y contrato | GET/PATCH/DELETE, recursos anteriores y aislamiento cumplen 001 con las precisiones de P2; nunca envían y PATCH rechaza destinatario. OpenAPI y documentación de implementación explican destinatario obligatorio, reglas por canal, errores y ruptura de compatibilidad de POST | RF-8–RF-10, RNF-1, RNF-2 |
| CA-7 — Extensibilidad acotada | Revisión demuestra que añadir un canal requiere su comportamiento y alta/contratos/restricciones pertinentes, no editar reglas existentes ni el flujo común; sin implementar un canal extra o prescribir un patrón en esta spec | RNF-4 |
| CA-8 — Verificación final | Pruebas de éxito, errores, límites y regresión usando pytest, TestClient y unittest.mock existentes; integración con PostgreSQL de testing y fixtures `db_test_client`/`db_session`, sin SQLite ni dependencias nuevas; suite completa correcta y conformidad expresa del usuario para cerrar | Todos, RNF-5 |

La verificación completa es `./up_test.sh` desde la raíz. Para un caso enfocado se usa `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/<archivo>.py::<test>`. Los resultados reales del implementador constan en el plan y las tareas; esta actualización documental no repitió comandos ni tests. No aplica verificación visual.

## Dudas abiertas
Ninguna pendiente de alcance: P1, P2, P3/P3b y P4 quedaron resueltas por la aprobación explícita comunicada por el coordinador. El usuario aprobó el [plan](plan.md) el 2026-11-09 con «apruebo el plan» y posteriormente todas las [tareas](tasks.md) con «si apruebo todas las tareas, ejecutalas todas y avisame cuando termines», según lo comunicado por el coordinador. La ejecución autorizada T1–T6 terminó con evidencias técnicas registradas; no autoriza cierre, cambios de alcance ni otras fases. La spec sigue aprobada hasta recibir conformidad expresa del usuario para cerrarla.
