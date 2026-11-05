@echo off
rem Starts the CheckMate AI backend inside the Anaconda env (default: checkmate-ai),
rem the same way "conda activate checkmate-ai" + "uvicorn main:app" would.
rem Used by scripts\start-checkmate.ps1, but you can also double-click it.
rem Overrides: CHECKMATE_CONDA_ROOT, CHECKMATE_CONDA_ENV, CHECKMATE_PYTHON.
rem Output is shown here AND appended to logs\backend.log.
title CheckMate Backend
cd /d "%~dp0..\backend"

if "%CHECKMATE_CONDA_ENV%"=="" set "CHECKMATE_CONDA_ENV=checkmate-ai"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=%USERPROFILE%\anaconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=%USERPROFILE%\miniconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%LOCALAPPDATA%\anaconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=%LOCALAPPDATA%\anaconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%LOCALAPPDATA%\miniconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=%LOCALAPPDATA%\miniconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "C:\ProgramData\anaconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=C:\ProgramData\anaconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" set "CHECKMATE_CONDA_ROOT=C:\ProgramData\miniconda3"

if "%CHECKMATE_PYTHON%"=="" if exist "%CHECKMATE_CONDA_ROOT%\envs\%CHECKMATE_CONDA_ENV%\python.exe" set "CHECKMATE_PYTHON=%CHECKMATE_CONDA_ROOT%\envs\%CHECKMATE_CONDA_ENV%\python.exe"
if "%CHECKMATE_PYTHON%"=="" set "CHECKMATE_PYTHON=python"

rem Activate the env so its DLL folders (Library\bin etc.) are on PATH, exactly like "conda activate".
set "CHECKMATE_ENV_DIR="
if exist "%CHECKMATE_PYTHON%" for %%P in ("%CHECKMATE_PYTHON%") do set "CHECKMATE_ENV_DIR=%%~dpP"
if defined CHECKMATE_ENV_DIR set "CHECKMATE_ENV_DIR=%CHECKMATE_ENV_DIR:~0,-1%"
if defined CHECKMATE_ENV_DIR if exist "%CHECKMATE_CONDA_ROOT%\Scripts\activate.bat" call "%CHECKMATE_CONDA_ROOT%\Scripts\activate.bat" "%CHECKMATE_ENV_DIR%"

set PYTHONUTF8=1
echo Backend  : http://localhost:8000   (docs: /docs, readiness: /health/full)
echo Python   : %CHECKMATE_PYTHON%
if defined CONDA_PREFIX echo Conda env: %CONDA_PREFIX%
echo Log file : %~dp0..\logs\backend.log
echo.
if not exist "%~dp0..\logs" mkdir "%~dp0..\logs"
echo ===== %date% %time% run-backend.cmd: python=%CHECKMATE_PYTHON% conda_prefix=%CONDA_PREFIX% db=%DATABASE_NAME%>> "%~dp0..\logs\backend.log"
"%CHECKMATE_PYTHON%" "%~dp0tee_run.py" "%~dp0..\logs\backend.log" -- "%CHECKMATE_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000
echo.
echo Backend stopped (exit code %ERRORLEVEL%). See logs\backend.log. Press any key to close this window.
pause >nul
