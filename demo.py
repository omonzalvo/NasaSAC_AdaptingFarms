"""Demo independiente: streamlit run demo.py (NASA no se consulta)."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from terrashift_ai.streamlit_panel import render_panel
st.set_page_config(page_title='TerraShift — integración IA', layout='wide')
st.title('TerraShift — análisis ambiental')
st.caption('Ejemplo histórico guardado de NASA POWER. La llamada a Gemini es real al pulsar el botón.')
x = json.loads(Path(__file__).with_name('example_power.json').read_text())
df = pd.DataFrame.from_dict(x['daily'], orient='index')
df.index = pd.to_datetime(df.index)
df.attrs['source_metadata'] = x['source_metadata']
render_panel(df, latitude=x['latitude'], longitude=x['longitude'], start=x['start'], end=x['end'])
