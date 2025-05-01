@echo off
setlocal

REM --------------------------------------------------
REM install_deps_and_run.bat — instala Python si falta,
REM instala dependencias y ejecuta main.py y cierra consola
REM --------------------------------------------------

REM Crear carpeta de logs y definir fichero
set "LOGDIR=%~dp0logs"
set "LOGFILE=%LOGDIR%\bat.log"
if not exist "%LOGDIR%" md "%LOGDIR%"

REM 1) Comprobar Python
echo [INFO] Paso 1: comprobando si Python esta instalado...
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PY=py -3"
    set "PYW=pyw -3"
    echo    - usando lanzador "py"
    goto check_pip
)
where python >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PY=python"
    set "PYW=pythonw"
    echo    - usando lanzador "python"
    goto check_pip
)
echo    - no se detecto Python

REM 2) Descargar e instalar Python
echo [INFO] Paso 2: descargando instalador de Python...
set "PY_URL=https://www.python.org/ftp/python/3.10.9/python-3.10.9-amd64.exe"
set "PY_INSTALLER=%TEMP%\python-installer.exe"
powershell -NoProfile -Command ^
  "Try { Invoke-WebRequest '%PY_URL%' -OutFile '%PY_INSTALLER%' -UseBasicParsing } Catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] fallo al descargar instalador >>"%LOGFILE%"
    exit /B 1
)
echo    - instalando Python en modo silencioso...
"%PY_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    del /F /Q "%PY_INSTALLER%" >nul 2>&1
    echo [ERROR] fallo en la instalacion de Python >>"%LOGFILE%"
    exit /B 1
)
del /F /Q "%PY_INSTALLER%" >nul 2>&1
set "PY=py -3"
set "PYW=pyw -3"
echo    - Python instalado correctamente

:check_pip
REM 3) Verificar y actualizar pip
echo [INFO] Paso 3: verificando y actualizando pip...
%PY% -m ensurepip --upgrade >nul 2>&1
%PY% -m pip install --upgrade pip >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] fallo al actualizar pip >>"%LOGFILE%"
    exit /B 1
)
echo    - pip actualizado

REM 4) Instalar dependencias
echo [INFO] Paso 4: instalando dependencias desde requirements.txt...
if exist "%~dp0requirements.txt" (
    %PY% -m pip install -r "%~dp0requirements.txt" >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] fallo al instalar dependencias >>"%LOGFILE%"
        exit /B 1
    )
    echo    - dependencias instaladas
) else (
    echo    - requirements.txt no encontrado; omitiendo
)

REM 5) Ejecutar main.py en modo GUI y cerrar esta consola
echo [INFO] Paso 5: lanzando main.py y cerrando consola...
cd /d "%~dp0"
start "" %PYW% main.py

endlocal
exit /B 0