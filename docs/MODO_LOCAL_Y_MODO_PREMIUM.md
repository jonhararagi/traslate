# Modo local y modo premium en NovelTrad

## Modo local (predeterminado)

- Motor determinista: glosario aprobado, mapa explícito de frases y normalización tipográfica.
- No carga modelos, no necesita internet, no llama a APIs y usa RAM adicional mínima.
- Conserva nombres y términos marcados como protegidos.
- No puede traducir una oración desconocida por sí solo. El resultado debe identificarse como aplicación de reglas, no como traducción neuronal.

## Modo Premium por cuenta en Chromium

**Estado:** integrado en `main` mediante PR [#14](https://github.com/jonhararagi/traslate/pull/14). La versión principal validada antes de la auditoría de cierre fue `ca7eadf7c1847a64d95997c0ad98f6e062ca45d0`. Sus tests de Ubuntu/Windows y la compilación portátil de Windows, incluido el smoke test del ejecutable empaquetado, pasaron en GitHub Actions:
- [Tests de main](https://github.com/jonhararagi/traslate/actions/runs/38896672388)
- [Windows Portable Build de main](https://github.com/jonhararagi/traslate/actions/runs/38896672374)

NovelTrad abre un perfil persistente de Chromium para que la persona inicie sesión directamente en ChatGPT o Gemini. Desactiva la carga de imágenes y reduce cierta actividad de fondo, pero no garantiza un consumo de RAM fijo ni un ahorro específico. No lee, extrae ni almacena contraseñas, cookies o tokens. No envía prompts automáticamente: el usuario copia el prompt, lo pega en el sitio, espera la respuesta y la pega en NovelTrad.

### Vista previa de capítulo

El endpoint `POST /api/chapters/{chapter_id}/premium-browser-prompts/chunked` prepara prompts secuenciales con glosario aprobado, perfil editorial, delimitadores de texto fuente y contexto previo limitado. El usuario pega la respuesta en el campo de cada fragmento. La vista previa no guarda automáticamente: solo «Pasar al editor» la transfiere al editor y después el usuario debe guardar explícitamente.

Por defecto, la operación divide el texto en fragmentos de 3.500 caracteres, con configuración interna/API entre 1.000 y 6.000, y hasta 200.000 caracteres por capítulo. Los límites reducen el tamaño de cada operación, pero no garantizan que el proveedor respete todo el contexto o conserve cada matiz.

### Cola persistente de libro completo

- Al crear una cola se guarda el proveedor elegido (ChatGPT o Gemini), el manifiesto de fragmentos y una instantánea del glosario aprobado. La creación no llama a ningún proveedor.
- `POST /api/translation-jobs/{job_id}/next-prompt` reserva un solo fragmento y devuelve el prompt. No hay envío automático.
- `POST /api/translation-jobs/{job_id}/chunks/{chunk_id}/submit` persiste la respuesta pegada como completada pero **no revisada**.
- Pausa, reanudación, reintento de fragmentos fallidos y recuperación tras reiniciar conservan el progreso. Una respuesta ya reservada se puede guardar después de pausar; el trabajo permanece pausado.
- El usuario compara cada salida con su original y guarda la revisión explícitamente. La aplicación al libro permanece bloqueada hasta que todos los fragmentos estén completados y revisados. Una sección que ya recibió una traducción por otra vía no debe sobrescribirse; el original importado permanece intacto.
- Las advertencias heurísticas de calidad (salida vacía/idéntica, longitud sospechosa, diferencias de párrafos, posibles omisiones y repeticiones) son señales para revisar, no una puntuación ni una garantía de corrección.

### Aislamiento entre proveedores y endpoint local heredado

La cola de cuenta usa proveedores `chatgpt` o `gemini` y debe recorrer `next-prompt` + `submit`. El endpoint heredado `POST /api/translation-jobs/{job_id}/run-next` llama a Ollama en loopback y ahora debe usarse únicamente para trabajos creados explícitamente con `provider: "ollama"`; se rechaza si el trabajo fue creado para ChatGPT/Gemini. A la inversa, los endpoints de prompt/respuesta manual rechazan un trabajo local `ollama`. La interfaz no ofrece Ollama como proveedor de cola.

También queda un endpoint de vista previa neuronal heredado, `POST /api/chapters/{chapter_id}/premium-translation-preview`, que llama a Ollama localmente. No es el modo Premium por cuenta ni forma parte de la cola manual. No instala ni descarga modelos. Si Ollama no está instalado/iniciado, la aplicación devuelve un error; no hay fallback a servicios remotos.

### Presupuesto conservador para Ryzen 5 5600G y 16 GB RAM

El modo Local es la opción de menor consumo: reglas aprobadas, glosario y normalización tipográfica deterministas; no carga modelos neuronales ni llama a la red. No puede traducir frases desconocidas por sí solo.

El modo Premium por cuenta evita cargar pesos neuronales locales, pero Chromium y las pestañas del proveedor consumen RAM. Conviene mantener una sola sesión de proveedor y procesar un fragmento a la vez. El bloqueo de imágenes puede ayudar, pero no permite prometer una cantidad de RAM libre. No hace falta instalar ni mantener Ollama ejecutándose para utilizar la cola ChatGPT/Gemini.

### Validación que sigue pendiente

Los tests y el smoke test del paquete de GitHub Actions no validan la cuenta personal ni la máquina del usuario. Falta en un Windows real: iniciar sesión directamente en ChatGPT o Gemini, completar la vista previa y una cola pequeña, cerrar/reabrir NovelTrad, comprobar pausa/reanudación/reintento y revisión, y contrastar la calidad de un fragmento de una edición que el usuario esté autorizado a utilizar. No hay benchmark de calidad de un capítulo real. Los PDF escaneados requieren OCR, que todavía no está implementado.

## Primera novela: I Became the Academy Villain's Daughter

El perfil está en `data/novels/i_became_the_academy_villains_daughter.json`. Incluye títulos alternativos y candidatos terminológicos sin aprobar. Al importar un archivo cuyo nombre coincide exactamente (ignorando mayúsculas y signos de puntuación) con el título principal o uno de sus títulos alternativos, NovelTrad copia los candidatos iniciales al glosario de ese libro con estado **no aprobado** y regla provisional de conservación. No se crean para libros no coincidentes, no se aprueban automáticamente y se pueden editar o borrar en el glosario. La coincidencia usa el nombre del archivo, no análisis del contenido, por lo que conviene nombrar el archivo con el título de la obra para activar esta ayuda. El nombre **Oknodie** aparece en listados editoriales y de serie; debe verificarse contra la edición exacta importada. Los nombres propios, bromas, títulos, nombres de habilidades, rangos, organizaciones y honoríficos se deben extraer de los capítulos reales y aprobar uno por uno. No se inventarán traducciones a partir de resúmenes secundarios.

Fuentes de referencia inicial para identificar la obra (no sustituyen el texto de la edición importada):
- Novelpia Global: https://global.novelpia.com/novel/41?sid=main1
- Tapas: https://tapas.io/series/i-became-the-villains-daughter-at-the-academy/info


## Cola persistente de libro completo

La sección «Traducción de libro completo» permite preparar una cola persistente y seleccionar ChatGPT o Gemini. «Generar siguiente prompt» reserva un único fragmento y muestra el prompt para copiarlo manualmente al sitio; NovelTrad nunca lo envía. La respuesta se pega y guarda localmente como no revisada. Pausar impide iniciar nuevos fragmentos; una respuesta del fragmento ya reservado aún puede guardarse y el trabajo permanece pausado. Reanudar continúa desde el primer fragmento pendiente y «Reintentar fallidos» vuelve a habilitar únicamente los fallidos. El manifiesto, los intentos y las respuestas provisionales se guardan en SQLite y se recuperan al reiniciar. Aplicar permanece bloqueado hasta que todos los fragmentos estén traducidos y revisados. El texto original es de solo lectura y no se modifica.

La cola limita cada sección a 200.000 caracteres, usa 3.500 caracteres por fragmento por defecto (configurable por API entre 1.000 y 6.000) y 1.200 caracteres de contexto previo por defecto. El glosario aprobado se guarda como instantánea al crear el trabajo. Una traducción completa no equivale a una traducción de calidad validada: los nombres y términos ambiguos requieren revisión humana.


## Análisis local de candidatos del glosario

La función ya integrada añade «Buscar candidatos en el texto original» al panel del glosario. Examina el texto local importado; combina los términos del perfil de Oknodie con una lista heurística gamer/otaku y nombres potenciales detectados por mayúsculas repetidas. Cada candidato incluye frecuencia y hasta tres fragmentos breves con capítulo y ubicación. El escaneo no llama a Ollama, a la nube ni a ningún servicio externo.

Los candidatos se guardan en SQLite con estado pendiente, aprobado o ignorado. Volver a escanear actualiza la frecuencia/evidencia sin restablecer una decisión previa. Aprobar exige que el usuario revise forma preferida, regla y notas. El botón «Ignorar» solo oculta ese candidato de la lista pendiente. Los nombres que se infieren solo por mayúsculas pueden ser falsos positivos; no se deben aprobar sin leer la evidencia. El escaneo está limitado a 25 millones de caracteres y 500 candidatos por pasada. Estos límites son protección de recursos, no una promesa de exhaustividad.


## Advertencias heurísticas de calidad por fragmento (función integrada)

La cola registra hasta cinco advertencias por fragmento completado: salida vacía o idéntica al original, longitud desproporcionadamente corta/larga, estructura de párrafos muy distinta, marcadores de omisión/respuesta genérica y posible repetición extensa en la salida. Las advertencias se guardan junto a cada fragmento y se vuelven a calcular al guardar una revisión manual. En la lista de fragmentos se indica cuáles requieren atención.

Estas verificaciones son heurísticas y deliberadamente no bloquean una revisión por sí solas. Las traducciones pueden expandirse o contraerse según el idioma, una frase repetida puede ser intencional y algunos fragmentos (nombres, interfaz, terminología) pueden coincidir con el original. La ausencia de alertas **no** certifica la calidad. La cola sigue exigiendo la revisión explícita de todos los fragmentos antes de aplicar el resultado final.


## Coherencia de reglas aprobadas del glosario (función integrada)

Las reglas aprobadas `protect`, `preserve` y `translate` se envían al modelo con instrucciones explícitas. Además, después de traducir y después de guardar la revisión, NovelTrad comprueba si la forma preferida aparece en el resultado cuando el término fuente estaba en el fragmento original. Si falta, crea una advertencia visible en la revisión. Las reglas `contextual` no generan una alerta por ausencia, porque no deben imponerse en todos los usos. Esta comprobación es un detector conservador de términos ausentes, no una prueba de equivalencia semántica: puede haber falsos positivos si cambia la flexión o el término no debe aparecer en la traducción final.


## Perfil terminológico inicial de la primera novela

La lista de términos es orientativa y todos los candidatos comienzan pendientes. El análisis extrae muestras literales del texto importado; solo la tarjeta con evidencia permite aprobar los términos sembrados desde el perfil. Las referencias editoriales, convenciones gamer y términos pedidos por el usuario no equivalen a evidencia de capítulo. Véase [Perfil terminológico inicial](PERFIL_TERMINOLOGICO_INICIAL.md) para la lista, reglas sugeridas, riesgos y pruebas de aceptación.
