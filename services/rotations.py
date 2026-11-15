"""Comparación de tres estrategias de rotación para el siguiente cultivo.

Estrategias:
    actual      repetir el cultivo actual.
    leguminosa  introducir frijol (puede fijar nitrógeno).
    sequia      probar sorgo (menos sensible a sequía).

Cada estrategia recibe puntos en tres componentes cuyo peso depende de la prioridad
del agricultor (ver WEIGHTS):
    agua        lluvia de la ventana histórica frente al rango de agua FAO del cultivo.
    helada      todo el peso si no hubo heladas en la ventana, cero si las hubo.
    diversidad  todo el peso si la secuencia mezcla familias de cultivos.

El índice total solo se calcula si los tres componentes se pudieron evaluar. Es una
heurística transparente del equipo: no es probabilidad, aptitud ni recomendación.
El catálogo de cultivos está en data/crops.json.
"""
import json
import math
from pathlib import Path
import pandas as pd
from services.ambience import serie

CATALOG_PATH = Path(__file__).resolve().parents[1]/'data/crops.json'
WEIGHTS = {
    'Ahorrar agua': {'agua':60,'helada':20,'diversidad':20},
    'Mejorar el suelo': {'agua':20,'helada':20,'diversidad':60},
    'Ingresos extra': {'agua':40,'helada':30,'diversidad':30},
}

def catalog():
    """Lee el catálogo de cultivos (agua FAO, familia, sensibilidad, fuentes)."""
    return json.loads(CATALOG_PATH.read_text())


def compare_rotations(df, profile):
    """Compara las tres estrategias con los datos de POWER y el perfil del agricultor.

    profile trae: previous, current, priority, water, drainage, soil_ph, start, end,
    latitude y longitude (lo llena services.rotation_ui).

    Devuelve un diccionario con la evidencia usada (lluvia, heladas, grados-día),
    las tres estrategias con sus puntos, razones, restricciones y pendientes, y las
    limitaciones del método. Lanza ValueError si el perfil o la ventana no son válidos.
    """
    crops=catalog()['crops']
    current=profile['current']; previous=profile['previous']
    if current not in crops or previous not in [*crops,'Desconocido']:
        raise ValueError('Cultivo fuera del catálogo piloto.')
    start,end=pd.Timestamp(profile['start']),pd.Timestamp(profile['end'])
    if end<start or (end-start).days>365:
        raise ValueError('Selecciona una ventana histórica de hasta un año.')
    if start<df.index.min() or end>df.index.max():
        raise ValueError('La ventana debe estar dentro de los datos descargados.')
    if df.index.has_duplicates: raise ValueError('Fechas duplicadas.')
    frame=df.reindex(pd.date_range(start,end))
    rain,lo,hi=(serie(frame,n) for n in ['PRECTOTCORR','T2M_MIN','T2M_MAX'])
    rain=rain.where(rain>=0)
    n=len(frame)
    valid={'rain':int(rain.count()),'min':int(lo.count()),'max':int(hi.count())}
    # Require full coverage for numeric scores. Partial sums remain explicitly partial evidence.
    rain_total=float(rain.sum(min_count=1)) if rain.notna().any() else None
    frost=int((lo<=0).sum()) if lo.notna().all() else None
    gdd=float(((hi+lo)/2-10).clip(lower=0).sum()) if lo.notna().all() and hi.notna().all() else None
    weights=WEIGHTS[profile['priority']]
    rows=[]
    for ident,title,candidate in [('actual','Continuar cultivo actual',current),('leguminosa','Introducir leguminosa','Frijol'),('sequia','Explorar cereal menos sensible a sequía','Sorgo')]:
        crop=crops[candidate]
        missing=['Variedad local y duración de su ciclo; calendario de siembra/cosecha.',
                 'Requerimiento de grados-día específico de variedad: no disponible.',
                 'Análisis local de nutrientes, plagas, enfermedades y manejo de residuos.']
        reasons=[]; restrictions=[]
        scores={'agua':None,'helada':None,'diversidad':None}
        if profile['water']=='Temporal' and valid['rain']==n:
            scores['agua']=round(weights['agua']*min(rain_total/crop['water_mm'][0],1),1)
            reasons.append(f"Lluvia histórica disponible {rain_total:.1f} mm frente a referencia FAO {crop['water_mm'][0]}–{crop['water_mm'][1]} mm/ciclo. Es una relación exploratoria; no lluvia efectiva ni agua utilizable por el cultivo.")
            if rain_total<crop['water_mm'][0]: restrictions.append('La lluvia observada no alcanza el extremo inferior orientativo de demanda; revisar agua almacenada y distribución.')
        else:
            missing.append('Falta cobertura completa de lluvia o cuantificar riego/agua disponible; componente agua no evaluado.')
        if frost is not None:
            scores['helada']=weights['helada'] if frost==0 else 0
            reasons.append(f'{frost} días con mínima ≤ 0 °C en la ventana histórica. Sin pronóstico para el próximo ciclo.')
            if frost: restrictions.append('Hay exposición histórica a heladas para un cultivo sensible; revisar fechas y variedad.')
        else: missing.append('Faltan temperaturas mínimas: heladas no evaluadas.')
        if previous!='Desconocido':
            seq=[previous,current,candidate]
            families={crops[c]['family'] for c in seq}
            # Proxy only: having both crop families does not establish soil improvement.
            scores['diversidad']=weights['diversidad'] if len(families)>1 else 0
            reasons.append('Diversidad de familias en la secuencia: '+', '.join(sorted(families))+'. No mide mejora del suelo.')
        else: missing.append('Cultivo anterior desconocido: diversidad de la secuencia no evaluada.')
        if candidate==current: reasons.append('Esta alternativa repite el cultivo actual; no representa un cambio de especie.')
        if candidate=='Frijol':
            reasons.append('Puede fijar parte del nitrógeno mediante simbiosis; no elimina automáticamente la fertilización.')
            if current=='Frijol': restrictions.append('Frijol en ciclos consecutivos: revisar riesgo sanitario antes de repetir.')
            if profile['drainage']=='Deficiente': restrictions.append('El frijol requiere buen drenaje; resolver el drenaje antes de considerarlo.')
        if profile['drainage']=='Desconocido': missing.append('Drenaje local desconocido.')
        if profile.get('soil_ph') is None: missing.append('pH local no informado.')
        elif candidate=='Frijol' and not 5.5<=profile['soil_ph']<=6.5:
            restrictions.append('pH fuera del intervalo orientativo de la ficha CGIAR de frijol; requiere revisión local, no descarte automático.')
        if profile['priority']=='Ingresos extra': missing.append('Costos, rendimiento local y precio de venta: rentabilidad no evaluada; índice técnico sin componente económico.')
        evaluated=sum(weights[k] for k,v in scores.items() if v is not None)
        total=round(sum(v for v in scores.values() if v is not None),1) if evaluated==100 else None
        rows.append(dict(id=ident,title=title,sequence=[previous,current,candidate],crop=candidate,
                         score=total,evaluated_weight=evaluated,components=scores,weights=weights,
                         status='Revisar restricciones' if restrictions else 'Requiere validación local',
                         reasons=reasons,restrictions=restrictions,missing=missing,sources=crop['sources']))
    return dict(version='1.0',profile=profile,window={'start':str(start.date()),'end':str(end.date()),'days':n},
                evidence=dict(rain_mm=rain_total,frost_days=frost,gdd_base10=gdd,valid_days=valid),
                strategies=rows,limitations=[
                    'Índice exploratorio del proyecto: no probabilidad, aptitud agronómica ni recomendación de siembra.',
                    'Las tres estrategias evalúan solo el siguiente cultivo de una secuencia propuesta; no simulan tres cosechas.',
                    'Datos regionales históricos. No predicen clima, rendimiento, mejora del suelo ni ingresos.',
                    'Los rangos FAO son orientativos para el ciclo completo; confirma que la ventana elegida corresponda al ciclo local.',
                    'Suelo, grados-día de madurez y viabilidad económica no forman parte del puntaje. Una restricción debe revisarse aunque el índice sea alto.'])
