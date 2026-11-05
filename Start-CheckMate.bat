@echo off
rem ============================================================
rem  CheckMate AI — one-click start
rem  Checks MongoDB, LM Studio (+ vision model), GPU, Python, Node,
rem  then launches the backend and frontend and opens the app.
rem  Options (append to the command line):
rem    -NoBrowser  -SkipModelLoad  -ChecksOnly  -NoElevate
rem ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-checkmate.ps1" %*
echo.
pause
