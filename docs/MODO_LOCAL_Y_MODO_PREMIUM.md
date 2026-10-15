# Modo local y modo premium en NovelTrad

## Modo local (predeterminado)

- Motor determinista: glosario aprobado, mapa explícito de frases y normalización tipográfica.
- No carga modelos, no necesita internet, no llama a APIs y usa RAM adicional mínima.
- Conserva nombres y términos marcados como protegidos.
- No puede traducir una oración desconocida por sí solo. El resultado debe identificarse como aplicación de reglas, no como traducción neuronal.

## Modo premium (local, bajo demanda)

Premium es un modo real de inferencia neuronal local, no una suscripción y no un servicio en la nube. La implementación usa el endpoint de Ollama en `127.0.0.1:11434`. Modelo predeterminado: `qwen2.5:3b`; se puede cambiar mediante `NOVELTRAD_PREMIUM_MODEL`.

### Activación manual en Windows

1. Instalar Ollama por separado desde su sitio oficial y abrirlo.
2. Descargar manualmente un modelo compatible; por ejemplo, `ollama pull qwen2.5:3b`. NovelTrad no descarga pesos ni inicia instalaciones por su cuenta.
3. Abrir NovelTrad, elegir **Modo premium** y generar una vista previa. Si Ollama o el modelo faltan, la aplicación muestra un error y no deriva el texto a internet.
4. Revisar el resultado y pulsar **Pasar al editor**. Guardar sigue siendo una acción manual.

### Presupuesto conservador para Ryzen 5 5600G y 16 GB RAM

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
- La ejecución del modelo sigue dependiendo de Ollama local y se inicia manualmente; no hay llamadas a servicios externos ni descarga automática de modelos.
- Falta una comprobación de calidad con capítulos reales de la edición que el usuario importe. El modo Local no es traducción automática general: solo aplica reglas aprobadas. No se debe afirmar que una novela está bien traducida sin comprobar sus resultados.

## Primera novela: I Became the Academy Villain's Daughter

El perfil está en `data/novels/i_became_the_academy_villains_daughter.json`. Incluye títulos alternativos y candidatos terminológicos sin aprobar. Al importar un archivo cuyo nombre coincide exactamente (ignorando mayúsculas y signos de puntuación) con el título principal o uno de sus títulos alternativos, NovelTrad copia los candidatos iniciales al glosario de ese libro con estado **no aprobado** y regla provisional de conservación. No se crean para libros no coincidentes, no se aprueban automáticamente y se pueden editar o borrar en el glosario. La coincidencia usa el nombre del archivo, no análisis del contenido, por lo que conviene nombrar el archivo con el título de la obra para activar esta ayuda. El nombre **Oknodie** aparece en listados editoriales y de serie; debe verificarse contra la edición exacta importada. Los nombres propios, bromas, títulos, nombres de habilidades, rangos, organizaciones y honoríficos se deben extraer de los capítulos reales y aprobar uno por uno. No se inventarán traducciones a partir de resúmenes secundarios.

Fuentes de referencia inicial para identificar la obra (no sustituyen el texto de la edición importada):
- Novelpia Global: https://global.novelpia.com/novel/41?sid=main1
- Tapas: https://tapas.io/series/i-became-the-villains-daughter-at-the-academy/info


## Cola persistente de libro completo

La sección «Traducción de libro completo» de la biblioteca permite preparar la cola, iniciar/reanudar, pausar, reintentar fragmentos fallidos, revisar cada salida y aplicar las traducciones al editor de la biblioteca. Preparar la cola no consume inferencia. La ejecución solo empieza con una acción explícita. El manifiesto y las traducciones provisionales se guardan en la base local; cerrar NovelTrad no borra el avance. El botón de aplicación permanece bloqueado hasta que todos los fragmentos estén traducidos y revisados. El texto original es de solo lectura y no se actualiza desde esta función.

La cola limita cada sección a 200.000 caracteres, usa 3.500 caracteres por fragmento por defecto (configurable por API entre 1.000 y 6.000) y 1.200 caracteres de contexto previo por defecto. El glosario aprobado se guarda como instantánea al crear el trabajo. Una traducción completa no equivale a una traducción de calidad validada: los nombres y términos ambiguos requieren revisión humana.


## Análisis local de candidatos del glosario

La rama de trabajo de esta función añade «Buscar candidatos en el texto original» al panel del glosario. Examina el texto local importado; combina los términos del perfil de Oknodie con una lista heurística gamer/otaku y nombres potenciales detectados por mayúsculas repetidas. Cada candidato incluye frecuencia y hasta tres fragmentos breves con capítulo y ubicación. El escaneo no llama a Ollama, a la nube ni a ningún servicio externo.

Los candidatos se guardan en SQLite con estado pendiente, aprobado o ignorado. Volver a escanear actualiza la frecuencia/evidencia sin restablecer una decisión previa. Aprobar exige que el usuario revise forma preferida, regla y notas. El botón «Ignorar» solo oculta ese candidato de la lista pendiente. Los nombres que se infieren solo por mayúsculas pueden ser falsos positivos; no se deben aprobar sin leer la evidencia. El escaneo está limitado a 25 millones de caracteres y 500 candidatos por pasada. Estos límites son protección de recursos, no una promesa de exhaustividad.
