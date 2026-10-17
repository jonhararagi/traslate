# Aprendizaje reutilizable y exportación por capítulo

NovelTrad mantiene el texto traducido y las decisiones reutilizables en carpetas diferentes dentro de los datos locales de cada novela:

- `traduccion/capitulo-NNN.md`: solo prosa traducida.
- `aprendizaje/nombres-y-personajes.json`
- `aprendizaje/terminologia-otaku-gamer.json`
- `aprendizaje/simbolos-y-formato.json`
- `aprendizaje/reglas-de-traduccion.json`
- `aprendizaje/ambiguedades-resueltas.json`
- `aprendizaje/README.md`: índice de cantidades por estado.

## API local

- `GET /api/books/{book_id}/learning`: resumen de decisiones por categoría.
- `POST /api/books/{book_id}/learning/decisions`: registra una decisión. El campo `evidence` debe ser una subcadena literal de `original_text` en el capítulo señalado por `chapter_index` (índice desde cero).
- `POST /api/books/{book_id}/learning/export-markdown`: exporta capítulos con traducción no vacía a Markdown y actualiza el índice de aprendizaje.

El esquema de decisión usa `category` (`names`, `terminology`, `symbols`, `rules` o `ambiguities`), `source`, `target`, `decision_type`, `context`, `chapter_index`, `evidence`, `status` y `notes`. Los estados son `candidate`, `confirmed` y `rejected`. Las reglas rechazadas no se promueven. Solo las decisiones confirmadas se incorporan al prompt manual de fragmentos futuros; las candidatas no se tratan como instrucciones confirmadas.

## Revisión desde la interfaz

En el lector, el botón **Aprendizaje** abre un formulario para registrar una decisión candidata con categoría, capítulo, término original, tratamiento propuesto, contexto y evidencia literal. La lista muestra el estado y la evidencia de cada entrada, y permite confirmar o rechazar candidatas sin llamar a la API manualmente. La interfaz no convierte candidatas en reglas automáticamente; una decisión rechazada permanece rechazada.

## Contrato de aprendizaje

La deduplicación usa término original, tratamiento en español y tipo de decisión, con normalización Unicode, mayúsculas y espacios. Una coincidencia no crea una nueva regla; puede agregar evidencia contextual de otro capítulo. El fragmento de evidencia y el contexto deben ser útiles para distinguir usos contextuales como el verbo gamer `farm` frente a un uso literal.

Una acción narrativa recurrente no se convierte automáticamente en una regla terminológica. Se registra solo si define una convención reutilizable, una decisión de estilo o una ambigüedad real. No se extrae ni se aprueba aprendizaje automáticamente a partir de una traducción sin revisión.

## Limitaciones y verificación

Estas rutas guardan decisiones explícitas; no sustituyen una evaluación lingüística humana ni demuestran que una traducción sea correcta. El endpoint Markdown exporta los capítulos traducidos que ya están guardados; no descarga ni genera capítulos ausentes. El proyecto necesita una copia de la edición autorizada importada por el usuario antes de procesar una novela completa.
