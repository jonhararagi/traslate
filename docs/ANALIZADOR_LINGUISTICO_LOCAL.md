# Analizador lingüístico local e inspección narrativa conservadora

## Alcance implementado en esta rama

`noveltrad.linguistic_analysis` agrega una base determinista sin modelos ni acceso a red:

- Segmenta oraciones y tokens con offsets sobre el texto original.
- Asigna etiquetas gramaticales heurísticas; no son un análisis sintáctico completo.
- Busca alias definidos por el usuario, priorizando el alias más largo y evitando menciones solapadas.
- Emite advertencias cuando aparecen pronombres o candidatos a nombres propios; no afirma resolver correferencias.
- Compara hechos estructurados que el usuario ya registró con una fuente. Los valores confirmados incompatibles se informan para revisión; hipótesis e inferencias quedan separadas y no crean conflictos de canon.

## Límites

Este módulo no traduce frases desconocidas, no extrae hechos canónicos automáticamente, no demuestra causalidad y no resuelve pronombres. Es infraestructura verificable para futuras fases, no un motor de razonamiento narrativo completo. Los offsets usan índices de cadena de Python. Las etiquetas de categoría son heurísticas y pueden equivocarse.

## Pruebas y criterio de aceptación

Las pruebas cubren offsets, alias superpuestos, advertencias heurísticas, conflictos con procedencia y la separación entre hipótesis y hechos confirmados. Deben ejecutarse junto con toda la suite existente en Python 3.11+ y con la compilación/smoke test de Windows antes de integrar. La rama no debe fusionarse si falla cualquier prueba o si la integración altera el original, la cola de traducción o el aislamiento entre proveedores.
