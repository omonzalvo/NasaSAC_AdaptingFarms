"""Instala el panel de IA en una aplicación Streamlit compatible."""
import argparse
import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BEGIN = '# BEGIN TERRASHIFT_AI'
END = '# END TERRASHIFT_AI'
BLOCK = '''# BEGIN TERRASHIFT_AI
from terrashift_ai.streamlit_panel import render_panel as _terrashift_panel
_terrashift_panel(df, latitude=lat, longitude=lon,
                 start=inicio.strftime('%Y-%m-%d'),
                 end=fin.strftime('%Y-%m-%d'))
# END TERRASHIFT_AI
'''

def integrate(target, *, install_dependencies=True):
    target = Path(target).expanduser().resolve()
    app = target / 'app.py'
    if not app.is_file():
        raise ValueError('La carpeta seleccionada no contiene app.py.')
    original = app.read_text(encoding='utf-8-sig')
    if original.count(BEGIN) != original.count(END) or original.count(BEGIN) > 1:
        raise ValueError('El bloque de integración existente está incompleto. No se modificó el proyecto.')
    base = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', '', original, flags=re.S)
    tree = ast.parse(base)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    missing = {'df','lat','lon','inicio','fin'} - names
    if missing:
        raise ValueError('Esta versión de app.py no coincide con el contrato esperado. Faltan: '+', '.join(sorted(missing)))
    if 'terrashift_ai' in base:
        raise ValueError('Ya existe una integración manual de terrashift_ai. No se añadirá un segundo panel.')
    module = target / 'terrashift_ai'
    if module.exists() and not (module / '.installed-by-terrashift').is_file():
        raise ValueError('Ya existe una carpeta terrashift_ai no administrada por este instalador; se conservó intacta.')
    updated = base.rstrip() + '\n\n' + BLOCK
    compile(updated, str(app), 'exec')
    # Reutiliza el entorno del proyecto si existe; no cambia su versión de Python.
    candidates = [target/'.venv/Scripts/python.exe',target/'.venv/bin/python', target/'venv/Scripts/python.exe',target/'venv/bin/python']
    python = next((str(p) for p in candidates if p.is_file()), sys.executable)
    if install_dependencies:
        subprocess.run([python,'-m','pip','install','-r',str(ROOT/'requirements-ia.txt')],check=True)
    backup = target / ('.terrashift-backups/' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True)
    files = ['app.py','requirements.txt','.gitignore','INICIAR_APP_IA.bat']
    for name in files:
        p = target/name
        if p.exists(): shutil.copy2(p,backup/name)
    if module.exists(): shutil.copytree(module,backup/'terrashift_ai')
    shutil.copytree(ROOT/'terrashift_ai',module,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    (module/'.installed-by-terrashift').write_text('1.1\n')
    app.write_text(updated,encoding='utf-8')
    req = target/'requirements.txt'
    text = req.read_text() if req.exists() else ''
    additions=[]
    for line in (ROOT/'requirements-ia.txt').read_text().splitlines():
        name=re.split(r'[<>=!~\[]',line)[0].strip()
        if name and not re.search(r'^\s*'+re.escape(name)+r'(?=[<>=!~\[\s;]|$)',text,re.M|re.I): additions.append(line)
    if additions: req.write_text(text.rstrip()+'\n'+'\n'.join(additions)+'\n')
    ignore=target/'.gitignore'
    text=ignore.read_text() if ignore.exists() else ''
    for line in ('.streamlit/secrets.toml','.terrashift-backups/','__pycache__/'):
        if line not in text.splitlines(): text=text.rstrip()+'\n'+line+'\n'
    ignore.write_text(text)
    (target/'INICIAR_APP_IA.bat').write_text('@echo off\ncd /d "%~dp0"\n"'+python+'" -m streamlit run app.py\npause\n')
    return backup

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',nargs='?')
    args=parser.parse_args()
    path=args.project or input('Pega la ruta de la carpeta del proyecto (donde está app.py): ').strip().strip('"')
    try:
        backup=integrate(path)
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError) as exc:
        print('No se completó la integración:',exc)
        return 1
    print('Integración lista. Respaldo:',backup)
    print('Abre INICIAR_APP_IA.bat dentro del proyecto, o ejecútalo como siempre.')
    return 0
if __name__=='__main__': sys.exit(main())
