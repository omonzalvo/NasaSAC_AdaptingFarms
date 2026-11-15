"""Deterministic indicators; no model calls or agronomic predictions."""
import hashlib
import json
import math

import pandas as pd

VARIABLES = {
    "PRECTOTCORR": ("Precipitación acumulada en días disponibles", "mm", "sum"),
    "T2M": ("Temperatura media de días disponibles", "°C", "mean"),
    "T2M_MAX": ("Media de temperaturas máximas diarias disponibles", "°C", "mean"),
    "ALLSKY_SFC_SW_DWN": ("Radiación solar diaria media disponible", "MJ/m²/day", "mean"),
    "WS10M": ("Velocidad media del viento a diez metros", "m/s", "mean"),
    "WS50M": ("Velocidad media del viento a cincuenta metros", "m/s", "mean"),
    "T2MDEW": ("Temperatura media del punto de rocío", "°C", "mean"),
    "T2MWET": ("Temperatura media de bulbo húmedo", "°C", "mean"),
    "ALLSKY_KT": ("Índice medio de claridad", "adimensional", "mean"),
    "ALLSKY_SFC_PAR_TOT": ("Radiación fotosintéticamente activa diaria media", "MJ/m²/day", "mean"),
    "T2M_MIN": ("Media de temperaturas mínimas diarias disponibles", "°C", "mean"),
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def summarize_climate(df, lat, lon, start, end):
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end < start or (end - start).days > 3660:
        raise ValueError("El período debe estar ordenado y no superar diez años.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fuera de rango.")
    days = pd.date_range(start, end)
    frame = df.copy()
    frame.index = pd.to_datetime(frame.index).normalize()
    if frame.index.has_duplicates:
        raise ValueError("La fuente contiene fechas duplicadas.")
    frame = frame.reindex(days)
    facts = []
    monthly = []
    for variable, (label, unit, operation) in VARIABLES.items():
        values = pd.to_numeric(frame.get(variable, pd.Series(index=days, dtype=float)), errors="coerce")
        values = values.where(values.map(lambda v: pd.notna(v) and math.isfinite(v) and v != -999))
        if variable == "PRECTOTCORR":
            values = values.where(values >= 0)
        count = int(values.count())
        number = (values.sum(min_count=1) if operation == "sum" else values.mean())
        facts.append({"id": variable, "label": label, "value": None if pd.isna(number) else round(float(number), 2),
                      "unit": unit, "valid_days": count, "expected_days": len(days),
                      "coverage_pct": round(count / len(days) * 100, 1)})
        for month, group in values.groupby(values.index.to_period("M")):
            number = group.sum(min_count=1) if operation == "sum" else group.mean()
            monthly.append({"id": f"{variable}:{month}", "variable": variable, "month": str(month),
                            "value": None if pd.isna(number) else round(float(number), 2),
                            "unit": unit, "valid_days": int(group.count()), "expected_days": len(group)})
    return {"source": "NASA POWER Daily API", "source_url": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
            "latitude": lat, "longitude": lon, "start": str(start.date()), "end": str(end.date()),
            "time_standard": "LST", "facts": facts, "monthly": monthly,
            "source_metadata": df.attrs.get("source_metadata", {}),
            "limits": ["Datos históricos regionales; no medición exacta de la parcela.",
                       "Un solo período no demuestra una tendencia climática ni predice la próxima cosecha.",
                       "Acumulados parciales no equivalen a totales del período completo.",
                       "No hay catálogo agronómico validado conectado: no se recomiendan rotaciones específicas."]}
