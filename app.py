"""Prometheus: app de Streamlit para el NASA Space Apps Challenge 2026 (Team Nova Aquila).

Flujo de la página:
    1. Mapa con capas de NASA GIBS; el usuario hace clic en su parcela.
    2. Se descartan los clics en el mar (services.land).
    3. Se descarga un año de NASA POWER y diez años para comparar (services.power).
    4. Se calculan indicadores y riesgos (services.ambience, services.zone, services.risk).
    5. Prometheus redacta un informe del clima (services.llm).
    6. Se muestran métricas y gráficas.
    7. El agricultor compara tres rotaciones de cultivo (services.rotation_ui).

Ejecutar:  docker compose up -d --build   o   streamlit run app.py
"""
import re

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from services.power import get_power_data
from services.gibs import CAPAS, CAPAS_WMS, WMS_URL, tile_url, ultima_fecha_disponible
from services.llm import explicar
from services.ambience import indicadores, tabla_mensual, indicadores_extra, anomalias_mensuales
from services import risk, zone
from services.land import classify_point
from services.rotation_ui import render_rotations

## Configuración de la página
st.set_page_config(page_title="Prometheus", page_icon="🌱", layout="wide")

# Título animado minimalista: aparece con un fade in y se escribe letra por letra
# (máquina de escribir), con un cursor que parpadea al final.
# Usa una fuente monoespaciada para que cada letra ocupe exactamente 1ch.
# Si el sistema pide menos movimiento (prefers-reduced-motion), el título queda fijo.
TITULO = "PROMETHEUS"
st.markdown(
    f"""
    <style>
    .titulo-wrap {{
        text-align: center;
        margin: 0.4em 0 0.3em;
        animation: titulo-fade 0.8s ease-out both;
    }}
    .titulo-prometheus {{
        display: inline-block;
        font-family: "Source Code Pro", ui-monospace, Menlo, monospace;
        font-size: clamp(2rem, 6vw, 3.6rem);
        font-weight: 600;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        padding-right: 0.1em;
        width: {len(TITULO)}ch;
        border-right: 0.08em solid currentColor;
        animation: titulo-escribir 1.6s steps({len(TITULO)}) 0.5s both,
                   titulo-cursor 0.9s step-end infinite;
    }}
    @keyframes titulo-fade {{
        from {{ opacity: 0; }}
        to   {{ opacity: 1; }}
    }}
    @keyframes titulo-escribir {{
        from {{ width: 0; }}
        to   {{ width: {len(TITULO)}ch; }}
    }}
    @keyframes titulo-cursor {{
        50% {{ border-color: transparent; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
        .titulo-wrap, .titulo-prometheus {{ animation: none; }}
        .titulo-prometheus {{ border-right: none; }}
    }}
    </style>
    <div class="titulo-wrap">
        <div class="titulo-prometheus" role="heading" aria-level="1">{TITULO}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: gray;'>NASA Space Apps Challenge 2026 - Team: Nova Aquila</p>",
    unsafe_allow_html=True,
)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


## Funciones con caché
@st.cache_data(ttl=3600)
def explicacion(contexto):
    """Informe del clima de Prometheus, guardado una hora para no repetir llamadas."""
    return explicar(contexto)


@st.cache_data(ttl=1800)
def fecha_reciente(capa, matriz, formato):
    """Última fecha con imagen de una capa GIBS, guardada 30 minutos."""
    return ultima_fecha_disponible(capa, matriz, formato)


@st.cache_data(ttl=3600)
def cargar_clima(lat, lon, inicio, fin):
    """Datos diarios de NASA POWER, guardados una hora por punto y periodo."""
    return get_power_data(lat, lon, inicio, fin)


## Agente de interpretación (Gemini)
def interpretar_clima(df, lat, lon, extra_texto=""):
    """Le pasa a Gemini los datos de NASA POWER para que los lea y redacte el informe."""
    st.subheader("Prometheus · interpretación del clima")

    mensual = tabla_mensual(df)
    mensual.index = [f"{MESES[d.month - 1]} {d.year}" for d in mensual.index]
    tabla = mensual.to_csv(float_format="%.2f", index_label="mes")

    dia_lluvia = df["PRECTOTCORR"].idxmax()
    dia_calor = df["T2M_MAX"].idxmax()

    contexto = (
        f"Ubicación: latitud {lat:.2f}, longitud {lon:.2f}.\n"
        f"Periodo: {df.index.min():%d/%m/%Y} a {df.index.max():%d/%m/%Y}.\n"
        f"Lluvia total del periodo: {df['PRECTOTCORR'].sum():.0f} mm.\n"
        f"Día de más lluvia: {dia_lluvia:%d/%m/%Y} ({df['PRECTOTCORR'].max():.1f} mm).\n"
        f"Día más caluroso: {dia_calor:%d/%m/%Y} ({df['T2M_MAX'].max():.1f} °C).\n\n"
        f"Datos mensuales (NASA POWER):\n{tabla}"
        f"{extra_texto}"
    )

    try:
        with st.spinner("Prometheus está leyendo los datos de la NASA..."):
            texto = explicacion(contexto)
        st.markdown(re.sub(r"\n(?!\n)", "\n\n", texto))
        st.caption("Informe redactado por Prometheus (IA con tecnología Gemini de Google) a partir de datos de NASA POWER. Es orientativo.")
    except Exception as e:
        st.warning(f"No se pudo generar la explicación en este momento: {e}")


## Mapa interactivo
def guardar_clic(estado):
    """Guarda el último clic del mapa con la longitud normalizada a [-180, 180]."""
    if estado and estado.get("last_clicked"):
        clic = estado["last_clicked"]
        lat = max(-90.0, min(90.0, clic["lat"]))
        lon = ((clic["lng"] + 180) % 360) - 180
        st.session_state["punto"] = (lat, lon)


if "punto" not in st.session_state:
    st.session_state["punto"] = None

filtro = st.segmented_control(
    "Filtros del mapa",
    ["Sin filtro", *CAPAS.keys(), *CAPAS_WMS.keys()],
    default="Sin filtro",
) or "Sin filtro"

fecha = None
capa_sel = CAPAS.get(filtro)
wms_sel = CAPAS_WMS.get(filtro)
if capa_sel:
    capa, matriz, formato, zoom_max = capa_sel
    auto = fecha_reciente(capa, matriz, formato)
    fecha = st.date_input(
        "Fecha de la capa (por defecto, la más reciente disponible)",
        auto,
        max_value=pd.Timestamp.today().normalize().date(),
    )
elif wms_sel:
    retraso = wms_sel[2]
    fecha = st.date_input(
        "Fecha de la capa",
        (pd.Timestamp.today().normalize() - pd.Timedelta(days=retraso)).date(),
        max_value=pd.Timestamp.today().normalize().date(),
    )

# El mapa se rehace (key nueva) cuando cambia el filtro o la fecha: así sigue recibiendo clics
firma = f"{filtro}|{fecha}"
KEY_MAPA = f"mapa|{firma}"

if st.session_state.get("firma") != firma:
    st.session_state["firma"] = firma
    p = st.session_state["punto"]
    st.session_state["vista_inicial"] = (
        {"centro": list(p), "zoom": 5} if p else {"centro": [20, 0], "zoom": 2}
    )

guardar_clic(st.session_state.get(KEY_MAPA))

vista = st.session_state["vista_inicial"]
m = folium.Map(
    location=vista["centro"],
    zoom_start=vista["zoom"],
    min_zoom=2,
    world_copy_jump=True,
    double_click_zoom=False,
)

cambiante = folium.FeatureGroup(name="dinamico")

# Capas de la NASA (mosaicos WMTS)
if capa_sel and fecha:
    folium.TileLayer(
        tiles=tile_url(capa, matriz, formato, fecha),
        attr="NASA GIBS",
        name=filtro,
        overlay=True,
        opacity=0.6,
        max_native_zoom=zoom_max,
    ).add_to(cambiante)
    st.caption(f"Mostrando {filtro} del {fecha:%d/%m/%Y}")

# Capas de la NASA (WMS: incendios y humedad del suelo SMAP)
if wms_sel and fecha:
    ident, fmt, _ = wms_sel
    folium.WmsTileLayer(
        url=WMS_URL,
        layers=ident,
        fmt=fmt,
        transparent=True,
        version="1.1.1",
        attr="NASA GIBS",
        name=filtro,
        overlay=True,
        opacity=0.8,
        time=f"{fecha:%Y-%m-%d}",
    ).add_to(cambiante)
    st.caption(f"Mostrando {filtro} del {fecha:%d/%m/%Y}")

if st.session_state["punto"]:
    folium.Marker(list(st.session_state["punto"]), tooltip="Parcela").add_to(cambiante)

mapa = st_folium(
    m,
    key=KEY_MAPA,
    feature_group_to_add=cambiante,
    height=550,
    use_container_width=True,
    returned_objects=["last_clicked"],
)

guardar_clic(mapa)

## Datos del punto elegido
punto = st.session_state["punto"]
if not punto:
    st.info("Haz clic en el mapa para ver el clima de tu parcela.")
    st.stop()

lat, lon = punto

tipo_punto = classify_point(lat, lon)
if tipo_punto == "ocean":
    st.warning("Ese punto está en el mar. Haz clic sobre tierra firme para analizar una parcela.")
    st.stop()
if tipo_punto == "uncertain":
    st.info("El punto está cerca de la costa: revisa que corresponda a tierra firme.")

fin = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
inicio = fin - pd.Timedelta(days=364)

try:
    with st.spinner("Descargando datos de NASA POWER..."):
        df = cargar_clima(lat, lon, inicio.strftime("%Y%m%d"), fin.strftime("%Y%m%d"))
except Exception as e:
    st.error(f"No se pudieron obtener los datos: {e}")
    st.stop()

# Indicadores ambientales y comparación con los 10 años anteriores
amb = indicadores(df)
extra = indicadores_extra(df)

try:
    inicio_h = fin - pd.DateOffset(years=10)
    df_hist = cargar_clima(lat, lon, inicio_h.strftime("%Y%m%d"), fin.strftime("%Y%m%d"))
    anom = anomalias_mensuales(df, df_hist)
except Exception:
    anom = None

extra_texto = "\n\nIndicadores calculados:\n" + "\n".join(
    f"{k}: {v:.1f}" for k, v in {**amb, **extra}.items()
)
if anom is not None and not anom.empty:
    extra_texto += (
        "\n\nComparación con el promedio de los 10 años anteriores (solo meses completos):\n"
        + anom.to_csv(float_format="%.1f")
    )

# Informe de Gemini
interpretar_clima(df, lat, lon, extra_texto)

st.divider()
st.write(f"Punto seleccionado: **{lat:.3f}, {lon:.3f}**")

## Métricas de lluvia y temperatura
c1, c2, c3 = st.columns(3)
c1.metric("Lluvia total", f"{df['PRECTOTCORR'].sum():.0f} mm")
c2.metric("Temp. media", f"{df['T2M'].mean():.1f} °C")
c3.metric("Temp. máx. media", f"{df['T2M_MAX'].mean():.1f} °C")

# Riesgos del punto (sin peticiones extra: usan el año que ya descargamos)
fila_pt = zone.resumen_celda(df)
fila_pt.update(lat=lat, lon=lon, paso=zone.PASO)
pt = risk.calcular(pd.DataFrame([fila_pt]))
mostrar = [
    (nombre.replace("Riesgo: ", ""), col)
    for nombre, (col, _) in risk.CAPAS_RIESGO.items()
    if col in pt.columns and pd.notna(pt[col].iloc[0])
]
if mostrar:
    st.subheader("Riesgos en tu punto (últimos 12 meses)")
    for col_st, (nombre, col) in zip(st.columns(len(mostrar)), mostrar):
        col_st.metric(nombre, f"{pt[col].iloc[0]:.0f}/100")

st.subheader("Ambiente (observaciones de la NASA)")
a1, a2, a3, a4 = st.columns(4)
a1.metric("Días de helada", amb["dias_helada"], help="Días con temperatura mínima ≤ 0 °C")
a2.metric("Días de calor extremo", amb["dias_calor_extremo"], help="Temperatura máxima ≥ 35 °C")
a3.metric("Racha seca más larga", f"{amb['racha_seca_dias']} días", help="Días seguidos con menos de 1 mm")
a4.metric("Días de lluvia intensa", amb["dias_lluvia_intensa"], help="20 mm o más en un solo día")

e1, e2, e3, e4 = st.columns(4)
e1.metric("Grados-día (base 10 °C)", f"{extra['gdd_base10']:.0f}")
e2.metric("Rango diario medio", f"{extra['rango_diurno']:.1f} °C")
e3.metric("Periodo sin heladas", f"{extra['periodo_sin_helada_dias']} días")
e4.metric("Lluvia en 3 meses", f"{extra['concentracion_lluvia']:.0f} %")

## Gráficas
st.caption("Temperatura diaria del último año (°C)")
st.line_chart(df[["T2M", "T2M_MAX"]])

vista_lluvia = st.radio("Ver lluvia por", ["Día", "Semana", "Mes"], index=1, horizontal=True)
reglas = {"Día": None, "Semana": "W", "Mes": "MS"}
lluvia = df["PRECTOTCORR"]
if reglas[vista_lluvia]:
    lluvia = lluvia.resample(reglas[vista_lluvia]).sum()

st.caption(f"Lluvia por {vista_lluvia.lower()} del último año (mm)")
st.bar_chart(lluvia)

if anom is not None and not anom.empty:
    st.caption("Lluvia del último año frente al promedio de los 10 años anteriores (%)")
    st.bar_chart(anom["lluvia_vs_normal_%"])

## Comparación de rotaciones
st.divider()
render_rotations(df, lat, lon)
