# Microventana de asistencia narrativa

NovelTrad y WordWaifu comparten un contrato de asistencia editorial manual (nivel 1), sin dependencia de API ni modelo integrado.

## Flujo
- La aplicación prepara un prompt contextual en el equipo.
- El usuario revisa y edita el fragmento y el contexto.
- Una casilla de consentimiento explícito habilita copiar el prompt y abrir ChatGPT o Gemini.
- El usuario pega y envía manualmente el contenido, luego trae la respuesta y decide si aplica alguna propuesta.
- No hay llamadas de red de asistencia, lectura de sesiones/cookies, automatización del navegador ni guardado automático de prompts o respuestas.

## Tareas
Traducción orientativa, análisis de contexto/personajes/relaciones, continuidad, estilo y términos candidatos para el glosario. Los resultados son sugerencias, no canon ni cambios aplicados.

## Privacidad y límites
El texto permanece local mientras se prepara el prompt. Copiarlo y pegarlo en un servicio externo lo comparte con ese proveedor; por eso la casilla es obligatoria y la persona decide qué fragmento incluye. Abrir una web no concede acceso programático a la sesión ni permite que NovelTrad lea su respuesta. Las cuotas dependen del proveedor y de la cuenta; no se promete acceso ilimitado o gratuito.

El nivel 2 solo podrá considerarse si existe una integración oficial documentada y autorizada. No se permite scraping de sesiones, automatización de la interfaz web ni evasión de límites.
