"""Contract for the host application’s NASA POWER DataFrame; calculations precede the LLM."""
import json
import pandas as pd
from .climate import summarize_climate, fingerprint, VARIABLES
from .gemini import analyze, DEFAULT_MODEL, AnalysisError

PROFILE_FIELDS = ('crop', 'history', 'water', 'soil', 'goal', 'planting_window')

def prepare_analysis(df, *, latitude, longitude, start, end, profile=None):
    """No network. Dates must be the REQUESTED interval, not observed min/max.

    Input: daily POWER values with original units and -999/NaN for missing.
    Index: dates (DatetimeIndex, YYYY-MM-DD or POWER YYYYMMDD strings).
    Output: JSON-serializable evidence, quality warnings and stable request_id.
    Unknown columns are explicitly reported, never treated as measurements.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError('Entrega una tabla diaria no vacía de NASA POWER.')
    if df.columns.has_duplicates:
        raise ValueError('La tabla tiene columnas duplicadas.')
    frame = df.copy(deep=True)
    if isinstance(frame.index, pd.RangeIndex) or pd.api.types.is_numeric_dtype(frame.index.dtype):
        raise ValueError('El índice debe contener fechas, no números de fila.')
    frame.index = pd.to_datetime(frame.index, errors='raise')
    if frame.index.tz is not None:
        raise ValueError('Se esperan fechas diarias sin zona horaria; no convertir UTC/LST automáticamente.')
    if frame.index.hasnans or (frame.index != frame.index.normalize()).any():
        raise ValueError('Se esperan fechas diarias válidas a medianoche, no datos horarios.')
    if not any(c in VARIABLES for c in frame.columns):
        raise ValueError('No hay variables NASA POWER compatibles en la tabla.')
    profile = {} if profile is None else profile
    if not isinstance(profile, dict) or set(profile) - set(PROFILE_FIELDS):
        raise ValueError('Perfil inválido. Campos: ' + ', '.join(PROFILE_FIELDS))
    cleaned = {}
    for k, v in profile.items():
        if not isinstance(v, str) or len(v) > 1000:
            raise ValueError('Cada campo del perfil debe ser texto de hasta 1000 caracteres.')
        cleaned[k] = v.strip()
    expected_units = {
        'PRECTOTCORR': {'mm/day'}, 'T2M': {'C'}, 'T2M_MIN': {'C'}, 'T2M_MAX': {'C'},
        'T2MDEW': {'C'}, 'T2MWET': {'C'}, 'WS10M': {'m/s'}, 'WS50M': {'m/s'},
        'ALLSKY_KT': {'dimensionless'}, 'ALLSKY_SFC_SW_DWN': {'MJ/m^2/day'},
        'ALLSKY_SFC_PAR_TOT': {'MJ/m^2/day'},
    }
    metadata = frame.attrs.get('source_metadata', {})
    for name, spec in metadata.get('parameters', {}).items():
        if name in expected_units and spec.get('units') not in expected_units[name]:
            raise ValueError(f'Unidad inesperada en {name}; convierte explícitamente a las unidades POWER AG del contrato.')
    climate = summarize_climate(frame, float(latitude), float(longitude), start, end)
    # el proyecto anfitrión currently discards upstream metadata; do not fabricate verification.
    climate['time_standard'] = frame.attrs.get('source_metadata', {}).get('header', {}).get('time_standard', 'No informado por el proveedor de la tabla')
    warnings = []
    if not metadata.get('parameters'):
        warnings.append('Unidades asumidas según NASA POWER community=AG. El proveedor no entregó metadatos de unidades.')
    ignored = sorted(str(c) for c in frame.columns if c not in VARIABLES)
    if ignored:
        warnings.append('Columnas no interpretadas: ' + ', '.join(ignored))
    outside = ((frame.index < pd.Timestamp(climate['start'])) | (frame.index > pd.Timestamp(climate['end']))).sum()
    if outside:
        warnings.append(f'Se excluyeron {int(outside)} filas fuera del período solicitado.')
    for fact in climate['facts']:
        if fact['valid_days'] < fact['expected_days']:
            warnings.append(f"{fact['id']}: {fact['valid_days']}/{fact['expected_days']} días válidos. No confundir el acumulado disponible con el total del período.")
    payload = {'contract_version': '1.0', 'climate': climate, 'profile': cleaned, 'warnings': warnings}
    # Enforce serializability before any API request; disallow NaN / credentials.
    try:
        payload['request_id'] = fingerprint(payload)
    except (ValueError, TypeError) as exc:
        raise ValueError('Los metadatos deben ser JSON sin NaN ni objetos especiales.') from exc
    return payload


def analyze_prepared(prepared, *, api_key, model=DEFAULT_MODEL):
    """One server-side call, no automatic retries; preserve evidence on failure."""
    if prepared.get('contract_version') != '1.0':
        raise ValueError('Versión de contrato no compatible.')
    result = analyze(prepared['climate'], prepared['profile'], api_key, model)
    return {**prepared, **result}


def analyze_dataframe(df, *, latitude, longitude, start, end, profile=None, api_key, model=DEFAULT_MODEL):
    prepared = prepare_analysis(df, latitude=latitude, longitude=longitude, start=start, end=end, profile=profile)
    return analyze_prepared(prepared, api_key=api_key, model=model)
