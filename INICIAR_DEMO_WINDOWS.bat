@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements-ia.txt streamlit
if errorlevel 1 goto error
.venv\Scripts\python.exe -m streamlit run demo.py
exit /b
:error
 echo No se pudo preparar el entorno. Revisa el mensaje anterior.
 pause
