<#
.SYNOPSIS
    Stops the CheckMate AI backend (port 8000), frontend (port 5173), the public
    tunnel (ngrok / cloudflared) if one is open, and unloads the LM Studio model
    to free GPU memory.
    MongoDB (Windows service) and the LM Studio server are left running.

.PARAMETER StopLmServer   Also stop the LM Studio local server.
#>
param(
    [switch]$StopLmServer
)
$ErrorActionPreference = 'Continue'

function Stop-Listener($Port, $Label) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "  $Label : nothing listening on port $Port"; return }
    foreach ($pid_ in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $p = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host "  $Label : stopping $($p.ProcessName) (pid $pid_)"
            # Kill the whole tree so the cmd window that hosts it closes too.
            cmd /c "taskkill /PID $pid_ /T /F >nul 2>&1"
        }
    }
}

Write-Host ''
Write-Host '  Stopping CheckMate AI...' -ForegroundColor Cyan
Stop-Listener 8000 'Backend '
Stop-Listener 5173 'Frontend'

$Lms = if ($env:CHECKMATE_LMS) { $env:CHECKMATE_LMS } else { "$env:USERPROFILE\.lmstudio\bin\lms.exe" }
if (Test-Path $Lms) {
    Write-Host '  LM Studio: unloading models'
    cmd /c "`"$Lms`" unload --all 2>&1" | Out-Null
    if ($StopLmServer) {
        Write-Host '  LM Studio: stopping server'
        cmd /c "`"$Lms`" server stop 2>&1" | Out-Null
    }
}
foreach ($name in @('ngrok', 'cloudflared')) {
    foreach ($p in @(Get-Process -Name $name -ErrorAction SilentlyContinue)) {
        Write-Host "  Tunnel   : stopping $name (pid $($p.Id))"
        cmd /c "taskkill /PID $($p.Id) /T /F >nul 2>&1"
    }
}
Write-Host '  Done. (MongoDB service left running.)' -ForegroundColor Green
