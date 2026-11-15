"""Detecta si un punto está en tierra o en el mar, sin internet.

Usa el contorno de continentes de Natural Earth (escala 1:110 millones) guardado en
data/ne_110m_land.geojson. Es una revisión gruesa: no conoce límites de parcelas ni
distingue tierra agrícola de ciudades o desiertos.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
from shapely.geometry import Point, shape
from shapely.ops import unary_union

@lru_cache(maxsize=1)
def _land():
    """Carga el contorno de tierra una sola vez y lo guarda en memoria."""
    data=json.loads((Path(__file__).resolve().parents[1]/'data/ne_110m_land.geojson').read_text())
    return unary_union([shape(f['geometry']) for f in data['features']])

def classify_point(lat,lon):
    """Devuelve 'land', 'ocean' o 'uncertain' para una coordenada.

    'uncertain' significa que el punto está a menos de 0.15° (unos 15 km) de la
    costa, donde el contorno es demasiado grueso para decidir.
    """
    if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
        raise ValueError('Coordenadas fuera de rango.')
    p=Point(lon,lat); land=_land()
    if land.boundary.distance(p)<0.15:
        return 'uncertain'
    return 'land' if land.covers(p) else 'ocean'
