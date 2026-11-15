"""Interfaz de Streamlit para comparar rotaciones de cultivo.

Muestra el formulario del agricultor, llama a services.rotations para calcular las
tres estrategias, pide la explicación a Prometheus (opcional) y presenta los
resultados en tarjetas. Si la IA no está disponible, muestra una orientación
basada solo en las reglas del proyecto.
"""
import hashlib
import json
import time
import pandas as pd
import streamlit as st
from services.rotations import catalog, compare_rotations


def render_rotations(df, lat, lon):
    """Dibuja la sección de rotaciones para el punto (lat, lon) con sus datos de POWER.

    Guarda el último resultado en st.session_state ligado al punto y a los datos,
    para que un punto nuevo nunca muestre un resultado viejo.
    """
    st.header('2 · Cuéntanos sobre tu cultivo')
    st.write('Compara opciones para tu siguiente ciclo usando información histórica y tus prioridades.')
    crops=list(catalog()['crops'])
    st.caption('Catálogo piloto ampliable: hoy incluye '+', '.join(c.lower() for c in crops)+'. Se pueden agregar cultivos con sus datos FAO sin cambiar el código. Los resultados son orientativos y no predicen el clima futuro.')
    st.caption('Al comparar, Prometheus recibirá la ubicación y estos datos para generar una explicación. No incluyas datos personales.')
    with st.form('rotation_profile'):
        st.markdown('**Cultivos y objetivo**')
        c1,c2=st.columns(2)
        previous=c1.selectbox('Cultivo del ciclo anterior',['Desconocido',*crops])
        current=c2.selectbox('Cultivo actual',crops)
        priority=st.selectbox('Prioridad',['Ahorrar agua','Mejorar el suelo','Ingresos extra'])
        st.markdown('**Agua y suelo**')
        c1,c2=st.columns(2)
        water=c1.selectbox('Disponibilidad de agua',['Temporal','Riego','Desconocido'], help='Temporal significa que depende de la lluvia.')
        drainage=c2.selectbox('Drenaje observado en el suelo',['Desconocido','Bueno','Deficiente'])
        ph_known=c1.checkbox('Tengo un pH medido del suelo')
        ph=c2.number_input('pH medido',min_value=0.0,max_value=14.0,value=7.0,step=0.1)
        st.markdown('**Periodo histórico a consultar**')
        st.caption('Elige fechas que correspondan al ciclo que quieres explorar.')
        c1,c2=st.columns(2)
        default_start=max(df.index.min(),df.index.max()-pd.Timedelta(days=119))
        start=c1.date_input('Inicio de la ventana histórica',value=default_start.date(),min_value=df.index.min().date(),max_value=df.index.max().date())
        end=c2.date_input('Fin de la ventana histórica',value=df.index.max().date(),min_value=df.index.min().date(),max_value=df.index.max().date())
        submitted=st.form_submit_button('Analizar mis opciones')
    # Bind results to point AND full source values. A new location never shows an old result.
    data_key=hashlib.sha256((str((lat,lon))+df.to_json()).encode()).hexdigest()
    saved=st.session_state.get('rotation_result')
    if saved and saved['data_key']!=data_key:
        st.session_state.pop('rotation_result',None); st.session_state.pop('rotation_ai',None); saved=None
    if submitted:
        profile=dict(previous=previous,current=current,priority=priority,water=water,drainage=drainage,
                     soil_ph=ph if ph_known else None,start=str(start),end=str(end),latitude=lat,longitude=lon)
        try: report=compare_rotations(df,profile)
        except ValueError as exc: st.error(str(exc)); return
        saved={'data_key':data_key,'report':report}
        st.session_state['rotation_result']=saved
        st.session_state.pop('rotation_ai',None)
    if not saved: return
    report=saved['report']
    st.caption('Resultados del último formulario enviado. Si cambias campos, pulsa Comparar para actualizarlos.')
    st.write('Prioridad evaluada: **'+report['profile']['priority']+'**')
    payload=json.dumps(report,ensure_ascii=False,allow_nan=False)
    from services.settings import gemini_settings
    key, model = gemini_settings()
    ai = st.session_state.get('rotation_ai')
    if ai and (ai.get('payload') != payload or ai.get('model') != model):
        ai = None
    st.markdown('### 3 · Tu orientación')
    if submitted and key:
        try:
            from services.llm import explicar_rotaciones
            with st.spinner('Preparando una explicación para ti...'):
                text = explicar_rotaciones(payload)
            ai = {'payload': payload, 'model': model, 'text': text}
            st.session_state['rotation_ai'] = ai
        except Exception:
            st.info('No pudimos consultar a Prometheus. Aquí tienes una orientación basada en las reglas del proyecto.')
    if ai:
        st.markdown('**Explicación de Prometheus (IA)**')
        st.markdown(ai['text'])
        st.caption('Explicación generada por Prometheus (IA con tecnología Gemini de Google) a partir de datos históricos. Revísala junto con las advertencias y fuentes.')
    else:
        st.markdown('**Orientación por reglas del proyecto (sin IA)**')
        st.write('Estas son opciones para explorar en tu siguiente ciclo; revisa las condiciones antes de tomar una decisión:')
        for item in report['strategies']:
            st.markdown('**' + item['title'] + ' — ' + item['crop'] + '**')
            if item['restrictions']:
                st.write('Atención: ' + item['restrictions'][0])
            elif item['reasons']:
                st.write(item['reasons'][0])
            else:
                st.write('Falta información para evaluar esta opción.')
        if not key:
            st.caption('Agrega GEMINI_API_KEY al archivo .env para activar las explicaciones de Prometheus.')
    st.warning('Esta orientación usa datos históricos y reglas exploratorias. No predice cosechas ni reemplaza la asesoría local.')
    if not ai and key and not submitted and st.button('Volver a intentar con Prometheus'):
        try:
            from services.llm import explicar_rotaciones
            with st.spinner('Preparando la explicación...'):
                text = explicar_rotaciones(payload)
            st.session_state['rotation_ai'] = {'payload':payload,'model':model,'text':text}
            st.rerun()
        except Exception:
            st.warning('Prometheus no está disponible. Puedes seguir usando la orientación anterior.')
    st.markdown('### 4 · Compara tus opciones')
    st.info('Revisa primero las restricciones y lo que falta comprobar. Un puntaje mayor no garantiza mejores resultados.')
    with st.expander('Ver tabla de comparación'):
        rows=[]
        for s in report['strategies']:
            rows.append({'Estrategia':s['title'],'Secuencia':' → '.join(s['sequence']),
                         'Índice exploratorio':f"{s['score']}/100" if s['score'] is not None else 'No calculable',
                         'Peso evaluable':f"{s['evaluated_weight']}/100",'Estado':s['status']})
        st.dataframe(rows,hide_index=True,use_container_width=True)
    cols = st.columns(3)
    for column, strategy in zip(cols, report['strategies']):
        with column:
            with st.container(border=True):
                st.markdown('#### '+strategy['title'])
                st.caption('Anterior → actual → propuesto')
                st.write(' → '.join(strategy['sequence']))
                if strategy['restrictions']:
                    st.warning('Atención: '+strategy['restrictions'][0])
                else:
                    st.info('Sin restricciones detectadas por estas reglas; requiere validación local.')
                label = f"{strategy['score']}/100" if strategy['score'] is not None else 'Datos insuficientes'
                st.markdown('**Índice exploratorio: '+label+'**')
                st.caption(strategy['status'])
                for name, display in [('agua','Agua'),('helada','Helada'),('diversidad','Diversidad')]:
                    value=strategy['components'][name]
                    text = 'No evaluado' if value is None else f"{value:g} de {strategy['weights'][name]} puntos"
                    st.write(f"{display}: {text}")
                with st.expander('Razones, pendientes y fuentes'):
                    for title,field in [('Razones','reasons'),('Restricciones','restrictions'),('Falta comprobar','missing')]:
                        st.markdown('**'+title+'**')
                        for text in strategy[field]: st.write('• '+text)
                    for url in strategy['sources']: st.markdown(f'[Fuente agronómica]({url})')
    with st.expander('Datos, método y catálogo'):
        st.write('Catálogo piloto ampliable (data/crops.json): '+', '.join(catalog()['crops'])+'. Cada cultivo nuevo necesita su rango de agua FAO, familia botánica, sensibilidad a helada y fuentes.')
        st.write('Periodo consultado: '+report['window']['start']+' a '+report['window']['end'])
        st.write('La comparación usa lluvia histórica, heladas y diversidad de cultivos cuando hay datos suficientes.')
        for line in report['limitations']: st.write('• '+line)
        st.write('Agua: peso × min(lluvia histórica / extremo inferior FAO, 1), solo temporal y cobertura completa. Helada: peso si no hay días ≤0 °C, cero si hay. Diversidad: peso si aparecen ambas familias; cero si una sola. Son reglas del equipo, no de NASA o FAO.')
