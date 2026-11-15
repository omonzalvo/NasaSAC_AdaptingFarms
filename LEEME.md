# TerraShift IA

## Integrar en el proyecto

1. Descomprime este paquete.
2. Ejecuta **INTEGRAR_WINDOWS.bat**.
3. Pega la ruta de la carpeta del proyecto, la que contiene `app.py`.
4. Cuando termine, ejecuta **INICIAR_APP_IA.bat** dentro del proyecto, o ábrelo como siempre.

No hay que copiar fragmentos ni editar archivos. El instalador copia el módulo,
conecta el panel, comprueba dependencias y guarda un respaldo de los archivos afectados.
Conserva el mapa, los servicios de NASA y las credenciales existentes.
Puedes repetir la instalación: actualiza su bloque sin duplicar el panel.
Si el código anfitrión cambió su contrato, se detiene con un mensaje en lugar de
intentar una modificación incompatible.

Requisitos: Windows, Python 3.10 o superior e internet para instalar dependencias.
La aplicación anfitriona debe tener instalado Streamlit y sus dependencias habituales.
También puedes ejecutar `python integrar.py "ruta/al/proyecto"` desde otro sistema.

## Clave de Gemini

Si el proyecto ya tiene GEMINI_API_KEY configurada en el entorno o en secrets.toml,
se utiliza automáticamente. Si no, la página muestra un campo protegido para
introducirla. No necesitas editar código ni archivos de configuración.
La clave introducida en pantalla se mantiene únicamente en la sesión y no se
incluye en los archivos descargables. Usa tu propia clave y no compartas credenciales.

## Probar por separado

Ejecuta **INICIAR_DEMO_WINDOWS.bat**. La página utiliza datos históricos guardados
para mostrar el panel sin depender del mapa. Introduce tu clave en pantalla y pulsa
**Analizar con Gemini**. La llamada a Gemini es real; los datos de ejemplo son de enero de 2025.

## Qué hace

Recibe las once variables actuales de NASA POWER, calcula indicadores y cobertura,
interpreta los datos con Gemini y muestra evidencias, preguntas y próximos pasos.
Los resultados cambian de contexto según el perfil. No genera pronósticos ni
prescripciones de cultivos: todavía no hay un catálogo agronómico conectado.

## Compatibilidad

Preparado para la versión 133d9d4 del proyecto anfitrión. Utiliza las variables
`df`, `lat`, `lon`, `inicio` y `fin`, disponibles en su app.py actual.
El instalador comprueba esos nombres, pero no puede garantizar compatibilidad con
cambios futuros de estructura. No publica cambios en GitHub.

Los respaldos quedan en `.terrashift-backups` dentro del proyecto.
Para restaurar, recupera app.py y los otros archivos del respaldo elegido.
El módulo añadido se puede retirar si se restaura una versión sin integración.

No incluyas `.venv`, secrets.toml ni respaldos al compartir. Entrega el ZIP original.
