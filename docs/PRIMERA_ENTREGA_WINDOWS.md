# Primera entrega de NovelTrad para Windows

## Objetivo

Crear una versión local portable que se pueda abrir sin instalar Python. Esta primera entrega empaqueta la aplicación web local existente en una carpeta Windows; no convierte todavía NovelTrad en un traductor completo.

## Crear el paquete

Requisitos para compilar: Windows x64, Python 3.11 instalado con el Python Launcher y conexión a Internet para instalar dependencias de compilación.

Desde PowerShell, en la carpeta raíz del repositorio:

    .\scripts\build-windows.ps1

El script crea un entorno virtual, instala dependencias de pruebas y empaquetado, ejecuta toda la suite de pruebas y solo si pasa genera dist\NovelTrad\NovelTrad.exe.

Distribuir la carpeta completa dist\NovelTrad, comprimida como ZIP. No distribuir solo el EXE: PyInstaller en modo onedir mantiene sus bibliotecas auxiliares junto al ejecutable. Al abrirlo, se inicia el servidor en 127.0.0.1:8765 y se abre el navegador predeterminado.

## Datos y privacidad

- La biblioteca del usuario continúa en %LOCALAPPDATA%\NovelTrad; no se incluye en el paquete.
- El servidor enlaza únicamente a 127.0.0.1, no a la red pública.
- El paquete no incorpora ni descarga modelos de traducción.
- El modo Premium sigue siendo una función opcional que necesita que el usuario instale/configure Ollama y un modelo por separado.
- Las novelas importadas, traducciones y copias de seguridad no deben borrarse al actualizar el ejecutable.

## Qué significa “listo”

Una compilación satisfactoria en CI demuestra que el paquete puede generarse y que las pruebas automatizadas pasan en el runner. Antes de declarar la entrega de Windows verificada, también hay que descargar el artefacto, extraerlo en un equipo limpio y comprobar apertura/cierre, importación EPUB/PDF, persistencia, copias/restauración, exportación EPUB y arranque sin Ollama.

## Próximas capacidades separadas

La traducción integral requiere un motor real, procesamiento por fragmentos, continuidad contextual, revisión lado a lado, recuperación de fallos y validación de nombres/glosario. El modo determinista actual no traduce frases desconocidas. No se debe etiquetar esta primera compilación como traductor automático completo.
