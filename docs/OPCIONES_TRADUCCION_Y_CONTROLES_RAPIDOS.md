# Opciones de traducción y controles rápidos

## Objetivo

La cola de traducción de libro completo debe permitir elegir cómo se redacta el siguiente prompt y manejar la cola con acciones claras, sin obligar al usuario a buscar botones entre todos los controles.

## Preferencia para cada fragmento

Antes de generar el próximo prompt, el usuario puede elegir:

- **Fiel y natural:** conserva el contenido completo y usa español natural.
- **Priorizar jerga otaku/gamer:** preserva el vocabulario especializado cuando el contexto/glosario lo justifica.
- **Fluidez narrativa en español:** privilegia diálogos y prosa fluidos sin omitir hechos ni matices.
- **Más literal para comparar:** mantiene una formulación cercana al original y evita resolver ambigüedades sin evidencia.

También puede añadir una instrucción propia de hasta 2.000 caracteres. El servidor valida la opción, incluye la preferencia y la instrucción en el próximo prompt, y devuelve qué preferencia se usó. El texto personalizado no modifica el original, el glosario ni el canon de la novela; las restricciones de fidelidad, no omisión y no invención siguen vigentes.

La preferencia se aplica al prompt que se genera después de seleccionarla. Para comprobar qué recibió el proveedor, el usuario puede leer el prompt completo antes de copiarlo.

## Control rápido

El selector de acción y el botón **Enviar** ofrecen tres posibilidades:

- **Seguir:** genera el prompt del siguiente fragmento o reanuda una cola pausada. Si ya hay un prompt/fragmento en curso sin respuesta guardada, la acción queda deshabilitada para no saltarlo.
- **Parar:** pausa la cola y conserva el progreso; no borra traducciones, fuentes ni revisiones.
- **Enviar respuesta pegada:** guarda en la cola local la traducción que el usuario ya pegó. Queda sin revisar hasta que el usuario la compare con el original y guarde la revisión.

El mismo control no automatiza el envío a ChatGPT ni a Gemini. La respuesta sigue el flujo aprobado: copiar prompt, enviarlo manualmente al proveedor, pegar la respuesta en NovelTrad, revisar y aplicar explícitamente.

## Criterios de aceptación

1. El usuario puede seleccionar cada estilo sin editar el código.
2. La instrucción personalizada acepta texto opcional y no más de 2.000 caracteres.
3. Estilo e instrucción aparecen en el prompt exacto generado para el siguiente fragmento.
4. Una opción de estilo desconocida se rechaza sin reservar/cambiar un fragmento de la cola.
5. **Seguir** prepara el siguiente prompt y respeta el estado de la cola.
6. **Parar** pausa sin perder el trabajo guardado.
7. **Enviar** ejecuta la acción seleccionada dentro de NovelTrad; cuando se selecciona guardar una respuesta, se guarda como no revisada.
8. Ningún control envía el texto automáticamente a un proveedor externo.
9. El texto original nunca se modifica por el hecho de elegir una preferencia o parar la cola.

## Estado de implementación

La interfaz, validación de estilo, instrucción personalizada y controles rápidos están implementados en `src/noveltrad/main.py`. Las pruebas automatizadas cubren el prompt configurable, el rechazo de estilos desconocidos y la presencia de los controles de interfaz. La validación mediante CI para el SHA de implementación y el build portable debe confirmarse antes de presentar esta entrega como verificada.
