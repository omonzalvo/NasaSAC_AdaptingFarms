# Umbrales: son decisiones del proyecto. Ajústalos y documéntalos.
TOPE_HELADA = 30          # días de helada al año = riesgo 100
TOPE_CALOR = 60           # días con máxima >= 35 °C = riesgo 100
TOPE_RACHA_SECA = 120     # días secos seguidos = riesgo 100
HUMEDAD_REF = 0.6         # humedad de raíces (0 a 1) sin estrés
TOPE_FUEGO_COND = 60      # días de aire seco + calor + viento = riesgo 100

# nombre: (columna calculada, descripción)
CAPAS_RIESGO = {
    "Riesgo: heladas": ("helada", "días con temperatura mínima ≤ 0 °C"),
    "Riesgo: calor": ("calor", "días con temperatura máxima ≥ 35 °C"),
    "Riesgo: estrés hídrico": ("hidrico", "sequías largas y poca humedad en la zona de raíces"),
    "Riesgo: incendios (condiciones)": ("fuego_condiciones", "días de aire seco, calor y viento"),
}


def _t(x, tope):
    """Normaliza a 0-1 dividiendo entre un tope. Los NaN se quedan como NaN."""
    return (x / tope).clip(0, 1)


def calcular(df):
    """Agrega las columnas de riesgo (0 a 100) a la tabla de celdas."""
    d = df.copy()
    d["helada"] = 100 * _t(d["dias_helada"], TOPE_HELADA)
    d["calor"] = 100 * _t(d["dias_calor"], TOPE_CALOR)

    racha = _t(d["racha_seca"], TOPE_RACHA_SECA)
    if "humedad_raiz" in d and d["humedad_raiz"].notna().any():
        d["hidrico"] = 100 * (0.5 * racha + 0.5 * (1 - _t(d["humedad_raiz"], HUMEDAD_REF)))
    else:
        d["hidrico"] = 100 * racha

    if "dias_fuego_cond" in d:
        d["fuego_condiciones"] = 100 * _t(d["dias_fuego_cond"], TOPE_FUEGO_COND)

    return d
