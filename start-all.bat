@echo off
setlocal EnableDelayedExpansion

rem ============================================================
rem  Checkmate-AI — one-click launcher
rem  Starts: MongoDB (service) -> LM Studio server -> Backend -> Frontend
rem ============================================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "CONDA_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat"
set "CONDA_ENV=checkmate-ai"
set "LMS=%USERPROFILE%\.lmstudio\bin\lms.exe"

echo.
echo ============================================================
echo  Checkmate-AI launcher
echo  Project root: %PROJECT_ROOT%
echo ============================================================
echo.

rem ---------- 1. MongoDB ----------
echo [1/4] Checking MongoDB service...
sc query MongoDB >nul 2>&1
if errorlevel 1 (
    echo     [WARN] MongoDB service not registered. Start MongoDB Compass / mongod manually.
) else (
    for /f "tokens=3" %%S in ('sc query MongoDB ^| findstr /R "STATE"') do set "MONGO_STATE=%%S"
    if /I "!MONGO_STATE!"=="RUNNING" (
        echo     MongoDB is already running.
    ) else (
        echo     Starting MongoDB service...
        net start MongoDB >nul 2>&1
        if errorlevel 1 (
            echo     [WARN] Could not start MongoDB service. You may need to run as Administrator.
        ) else (
            echo     MongoDB started.
        )
    )
)

rem ---------- 2. LM Studio server ----------
echo [2/4] Starting LM Studio local server...
if exist "%LMS%" (
    "%LMS%" server start
    if errorlevel 1 (
        echo     [WARN] lms server start returned an error. If it is already running you can ignore this.
    )
    echo     Reminder: open LM Studio and load a model so the API at http://localhost:1234 can serve requests.
) else (
    echo     [WARN] lms CLI not found at %LMS%. Open LM Studio manually and load your model.
)

rem ---------- 3. Backend (uvicorn) in a new window ----------
echo [3/4] Launching backend in a new window...
if not exist "%CONDA_ACTIVATE%" (
    echo     [WARN] Conda activate script not found at %CONDA_ACTIVATE%.
    echo     Open a terminal, run: conda activate %CONDA_ENV%, then uvicorn manually.
) else (
    start "Checkmate Backend" cmd /k "call ""%CONDA_ACTIVATE%"" %CONDA_ENV% && cd /d ""%PROJECT_ROOT%\backend"" && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
)

rem ---------- 4. Frontend (vite) in a new window ----------
echo [4/4] Launching frontend in a new window...
start "Checkmate Frontend" cmd /k "cd /d ""%PROJECT_ROOT%\frontend"" && npm run dev"

echo.
echo ============================================================
echo  All services launched.
echo    Backend  : http://localhost:8000   (see "Checkmate Backend" window)
echo    Frontend : http://localhost:5173   (see "Checkmate Frontend" window)
echo    LM Studio: http://localhost:1234   (load a model in the LM Studio app)
echo    MongoDB  : mongodb://localhost:27017
echo.
echo  Close the spawned terminal windows to stop the backend / frontend.
echo  To stop LM Studio server later, run:  "%LMS%" server stop
echo ============================================================
echo.

endlocal
pause
