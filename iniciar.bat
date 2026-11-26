@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto nopython
  set "PY=python"
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto oldpython

if not exist "venv\Scripts\python.exe" (
  echo Creando el entorno de Python...
  %PY% -m venv venv
  if errorlevel 1 goto venvfail
)

echo Instalando librerias. La primera vez tarda unos minutos.
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

echo.
echo Abriendo FinSight en el navegador.
echo Para cerrarla, cierra esta ventana o pulsa Ctrl+C.
echo.
venv\Scripts\python.exe -m streamlit run app.py
goto end

:nopython
echo No encuentro Python.
echo 1. Abre https://www.python.org/downloads/
echo 2. Instala Python 3.11 o mas nuevo.
echo 3. En el instalador marca "Add python.exe to PATH".
echo 4. Vuelve a abrir iniciar.bat
goto end

:oldpython
echo Python esta instalado, pero es anterior a la version 3.11.
echo Instala Python 3.11 o mas nuevo desde https://www.python.org/downloads/
echo y marca "Add python.exe to PATH".
goto end

:venvfail
echo No se pudo crear el entorno virtual.
echo Copia todo el texto de esta ventana y envialo.
goto end

:pipfail
echo No se pudieron instalar las librerias.
echo Copia todo el texto de esta ventana y envialo.
goto end

:end
echo.
pause
