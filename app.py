import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.markdown("<h1 style='text-align: center;'>Adapting Farms 🌱</h1>", unsafe_allow_html=True)
st.caption("<p style='text-align: center;'>Nasa Space Apps Challenge 2026 - Team: Nova Aquila</p>", unsafe_allow_html=True)

m = folium.Map(location=[23.6, -102.5], zoom_start=5)
m.fit_bounds([[14.5, -118.5], [32.7, -86.5]])
st_folium(m, height=550, use_container_width=True)