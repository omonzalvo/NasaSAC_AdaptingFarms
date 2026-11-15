import requests
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from services.power import get_power_data
from services.gibs import CAPAS, tile_url, ultima_fecha_disponible

st.set_page_config(page_title="Adapting Farms", page_icon="🌱", layout="wide")

st.markdown("<h1 style='text-align: center;'>Adapting Farms</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: gray;'>NASA Space Apps Challenge 2026 - Team: Nova Aquila</p>",
    unsafe_allow_html=True,
)

@st.cache_data(ttl=1800)
def fecha_reciente(capa, matriz, formato):
    return ultima_fecha_disponible(capa, matriz, formato)


@st.cache_data(ttl=3600)
def cargar_clima(lat, lon, inicio, fin):
    return get_power_data(lat, lon, inicio, fin)


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
    auto = ultima_fecha_disponible(capa, matriz, formato)
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

mapa = st_folium(
    m,
    key=KEY_MAPA,
    feature_group_to_add=cambiante,
    height=550,
    use_container_width=True,
    returned_objects=["last_clicked"],
)

guardar_clic(mapa)

## Now

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