# Perfil terminológico inicial: I Became the Academy Villain's Daughter

## Alcance y estado

Este perfil inicia el tratamiento español de los nombres y la terminología otaku/gamer de esta obra. No afirma que el texto de capítulos haya sido leído o verificado. La lista de candidatos se obtiene de metadatos editoriales, vocabulario general y términos solicitados por el usuario; esas fuentes sirven para preparar una revisión, no para demostrar un sentido dentro del capítulo.

El perfil debe compararse con la edición exacta que el usuario importe legalmente. El listado en inglés de Tapas es una adaptación de cómic, no el archivo de prosa de la novela. El catálogo de fuentes y las restricciones de uso permanecen en el archivo de perfil. No se descarga, rastrea ni redistribuye texto de capítulos.

## Candidatos iniciales y reglas propuestas

Todas las entradas comienzan sin aprobar. La regla sugerida solo precarga la revisión y no modifica traducciones hasta que exista una aprobación explícita.

| Término de origen | Forma sugerida | Regla sugerida | Riesgo principal |
|---|---|---|---|
| Oknodie | Oknodie | protect | Nombre propio; comprobar la grafía exacta y no dividirlo fonéticamente. |
| Graduate from the Academy by Luck | Igual al original | preserve | Título del juego dentro de la obra; comprobar si aparece y si la edición establece una localización. |
| level | level | contextual | Puede ser nivel de personaje, piso, etapa, volumen o grado. |
| level up | subir de nivel | contextual | Puede ser narración, etiqueta de interfaz o mensaje del sistema. |
| farm | farmear | contextual | Solo en uso gamer de recolección repetitiva; también puede significar granja/cultivar. |
| farming | farmeo | contextual | Confirmar la mecánica y ajustar sintaxis a la frase. |
| grind | grindear | contextual | Puede aludir a progresión repetitiva o a un sentido físico distinto. |
| min-maxing | optimización extrema de estadísticas | contextual | Confirmar la estrategia; el usuario puede preferir conservar el préstamo inglés. |
| stats | estadísticas | contextual | Distinguir atributos de juego de estadísticas en sentido común. |
| build | build | contextual | Conservar como configuración de personaje; fuera del juego puede ser construcción. |
| steal | robar | contextual | Separar el verbo común de un posible nombre de habilidad. |
| Steal skill | Steal | contextual | No inferir que es una habilidad solo por las mayúsculas. |
| skill | habilidad | contextual | Aplicar únicamente si el contexto confirma el sistema de juego. |
| quest | misión | contextual | Confirmar si la edición distingue misión, tarea y objetivo. |
| drop | botín | contextual | Como verbo puede significar soltar, dejar caer, abandonar o bajar. |
| reroll | volver a tirar | contextual | La equivalencia depende de la mecánica concreta. |
| tsundere | tsundere | preserve | Mantener el arquetipo; no reducirlo a «fría» o «antipática». |
| farmed | farmear (conjugado según la frase) | contextual | No reemplazar siempre por el infinitivo ni aplicar fuera del contexto gamer. |
| lvl | lvl | contextual | Puede ser etiqueta abreviada de interfaz/estadísticas; en prosa quizá corresponda «nivel». |

El título de la novela se conserva en los metadatos del perfil, no en el glosario de términos narrativos.

## Flujo de evidencia y confirmación

1. Importar el EPUB o PDF permitido por el usuario. La importación crea candidatos iniciales pendientes solo si el título coincide con el perfil.
2. Abrir el glosario de esa novela y elegir «Buscar candidatos en el texto original». El análisis es local y no llama a un modelo.
3. Para cada coincidencia, revisar número de apariciones y las muestras literales, con capítulo y ubicación. El servicio expone hasta tres muestras cortas por término.
4. Revisar la forma sugerida y la regla. Cambiarlas si la evidencia contradice el valor inicial.
5. Pulsar «Confirmar y aprobar» solo si la muestra respalda la decisión. «Ignorar» conserva la decisión de no usar el candidato en futuras pasadas.
6. Solo las reglas aprobadas se aplican al modo local o se incluyen en los prompts de traducción. El original de los capítulos no se modifica.

El formulario de edición general no puede aprobar directamente un término sembrado desde este perfil sin una muestra literal y sin pasar por la tarjeta con evidencia. La API de aprobación también rechaza un candidato que no tenga una muestra de texto no vacía.

## Fuentes de evidencia

- **Metadatos editoriales:** ayudan a comprobar identidad o títulos, pero no confirman que una palabra aparezca en un capítulo.
- **Término solicitado por el usuario:** establece qué conviene buscar, no cómo funciona cada aparición.
- **Convención general de juegos/otaku:** aporta una hipótesis inicial de vocabulario, no una regla universal.
- **Muestra literal del capítulo importado:** es el requisito mínimo para confirmar la decisión terminológica. La persona debe leer el contexto y elegir la regla explícitamente.

No se usa un resumen de terceros como evidencia para decisiones específicas del capítulo. Tampoco se aprueba automáticamente ningún término mediante extracción, frecuencia, mayúsculas, nombre de archivo o modelo generativo.

## Riesgos conocidos

- Una misma forma inglesa puede tener varios significados y una sustitución global puede romper la gramática o la mecánica del juego.
- Una muestra breve puede ocultar ambigüedad; cuando sea necesario, el usuario debe ampliar el contexto antes de aprobar.
- Los nombres, títulos y reglas sugeridos por metadatos pueden diferir de la edición exacta importada.
- La detección literal encuentra formas escritas iguales; no reconoce por sí sola sinónimos, flexión irregular ni correferencia.
- La lista no es una traducción terminada ni una medida de calidad de capítulo. No existe todavía evidencia confirmada de un capítulo real adjunto a esta fase.

## Pruebas de aceptación

- [ ] La importación de la obra correcta prepara los candidatos del perfil como no aprobados.
- [ ] El perfil no crea una entrada de glosario para el título de la obra.
- [ ] Cada candidato tiene una regla sugerida válida, clase de referencia y requisitos de revisión.
- [ ] El análisis devuelve muestras literales del capítulo y no llama a modelos ni modifica el original.
- [ ] La tarjeta de revisión precarga la forma y regla sugeridas, pero muestra que son sugerencias.
- [ ] Intentar aprobar desde el formulario general una entrada de perfil sin evidencia devuelve HTTP 422.
- [ ] Intentar aprobar por API un candidato sin muestra literal devuelve HTTP 422.
- [ ] Después de analizar el texto, la aprobación explícita actualiza la entrada sembrada y deja el estado como aprobado.
- [ ] Repetir el análisis no restablece decisiones aprobadas o ignoradas.
- [ ] Solo las reglas aprobadas se reutilizan en traducciones; las candidatas pendientes no alteran el texto.

## Resultado de esta fase

El código y las pruebas automatizadas pueden verificar el mecanismo de sugerencia, evidencia y aprobación humana. Las formas y los sentidos para la novela quedan en estado pendiente hasta escanear una copia autorizada y revisar sus contextos reales.
