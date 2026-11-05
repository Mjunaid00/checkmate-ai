@echo off
rem Starts the CheckMate AI frontend (Vite dev server on port 5173).
rem Output is shown here AND appended to logs\frontend.log when a Python is available.
rem Overrides: CHECKMATE_CONDA_ROOT, CHECKMATE_CONDA_ENV, CHECKMATE_PYTHON (only used for logging).
title CheckMate Frontend
cd /d "%~dp0..\frontend"
if not exist node_modules\vite (
    echo node_modules missing - running npm install...
    call npm install
)

if "%CHECKMATE_CONDA_ENV%"=="" set "CHECKMATE_CONDA_ENV=checkmate-ai"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%USERPROFILE%\anaconda3\envs\%CHECKMATE_CONDA_ENV%\python.exe" set "CHECKMATE_CONDA_ROOT=%USERPROFILE%\anaconda3"
if "%CHECKMATE_CONDA_ROOT%"=="" if exist "%USERPROFILE%\miniconda3\envs\%CHECKMATE_CONDA_ENV%\python.exe" set "CHECKMATE_CONDA_ROOT=%USERPROFILE%\miniconda3"
if "%CHECKMATE_PYTHON%"=="" if exist "%CHECKMATE_CONDA_ROOT%\envs\%CHECKMATE_CONDA_ENV%\python.exe" set "CHECKMATE_PYTHON=%CHECKMATE_CONDA_ROOT%\envs\%CHECKMATE_CONDA_ENV%\python.exe"

echo Frontend : http://localhost:5173
echo Log file : %~dp0..\logs\frontend.log
echo.
if "%CHECKMATE_PYTHON%"=="" (
    call npm run dev
) else (
    "%CHECKMATE_PYTHON%" "%~dp0tee_run.py" "%~dp0..\logs\frontend.log" -- npm run dev
)
echo.
echo Frontend stopped (exit code %ERRORLEVEL%). See logs\frontend.log. Press any key to close this window.
pause >nul
