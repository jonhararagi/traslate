# Benchmark reproducible para elegir un bot de novela

**Propósito:** comparar los modelos a los que el usuario realmente tenga acceso antes de elegir uno como motor principal del Taller de novela.  
**Estado:** plantilla de evaluación; no contiene resultados medidos todavía.

## Cómo ejecutarlo sin sesgo

1. Crear el mismo proyecto de prueba, con la misma guía de estilo y las mismas fichas de memoria.
2. Usar exactamente el mismo prompt, longitud objetivo, temperatura/opciones disponibles y conjunto de recuerdos para cada modelo.
3. Evaluar los resultados sin mirar qué modelo los generó si es posible.
4. Ejecutar cada prueba al menos dos veces: así se distingue una capacidad consistente de una respuesta afortunada.
5. Guardar el texto de entrada, salida, fecha, modelo identificable, opciones empleadas, incidencias y puntuación.
6. No dar por ganador un modelo basándose solo en fluidez o en una gran ventana de contexto.

No utilizar capítulos comerciales enteros para el benchmark. Las pruebas siguientes son datos sintéticos originales creados para evaluar el flujo.

## Proyecto sintético de prueba

**Título:** *El reloj que olvidó el invierno*  
**Idioma de salida:** español neutro latinoamericano.  
**Estilo:** fantasía de misterio, prosa clara, escenas concisas, diálogo natural; evitar grandilocuencia excesiva.  
**Punto de vista:** tercera persona limitada desde Mara.  
**Regla de conocimiento:** el narrador no puede revelar pensamientos privados de otros personajes.

### Hechos aprobados de canon

- Mara es una aprendiz de relojera de 19 años. Puede reparar mecanismos, pero no puede detener el tiempo.
- Ivo es su hermano menor, tiene 14 años y desconoce la existencia de la cámara subterránea.
- La ciudad de Brumaclara tiene una campana pública que suena al comienzo de cada invierno.
- La campana dejó de sonar hace tres días; desde entonces, ningún copo de nieve ha tocado el suelo.
- El reloj de bolsillo de Mara se atrasa exactamente cuatro minutos al entrar en la estación abandonada.
- La llave de cobre abre el taller, no la cámara subterránea.
- Se sospecha que el alcalde conoce el motivo del silencio de la campana, pero esto no está confirmado.
- La cámara subterránea existe, pero Ivo no la ha descubierto.
- No está establecido que Mara pueda volver el tiempo atrás ni que la campana sea la causa real del fenómeno.

### Prueba A — Escritura con restricciones

**Prompt común:**

> Escribe una escena original de 450–600 palabras en español neutro latinoamericano. Mara entra en la estación abandonada y nota que su reloj de bolsillo se atrasa cuatro minutos. Ivo la espera fuera y no debe descubrir la cámara subterránea. Mantén la tercera persona limitada a Mara, una voz de fantasía de misterio y diálogo natural. No hagas que Mara detenga o revierta el tiempo. No reveles la causa real del silencio de la campana: sigue sin estar establecida. Termina con una pista nueva que pueda interpretarse de dos maneras, sin convertirla automáticamente en canon.

**Qué se mide:** idioma y ritmo, voz narrativa, uso correcto del canon, respeto a restricciones y capacidad de abrir un misterio sin resolverlo arbitrariamente.

### Prueba B — Consulta de lore sin inventar

**Prompt común:**

> ¿Se ha confirmado que el alcalde causó el silencio de la campana? Responde en cuatro apartados: ESTABLECIDO, NO ESTABLECIDO, EVIDENCIA INTERNA y SIGUIENTE PASO. No inventes acontecimientos, fuentes ni citas. Si un dato no aparece entre los hechos aprobados, dilo.

**Resultado correcto esperado:** el silencio de la campana y la sospecha respecto al alcalde están establecidos; que el alcalde sea el causante no está confirmado; el bot debe expresar esa distinción y no agregar una supuesta prueba.

### Prueba C — Continuidad y límites de conocimiento

**Prompt común:**

> Audita esta idea de escena: «Ivo baja al sótano y le explica a Mara qué hay en la cámara subterránea. Mara usa la llave de cobre para abrir la cámara y rebobina el tiempo cinco minutos». Devuelve una tabla con cada contradicción, hecho canónico relacionado, gravedad y propuesta de corrección. No reescribas la escena ni modifiques el canon.

**Resultado correcto esperado:** al menos tres problemas: Ivo no conoce la cámara; la llave abre el taller, no la cámara; Mara no puede detener ni rebobinar el tiempo. Las propuestas deben ser alternativas no canónicas.

### Prueba D — Voz e idioma

**Prompt común:**

> Edita el siguiente texto manteniendo los hechos y la voz de Mara. Devuelve la versión editada y una lista breve de cambios. No inventes emociones, acciones ni información adicional.
>
> «Mara miró el reloj. Estaba tarde cuatro minutos otra vez. Eso no era normal y la estación no tenía que poder hacer eso. —No voy a entrar —dijo ella, entrando. La puerta hizo un ruido como viejo.»

**Qué se mide:** español natural, diálogos, precisión, coherencia interna y transparencia de los cambios. El modelo no debería alterar hechos para mejorar la prosa.

## Hoja de puntuación

Calificar cada dimensión de 1 a 5 en cada prueba. Guardar una nota de evidencia, no solo el número.

| Dimensión | Peso inicial | Qué es un 5 |
|---|---:|---|
| Prosa en español | 20 % | Natural, clara, con ritmo y sin calcos notorios. |
| Continuidad/canon | 25 % | Respeta todos los hechos y restricciones sin contradicciones. |
| Seguimiento de instrucciones | 15 % | Cumple formato, extensión, punto de vista y tarea. |
| Voz y caracterización | 15 % | Mantiene la perspectiva y no homogeniza las voces. |
| No inventar datos en consultas de lore | 10 % | Separa hechos, hipótesis y vacíos; identifica límites. |
| Editabilidad/formato | 5 % | Salida utilizable, limpia y fácil de revisar. |
| Latencia, coste y privacidad | 10 % | Adecuado al uso habitual y al nivel de privacidad requerido. |

Puntuación ponderada = suma de (nota / 5 × peso). Usar pesos expresados como porcentaje. Puntuar privacidad por la arquitectura real de uso, no por las promesas del modelo.

## Registro por modelo

Copiar esta ficha una vez por modelo/proveedor evaluado:

- Proveedor:
- Nombre y versión del modelo, si se conoce:
- Fecha:
- Modo de uso: cuenta en navegador/manual, API o local:
- Ajustes conocidos:
- Prueba A: nota + evidencia:
- Prueba B: nota + evidencia:
- Prueba C: nota + evidencia:
- Prueba D: nota + evidencia:
- Puntuación total:
- Errores graves:
- Errores repetidos:
- Latencia aproximada:
- Coste/limites aplicables:
- Datos enviados al proveedor:
- ¿Se repitió la prueba?:
- Decisión: preferido / suplente / no recomendado / datos insuficientes.

## Reglas de decisión

- Un promedio alto no compensa violaciones repetidas del canon o de privacidad.
- Una equivocación de continuidad sobre un hecho explícito cuenta como fallo importante, aunque la prosa sea elegante.
- No elegir el modelo más grande por defecto: seleccionar el que ofrece mejor consistencia y calidad para el coste, latencia y modo de privacidad aceptables.
- El bot debe poder cambiar de proveedor sin perder el proyecto ni su memoria.
- El resultado del benchmark es una recomendación provisional con fecha; no una afirmación universal sobre todos los usos ni todas las versiones futuras.
- Repetir la evaluación cuando cambie el modelo o cambien significativamente el prompt, la recuperación o el formato de memoria.

## Estado inicial

No se han ejecutado pruebas comparativas en este documento. No hay aún un modelo ganador ni puntuaciones fabricadas. El benchmark debe ejecutarse desde el panel cuando se integre el flujo de selección de proveedor y memoria.
