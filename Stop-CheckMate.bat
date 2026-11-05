@echo off
rem Stops the CheckMate AI backend + frontend and unloads the LM Studio model.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-checkmate.ps1" %*
echo.
pause
