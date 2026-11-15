import concurrent.futures as cf
import io
import math
import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from services.power import get_power_data

PASO = 0.5
DATA = Path("data")

COLUMNAS_CLIMA = [
    "lat", "lon", "paso", "lluvia_mm", "dias_lluvia_intensa", "racha_seca",
    "dias_helada", "dias_calor", "humedad_raiz", "dias_fuego_cond", "error",
]


def centro_celda(lat, lon, paso=PASO):
    return round(round(lat / paso) * paso, 4), round(round(lon / paso) * paso, 4)


def celdas_alrededor(lat, lon, n=1, paso=PASO):
    """Celdas (2n+1)x(2n+1) centradas en la celda que contiene el punto."""
    lc, oc = centro_celda(lat, lon, paso)
    filas = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            la, lo = round(lc + i * paso, 4), round(oc + j * paso, 4)
            if abs(la) <= 90 and abs(lo) <= 180:
                filas.append((la, lo))
    df = pd.DataFrame(filas, columns=["lat", "lon"])
    df["paso"] = paso
    return df


def resumen_celda(df):
    """Indicadores de un año de datos diarios de POWER."""
    seco = (df["PRECTOTCORR"] < 1).astype(int)
    fila = {
        "lluvia_mm": float(df["PRECTOTCORR"].sum()),
        "dias_lluvia_intensa": int((df["PRECTOTCORR"] >= 20).sum()),
        "racha_seca": int(seco.groupby((seco == 0).cumsum()).cumsum().max()),
        "dias_helada": int((df["T2M_MIN"] <= 0).sum()),
        "dias_calor": int((df["T2M_MAX"] >= 35).sum()),
    }
    if "GWETROOT" in df:
        fila["humedad_raiz"] = float(df["GWETROOT"].mean())
    if "RH2M" in df and "WS10M" in df:
        # Índice propio y simple: aire seco + calor + viento
        fila["dias_fuego_cond"] = int(
            ((df["RH2M"] < 30) & (df["T2M_MAX"] >= 30) & (df["WS10M"] >= 5)).sum()
        )
    return fila


def _una_celda(lat, lon, ini, fin):
    try:
        fila = resumen_celda(get_power_data(lat, lon, ini, fin))
    except Exception as e:
        return {"lat": lat, "lon": lon, "error": str(e)[:200]}
    fila.update(lat=lat, lon=lon)
    return fila


def clima_zona(celdas, hilos=4):
    fin = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
    ini = fin - pd.Timedelta(days=364)
    a, b = ini.strftime("%Y%m%d"), fin.strftime("%Y%m%d")
    with cf.ThreadPoolExecutor(hilos) as ex:
        filas = list(ex.map(lambda c: _una_celda(c[0], c[1], a, b), zip(celdas["lat"], celdas["lon"])))
    out = pd.DataFrame(filas)
    out["paso"] = float(celdas["paso"].iloc[0])
    return out.reindex(columns=COLUMNAS_CLIMA)


def pendiente_zona(celdas):
    """Pendiente media y % de terreno con más de 10° a partir de SRTM (3 segundos de arco)."""
    import earthaccess

    paso = float(celdas["paso"].iloc[0])
    w, s = celdas["lon"].min() - paso / 2, celdas["lat"].min() - paso / 2
    e, n = celdas["lon"].max() + paso / 2, celdas["lat"].max() + paso / 2

    earthaccess.login(strategy="environment")   # usa EARTHDATA_USERNAME y EARTHDATA_PASSWORD
    res = earthaccess.search_data(short_name="SRTMGL3", version="003", bounding_box=(w, s, e, n))
    if not res:
        raise RuntimeError("No hay datos SRTM para esta zona (cubren de 56° S a 60° N)")

    carpeta = DATA / "srtm"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = [str(f) for f in earthaccess.download(res, str(carpeta))]

    lat0, lat1 = math.floor(s), math.ceil(n)
    lon0, lon1 = math.floor(w), math.ceil(e)
    N = 1200  # píxeles por grado
    mosaico = np.full(((lat1 - lat0) * N, (lon1 - lon0) * N), np.nan, dtype=np.float32)

    for f in archivos:
        if not f.lower().endswith(".hgt.zip"):
            continue
        m = re.search(r"([NS])(\d{2})([EW])(\d{3})", Path(f).name)
        la = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
        lo = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
        with zipfile.ZipFile(f) as z:
            nombre = [x for x in z.namelist() if x.lower().endswith(".hgt")][0]
            t = np.frombuffer(z.read(nombre), dtype=">i2").reshape(1201, 1201).astype(np.float32)
        t[t == -32768] = np.nan
        r, c = (lat1 - (la + 1)) * N, (lo - lon0) * N
        if r < 0 or c < 0 or r + N > mosaico.shape[0] or c + N > mosaico.shape[1]:
            continue
        mosaico[r:r + N, c:c + N] = t[:N, :N]

    dy = 92.6  # metros por 3 segundos de arco
    filas = []
    for c in celdas.itertuples():
        top = c.lat + paso / 2
        r0, r1 = int(round((lat1 - top) * N)), int(round((lat1 - (c.lat - paso / 2)) * N))
        c0, c1 = int(round((c.lon - paso / 2 - lon0) * N)), int(round((c.lon + paso / 2 - lon0) * N))
        z = mosaico[max(r0, 0):r1, max(c0, 0):c1]
        if z.size == 0 or np.all(np.isnan(z)):
            continue
        lat_fila = top - (np.arange(z.shape[0]) + 0.5) / N
        dx = dy * np.cos(np.radians(lat_fila))[:, None]
        dzdy = np.gradient(z, dy, axis=0)
        dzdx = np.gradient(z, axis=1) / dx
        pend = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
        v = pend[~np.isnan(pend)]
        if v.size == 0:
            continue
        filas.append(
            {
                "lat": c.lat,
                "lon": c.lon,
                "elev_media": float(np.nanmean(z)),
                "pend_media": float(v.mean()),
                "pct_pend_10": float((v > 10).mean() * 100),
            }
        )
    return pd.DataFrame(filas, columns=["lat", "lon", "elev_media", "pend_media", "pct_pend_10"])


def incendios_zona(celdas, dias=90):
    """Cuenta detecciones de incendio de FIRMS por celda. Devuelve (tabla, ventanas_fallidas, total)."""
    llave = os.getenv("FIRMS_MAP_KEY")
    if not llave:
        raise RuntimeError("Falta FIRMS_MAP_KEY en el archivo .env")

    paso = float(celdas["paso"].iloc[0])
    lat_min, lon_min = celdas["lat"].min(), celdas["lon"].min()
    w, s = lon_min - paso / 2, lat_min - paso / 2
    e, n = celdas["lon"].max() + paso / 2, celdas["lat"].max() + paso / 2

    hoy = pd.Timestamp.today().normalize()
    inicio = hoy - pd.Timedelta(days=dias - 1)
    ventanas = [inicio + pd.Timedelta(days=5 * k) for k in range(math.ceil(dias / 5))]

    def pedir(dia):
        for fuente in ("VIIRS_NOAA20_NRT", "VIIRS_NOAA20_SP"):
            url = (
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{llave}/{fuente}/"
                f"{w},{s},{e},{n}/5/{dia:%Y-%m-%d}"
            )
            try:
                r = requests.get(url, timeout=120)
            except requests.RequestException:
                continue
            if r.ok and r.text.startswith("latitude"):
                return pd.read_csv(io.StringIO(r.text))
        return None

    with cf.ThreadPoolExecutor(6) as ex:
        partes = list(ex.map(pedir, ventanas))
    falladas = sum(p is None for p in partes)
    ok = [p for p in partes if p is not None]
    if not ok:
        raise RuntimeError("FIRMS no devolvió datos (revisa FIRMS_MAP_KEY)")

    df = pd.concat(ok, ignore_index=True)
    if "confidence" in df:
        df = df[~df["confidence"].astype(str).str.lower().isin(["l", "low"])]

    c = celdas[["lat", "lon"]].copy()
    if df.empty:
        return c.assign(incendios_ventana=0), falladas, len(ventanas)

    c["iy"] = np.round((c["lat"] - lat_min) / paso).astype(int)
    c["ix"] = np.round((c["lon"] - lon_min) / paso).astype(int)
    iy = np.floor((df["latitude"] - (lat_min - paso / 2)) / paso).astype(int)
    ix = np.floor((df["longitude"] - (lon_min - paso / 2)) / paso).astype(int)
    cuenta = pd.DataFrame({"iy": iy, "ix": ix}).value_counts().rename("incendios_ventana").reset_index()
    out = c.merge(cuenta, on=["iy", "ix"], how="left").fillna({"incendios_ventana": 0})
    return out[["lat", "lon", "incendios_ventana"]], falladas, len(ventanas)