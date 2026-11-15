"""Indicadores ambientales calculados a partir de los datos diarios de NASA POWER.

Todo lo que muestra la app (métricas, tabla mensual, anomalías) y lo que se le
envía a Prometheus sale de estas funciones. Las cuentas se hacen aquí, en código,
para que la IA solo interprete números ya calculados y no invente cifras.
"""
import numpy as np
import pandas as pd


def serie(df, name):
    """Columna numérica limpia; los valores faltantes de la NASA (-999) quedan como NaN."""
    s = pd.to_numeric(df.get(name, pd.Series(index=df.index, dtype=float)), errors="coerce")
    return s.replace([np.inf, -np.inf, -999], np.nan)


def indicadores(df):
    """Indicadores ambientales a partir de los datos diarios de NASA POWER."""
    d = {}
    d["lluvia_total_mm"] = float(df["PRECTOTCORR"].sum())
    d["dias_lluvia_intensa"] = int((df["PRECTOTCORR"] >= 20).sum())
    d["dias_helada"] = int((df["T2M_MIN"] <= 0).sum())
    d["dias_calor_extremo"] = int((df["T2M_MAX"] >= 35).sum())

    seco = (df["PRECTOTCORR"] < 1).astype(int)
    d["racha_seca_dias"] = int(seco.groupby((seco == 0).cumsum()).cumsum().max())

    if "GWETTOP" in df:
        d["humedad_superficie"] = float(df["GWETTOP"].mean())
    if "GWETROOT" in df:
        d["humedad_raiz"] = float(df["GWETROOT"].mean())
    if "EVLAND" in df:
        d["evaporacion_mm"] = float(df["EVLAND"].sum())
        d["balance_hidrico_mm"] = d["lluvia_total_mm"] - d["evaporacion_mm"]
    return d

def tabla_mensual(df):
    """Tabla mensual con todas las variables disponibles (para gráficas y para Gemini)."""
    agg = {"PRECTOTCORR": "sum", "T2M": "mean", "T2M_MAX": "mean", "T2M_MIN": "mean"}
    nombres = {
        "PRECTOTCORR": "lluvia_mm",
        "T2M": "temp_media_C",
        "T2M_MAX": "temp_max_media_C",
        "T2M_MIN": "temp_min_media_C",
    }
    opcionales = [
        ("GWETTOP", "humedad_superficie_0a1", "mean"),
        ("GWETROOT", "humedad_raiz_0a1", "mean"),
        ("EVLAND", "evaporacion_mm", "sum"),
        ("ALLSKY_SFC_SW_DWN", "radiacion_kWh_m2_dia", "mean"),
        ("WS10M", "viento_m_s", "mean"),
    ]
    for col, nombre, como in opcionales:
        if col in df:
            agg[col] = como
            nombres[col] = nombre

    m = df.resample("MS").agg(agg).rename(columns=nombres)
    m["dias_helada"] = (df["T2M_MIN"] <= 0).resample("MS").sum()
    if "evaporacion_mm" in m:
        m["balance_hidrico_mm"] = m["lluvia_mm"] - m["evaporacion_mm"]
        m["dias_con_datos"] = df["PRECTOTCORR"].resample("MS").count()
    return m

def indicadores_extra(df):
    """Lecturas adicionales del clima a partir de los datos diarios."""
    d = {}
    gdd = ((df["T2M_MAX"] + df["T2M_MIN"]) / 2 - 10.0).clip(lower=0)
    d["gdd_base10"] = float(gdd.sum())
    d["rango_diurno"] = float((df["T2M_MAX"] - df["T2M_MIN"]).mean())

    libre = (df["T2M_MIN"] > 0).astype(int)
    d["periodo_sin_helada_dias"] = int(libre.groupby((libre == 0).cumsum()).cumsum().max())

    mensual = df["PRECTOTCORR"].resample("MS").sum()
    total = mensual.sum()
    d["concentracion_lluvia"] = float(mensual.nlargest(3).sum() / total * 100) if total > 0 else 0.0
    return d


def anomalias_mensuales(df_anio, df_hist):
    """Compara cada mes completo del último año con el promedio histórico del mismo mes."""
    hist = df_hist[df_hist.index < df_anio.index.min()]   # excluye el año analizado

    dias = df_anio["PRECTOTCORR"].resample("MS").count()
    completos = dias[dias == dias.index.days_in_month].index

    act = df_anio.resample("MS").agg({"PRECTOTCORR": "sum", "T2M": "mean"}).loc[completos]
    hist_m = hist.resample("MS").agg({"PRECTOTCORR": "sum", "T2M": "mean"})
    normal = hist_m.groupby(hist_m.index.month).mean()

    out = pd.DataFrame(index=act.index)
    out["lluvia_mm"] = act["PRECTOTCORR"]
    out["lluvia_normal_mm"] = [normal.loc[m, "PRECTOTCORR"] for m in act.index.month]
    base = out["lluvia_normal_mm"].where(out["lluvia_normal_mm"] > 0)
    out["lluvia_vs_normal_%"] = (out["lluvia_mm"] / base - 1) * 100
    out["temp_vs_normal_C"] = act["T2M"].values - [normal.loc[m, "T2M"] for m in act.index.month]
    return out
