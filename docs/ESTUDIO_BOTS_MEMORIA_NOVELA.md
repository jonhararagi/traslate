# Estudio: bots, idioma, lore y memoria para crear novelas

**Fecha de investigación:** 2026-10-26  
**Repositorio:** `jonhararagi/traslate`  
**Rama de trabajo:** `feat/novel-writing-studio-memory-panel`  
**Estado:** estudio y especificación preliminar; **el panel de creación de novelas todavía no está implementado**.

## Decisión ejecutiva

No conviene permitir que «cualquier bot» escriba la novela sin control ni asumir que un modelo recordará todo por tener una ventana de contexto grande. La propuesta es separar cuatro elementos:

1. **Modelo:** el motor que redacta, analiza o propone ideas. Debe poder cambiarse sin perder el proyecto.
2. **Personalidad/rol del bot:** instrucciones concretas para el tipo de tarea (coautor, guardián del lore, editor de continuidad, editor de idioma o planificador).
3. **Memoria interna del proyecto:** datos persistentes, estructurados, consultables y versionados, guardados localmente.
4. **Control de canon:** distinguir los hechos aprobados por el autor de las propuestas generadas, los borradores y las contradicciones no resueltas.

La memoria es la parte que evita depender de una conversación larga. Cambiar de modelo no debe borrar personajes, reglas del mundo, el idioma ni el historial de capítulos.

## Qué enseñan las herramientas existentes

| Herramienta/patrón | Aporta | Riesgo o límite | Lección para NovelTrad |
|---|---|---|---|
| [SillyTavern — World Info/Lorebooks](https://docs.sillytavern.app/usage/core-concepts/worldinfo/) | Inserta entradas de lore cuando aparecen palabras clave; el prompt incluye información contextual relevante. | La documentación advierte que el lore guía al modelo, pero no garantiza que el modelo lo respete. | Recuperar lore de forma selectiva y auditar la respuesta; no tratar una entrada insertada como garantía de continuidad. |
| [SillyTavern — conceptos y funciones](https://docs.sillytavern.app/) | Tarjetas de personaje, chats de grupo, documentación de personajes y recuperación de documentos/Data Bank. | Es una interfaz muy flexible de conversación/roleplay; el autor debe definir por su cuenta cómo mantener el canon de una novela. | Separar las tarjetas de rol de la memoria estructurada de la obra. Los roles pueden ser presets del mismo modelo, no bots diferentes ejecutándose a la vez. |
| [Novelcrafter — Codex](https://www.novelcrafter.com/help/docs/codex/the-codex) | Un centro organizado de personajes, lugares, objetos y hechos de la historia que el escritor puede consultar. | Tener un códice no elimina las alucinaciones ni los conflictos entre versiones. | Construir una biblia narrativa editable con estados, fuentes, relaciones y control de cambios. |
| NovelTrad actual | Lector EPUB/PDF, persistencia SQLite, glosario por libro, originales inmutables, historial de traducciones y asistencia ChatGPT/Gemini por intercambio manual. | El producto está orientado principalmente a leer/traducir; aún no es un taller completo para escribir y mantener la biblia de una novela original. | Añadir un espacio separado «Taller de novela» reutilizando la persistencia local, la selección explícita del proveedor y la revisión manual. |

## Memoria narrativa que debe conservarse

La memoria no será solo una transcripción de chats. Debe guardar objetos que se puedan consultar de forma precisa:

- **Biblia del proyecto:** premisa, género, tono, público, límites creativos, idioma de salida, persona y tiempo verbal preferidos.
- **Personajes:** nombres y alias, edad si se conoce, apariencia, voz, objetivos, miedos, habilidades, límites, relaciones, secretos y qué información conoce cada personaje.
- **Mundo y lore:** lugares, culturas, organizaciones, reglas físicas/mágicas, tecnología, economía, rangos, objetos, sistemas de poder y sus restricciones.
- **Cronología:** acontecimiento, fecha relativa, lugar, participantes, consecuencias y capítulos en los que se estableció.
- **Tramas y pistas:** hilo narrativo, pregunta abierta, pista plantada, revelación prevista, estado y capítulo de origen.
- **Idioma y estilo:** idioma, variedad regional del español, registro, tratamiento, convención de diálogo, formato de pensamientos, honoríficos, glosario y ejemplos aprobados por el autor.
- **Capítulos y escenas:** objetivo dramático, punto de vista, personajes presentes, cambios de estado, resumen factual y versión del texto.
- **Continuidad y decisiones:** contradicciones detectadas, dudas pendientes, decisiones aprobadas/rechazadas y registro de quién cambió cada dato.
- **Reglas de seguridad narrativa:** secretos que no deben revelarse todavía, spoilers por arco, límites de perspectiva y hechos que no se pueden modificar sin aprobación.

Cada hecho de canon debe incluir como mínimo: identificador, categoría, contenido, estado (`propuesto`, `aprobado`, `rechazado`, `en_conflicto`), origen (capítulo/escena/decisión del autor), fecha y registro de versiones. La IA no puede convertir una idea suya en canon automáticamente.

## Panel propuesto

La interfaz debe mostrar tres zonas principales y no una ventana de chat aislada:

- **Centro — Escritura y chat:** redactar escena/capítulo, continuar fragmento, reescribir con una indicación o pedir ideas. Los resultados se mantienen como borrador hasta que el autor los guarde.
- **Panel lateral — Memoria recuperada:** mostrar qué personajes, reglas de lore, eventos y decisiones se incluyeron en el contexto de esa respuesta, con botón para abrir su ficha y comprobar estado/fuente.
- **Panel lateral de edición — Biblia de la novela:** administrar personajes, lugares, lore, cronología, idioma/estilo, tramas, pistas y borradores. Los cambios sugeridos por el bot llegan como propuestas que se aceptan, editan o rechazan.

Pestañas iniciales: **Escritura**, **Personajes**, **Lore**, **Cronología**, **Tramas y pistas**, **Idioma y estilo**, **Borradores** e **Historial**.

### Roles de bot recomendados

No hace falta ejecutar cinco modelos distintos. Para la primera versión conviene usar **un proveedor/modelo elegido por el usuario y perfiles de tarea**, que son más baratos, más fáciles de medir y menos propensos a discutir entre sí.

1. **Coautor:** genera una escena según objetivo dramático, voz, punto de vista, idioma y contexto recuperado. Distingue propuesta de canon.
2. **Guardián del lore:** responde sobre la biblia consultada. Debe citar la ficha o capítulo interno utilizado; si la información no aparece, dice «no establecido» y no inventa.
3. **Editor de continuidad:** busca contradicciones de cronología, relaciones, poderes, conocimiento de personajes, reglas y hechos ya fijados. Informa evidencia y gravedad; no corrige el texto sin permiso.
4. **Editor de idioma:** revisa claridad, ritmo, diálogo y coherencia de la voz en el idioma elegido. No cambia hechos ni personalidad.
5. **Planificador:** propone premisa, arcos, ritmo, objetivos de capítulo y pistas. Toda propuesta nueva queda pendiente de aprobación.

Los roles son plantillas de instrucciones y herramientas de memoria, no cinco personalidades que deban ejecutarse simultáneamente. Solo se necesitaría una segunda pasada del modelo cuando el usuario la solicite o cuando una revisión concreta aporte valor.

**La primera implementación permite además crear perfiles de bot propios por proyecto.** Cada perfil guarda nombre, especialidad, proveedor preferido e instrucciones personalizadas. El autor puede seleccionarlo, editarlo o eliminarlo. Esto crea un bot especializado a nivel de instrucciones y memoria de la aplicación; no entrena un modelo nuevo ni convierte esas instrucciones en un mensaje de sistema privado del proveedor. Se le entrega el prompt compuesto cuando el usuario lo copia manualmente.

## Cómo seleccionar un buen modelo en lugar de aceptar cualquiera

La selección no se debe basar únicamente en popularidad, nombre, contexto máximo o una demostración llamativa. Se debe medir el modelo con tareas idénticas y memoria idéntica.

Criterios recomendados (escala de 1 a 5):

- calidad literaria y naturalidad en español;
- seguimiento de instrucciones y del tono;
- continuidad con los hechos de la biblia;
- respeto de límites de conocimiento y spoilers;
- ausencia de detalles inventados cuando se pregunta por el canon;
- consistencia de voces y personajes;
- capacidad de continuar una escena sin repetir ni saltarse hechos;
- facilidad para editar/copiar el resultado y obediencia al formato;
- latencia/coste práctico y privacidad;
- estabilidad al repetir la prueba.

Ponderación inicial sugerida para novela: continuidad/canon 25 %, prosa en español 20 %, seguimiento de instrucciones 15 %, caracterización/voz 15 %, no inventar datos al consultar lore 10 %, edición y formato 5 %, latencia/coste/privacidad 10 %. Los pesos son una propuesta inicial que debe ajustarse a las prioridades del autor; no son una clasificación universal de modelos.

### Limitación real del PC

El entorno documentado del usuario es Windows, Ryzen 5 5600G y 16 GB de RAM, con memoria disponible limitada por otras aplicaciones. No se debe instalar ni mantener un modelo local pesado en ejecución como requisito.

Ollama publica tamaños de artefacto para la familia Qwen3 que varían mucho: por ejemplo, Qwen3 4B aparece alrededor de 2.5 GB y Qwen3 8B alrededor de 5.2 GB; el archivo del modelo no representa todo el consumo de RAM, que también depende del contexto, caché, cuantización y otros procesos ([catálogo de Qwen3](https://ollama.com/library/qwen3)). La documentación de LM Studio recomienda al menos 16 GB de RAM para Windows y una GPU con 4 GB de VRAM dedicada como referencia; la máquina indicada no tiene una GPU dedicada equivalente ([requisitos de LM Studio](https://lmstudio.ai/docs/app/system-requirements)). Por ello, el modelo local debe quedar como experimento opcional y medido, no como opción por defecto.

Para una primera versión, la ruta práctica es **ChatGPT o Gemini mediante el flujo manual visible ya usado por NovelTrad**: elegir proveedor, preparar un prompt con contexto acotado, copiarlo, enviarlo desde la sesión iniciada por el usuario y pegar la respuesta. No se agrega una API de pago, no se automatiza el envío, no se leen credenciales y no se transmite toda la novela por defecto. La elección del modelo exacto queda en manos de las opciones disponibles para la cuenta y debe compararse con el benchmark; la interfaz no debe fingir conocer el modelo activo si el sitio no lo expone con fiabilidad.

## Memoria recuperable sin cargar todo el libro

Para la primera versión basta con una base SQLite local, indexada por proyecto, tipo de ficha, palabras clave, capítulo, personaje, lugar y estado de canon. Se puede empezar con búsqueda de texto completo y filtros deterministas; una base vectorial/embeddings es una mejora opcional si las pruebas demuestran que la búsqueda literal no encuentra recuerdos pertinentes.

Cada solicitud al modelo debe contener solo:
1. guía de estilo y reglas globales cortas;
2. instrucciones de la tarea y objetivo de escena;
3. fichas de lore y personajes relevantes, con estado y procedencia;
4. resumen del capítulo anterior y el punto de continuidad;
5. extracto reciente necesario para continuar la voz y la escena.

La ventana de contexto del modelo no es memoria persistente. Al cerrar y abrir NovelTrad, el proyecto debe reconstruirse desde SQLite. No hace falta inyectar todos los capítulos ni todas las conversaciones: se recupera el subconjunto relevante y se registra qué elementos se enviaron.

## Esquema funcional mínimo

- `writing_projects`: proyecto, título, género, idioma, configuración editorial, carpeta y fechas.
- `memory_items`: tipo, título, contenido, palabras clave, estado de canon, fuente interna y versión.
- `memory_relations`: relaciones entre entidades y eventos (p. ej., quién conoce qué, quién participó en un evento).
- `story_chapters` / `story_scenes`: borradores, números, objetivo dramático, POV, versión y resumen.
- `writing_sessions`: tareas, proveedor elegido, identificador del modelo si se conoce y resultados pegados por el usuario.
- `memory_proposals`: cambios sugeridos por el bot, evidencia, estado de revisión y decisión del autor.
- `continuity_findings`: contradicción, hechos implicados, fuente, gravedad y resolución.
- `change_log`: historial auditable de altas, ediciones, aprobaciones y rechazos.

La base y la novela pertenecen al usuario y permanecen locales por defecto. Exportación/importación opcional en JSON/Markdown debe permitir copias de seguridad y migración de un proyecto a otro sin depender de una cuenta externa.

## Plan de implementación por etapas

**Fase 1 — Panel con memoria persistente**
- Crear/abrir varios proyectos de novela.
- Editar la biblia, idioma, personajes y lore.
- Guardar escenas y capítulos como borradores versionados.
- Ver el estado de canon y el historial después de reiniciar.
- Generar un prompt de coautor con el contexto relevante y hacer el intercambio manual con el proveedor seleccionado.
- Guardar la respuesta como borrador, nunca sobrescribirla ni cambiar canon automáticamente.

**Fase 2 — Recuperación y guardián del lore**
- Índice de texto completo local, búsqueda por alias y filtros por proyecto/estado/capítulo.
- Panel «Memoria usada en esta respuesta» con fuentes internas navegables.
- Respuestas de consulta que separan `ESTABLECIDO`, `NO ESTABLECIDO`, `NO ENCONTRADO` y `CONFLICTO`.
- Propuestas de memoria editables; aprobación humana obligatoria.

**Fase 3 — Calidad y elección de modelo**
- Ejecutar el mismo conjunto de pruebas con cada proveedor/modelo disponible.
- Mostrar puntuación por criterio, ejemplos y fallos; no declarar un ganador a partir de una única muestra.
- Comparar privacidad, latencia, coste y límite de contexto.
- Probar el modo local solo con medición de RAM y calidad y sin descargar modelos automáticamente.

**Fase 4 — Herramientas editoriales**
- Auditoría de continuidad, cronología, personajes que saben información, voz de diálogo, arcos y pistas.
- Revisión de un capítulo sin editar automáticamente el canon.
- Exportación del manuscrito y de la biblia narrativa.

## Criterios de aceptación

1. Tras cerrar y abrir la aplicación, reaparecen proyecto, personajes, lore, capítulos, estado de canon e historial exactos.
2. El panel cita qué memoria interna usó para una respuesta y permite inspeccionarla.
3. Una propuesta generada no se considera canon hasta aprobación explícita.
4. Si una consulta de lore no tiene evidencia guardada, el bot lo dice en vez de inventar una respuesta presentada como hecho.
5. Si dos recuerdos se contradicen, la interfaz marca `CONFLICTO`, muestra ambos y no los fusiona silenciosamente.
6. Se puede elegir proveedor/rol, copiar el prompt y pegar la salida; no existe envío invisible a un tercero.
7. Las solicitudes no incluyen el libro completo por defecto.
8. Las escenas se guardan como borrador versionado y el original nunca se sobrescribe.
9. Un benchmark repetible compara modelos usando el mismo prompt y las mismas fichas de memoria.
10. La función nueva no rompe el lector, las traducciones, el glosario de traducción ni sus copias de seguridad.

## Fuentes consultadas

- SillyTavern, *World Info*: https://docs.sillytavern.app/usage/core-concepts/worldinfo/
- SillyTavern, documentación general (tarjetas, Data Bank y funciones): https://docs.sillytavern.app/
- Novelcrafter, *The Codex*: https://www.novelcrafter.com/help/docs/codex/the-codex
- Ollama, catálogo Qwen3 y tamaños de modelos: https://ollama.com/library/qwen3
- LM Studio, requisitos del sistema: https://lmstudio.ai/docs/app/system-requirements
- NovelTrad, guía interna del modo Local/Premium: https://github.com/jonhararagi/traslate/blob/main/docs/MODO_LOCAL_Y_MODO_PREMIUM.md
- NovelTrad, guía interna de perfiles de prosa: https://github.com/jonhararagi/traslate/blob/main/docs/PROSA_Y_TRADUCCION_OFFLINE.md

**Alcance honesto:** este documento es una investigación y especificación de producto. No demuestra todavía que el panel narrativo esté construido, ni que ningún modelo haya ganado una evaluación práctica. La siguiente entrega de implementación debe añadir funciones y pruebas, no limitarse a mostrar esta documentación.
