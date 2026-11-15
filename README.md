# Prometheus — NasaSAC_AdaptingFarms

> **EN:** Prometheus is a Streamlit app built for the NASA Space Apps Challenge 2026. A farmer clicks their field on a map. The app reads a year of NASA POWER data plus a 10-year baseline and computes climate and risk indicators. It then compares three crop-rotation strategies against the farmer's priorities. An AI assistant (Prometheus, powered by Google Gemini) explains the results in plain language. The tool supports farmers' judgment; it does not replace it.

Prometheus ayuda a un agricultor a explorar opciones de rotación de cultivos con datos de la NASA. Funciona así:

1. El agricultor elige su parcela en un mapa.
2. La app descarga el clima de ese punto y calcula indicadores y riesgos.
3. Compara tres estrategias de rotación según la prioridad del agricultor: ahorrar agua, mejorar el suelo o tener ingresos extra.
4. Prometheus, la IA del proyecto, explica los resultados en lenguaje sencillo.

Es una herramienta de apoyo: **no reemplaza el criterio del agricultor ni la asesoría agronómica local**.

## Equipo — Nova Aquila

| Rol | Nombre | Universidad |
|---|---|---|
| Head Developer | Onassis Monzalvo Sanchez | Texas State University |
| Developer | Osmar Said Gallegos | Arkansas State University |
| Researcher & UI Design | Hannia Lizet De León Martínez | Arkansas State University |
| Researcher & UI Design | Dulce Beatriz Del Castillo Cazares | Arkansas State University |
| Researcher & UI Design | Eva Valeria Ramírez Escamilla | Arkansas State University |

## Cómo ejecutarla

1. Crea un archivo `.env` en la raíz del proyecto:

   ```
   GEMINI_API_KEY=tu_clave_de_google_ai_studio
   # Opcional: GEMINI_MODEL=gemini-3.5-flash
   ```

   Sin clave, la app funciona igual. Solo se omiten las explicaciones de Prometheus y se muestra la orientación por reglas.

2. Arranca con Docker:

   ```bash
   docker compose up -d --build
   ```

3. Abre http://localhost:8501.

Usa `--build` cada vez que cambie `requirements.txt`. Si solo cambias archivos `.py`, basta con recargar la página, porque `docker-compose.yml` monta la carpeta dentro del contenedor.

**Sin Docker:** instala con `pip install -r requirements.txt` y ejecuta `streamlit run app.py`. En ese caso `.env` no se carga solo: exporta `GEMINI_API_KEY` o usa `.streamlit/secrets.toml`.

## Estructura

```
app.py                 Página principal: mapa, clima, métricas, gráficas y rotaciones
services/
  power.py             Descarga datos diarios de NASA POWER
  gibs.py              Capas visuales de NASA GIBS para el mapa
  land.py              Distingue tierra de mar (sin internet)
  ambience.py          Indicadores: heladas, calor, rachas secas, grados-día, anomalías
  zone.py              Resume el año en los datos que usa risk.py
  risk.py              Índices de riesgo de 0 a 100
  rotations.py         Comparación de las tres estrategias de rotación
  rotation_ui.py       Formulario y tarjetas de la comparación
  llm.py               Prometheus: instrucciones y llamadas a Gemini
  settings.py          Dónde se buscan la clave y el modelo de Gemini
data/
  crops.json           Catálogo de cultivos (agua FAO, familia, fuentes)
  ne_110m_land.geojson Contorno de continentes (Natural Earth)
```

## Datos que usa

| Fuente | Qué aporta | Uso |
|---|---|---|
| **NASA POWER** (API diaria, comunidad AG) | Lluvia, temperatura, humedad del suelo, evaporación, humedad relativa, viento y radiación | Todos los cálculos |
| **NASA GIBS**: MODIS LST, MODIS NDVI, GPM IMERG, VIIRS | Calor, vegetación, lluvia e incendios | Solo capas visuales del mapa |
| **FAO** (en `data/crops.json`) | Rangos de agua por ciclo de maíz, frijol y sorgo | Componente "agua" de las rotaciones |
| **Natural Earth** | Contorno de tierra | Rechazar clics en el mar |

## Cómo se calcula

**Indicadores** (`ambience.py`):
- Días de helada: temperatura mínima ≤ 0 °C.
- Días de calor extremo: temperatura máxima ≥ 35 °C.
- Racha seca: la mayor cantidad de días seguidos con menos de 1 mm de lluvia.
- Lluvia intensa: días con 20 mm o más.
- Grados-día: suma de la temperatura media por encima de 10 °C.
- Anomalías: cada mes completo frente al promedio de los 10 años anteriores.
- Balance hídrico: lluvia menos evaporación (`EVLAND`).

**Riesgos** (`risk.py`): cada conteo se divide entre un tope del equipo (por ejemplo, 30 días de helada equivalen a riesgo 100). Los topes están al inicio del archivo y se pueden ajustar.

**Rotaciones** (`rotations.py`): compara tres estrategias para el siguiente cultivo:
- Repetir el cultivo actual.
- Introducir frijol, una leguminosa.
- Probar sorgo, menos sensible a sequía.

Cada estrategia suma puntos de agua, helada y diversidad de familias. El peso de cada componente depende de la prioridad del agricultor. El índice solo aparece si los tres componentes se pudieron evaluar, y cualquier restricción pesa más que un puntaje alto.

**Prometheus** (`llm.py`): recibe solo números ya calculados y tiene la orden de no inventar cifras. Explica los términos técnicos y aclara las diferencias entre datos satelitales y estaciones en tierra.

## Limitaciones

- **Resolución gruesa:** POWER usa una malla de unos 50 km, así que no distingue diferencias dentro de una parcela.
- **Datos históricos:** no son pronósticos.
- **Catálogo piloto:** solo incluye maíz, frijol y sorgo.
- **Faltan datos de suelo:** el análisis no tiene textura ni nutrientes, y el pH y el drenaje los indica el agricultor.
- **Sin evaluación económica:** no se calcula la rentabilidad.
- **Puntajes heurísticos:** son reglas del equipo, no probabilidades.

## Licencia

Ver [LICENSE](LICENSE).
