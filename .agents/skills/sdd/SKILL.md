---
name: sdd
description: Úsala siempre que trabajes con Spec-Driven Development en este proyecto (docs/constitution.md o cualquier archivo dentro de specs/) - redactar, revisar o cambiar specs, planes y tareas, o implementar y validar tareas de una spec.
---

# Spec-Driven Development (SDD)

## Contexto y límites
- Lee `AGENTS.md`, `docs/constitution.md`, `MEMORY.md`, la spec activa y el código relacionado antes de proponer cambios. No preguntes lo que el repositorio ya responde.
- Cada funcionalidad vive en `specs/NNN-nombre/`, con solo `spec.md`, `plan.md` y `tasks.md` por defecto. No renombres ni sobrescribas trabajo existente sin aprobación.
- La constitución fija los principios y la spec aprobada el comportamiento y el alcance. Las skills son apoyo técnico, no permiso para ampliar ese alcance.
- Si los documentos se contradicen, señala el conflicto y pide una decisión. No elijas silenciosamente qué instrucción ignorar.
- Aplica este flujo a cambios nuevos, sin crear specs retrospectivas de todo el código existente.

## Flujo y aprobaciones
1. **Spec y aclaraciones:** acuerda el qué y el por qué; resuelve dudas que afecten alcance, comportamiento o criterios de aceptación. Espera aprobación explícita de la spec antes del plan.
2. **Plan:** propone cómo cumplir la spec con el stack actual, justifica decisiones técnicas y espera aprobación antes de desglosar tareas.
3. **Tareas:** presenta el orden de implementación y las comprobaciones de cada tarea. Espera aprobación antes de implementar.
4. **Implementación:** ejecuta una sola tarea aprobada con tests primero; informa el resultado y espera aprobación antes de la siguiente.
5. **Validación y cierre:** contrasta los resultados con los criterios de aceptación, presenta evidencias y espera conformidad del usuario antes de cerrar la spec.
- Una aprobación no autoriza fases que todavía no se presentaron. No registres aprobaciones implícitas o inventadas.
- Al terminar cada fase o tarea, actualiza el bloque de trabajo activo de `MEMORY.md` con fase, aprobaciones, próximo paso y bloqueos. No copies allí requisitos ni listas de tareas.
- En el agente Plan, presenta borradores en la conversación; no intentes guardar documentos del repositorio si el modo no lo permite. Para persistirlos, solicita cambiar a un agente con edición.

## Plantilla de spec (spec.md)
```markdown
# Spec NNN — <Nombre>
Estado: borrador | aprobada | implementada
## Contexto y objetivo
## Usuarios
## Historias de usuario
- HU-1. Como <rol>, quiero <acción> para <beneficio>.
## Definiciones (solo si hay términos que puedan interpretarse de varias formas)
## Requisitos funcionales
## Requisitos no funcionales
## Casos límite
## Fuera de alcance
## Criterios de finalización
## Dudas abiertas
- [NECESITA ACLARACIÓN] <duda>
```
- La spec describe el QUÉ y el POR QUÉ. Las decisiones de stack, arquitectura y archivos pertenecen al plan; referencia la constitución sin copiarla.
- Usa `RF-1`, `RF-2` para requisitos funcionales y `RNF-1`, `RNF-2` para los no funcionales. Los criterios de aceptación deben permitir comprobar su cumplimiento.
- `implementada` requiere validación y cierre aprobados; no basta con haber escrito el código. Si hay un bloqueo, conserva el estado previo y descríbelo en `MEMORY.md`.

## Requisitos en EARS (en español)
- RF-x: CUANDO <evento>, EL SISTEMA <respuesta>.
- RF-x: SI <condición no deseada>, ENTONCES EL SISTEMA <respuesta>.
- RF-x: MIENTRAS <estado>, EL SISTEMA <respuesta>.
- RF-x: EL SISTEMA <comportamiento permanente>.
- Cada requisito debe ser verificable: nada de "rápido", "intenso" o "bonito" sin un criterio medible.

## Plan (plan.md)
- Incluye archivos y responsabilidades, interfaces, decisiones justificadas y alternativas descartadas; pseudocódigo solo si aclara un algoritmo no trivial.
- Favorece funciones fáciles de probar. Inyecta fecha/hora únicamente cuando la lógica dependa del tiempo; no agregues parámetros o abstracciones sin necesidad.
- Describe tests de éxito, errores y límites usando las herramientas existentes; no instales dependencias de testing ni sustituyas PostgreSQL por SQLite.
- Relaciona cada RF/RNF con las tareas y tests que lo verifican. Una tabla breve en el plan basta; no crees otro documento de trazabilidad.
- Para tests locales del backend, ejecuta `python -m pytest -v tests/<archivo>.py::<test>` desde `backend/`, con el entorno existente y la base de testing disponible si corresponde.
- Para un test Docker desde la raíz: `docker compose -f docker-compose.test.yml run --rm --build tests python -m pytest -v tests/<archivo>.py::<test>`; reconstruir incluye los cambios de código.
- La verificación completa es `./up_test.sh` desde la raíz y requiere Docker activo. No supongas que existen comandos de tests del frontend mientras no esté implementado.

## Tareas (tasks.md)
```markdown
- [ ] **Tn. <Descripción>.** RF-x, RF-y
- Hecho cuando: <comprobación verificable>.
```
- Ordena por dependencias; cada tarea entrega un resultado pequeño, verificable y vinculado a requisitos aprobados.
- Usa 20–30 minutos como orientación, no como límite obligatorio. Si salen más de diez tareas, revisa si la spec abarca varias funcionalidades antes de proponer dividirla.

## Implementación
- Para cambios de comportamiento: escribe el test, ejecútalo y comprueba que falla por el motivo esperado; implementa lo mínimo y verifica que pasa. Un fallo de infraestructura no demuestra el estado rojo del comportamiento.
- No inventes tests de comportamiento para cambios exclusivamente documentales; verifica sus enlaces, formato y coherencia.
- Marca una tarea como terminada solo cuando cumpla su comprobación y hayas leído la salida de sus verificaciones. Si está bloqueada, déjala sin marcar y pide ayuda cuando sea necesaria.
- Informa archivos cambiados, RF/RNF cubiertos, comandos ejecutados y resultados; después detente antes de la siguiente tarea.
- No agregues dependencias ni realices commits, pushes, cambios de despliegue o acciones destructivas sin la autorización correspondiente.

## Cambios y cierre
- Si cambian requisitos, actualiza primero la spec y solicita nueva aprobación; después ajusta el plan y las tareas afectados y sus aprobaciones, antes de cambiar código.
- Una corrección técnica que preserva el comportamiento aprobado no requiere inventar requisitos nuevos; documenta el ajuste técnico y vuelve a pedir aprobación si cambia el plan acordado.
- Antes del cierre, comprueba cada criterio de aceptación, ejecuta `./up_test.sh` y revisa contratos, OpenAPI y documentación cuando corresponda. Registra comando, resultado y contexto de la ejecución.
- Si una comprobación falla o no puede ejecutarse, informa el bloqueo. No declares validada o cerrada la spec ni presentes verificaciones históricas como resultados de esta sesión.
