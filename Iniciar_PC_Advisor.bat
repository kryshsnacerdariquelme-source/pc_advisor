@echo off
setlocal enabledelayedexpansion
title PC Advisor
cd /d "%~dp0"
color 0B

echo ============================================
echo              PC ADVISOR
echo ============================================
echo.

rem -----------------------------------------------------------------
rem 1) Verificar si Python esta disponible en el equipo
rem -----------------------------------------------------------------
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo No se encontro Python instalado en este equipo.
    echo Se va a descargar e instalar automaticamente.
    echo ^(Se requiere conexion a internet, solo la primera vez^)
    echo.
    echo Descargando... por favor espera, no cierres esta ventana.
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%TEMP%\python_installer.exe' } catch { exit 1 }"
    if not exist "%TEMP%\python_installer.exe" (
        echo.
        echo No se pudo descargar Python. Verifica tu conexion a internet
        echo e intenta abrir este archivo de nuevo.
        echo.
        pause
        exit /b 1
    )
    echo Instalando Python ^(esto puede tardar 1-2 minutos^)...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
    del "%TEMP%\python_installer.exe" >nul 2>nul
    echo.
    echo Python quedo instalado. Cierra esta ventana y vuelve a hacer
    echo doble clic en "Iniciar_PC_Advisor.bat" para continuar.
    echo.
    pause
    exit /b 0
)

rem -----------------------------------------------------------------
rem 2) Preparar el entorno de la app (solo la primera vez)
rem -----------------------------------------------------------------
if not exist ".venv_pcadvisor\Scripts\python.exe" (
    echo Preparando PC Advisor por primera vez...
    echo Esto puede tardar varios minutos, no cierres esta ventana.
    echo.
    python -m venv .venv_pcadvisor
    if not exist ".venv_pcadvisor\Scripts\python.exe" (
        echo.
        echo No se pudo preparar el entorno de la aplicacion.
        pause
        exit /b 1
    )

    ".venv_pcadvisor\Scripts\python.exe" -m pip install --upgrade pip --quiet

    echo Instalando componentes necesarios ^(puede tardar unos minutos^)...
    ".venv_pcadvisor\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo.
        echo Hubo un problema instalando los componentes.
        echo Verifica tu conexion a internet e intenta de nuevo.
        echo.
        pause
        exit /b 1
    )

    echo.
    echo Listo. PC Advisor quedo instalado en este equipo.
    echo.
)

rem -----------------------------------------------------------------
rem 3) Iniciar el monitor de hardware en segundo plano (minimizado)
rem -----------------------------------------------------------------
taskkill /FI "WINDOWTITLE eq PC Advisor - Monitor*" /T /F >nul 2>nul
start "PC Advisor - Monitor" /min ".venv_pcadvisor\Scripts\python.exe" "Backend\monitor.py"

rem Dar tiempo a que el monitor genere la primera lectura
timeout /t 2 /nobreak >nul

rem -----------------------------------------------------------------
rem 4) Iniciar la interfaz web (abre el navegador automaticamente)
rem -----------------------------------------------------------------
echo Abriendo PC Advisor en tu navegador...
echo.
echo No cierres esta ventana mientras uses la app.
echo Para salir, simplemente cierra esta ventana.
echo.
".venv_pcadvisor\Scripts\python.exe" -m streamlit run "Frontend\app.py"

rem -----------------------------------------------------------------
rem 5) Al cerrar la app, apagar tambien el monitor de segundo plano
rem -----------------------------------------------------------------
taskkill /FI "WINDOWTITLE eq PC Advisor - Monitor*" /T /F >nul 2>nul

endlocal
