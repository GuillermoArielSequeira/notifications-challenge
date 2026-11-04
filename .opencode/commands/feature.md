---
description: Propone una spec y aclara requisitos antes de planificar una funcionalidad
agent: plan
---
Quiero añadir esta funcionalidad: $ARGUMENTS

1. Carga la skill `sdd` y lee explícitamente `AGENTS.md`, `docs/constitution.md`, `MEMORY.md` y el código relacionado. Si hay una spec activa, lee también su `spec.md`, `plan.md` y `tasks.md` cuando existan.
2. Identifica qué existe hoy y qué falta. Pregunta solo por decisiones de alcance, comportamiento o aceptación que el repositorio no resuelva; señala cualquier contradicción antes de continuar.
3. Propón en la conversación una spec breve con objetivo, requisitos verificables, casos límite, fuera de alcance, criterios de aceptación y dudas abiertas. Sigue la plantilla de la skill; no incluyas todavía el plan técnico.
4. Indica la carpeta propuesta `specs/NNN-nombre/` sin crearla, renombrar carpetas existentes ni asumir que una carpeta vacía es una spec aprobada.
5. Detente y espera aprobación explícita de la spec. Esa aprobación habilita proponer el plan, no implementar la funcionalidad: el plan y las tareas también requieren aprobación.

No modifiques archivos ni instales dependencias. Este comando usa el agente Plan y solo presenta borradores; para guardar los documentos aprobados en el repositorio, solicita cambiar a un agente con permisos de edición.
