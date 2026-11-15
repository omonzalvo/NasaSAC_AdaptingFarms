import requests
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from services.power import get_power_data
from services.gibs import CAPAS, tile_url, ultima_fecha_disponible
from services.llm import explicar
from services.ambience import indicadores, tabla_mensual, indicadores_extra, anomalias_mensuales

##Headers y configuración de la página
st.set_page_config(page_title="Adapting Farms", page_icon="🌱", layout="wide")

st.markdown("<h1 style='text-align: center;'>Adapting Farms</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: gray;'>NASA Space Apps Challenge 2026 - Team: Nova Aquila</p>",
    unsafe_allow_html=True,
)

##Cargando el LLM y la cache de datos
@st.cache_data(ttl=3600)
def explicacion(contexto):
    return explicar(contexto)
##Cargando datos de NASA POWER y cacheando
@st.cache_data(ttl=1800)
def fecha_reciente(capa, matriz, formato):
    return ultima_fecha_disponible(capa, matriz, formato)
##Intetractuando con el LLM
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
def interpretar_clima(df, lat, lon, extra_texto=""):
    st.subheader("Agente de interpretación del clima")

    mensual = tabla_mensual(df)
    mensual.index = [f"{MESES[i.month-1]} {i.year}" for i in mensual.index]
    tabla = mensual.to_csv(float_format="%.2f", index_label="Mes")
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
        st.write(texto)
        st.caption("Informe redactado por IA a partir de datos de NASA POWER. Es orientativo.")
    except Exception as e:
        st.warning(f"No se pudo generar la explicación en este momento: {e}")

##Cargando datos de NASA POWER y cacheando
@st.cache_data(ttl=3600)
def cargar_clima(lat, lon, inicio, fin):
    return get_power_data(lat, lon, inicio, fin)

###Mapa interactivo con folium
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
    ["Sin filtro", *CAPAS.keys()],
    default="Sin filtro",
) or "Sin filtro"

fecha = None
capa_sel = CAPAS.get(filtro)
if capa_sel:
    capa, matriz, formato, zoom_max = capa_sel
    auto = fecha_reciente(capa, matriz, formato)
    fecha = st.date_input(
        "Fecha de la capa (por defecto, la más reciente disponible)",
        auto,
        max_value=pd.Timestamp.today().normalize().date(),
    )

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

if capa_sel and fecha:
    url = (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        f"{capa}/default/{fecha:%Y-%m-%d}/{matriz}/{{z}}/{{y}}/{{x}}.{formato}"
    )
    folium.TileLayer(
        tiles=url,
        attr="NASA GIBS",
        name=filtro,
        overlay=True,
        opacity=0.6,
        max_native_zoom=zoom_max,
    ).add_to(cambiante)
    st.caption(f"Mostrando {filtro} del {fecha:%d/%m/%Y}")

if st.session_state["punto"]:
    folium.Marker(list(st.session_state["punto"]), tooltip="Parcela").add_to(cambiante)

##Definiendo el Mapa
mapa = st_folium(
    m,
    key=KEY_MAPA,
    feature_group_to_add=cambiante,
    height=550,
    use_container_width=True,
    returned_objects=["last_clicked"],
)

guardar_clic(mapa)

##Fetch de Datos de NASA POWER
punto = st.session_state["punto"]
if not punto:
    st.info("Haz clic en el mapa para ver el clima de tu parcela.")
    st.stop()

lat, lon = punto
st.write(f"Punto seleccionado: **{lat:.3f}, {lon:.3f}**")

fin = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
inicio = fin - pd.Timedelta(days=364)

try:
    with st.spinner("Descargando datos de NASA POWER..."):
        df = cargar_clima(lat, lon, inicio.strftime("%Y%m%d"), fin.strftime("%Y%m%d"))
except Exception as e:
    st.error(f"No se pudieron obtener los datos: {e}")
    st.stop()

#Agente de LLM
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

# Agente de IA
interpretar_clima(df, lat, lon, extra_texto)

##Tabla de lluvia y temperatura
c1, c2, c3 = st.columns(3)
c1.metric("Lluvia total", f"{df['PRECTOTCORR'].sum():.0f} mm")
c2.metric("Temp. media", f"{df['T2M'].mean():.1f} °C")
c3.metric("Temp. máx. media", f"{df['T2M_MAX'].mean():.1f} °C")
st.caption("Temperatura diaria del último año (°C)")
st.line_chart(df[["T2M", "T2M_MAX"]])

vista_lluvia = st.radio("Ver lluvia por", ["Día", "Semana", "Mes"], index=1, horizontal=True)
reglas = {"Día": None, "Semana": "W", "Mes": "MS"}
lluvia = df["PRECTOTCORR"]
if reglas[vista_lluvia]:
    lluvia = lluvia.resample(reglas[vista_lluvia]).sum()

st.caption(f"Lluvia por {vista_lluvia.lower()} del último año (mm)")
st.bar_chart(lluvia)
