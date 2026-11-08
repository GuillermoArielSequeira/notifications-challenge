# Spec 001 — Gestión de notificaciones propias

Estado: aprobada

## Contexto y objetivo
Permitir que un usuario autenticado cree, consulte, modifique y elimine sus propias notificaciones. Esta funcionalidad almacena las notificaciones, pero no las envía.

Se aplican los principios de [la constitución](../../docs/constitution.md).

## Usuarios
Usuarios registrados que hayan iniciado sesión.

## Historias de usuario
- **HU-1:** Como usuario, quiero crear una notificación indicando título, contenido y canal.
- **HU-2:** Como usuario, quiero modificar campos de una notificación propia.
- **HU-3:** Como usuario, quiero eliminar definitivamente una notificación propia.
- **HU-4:** Como usuario, quiero consultar todas mis notificaciones sin acceder a las de otras personas.

## Definiciones
- **Notificación propia:** pertenece al usuario autenticado que la creó.
- **Canal:** una única opción entre Email, SMS y Push.
- **Modificación parcial:** cambia únicamente los campos enviados; los omitidos conservan su valor.

## Requisitos funcionales
- **RF-1:** CUANDO un usuario cree una notificación válida, EL SISTEMA la guardará con un identificador único y la asociará al usuario autenticado.
- **RF-2:** EL SISTEMA exigirá título de 1–200 caracteres, contenido de 1–5000 caracteres y un canal permitido para crear una notificación.
- **RF-3:** SI título o contenido contienen únicamente espacios en blanco, ENTONCES EL SISTEMA rechazará la operación.
- **RF-4:** CUANDO un usuario modifique una notificación propia, EL SISTEMA actualizará únicamente los campos enviados, aplicando las mismas validaciones que en la creación.
- **RF-5:** SI una modificación no incluye ningún campo modificable, contiene valores nulos o incumple las validaciones, ENTONCES EL SISTEMA la rechazará sin guardar cambios.
- **RF-6:** CUANDO un usuario elimine una notificación propia, EL SISTEMA la borrará definitivamente y dejará de incluirla en las consultas.
- **RF-7:** CUANDO un usuario consulte sus notificaciones, EL SISTEMA devolverá exclusivamente todas las suyas; si no tiene ninguna, devolverá una lista vacía.
- **RF-8:** SI una operación apunta a una notificación inexistente o ajena, ENTONCES EL SISTEMA responderá como recurso no encontrado, sin revelar su existencia ni modificar datos.
- **RF-9:** EL SISTEMA impedirá cambiar el propietario y el identificador de una notificación.

## Requisitos no funcionales
- **RNF-1:** Todas las operaciones requieren un token válido; su ausencia o invalidez produce HTTP 401.
- **RNF-2:** Los errores de validación mantienen HTTP 422 y el contrato `detail` con `type`, `field` y `message`; los nuevos mensajes dirigidos al usuario están en español.
- **RNF-3:** Las operaciones sobre recursos inexistentes o ajenos responden HTTP 404.
- **RNF-4:** Las pruebas verifican aislamiento entre usuarios y usan únicamente datos de testing, conforme a la constitución.

## Casos límite
- Límites exactos de longitud y valores que los exceden.
- Campos obligatorios ausentes, nulos o con tipos incorrectos.
- Canal desconocido.
- Modificación de un solo campo o modificación vacía.
- Eliminación repetida de la misma notificación.
- Usuario sin notificaciones.
- Intentos de consultar o modificar datos de otro usuario.

Los textos se conservarán tal como se reciben; las longitudes se medirán sobre el valor recibido. La consulta no requiere un orden específico.

## Fuera de alcance
Envío real o simulado, destinatarios, programación de envíos, estados de entrega o lectura, recuperación de eliminadas, paginación, filtros, frontend y consulta individual como operación independiente.

## Criterios de finalización
- Las cuatro operaciones cumplen sus requisitos.
- Las pruebas cubren éxito, validaciones, límites, autenticación y aislamiento entre dos usuarios.
- Una operación rechazada no modifica datos.
- La suite completa pasa y los contratos y la documentación reflejan el comportamiento aprobado.

## Dudas abiertas
Ninguna pendiente: el usuario aprobó explícitamente la spec en la conversación. Los detalles técnicos se proponen en el plan y requieren aprobación independiente.
