"""Optional UI. Call render_panel after obtaining df, lat, lon, inicio, fin."""
import json
import os
import time
import streamlit as st
from . import prepare_analysis, analyze_prepared, AnalysisError, DEFAULT_MODEL


def render_panel(df, *, latitude, longitude, start, end):
    st.subheader('Interpretar condiciones con IA')
    st.caption('Análisis histórico regional. No es un pronóstico ni una prescripción agronómica.')
    with st.expander('Perfil de la parcela', expanded=True):
        crop = st.text_input('Cultivo actual', key='ts_crop')
        history = st.text_input('Cultivos anteriores', key='ts_history')
        water = st.selectbox('Acceso al agua', ['No informado', 'Solo lluvia (temporal)', 'Riego', 'Mixto'], key='ts_water')
        soil = st.text_input('Suelo: características conocidas', key='ts_soil')
        goal = st.selectbox('Objetivo', ['Entender las condiciones', 'Evaluar alternativas de rotación', 'Identificar información faltante sobre agua'], key='ts_goal')
        planting = st.text_input('Época de siembra prevista', key='ts_planting')
    try:
        prepared = prepare_analysis(df, latitude=latitude, longitude=longitude, start=start, end=end,
                                    profile=dict(crop=crop, history=history, water=water, soil=soil, goal=goal, planting_window=planting))
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        return
    def setting(name, default=''):
        value = os.getenv(name)
        if value is not None:
            return value
        try:
            return st.secrets.get(name, default)
        except (FileNotFoundError, KeyError):
            return default
    key = setting('GEMINI_API_KEY')
    if not key:
        key = st.text_input('Clave de Gemini', type='password', key='ts_session_api_key',
                            help='Se usa durante esta sesión. No se guarda en archivos ni se incluye en el análisis.')
    model = setting('GEMINI_MODEL', DEFAULT_MODEL)
    request_id = prepared['request_id'] + '|' + model
    saved = st.session_state.get('ts_result')
    if saved and saved['id'] != request_id:
        st.session_state.pop('ts_result', None)
        saved = None
    for warning in prepared['warnings']:
        st.warning(warning)
    with st.expander('Indicadores calculados y cobertura'):
        st.dataframe(prepared['climate']['facts'], use_container_width=True)
    st.download_button('Descargar evidencias sin IA', json.dumps(prepared, ensure_ascii=False, indent=2),
                       'terrashift_evidencias.json', 'application/json')
    if not key:
        st.info('Introduce tu clave de Gemini para activar el análisis.')
    st.caption('Se enviarán a Google las coordenadas, el perfil y los indicadores resumidos. No incluyas datos personales.')
    if st.button('Analizar con Gemini', disabled=not key):
        if saved:
            st.info('Se reutilizó el análisis de estos mismos datos.')
        elif time.time() - st.session_state.get('ts_last_attempt', 0) < 30:
            st.warning('Espera treinta segundos entre intentos.')
        else:
            st.session_state['ts_last_attempt'] = time.time()
            try:
                with st.spinner('Analizando evidencias...'):
                    result = analyze_prepared(prepared, api_key=key, model=model)
                saved = {'id': request_id, 'result': result}
                st.session_state['ts_result'] = saved
            except AnalysisError as exc:
                st.error(str(exc))
    if saved:
        result = saved['result']
        report = result['analysis']
        st.caption('Modelo: ' + result['model'])
        st.write(report['summary'])
        for warning in report['validation_warnings']:
            st.warning(warning)
        evidence = {f['id']: f for f in result['climate']['facts'] + result['climate']['monthly']}
        for observation in report['observations']:
            st.write(observation['explanation'])
            for ref in observation['evidence_ids']:
                f = evidence[ref]
                st.caption(f"{ref}: {f['value']} {f['unit']} · {f['valid_days']}/{f['expected_days']} días")
        for title, field in [('Información faltante', 'questions'), ('Próximos pasos', 'next_steps'), ('Limitaciones', 'limitations')]:
            st.markdown('**' + title + '**')
            for item in report[field]:
                st.write('• ' + item)
        st.download_button('Descargar análisis y evidencias', json.dumps(result, ensure_ascii=False, indent=2),
                           'terrashift_analisis.json', 'application/json')
