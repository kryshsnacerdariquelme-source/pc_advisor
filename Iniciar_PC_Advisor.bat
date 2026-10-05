@echo off
rem Ejecuta PC Advisor DESDE EL CODIGO (modo desarrollo / pruebas).
rem Para usuarios finales usa el instalador (ver LEEME.txt).
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instala Python 3.12 desde https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv_pcadvisor\Scripts\python.exe" (
    echo Preparando el entorno por primera vez ^(necesita internet^)...
    python -m venv .venv_pcadvisor
    ".venv_pcadvisor\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv_pcadvisor\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
)

rem pythonw = sin ventana de consola; la app se abre como programa de escritorio
start "" ".venv_pcadvisor\Scripts\pythonw.exe" "Desktop\main.py"
endlocal
