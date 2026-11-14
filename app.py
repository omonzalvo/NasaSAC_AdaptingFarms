import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from services.power import get_power_data

st.set_page_config(page_title="Adapting Farms", page_icon="🌱", layout="wide")

st.markdown("<h1 style='text-align: center;'>Adapting Farms 🌱</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: gray;'>NASA Space Apps Challenge 2026 - Team: Nova Aquila</p>",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def cargar_clima(lat, lon, inicio, fin):
    return get_power_data(lat, lon, inicio, fin)


# Memoria del punto elegido
if "punto" not in st.session_state:
    st.session_state["punto"] = None

m = folium.Map(location=[23.6, -102.5], zoom_start=5)
m.fit_bounds([[14.5, -118.5], [32.7, -86.5]])

# Marcador si ya hay un punto guardado
if st.session_state["punto"]:
    folium.Marker(list(st.session_state["punto"]), tooltip="Parcela").add_to(m)

# Guarda lo que devuelve el mapa
mapa = st_folium(m, height=550, use_container_width=True)

# Si hubo clic, lo guarda
if mapa and mapa.get("last_clicked"):
    st.session_state["punto"] = (
        mapa["last_clicked"]["lat"],
        mapa["last_clicked"]["lng"],
    )

# Si todavía no hay punto, avisa y detiene el resto
punto = st.session_state["punto"]
if not punto:
    st.info("Haz clic en el mapa para ver el clima de tu parcela.")
    st.stop()

lat, lon = punto
st.write(f"Punto seleccionado: **{lat:.3f}, {lon:.3f}**")

# Último año disponible (POWER tiene unos días de retraso)
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

st.line_chart(df[["T2M", "T2M_MAX"]])
st.bar_chart(df["PRECTOTCORR"])