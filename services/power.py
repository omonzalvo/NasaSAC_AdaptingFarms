import numpy as np
import pandas as pd
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

def get_power_data(lat, lon, start_date, end_date):
    """start_date y end_date en formato 'AAAAMMDD' (texto)."""
    params = {
        "start": start_date,
        "end": end_date,
        "latitude": lat,
        "longitude": lon,
        "community": "AG",
        "parameters": "ALLSKY_SFC_SW_DWN,PRECTOTCORR,WS10M,WS50M,T2M,T2MDEW,T2MWET,T2M_MIN,T2M_MAX,ALLSKY_KT,ALLSKY_SFC_PAR_TOT",
        "format": "JSON",
    }
    response = requests.get(POWER_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.replace(-999, np.nan)
    return df