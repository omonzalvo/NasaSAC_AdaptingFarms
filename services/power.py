"""Descarga de datos diarios de NASA POWER para un punto.

POWER combina observaciones satelitales y modelos (reanálisis) en una malla de
unos 50 km. Es la fuente de todos los cálculos de la app.

Variables que se piden (comunidad AG, agricultura):
    PRECTOTCORR  lluvia corregida (mm/día)
    T2M, T2M_MIN, T2M_MAX  temperatura media, mínima y máxima a 2 m (°C)
    T2MDEW, T2MWET  punto de rocío y bulbo húmedo (°C)
    RH2M  humedad relativa a 2 m (%)
    WS10M, WS50M  viento a 10 y 50 m (m/s)
    ALLSKY_SFC_SW_DWN, ALLSKY_SFC_PAR_TOT, ALLSKY_KT  radiación solar
    GWETTOP, GWETROOT, GWETPROF  humedad del suelo (0 a 1) en superficie, raíces y perfil
    EVLAND  evaporación desde el suelo (mm/día)
"""
import numpy as np
import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETROS = [
    "ALLSKY_SFC_SW_DWN", "PRECTOTCORR", "WS10M", "WS50M",
    "T2M", "T2MDEW", "T2MWET", "T2M_MIN", "T2M_MAX",
    "ALLSKY_KT", "ALLSKY_SFC_PAR_TOT",
    "GWETTOP", "GWETROOT", "GWETPROF", "EVLAND", "RH2M",
]

def get_power_data(lat, lon, start_date, end_date):
    """start_date y end_date en formato 'AAAAMMDD' (texto)."""
    params = {
        "start": start_date,
        "end": end_date,
        "latitude": lat,
        "longitude": lon,
        "community": "AG",
        "parameters": ",".join(dict.fromkeys(PARAMETROS)),
        "format": "JSON",
    }
    response = requests.get(POWER_URL, params=params, timeout=60)
    response.raise_for_status()
    if response.status_code != 200:
        raise RuntimeError(f"POWER respondió {response.status_code}: {response.text[:300]}")
    data = response.json()
    df = pd.DataFrame(data["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.replace(-999, np.nan)
    return df