# Piloto terminológico de Oknodie — NovelTrad

## Fuente de la obra y límites de importación

NovelTrad queda configurado con el perfil de **I Became the Academy Villain's Daughter** y 18 candidatos terminológicos iniciales. Al importar un EPUB/PDF cuyo título coincida exactamente con uno de los títulos reconocidos, el importador siembra esos términos en el glosario del libro como **no aprobados**. Esto prepara el espacio de trabajo; no descarga la novela ni rellena el libro con texto protegido.

Fuentes encontradas y su alcance:

- [Novelpia — novela original en coreano](https://novelpia.com/novel/96311). Es la fuente oficial del original. El acceso a capítulos puede requerir cuenta o pago.
- [Tapas — adaptación oficial en inglés](https://tapas.io/series/i-became-the-villains-daughter-at-the-academy/info). Es un cómic/adaptación, no la novela en prosa. Sirve para confirmar nombres y contexto general; no equivale a un EPUB/PDF de la novela.
- [Novel Updates — ficha y enlaces editoriales](https://www.novelupdates.com/series/i-became-the-daughter-of-the-academys-villain/). Es un directorio de metadatos, no el archivo de capítulos. Su ficha identifica Novelpia Global como editor inglés, pero debe verificarse la disponibilidad actual de la edición.

No se ha descargado ni incorporado ningún capítulo completo desde una fuente de terceros. El repositorio no debe redistribuir capítulos comerciales. Para probar la traducción del texto real, importa desde NovelTrad el EPUB/PDF de una edición a la que tengas acceso legítimo. Si la única edición disponible es el cómic en imágenes, hará falta OCR; esa función aún no está implementada.

## Qué se añadió

- Fuente de la obra, idioma, formato y URL de referencia guardados en `data/novels/i_became_the_academy_villains_daughter.json`.
- Candidatos para Oknodie, el título del juego, level/level up, farm/farming, grind, min-maxing, stats, build, steal/Steal, skill, quest, drop, reroll y tsundere.
- Todos permanecen sin aprobar. Los términos ambiguos no se deben aplicar como reemplazos globales.
- Banco de prueba sintético en `data/benchmarks/academy_villain_context_cases.json`. Son oraciones inventadas, no citas de la novela. Sirven para detectar errores de sentido antes de evaluar una traducción de capítulo real.

## Por qué un traductor genérico falla aquí

No alcanza con traducir palabra por palabra. En el banco de prueba, `farm` significa «farmear» al acumular experiencia, pero «granja» al referirse al lugar físico. `level` puede ser nivel de personaje o piso de una torre. `Steal` puede ser una etiqueta de habilidad, mientras que `steal` en la misma oración es el verbo «robar». `tsundere` es un arquetipo cultural, no un sinónimo completo de «fría».

El motor local actual hace sustituciones deterministas aprobadas; no comprende automáticamente esos contextos. El banco sirve para comprobar esta limitación y establecer criterios de aceptación, no para fingir que ya se ejecutó un traductor neuronal. La prueba real debe comparar el resultado de un motor disponible con una traducción de referencia revisada por una persona.

## Procedimiento de validación

1. Descarga/importa una edición autorizada en EPUB o PDF de texto seleccionable.
2. Usa el título reconocido en el nombre del archivo para que NovelTrad siembre los candidatos.
3. Revisa el glosario y aprueba solo nombres y equivalencias confirmados en esa edición.
4. Ejecuta el mismo fragmento con el modo de traducción elegido y conserva el original inmutable.
5. Compara omisiones, nombres, términos gamer/otaku, etiquetas del sistema, gramática, voz y contexto. No guardes la propuesta hasta revisarla.
6. Si una palabra depende del contexto, no la apruebes como sustitución global hasta que el programa soporte y pruebe reglas contextuales por ocurrencia.

## Estado honesto

El perfil y el banco de pruebas son datos de preparación. **No se ha traducido todavía un capítulo real de la novela**, porque el repositorio no contiene un EPUB/PDF autorizado y el cómic oficial en inglés no es un archivo de prosa compatible con el importador actual. Tampoco se afirma que Argos u otro motor haya sido ejecutado en esta sesión.
