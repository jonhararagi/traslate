# Perfiles de prosa y edición sin IA en NovelTrad

## Qué añade este módulo

NovelTrad dispone de perfiles genéricos de estilo editorial y de un motor determinista local. No necesita conexión de red ni un modelo para aplicar las reglas configuradas por el autor.

Perfiles iniciales:
- **Novela ligera en español** (`light_novel_es`): claridad, ritmo de lectura y convenciones de diálogo.
- **Traducción literaria fiel** (`faithful_literary_es`): voz, focalización, matices y ausencia de añadidos.
- **Novela web en español** (`webnovel_es`): consistencia serial, términos y estructura de capítulos.

Estos son perfiles editoriales genéricos, no copias de la voz de una novela comercial concreta. Para cada obra, el usuario debe documentar sus reglas autorizadas, ejemplos propios breves, nombres protegidos, honoríficos, registro, tratamiento de pensamientos y convención de diálogos. El programa no debe inventar una guía de estilo que no se haya proporcionado.

## Modo determinista sin IA

`apply_offline_rules` acepta texto, un perfil, reglas terminológicas aprobadas y un mapa de frases explícitas. Aplica sustituciones exactas sin distinguir mayúsculas/minúsculas, prefiere frases más largas, protege términos marcados y normaliza algunas convenciones tipográficas. `lint_chapter` genera advertencias no bloqueantes.

Las reglas no aprobadas se ignoran. El original del capítulo no se modifica por este módulo: devuelve un resultado para que el usuario lo revise y decida si lo guarda.

### Límite fundamental

Esto **no es un traductor automático general**. Si el diccionario solo contiene diez términos, el programa solo puede transformar esos términos; no puede comprender ni traducir las demás frases. No se debe presentar un capítulo como traducido si solo se aplicaron reemplazos.

Para traducir frases desconocidas sin un servicio remoto, NovelTrad ya incluye un **Modo premium** opcional que solicita inferencia a un modelo local de Ollama. El **Modo local** sigue siendo determinista y no carga IA. Premium no convierte automáticamente un libro entero: cada vista previa está limitada a 12.000 caracteres, no se guarda por sí sola y exige instalar el modelo manualmente. Un motor neuronal local sigue siendo IA, aunque no use internet ni una API de pago. La calidad debe evaluarse con capítulos de prueba y revisión humana.

## Flujo recomendado por novela

1. Importar EPUB/PDF y conservar el original inmutable.
2. Definir idioma de origen y destino.
3. Completar la guía de estilo específica de la obra.
4. Revisar y aprobar el glosario: personajes, lugares, títulos, poderes, objetos, honoríficos y términos recurrentes.
5. Aplicar reglas deterministas al texto de un capítulo.
6. Leer el informe de sustituciones y advertencias; comparar original y resultado.
7. Guardar solo después de revisión, manteniendo el historial de versiones.

## Criterios de aceptación

- [ ] Los perfiles se seleccionan por identificador estable y desconocidos producen un error explícito.
- [ ] Solo se aplican reglas aprobadas.
- [ ] Los nombres protegidos no se alteran por reglas posteriores.
- [ ] Las frases largas se procesan antes que sus subfrases.
- [ ] Los párrafos se conservan salvo normalizaciones documentadas.
- [ ] No se llama a servicios externos ni se usa persistencia desde el motor.
- [x] La interfaz ofrece Modo local y Modo premium como modos diferenciados; ambos producen una vista previa que no se guarda automáticamente.
- [x] Premium llama solo a Ollama en loopback, limita la entrada a 12.000 caracteres y solicita `keep_alive=0`.
- [ ] La traducción por fragmentos con continuidad entre peticiones y la validación de calidad sobre capítulos reales siguen pendientes.
- [ ] Una futura traducción completa requiere un motor local independiente y pruebas de calidad; no se acepta afirmar que está lista solo porque pasan pruebas unitarias.
