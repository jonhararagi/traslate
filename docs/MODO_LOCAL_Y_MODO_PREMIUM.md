# Modo local y modo premium en NovelTrad

## Modo local (predeterminado)

- Motor determinista: glosario aprobado, mapa explícito de frases y normalización tipográfica.
- No carga modelos, no necesita internet, no llama a APIs y usa RAM adicional mínima.
- Conserva nombres y términos marcados como protegidos.
- No puede traducir una oración desconocida por sí solo. El resultado debe identificarse como aplicación de reglas, no como traducción neuronal.

## Modo Premium por cuenta en Chromium — primera versión de vista previa

En la rama `feat/chromium-account-premium`, el usuario puede elegir ChatGPT o Gemini y abrir un perfil Chromium dedicado y persistente para iniciar sesión directamente en el sitio. El navegador se lanza con carga de imágenes desactivada (`--blink-settings=imagesEnabled=false`) y opciones para reducir actividad de fondo. No es un modo DevTools: es una opción de lanzamiento del navegador, y no garantiza que todos los elementos de la página sean solo texto.

NovelTrad genera prompts por fragmento con glosario aprobado y estilo editorial. En la vista previa de capítulo, el usuario copia el prompt, lo envía en el sitio del proveedor y pega la respuesta en NovelTrad. En la cola persistente de libro completo, la aplicación reserva un fragmento, muestra su prompt y guarda la respuesta pegada como traducción provisional sin revisar. No hay envío automático ni lectura de cookies/credenciales. La aplicación final de la cola permanece bloqueada hasta que todos los fragmentos estén traducidos y revisados.

**Estado actual (rama de trabajo del PR #14):** la vista previa de capítulo y la cola persistente ya tienen rutas de generación de prompt y pegado manual de respuestas para ChatGPT/Gemini. La cola guarda el proveedor y el progreso, procesa un fragmento por vez, conserva las respuestas sin revisar y exige revisión de todos los fragmentos antes de aplicar. Se añadieron pruebas unitarias iniciales; aún falta confirmar CI, revisar los casos de pausa/reanudación/reintento con pruebas de integración y realizar la prueba manual en Windows. `main` no ha cambiado. La arquitectura y los criterios están descritos en [PREMIUM_CHROMIUM_CHATGPT_GEMINI.md](PREMIUM_CHROMIUM_CHATGPT_GEMINI.md).

### Presupuesto conservador para Ryzen 5 5600G y 16 GB RAM

El flujo de cuenta por Chromium usa principalmente el navegador y la sesión web del proveedor, no pesos de modelos locales. Aun así, el navegador consume RAM; mantener pocas pestañas y procesar un fragmento a la vez es preferible. No debe ejecutarse Ollama en segundo plano para este modo. Los detalles que siguen describen el endpoint Ollama que existe actualmente y no la arquitectura Premium objetivo.

- Premium no se ejecuta automáticamente al importar/abrir un libro. La cola del libro completo solo comienza cuando el usuario pulsa «Iniciar / reanudar»; las llamadas de inferencia son secuenciales.
- La vista previa de capítulo usa fragmentos secuenciales de 3.500 caracteres por defecto, ajustables internamente entre 1.000 y 6.000, hasta 200.000 caracteres de origen por capítulo.
- Se solicita `num_ctx=4096`, una salida máxima de 4096 tokens, temperatura 0,1 y `keep_alive=0` para pedir a Ollama que descargue el modelo de memoria al terminar. La traducción de capítulos usa peticiones secuenciales, no paralelas.
- El uso real depende de la cuantización, el runtime, el tamaño del contexto y otras aplicaciones abiertas. Un modelo 3B cuantizado puede consumir varios GB entre pesos y memoria de ejecución; 16 GB no garantizan que no haya presión de RAM. Cerrar aplicaciones pesadas y preferir Local cuando no haga falta traducción neuronal.
- La vista previa de capítulo trocea automáticamente hasta 200.000 caracteres de origen en fragmentos de 3.500 caracteres por defecto (configuración interna permitida: 1.000–6.000), priorizando límites de párrafo y oración. El final de la traducción anterior se pasa al modelo como referencia de continuidad; no debe repetirse como salida. Los capítulos mayores de 200.000 caracteres se rechazan explícitamente.
- El endpoint de premium solo acepta la llamada a loopback codificada en la aplicación. No se configura una URL remota. No se envía el texto a proveedores externos.
- El modelo puede equivocarse, omitir matices, alterar nombres o traducir mal juegos de palabras. El glosario aprobado se incluye en el prompt, pero no es una garantía absoluta.

## Límites actuales y tareas pendientes

- La cola de libro completo crea un manifiesto persistente en SQLite con sección, fragmento, estado, intentos y error. Traduce un fragmento por petición; los resultados correctos sobreviven a un fallo posterior y pueden reanudarse tras cerrar la aplicación.
- Si un fragmento falla, el trabajo se detiene y conserva los fragmentos completados. «Reintentar fallidos» vuelve a poner solamente los fragmentos fallidos en la cola. Al reiniciar, un fragmento que quedó en ejecución se recupera como pendiente y el trabajo queda pausado.
- La cola captura el glosario aprobado cuando se crea para que las reglas no cambien a mitad del libro. El resultado sigue siendo provisional: cada fragmento debe marcarse revisado antes de «Aplicar traducciones revisadas».
- Aplicar escribe las traducciones finales solo en secciones que aún no tengan traducción, conservando el original. Si otra operación rellenó una sección mientras la cola estaba activa, la aplicación se bloquea sin sobrescribirla.
- La cola migrada no ejecuta Ollama: el usuario selecciona ChatGPT/Gemini, copia el prompt y pega la respuesta manualmente. El endpoint de vista previa neuronal antigua puede seguir existiendo como integración heredada separada; no es el flujo Premium por cuenta.
- Falta una comprobación de calidad con capítulos reales de la edición que el usuario importe. El modo Local no es traducción automática general: solo aplica reglas aprobadas. No se debe afirmar que una novela está bien traducida sin comprobar sus resultados.

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
