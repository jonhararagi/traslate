# Auditoría de ramas, integración y tareas pendientes

**Fecha:** 2026-10-16  
**SHA de referencia auditado:** `ca7eadf7c1847a64d95997c0ad98f6e062ca45d0`  
**Repositorio:** [jonhararagi/traslate](https://github.com/jonhararagi/traslate)

## Resultado ejecutivo

En el SHA de referencia, los PR #1–#14 estaban cerrados y fusionados; la búsqueda de GitHub no devolvió PR ni issues abiertos. Las 14 ramas históricas visibles correspondían a esos PR. La mayoría están divergidas de `main` porque los cambios se fusionaron mediante squash o porque algunos PR intermedios usaron ramas de trabajo como base. Esa divergencia no significa por sí sola que el contenido esté ausente. No se deben volver a fusionar las cabezas de esas ramas a ciegas.

La revisión del árbol actual confirmó archivos y pruebas para los grupos históricos: aplicación base, copias de seguridad y recuperación, asistencia narrativa manual, motor determinista offline, perfil de Oknodie, empaquetado de Windows, fragmentación de capítulo, validación del modelo heredado, cola persistente, candidatos de glosario con evidencia, advertencias de calidad, consistencia del glosario y handoff manual Chromium. No se identificó un conjunto de cambios de una rama antigua que justificara una reintegración directa de su cabeza completa.

## Inventario de ramas históricas y PR

| Rama histórica | PR | Estado comprobado | Resultado / decisión |
|---|---:|---|---|
| `feat/noveltrad-foundation` | [#1](https://github.com/jonhararagi/traslate/pull/1) | Cerrado, fusionado | Base local-first, lector y persistencia. |
| `feat/backup-import-hardening` | [#2](https://github.com/jonhararagi/traslate/pull/2) | Cerrado, fusionado en `feat/noveltrad-foundation` | La rama contiene endurecimiento de importación y copias recuperables; los scripts y la CLI de backup existen en el árbol actual. No reintegrar su cabeza obsoleta. |
| `feat/narrative-assistant-microwindow` | [#3](https://github.com/jonhararagi/traslate/pull/3) | Cerrado, fusionado en `feat/backup-import-hardening` | La ayuda narrativa manual está documentada y hay pruebas de la interfaz/opciones de asistencia. |
| `feat/offline-prose-rules` | [#4](https://github.com/jonhararagi/traslate/pull/4) | Cerrado, fusionado en `feat/narrative-assistant-microwindow` | El motor determinista y los perfiles están en `src/noveltrad/narrative_rules.py`, con pruebas y documentación. |
| `feat/academy-villain-glossary-seeding` | [#5](https://github.com/jonhararagi/traslate/pull/5) | Cerrado, fusionado | Perfil inicial de la novela; términos aún no aprobados hasta verificarlos contra la edición importada. |
| `feat/windows-first-release` | [#6](https://github.com/jonhararagi/traslate/pull/6) | Cerrado, fusionado | Empaquetado portable y flujo de build para Windows. |
| `feat/chunked-premium-translation` | [#7](https://github.com/jonhararagi/traslate/pull/7) | Cerrado, fusionado | Vista previa por fragmentos con continuidad y revisión. |
| `fix/premium-response-validation` | [#8](https://github.com/jonhararagi/traslate/pull/8) | Cerrado, fusionado | Respuestas inválidas/vacías del endpoint heredado se manejan como errores controlados. |
| `feat/full-book-translation-queue` | [#9](https://github.com/jonhararagi/traslate/pull/9) | Cerrado, fusionado | Cola persistente, recuperación y revisión obligatoria; el proveedor se migró después. |
| `feat/evidence-based-glossary-candidates` | [#10](https://github.com/jonhararagi/traslate/pull/10) | Cerrado, fusionado | Candidatos detectados localmente con evidencia; aprobar/ignorar exige acción humana. |
| `feat/translation-quality-warnings` | [#11](https://github.com/jonhararagi/traslate/pull/11) | Cerrado, fusionado | Indicadores heurísticos para orientar la revisión, no un certificado de calidad. |
| `feat/glossary-consistency-checks` | [#12](https://github.com/jonhararagi/traslate/pull/12) | Cerrado, fusionado | Señales de consistencia para reglas aprobadas, manteniendo flexibilidad contextual. |
| `fix/windows-portable-startup-smoke` | [#13](https://github.com/jonhararagi/traslate/pull/13) | Cerrado, fusionado | Diagnóstico de arranque y smoke test del ejecutable empaquetado. |
| `feat/chromium-account-premium` | [#14](https://github.com/jonhararagi/traslate/pull/14) | Cerrado, fusionado | ChatGPT/Gemini en Chromium visible, handoff manual y cola de libro completo migrada a prompt/respuesta. |

## Validación de la versión principal de referencia

- SHA: `ca7eadf7c1847a64d95997c0ad98f6e062ca45d0`.
- [Tests Ubuntu y Windows](https://github.com/jonhararagi/traslate/actions/runs/38896672388): exitosos.
- [Windows Portable Build y smoke test de `NovelTrad.exe`](https://github.com/jonhararagi/traslate/actions/runs/38896672374): exitosos.
- El artefacto `NovelTrad-Windows-x64` se asoció al SHA de referencia. SHA-256 del ZIP: `695d5c45bbc34d7a8437fa28b8076329635de086ab7a5ac88fb0095522b98633`.
- Esto verifica pruebas y arranque dentro de GitHub Actions, no la experiencia real en el PC del usuario.

## Hallazgo de integración en revisión

La cola actual usa un proveedor guardado en cada trabajo (`chatgpt` o `gemini`), pero el endpoint heredado `POST /api/translation-jobs/{job_id}/run-next` llama a Ollama. Antes de la corrección, la API no impedía ejecutar ese endpoint sobre un trabajo configurado para una cuenta externa; a la inversa, las rutas manuales tampoco distinguían una cola local.

La rama `fix/provider-isolation-and-project-closeout` corrige este cruce y añade pruebas de regresión:
- `TranslationJobInput` acepta `ollama` solo como selección explícita para uso API; la interfaz normal continúa ofreciendo solo ChatGPT/Gemini.
- `run-next` rechaza trabajos ChatGPT/Gemini.
- `next-prompt` y el endpoint de envío manual rechazan trabajos Ollama.
- Las pruebas de los flujos locales especifican explícitamente `provider: "ollama"`; se prueba que un trabajo ChatGPT/Gemini no llama al modelo local.

**Estado de este hallazgo:** cambios preparados en una rama de trabajo, pendientes de CI y revisión de integración. No deben describirse como ya fusionados hasta comprobar el PR y los workflows.

## Tareas realmente pendientes

1. **Prueba real en Windows del usuario:** ejecutar el contenido extraído del ZIP; iniciar sesión manualmente en ChatGPT/Gemini; probar una vista previa y una cola corta; cerrar/reabrir la app; comprobar pausa, respuesta después de pausar, reanudación, recuperación, reintento, revisión y bloqueo de aplicación hasta revisar todo; verificar exportación EPUB.
2. **Benchmark con texto autorizado:** medir omisiones, duplicaciones, deriva de párrafos y consistencia de Oknodie y términos contextuales como `farm`, `level`, `Steal` y `tsundere`. Los ejemplos sintéticos no prueban la calidad de la traducción real.
3. **OCR:** no está implementado; los PDF escaneados o páginas de cómic sin texto extraíble siguen fuera de alcance.
4. **Validación manual adicional:** restauración de backup, navegación de EPUB complejo, accesibilidad del lector y uso bajo carga de memoria real. CI no sustituye estas pruebas.
5. **Modo local:** sigue siendo un motor de reglas/glosario determinista y ligero, no un traductor neuronal general. Cualquier motor offline adicional requiere un benchmark por dirección y medición de RAM antes de recomendarlo.

## Política para las ramas antiguas

Las ramas antiguas se conservan como rastro de trabajo. No deben recibir merges de `main` a la fuerza ni volver a fusionarse completas solo para que desaparezca la divergencia. Si en el futuro aparece un cambio único y necesario, hay que aislar ese cambio en un PR pequeño, con una prueba que demuestre la necesidad. La ausencia de PR/issues abiertos no significa que las validaciones manuales pendientes hayan sido realizadas.
