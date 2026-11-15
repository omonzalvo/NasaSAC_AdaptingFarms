import pandas as pd
import requests

GIBS_URL = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
WMS_URL = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi"

# Capas de mosaicos (WMTS)
# nombre: (identificador de capa, matriz de zoom, formato, zoom máximo nativo)
CAPAS = {
    "Calor": ("MODIS_Terra_Land_Surface_Temp_Day", "GoogleMapsCompatible_Level7", "png", 7),
    "Lluvia": ("IMERG_Precipitation_Rate", "GoogleMapsCompatible_Level6", "png", 6),
    "Vegetación": ("MODIS_Terra_NDVI_8Day", "GoogleMapsCompatible_Level9", "png", 9),
}

# Capas WMS (incendios, humedad del suelo SMAP)
# nombre: (identificador, formato, días de retraso típico para la fecha por defecto)
CAPAS_WMS = {
    "Incendios": ("VIIRS_NOAA20_Thermal_Anomalies_375m_All", "image/png", 1),
}


def tile_url(capa, matriz, formato, fecha):
    """URL de los mosaicos para folium.TileLayer."""
    return f"{GIBS_URL}/{capa}/default/{fecha:%Y-%m-%d}/{matriz}/{{z}}/{{y}}/{{x}}.{formato}"


def ultima_fecha_disponible(capa, matriz, formato, max_dias=20):
    """Busca hacia atrás la fecha más reciente con imagen disponible."""
    hoy = pd.Timestamp.today().normalize()
    for i in range(max_dias):
        f = hoy - pd.Timedelta(days=i)
        url = f"{GIBS_URL}/{capa}/default/{f:%Y-%m-%d}/{matriz}/3/3/1.{formato}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and len(r.content) > 1500:
                return f.date()
        except requests.RequestException:
            pass
    return (hoy - pd.Timedelta(days=5)).date()