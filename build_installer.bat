@echo off
setlocal
title PC Advisor - Crear instalador
cd /d "%~dp0"

echo ============================================
echo   PC ADVISOR - Crear el instalador
echo ============================================
echo.

rem --- 1) Asegurar que el .exe existe (si no, compilarlo)
if exist "dist\PC_Advisor\PC_Advisor.exe" goto buscar_inno
echo No se encontro dist\PC_Advisor\PC_Advisor.exe. Se compilara primero...
call build_exe.bat
if not exist "dist\PC_Advisor\PC_Advisor.exe" goto sin_exe

:buscar_inno
rem --- 2) Buscar Inno Setup 6
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC goto sin_inno

echo Usando: %ISCC%
echo.
"%ISCC%" "installer\PC_Advisor.iss"
if errorlevel 1 goto error

echo.
echo ============================================
echo   LISTO
echo   Instalador:  installer_output\PC_Advisor_Setup_1.0.0.exe
echo   Ese es el archivo que debes entregar a los demas.
echo ============================================
echo.
pause
exit /b 0

:sin_inno
echo No se encontro Inno Setup 6. Descargalo e instalalo ^(gratis^) desde:
echo     https://jrsoftware.org/isdl.php
echo y vuelve a ejecutar este archivo.
echo.
pause
exit /b 1

:sin_exe
echo No se pudo generar el .exe. Revisa los errores anteriores.
pause
exit /b 1

:error
echo.
echo Fallo la creacion del instalador. Revisa los mensajes de arriba.
pause
exit /b 1
