@echo off
setlocal
title PC Advisor - Generar .exe
cd /d "%~dp0"

echo ============================================
echo   PC ADVISOR - Generar el .exe
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 goto sin_python

if exist ".venv_build\Scripts\python.exe" goto venv_listo
echo [1/3] Creando entorno de compilacion ^(solo la primera vez^)...
python -m venv .venv_build
if errorlevel 1 goto error
:venv_listo

echo [2/3] Instalando dependencias...
".venv_build\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv_build\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt --quiet
if errorlevel 1 goto error

echo [3/3] Compilando con PyInstaller ^(puede tardar varios minutos^)...
".venv_build\Scripts\python.exe" -m PyInstaller --noconfirm --clean PC_Advisor.spec
if errorlevel 1 goto error

echo.
echo ============================================
echo   LISTO
echo   Ejecutable:  dist\PC_Advisor\PC_Advisor.exe
echo   Siguiente paso: build_installer.bat  ^(crea el instalador^)
echo ============================================
echo.
pause
exit /b 0

:sin_python
echo No se encontro Python. Instala Python 3.12 desde https://www.python.org/downloads/
echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
echo.
pause
exit /b 1

:error
echo.
echo Algo fallo. Revisa los mensajes de arriba.
echo.
pause
exit /b 1
