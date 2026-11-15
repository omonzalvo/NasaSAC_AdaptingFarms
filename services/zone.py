"""Resumen de un año de datos en los indicadores que usa services.risk."""
PASO = 0.5


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
