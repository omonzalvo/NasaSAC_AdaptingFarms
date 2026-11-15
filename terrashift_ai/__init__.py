"""TerraShift integration API v1. No Streamlit or network at import time."""
from .adapter import prepare_analysis, analyze_dataframe, analyze_prepared
from .gemini import AnalysisError, DEFAULT_MODEL
__version__ = '1.0.0'
