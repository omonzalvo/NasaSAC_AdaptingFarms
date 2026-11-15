"""Dónde se busca la clave y el modelo de Gemini que usa Prometheus.

Orden de búsqueda de la clave (gana la primera que exista):
    1. La sesión de Streamlit (local_gemini_key), si algún día se agrega un campo en la interfaz.
    2. La variable de entorno GEMINI_API_KEY (archivo .env con Docker).
    3. Los Secrets de Streamlit (.streamlit/secrets.toml o Streamlit Community Cloud).

Nunca se escribe la clave en archivos.
"""
import os
DEFAULT_MODEL='gemini-3.5-flash'

def gemini_settings():
    """Devuelve (clave, modelo). La clave puede ser '' si no está configurada."""
    import streamlit as st
    key=os.getenv('GEMINI_API_KEY','')
    model=os.getenv('GEMINI_MODEL',DEFAULT_MODEL)
    try:
        key=key or st.secrets.get('GEMINI_API_KEY','')
        model=os.getenv('GEMINI_MODEL') or st.secrets.get('GEMINI_MODEL',DEFAULT_MODEL)
    except (FileNotFoundError, KeyError):
        pass
    return st.session_state.get('local_gemini_key','') or key, st.session_state.get('local_gemini_model',model) or model
