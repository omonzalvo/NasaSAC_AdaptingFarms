import folium
import pandas as pd

# Umbrales: son decisiones del proyecto. Ajústalos y documéntalos.
TOPE_HELADA = 30          # días de helada al año = riesgo 100
TOPE_CALOR = 60           # días con máxima >= 35 °C = riesgo 100
TOPE_RACHA_SECA = 120     # días secos seguidos = riesgo 100
HUMEDAD_REF = 0.6         # humedad de raíces (0 a 1) sin estrés
TOPE_PENDIENTE = 40       # % del terreno con pendiente > 10° = riesgo 100
TOPE_LLUVIA_INTENSA = 8   # días con >= 20 mm = riesgo 100
TOPE_FUEGO_COND = 60      # días de aire seco + calor + viento = riesgo 100
TOPE_INCENDIOS = 20       # detecciones al año en la celda = riesgo 100

# nombre del botón: (columna calculada, descripción para la leyenda)
CAPAS_RIESGO = {
    "Riesgo: heladas": ("helada", "días con temperatura mínima ≤ 0 °C"),
    "Riesgo: calor": ("calor", "días con temperatura máxima ≥ 35 °C"),
    "Riesgo: estrés hídrico": ("hidrico", "sequías largas y poca humedad en la zona de raíces"),
    "Riesgo: erosión": ("erosion", "pendientes fuertes con lluvias intensas (potencial, sin datos de suelo)"),
    "Riesgo: incendios (condiciones)": ("fuego_condiciones", "días de aire seco, calor y viento"),
    "Riesgo: incendios (historial)": ("fuego_historial", "detecciones satelitales de incendio en el periodo elegido"),
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

    if "pct_pend_10" in d:
        d["erosion"] = 100 * (
            0.6 * _t(d["pct_pend_10"], TOPE_PENDIENTE)
            + 0.4 * _t(d["dias_lluvia_intensa"], TOPE_LLUVIA_INTENSA)
        )

    if "dias_fuego_cond" in d:
        d["fuego_condiciones"] = 100 * _t(d["dias_fuego_cond"], TOPE_FUEGO_COND)

    if "incendios_ventana" in d:
        ventana = float(d["ventana_dias"].iloc[0]) if "ventana_dias" in d else 365.0
        tope = max(3.0, TOPE_INCENDIOS * ventana / 365)   # el tope se ajusta al periodo
        d["fuego_historial"] = 100 * _t(d["incendios_ventana"], tope)

    return d


def _color(p):
    if pd.isna(p):
        return "#999999"        # gris: sin dato (no es "riesgo cero")
    return "#2ecc71" if p < 34 else ("#f1c40f" if p < 67 else "#e74c3c")


def dibujar(df, columna, grupo):
    """Dibuja un rectángulo de color por celda dentro de un FeatureGroup de folium."""
    for _, f in df.iterrows():
        m = f["paso"] / 2
        folium.Rectangle(
            bounds=[[f["lat"] - m, f["lon"] - m], [f["lat"] + m, f["lon"] + m]],
            color=_color(f[columna]),
            weight=1,
            fill=True,
            fill_opacity=0.55,
            interactive=False,   # los clics pasan al mapa y siguen eligiendo el punto
        ).add_to(grupo)