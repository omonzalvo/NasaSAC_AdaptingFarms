# Referencia técnica de TerraShift IA

La instalación normal se hace con INTEGRAR_WINDOWS.bat. No requiere editar código.
Las siguientes funciones se documentan para desarrolladores; no son pasos de instalación.

## Uso sin nuestra interfaz

```python
from terrashift_ai import prepare_analysis, analyze_prepared, AnalysisError

prepared = prepare_analysis(
    df, latitude=lat, longitude=lon,
    start=inicio.strftime('%Y-%m-%d'), end=fin.strftime('%Y-%m-%d'),
    profile={"crop": "Maíz", "water": "Solo lluvia (temporal)",
             "goal": "Evaluar alternativas de rotación"})
# prepared es JSON serializable: se puede mostrar/guardar sin clave ni internet.
try:
    result = analyze_prepared(prepared, api_key=clave_del_servidor)
except AnalysisError as exc:
    mostrar_error(str(exc))  # Sustituye por tu función de interfaz.
else:
    mostrar_analisis(result) # Sustituye por tu función de interfaz.
```

También existe `analyze_dataframe(df, ..., api_key=...)` con los mismos argumentos.
No llama otra vez a NASA: utiliza tu tabla. `prepare_analysis` valida entrada;
`ValueError` significa un problema de contrato. `AnalysisError` es un error controlado
de clave, cuota, conexión o respuesta. No registrar secretos ni cuerpos de error remotos.

## Contrato de entrada

- pandas.DataFrame diario, índice DatetimeIndex o cadenas YYYY-MM-DD / YYYYMMDD.
- Sin fechas duplicadas, sin zona horaria, sin registros horarios.
- Fechas `start` / `end`: período SOLICITADO inclusive. No usar mínimo/máximo observado
  porque ocultaría días faltantes al inicio o final. Máximo aproximado diez años.
- Coordenadas latitude [-90,90], longitude [-180,180].
- Valores originales de NASA POWER `community=AG`, sin conversiones silenciosas.
- -999, NaN, infinitos y textos no numéricos se tratan como faltantes. Lluvia negativa se excluye.
- Se aceptan subconjuntos de variables; las ausentes quedan sin dato. Si ninguna tiene
  valores válidos, no se envía una llamada a Gemini.
- Columnas desconocidas se ignoran con advertencia. Imágenes GIBS no son datos numéricos.
- Perfil opcional: crop, history, water, soil, goal, planting_window;
  cada campo texto de hasta 1000 caracteres. No incluir nombres, teléfonos o claves.

| Variable | Unidad de ENTRADA esperada | Resumen |
|---|---|---|
| PRECTOTCORR | mm/day | Suma de valores diarios disponibles, en mm |
| T2M, T2M_MIN, T2M_MAX, T2MDEW, T2MWET | C | Media, en °C |
| WS10M, WS50M | m/s | Media |
| ALLSKY_SFC_SW_DWN, ALLSKY_SFC_PAR_TOT | MJ/m^2/day | Media diaria |
| ALLSKY_KT | dimensionless | Media |

Las unidades se contrastaron con los metadatos de la respuesta NASA POWER AG
incluida en example_power.json. Una media de máximas diarias NO es el máximo absoluto.
Se calculan resúmenes del período y por mes. Cobertura cuenta valores numéricos
presentes, no certifica la calidad científica del producto.

Opcional pero recomendado: antes de devolver df en services/power.py, conservar:
```python
df.attrs['source_metadata'] = {
    'header': data.get('header', {}),
    'parameters': data.get('parameters', {}),
    'geometry': data.get('geometry', {})
}
```
Si falta esa información se advierte que las unidades se asumen por contrato AG.
Si hay unidades declaradas incompatibles se rechaza la entrada: no convertimos automáticamente.
La referencia temporal LST/UTC se toma del encabezado si existe; de otro modo dice no informada.

## Contrato de salida

prepare_analysis devuelve:
- contract_version: "1.0"
- request_id: huella de datos, perfil y advertencias
- climate: fuente, ubicación, fechas, facts, monthly, metadatos y límites
- profile: perfil limpio
- warnings: advertencias de entrada

Cada fact: id, label, value (número o null), unit, valid_days, expected_days, coverage_pct.
Cada monthly: id (VARIABLE:YYYY-MM), variable, month, value, unit, valid_days, expected_days.

analyze_prepared agrega:
- analysis.summary: explicación general
- analysis.observations: explanation y evidence_ids para cada observación
- analysis.questions, next_steps, limitations: listas de textos
- analysis.validation_warnings: partes omitidas por cifras sin respaldo
- provider, model, requested_model, usage: información de la llamada

Las referencias deben existir y tener datos. La validación numérica es léxica:
NO demuestra que el modelo haya interpretado correctamente unidades, causalidad
ni relaciones agronómicas. Mostrar siempre evidencias y límites. No anunciar
«verificación científica» de la respuesta generada.

## Alcance de esta entrega

Analiza el historial ambiental disponible, lo relaciona con el perfil para orientar
preguntas y próximos pasos, y explica limitaciones. Recibe las once variables actuales.
Todavía NO recomienda rotaciones específicas, no pronostica clima, rendimiento,
beneficios económicos ni calcula requerimientos de riego. La integración de un
catálogo agronómico y reglas de comparación es la siguiente fase, separada de este contrato.
No extrae NDVI ni temperatura de imágenes GIBS; necesita series numéricas y metadatos
para incorporar productos adicionales. No manda datos diarios completos a Gemini;
manda indicadores del período y mensuales.

## Prueba independiente

Con Python 3.10 o superior, instala requirements-ia.txt y Streamlit; introduce tu clave en la página si no está configurada en el entorno.
Ejecuta `python -m streamlit run demo.py`, o INICIAR_DEMO_WINDOWS.bat.
Incluye una respuesta histórica NASA guardada de enero 2025: no es una consulta reciente.
No llama a NASA; Gemini sí se consulta al pulsar el botón. Sin clave puedes inspeccionar
los indicadores y descargar evidencias.

## Validación realizada

`python -m unittest discover -s tests -v` — 18 pruebas aprobadas, incluidas instalación repetida y protección de archivos:
11 variables, unidades, cobertura, faltantes, índice/fechas, coordenadas, referencias,
perfil, respuesta simulada, credenciales y cuota. También se probó el panel con
Streamlit AppTest: sin clave, respuesta simulada, reutilización e invalidación por cambio.
No se realizó llamada real a Gemini en esta entrega: falta tu clave del servidor.
No se alteró ni publicó el repositorio de el proyecto anfitrión.

## Prueba de aceptación de el proyecto anfitrión

1. Seleccionar un punto y esperar su df.
2. Verificar indicadores y días válidos del panel.
3. Introducir la clave en la página si no existe una configuración previa.
4. Pulsar analizar: verificar respuesta y evidencias, descargar JSON.
5. Repetir botón: debe reutilizar resultado; cambiar punto/perfil: debe limpiar el anterior.
6. Cambiar PRECTOTCORR a NaN en una COPIA de la tabla: no debe aparecer 0 mm.

No hay reintentos automáticos ni un modelo alternativo de pago. El panel espera
30 segundos entre intentos y conserva solo el último análisis en la sesión.
No es una cuota global ni una garantía de costo cero: depende del proyecto de Google.
No activar facturación para esta demo sin decidirlo expresamente.
