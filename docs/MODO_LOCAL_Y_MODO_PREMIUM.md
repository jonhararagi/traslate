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

- Premium no se ejecuta en segundo plano ni automáticamente al importar/abrir un libro.
- Solo se permite una petición por acción; límite actual: 12.000 caracteres por vista previa.
- Se solicita `num_ctx=4096`, una salida máxima de 4096 tokens, temperatura 0,1 y `keep_alive=0` para pedir a Ollama que descargue el modelo de memoria al terminar.
- El uso real depende de la cuantización, el runtime, el tamaño del contexto y otras aplicaciones abiertas. Un modelo 3B cuantizado puede consumir varios GB entre pesos y memoria de ejecución; 16 GB no garantizan que no haya presión de RAM. Cerrar aplicaciones pesadas y preferir Local cuando no haga falta traducción neuronal.
- Si el capítulo supera el límite, NovelTrad devuelve un error explícito; el usuario debe dividirlo en fragmentos. El troceado automático y la reconciliación de contexto entre fragmentos siguen pendientes.
- El endpoint de premium solo acepta la llamada a loopback codificada en la aplicación. No se configura una URL remota. No se envía el texto a proveedores externos.
- El modelo puede equivocarse, omitir matices, alterar nombres o traducir mal juegos de palabras. El glosario aprobado se incluye en el prompt, pero no es una garantía absoluta.

## Límites actuales y tareas pendientes

- Premium produce una traducción neuronal del texto del capítulo solo si cabe en el límite de 12.000 caracteres. No guarda el resultado por sí mismo.
- Falta una experiencia de traducción por fragmentos con comparación original/traducción, reintentos por fragmento y continuidad entre contextos.
- Falta una comprobación de calidad con capítulos reales de la edición que el usuario importe.
- El modo Local no es traducción automática general; solo aplica reglas aprobadas.
- Nunca se debe afirmar que el libro completo está traducido sin verificar cada capítulo y sus resultados.

## Primera novela: I Became the Academy Villain's Daughter

El perfil está en `data/novels/i_became_the_academy_villains_daughter.json`. Incluye títulos alternativos y candidatos terminológicos sin aprobar. Al importar un archivo cuyo nombre coincide exactamente (ignorando mayúsculas y signos de puntuación) con el título principal o uno de sus títulos alternativos, NovelTrad copia los candidatos iniciales al glosario de ese libro con estado **no aprobado** y regla provisional de conservación. No se crean para libros no coincidentes, no se aprueban automáticamente y se pueden editar o borrar en el glosario. La coincidencia usa el nombre del archivo, no análisis del contenido, por lo que conviene nombrar el archivo con el título de la obra para activar esta ayuda. El nombre **Oknodie** aparece en listados editoriales y de serie; debe verificarse contra la edición exacta importada. Los nombres propios, bromas, títulos, nombres de habilidades, rangos, organizaciones y honoríficos se deben extraer de los capítulos reales y aprobar uno por uno. No se inventarán traducciones a partir de resúmenes secundarios.

Fuentes de referencia inicial para identificar la obra (no sustituyen el texto de la edición importada):
- Novelpia Global: https://global.novelpia.com/novel/41?sid=main1
- Tapas: https://tapas.io/series/i-became-the-villains-daughter-at-the-academy/info
