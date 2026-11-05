<#
.SYNOPSIS
    CheckMate AI - one-click launcher with pre-flight checks.

.DESCRIPTION
    1. Verifies project files and backend/.env
    2. Finds the "checkmate-ai" Anaconda environment (creates it if missing), installs the
       CUDA build of PyTorch and any missing packages from backend/requirements.txt, and
       confirms the backend imports and that PyTorch sees the GPU
    3. Checks Node.js and installs frontend dependencies if needed
    4. Reports GPU status (nvidia-smi) and free system RAM
    5. Starts MongoDB if needed: "net start MongoDB" in an administrator window (one UAC prompt);
       a hosted database (MongoDB Atlas, mongodb+srv://...) is only pinged
    6. Starts the LM Studio server and loads the configured vision model
    7. Launches the backend (uvicorn, inside the conda env) and the frontend (vite) in their own windows
    8. Waits for both and runs the backend's /health/full readiness probe
    9. Opens a public tunnel to the backend when TUNNEL_PROVIDER is set in backend/.env
       (ngrok or cloudflared), so a frontend hosted on GitHub Pages can reach this PC
   10. Prints a PASS / WARN / FAIL table and opens the app in the browser

    Double-click Start-CheckMate.bat in the project root to run this.

.PARAMETER NoBrowser      Do not open the browser at the end.
.PARAMETER SkipModelLoad  Only check LM Studio; do not try to load the model.
.PARAMETER ChecksOnly     Run every check but do not launch backend/frontend.
.PARAMETER NoElevate      Never show a UAC prompt (MongoDB must already be running).
.PARAMETER NoInstall      Never install anything (no conda create, pip install or npm install); only report.
.PARAMETER NoRestore      Do not load db-backup\<database>.jsonl.gz into an empty database.
.PARAMETER NoTunnel       Do not open the public tunnel even when TUNNEL_PROVIDER is set.

.NOTES
    Review this script before running it on a new machine. Environment overrides:
      CHECKMATE_CONDA_ROOT  Anaconda/Miniconda root (default: %USERPROFILE%\anaconda3 or miniconda3)
      CHECKMATE_CONDA_ENV   conda env name (default: checkmate-ai)
      CHECKMATE_PYTHON      python.exe to use instead of the conda env
      CHECKMATE_LMS         LM Studio CLI (default: %USERPROFILE%\.lmstudio\bin\lms.exe)
    pip output is also written to logs\pip-install.log.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipModelLoad,
    [switch]$ChecksOnly,
    [switch]$NoElevate,
    [switch]$NoInstall,
    [switch]$NoRestore,
    [switch]$NoTunnel
)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir  = Join-Path $ProjectRoot 'backend'
$FrontendDir = Join-Path $ProjectRoot 'frontend'
$ScriptsDir  = $PSScriptRoot
$LogsDir     = Join-Path $ProjectRoot 'logs'
$PipLog      = Join-Path $LogsDir 'pip-install.log'
$CheckScript = Join-Path $ScriptsDir 'check_env.py'

$BackendPort  = 8000
$FrontendPort = 5173
$BackendUrl   = "http://localhost:$BackendPort"
$FrontendUrl  = "http://localhost:$FrontendPort"

# ───────────────────────────── helpers ──────────────────────────────────────
$Results = New-Object System.Collections.ArrayList
$script:HasFail = $false

function Write-Banner {
    Write-Host ''
    Write-Host '  ╔══════════════════════════════════════════════════════╗' -ForegroundColor Cyan
    Write-Host '  ║            CheckMate AI - one-click launcher          ║' -ForegroundColor Cyan
    Write-Host '  ╚══════════════════════════════════════════════════════╝' -ForegroundColor Cyan
    Write-Host "  Project: $ProjectRoot"
    Write-Host ''
}

function Write-Step($n, $title) {
    Write-Host ("[{0}] {1}" -f $n, $title) -ForegroundColor White
}

function Add-Result($Name, $Status, $Detail) {
    [void]$Results.Add([pscustomobject]@{ Check = $Name; Status = $Status; Detail = $Detail })
    $color = 'Green'
    if ($Status -eq 'WARN') { $color = 'Yellow' }
    if ($Status -eq 'FAIL') { $color = 'Red'; $script:HasFail = $true }
    Write-Host ("      {0,-5} {1}" -f $Status, $Detail) -ForegroundColor $color
}

function Test-Port($HostName, $Port, $TimeoutMs = 1500) {
    # Tries IPv4 and IPv6 loopback explicitly: Vite listens on ::1 only, uvicorn on 0.0.0.0.
    $targets = @()
    if ($HostName -in @('localhost', '127.0.0.1', '::1')) {
        $targets = @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::IPv6Loopback)
    } else {
        try { $targets = [System.Net.Dns]::GetHostAddresses($HostName) } catch { return $false }
    }
    foreach ($ip in $targets) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient($ip.AddressFamily)
            $iar = $client.BeginConnect($ip, [int]$Port, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
            if ($ok -and $client.Connected) { $client.EndConnect($iar); $client.Close(); return $true }
            $client.Close()
        } catch { }
    }
    return $false
}

function Wait-Port($HostName, $Port, $TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $HostName $Port) { return $true }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Get-Json($Url, $TimeoutSec = 5) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec -ErrorAction Stop } catch { return $null }
}

function Wait-Json($Url, $TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $r = Get-Json $Url 3
        if ($null -ne $r) { return $r }
        Start-Sleep -Milliseconds 1000
    }
    return $null
}

function Invoke-Native($Exe, $ArgString) {
    # Runs a native tool through cmd and returns its output; stderr never becomes a PowerShell error record.
    $out = cmd /c "`"$Exe`" $ArgString 2>&1"
    return ($out | Out-String).Trim()
}

function Invoke-Live($Exe, $ArgString, $WorkDir) {
    # Runs a native tool in this console (so pip/npm progress is visible) and returns its exit code.
    $params = @{ FilePath = $Exe; ArgumentList = $ArgString; NoNewWindow = $true; Wait = $true; PassThru = $true }
    if ($WorkDir) { $params['WorkingDirectory'] = $WorkDir }
    try {
        $p = Start-Process @params
        return $p.ExitCode
    } catch {
        Write-Host "      could not run $Exe : $($_.Exception.Message)" -ForegroundColor Red
        return 1
    }
}

function Read-DotEnv($Path) {
    $map = @{}
    if (Test-Path $Path) {
        foreach ($line in Get-Content $Path) {
            $t = $line.Trim()
            if ($t -eq '' -or $t.StartsWith('#')) { continue }
            $idx = $t.IndexOf('=')
            if ($idx -lt 1) { continue }
            $k = $t.Substring(0, $idx).Trim()
            $v = $t.Substring($idx + 1).Trim()
            if ($v.Length -ge 2 -and (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'")))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            $map[$k] = $v
        }
    }
    return $map
}

function Find-First($Candidates) {
    foreach ($c in $Candidates) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-EnvPython {
    # python.exe of the conda env: explicit override, <conda root>\envs\<name>, or an env
    # created elsewhere with --prefix (listed in ~\.conda\environments.txt).
    if ($env:CHECKMATE_PYTHON -and (Test-Path $env:CHECKMATE_PYTHON)) { return $env:CHECKMATE_PYTHON }
    if ($CondaRoot) {
        $p = Join-Path $CondaRoot "envs\$CondaEnvName\python.exe"
        if (Test-Path $p) { return $p }
    }
    $envsTxt = Join-Path $env:USERPROFILE '.conda\environments.txt'
    if (Test-Path $envsTxt) {
        foreach ($line in Get-Content $envsTxt) {
            $t = $line.Trim()
            if ($t -and ((Split-Path -Leaf $t) -ieq $CondaEnvName) -and (Test-Path (Join-Path $t 'python.exe'))) {
                return (Join-Path $t 'python.exe')
            }
        }
    }
    return $null
}

function Find-Tool($Name, $Candidates) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($c in @($Candidates)) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

function Test-PublicHealth($Url, $TimeoutSec) {
    # GET <url>/health through the tunnel until it answers JSON. The header makes ngrok's
    # free plan skip its browser warning page.
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri "$Url/health" -TimeoutSec 8 -Headers @{ 'ngrok-skip-browser-warning' = '1' } -ErrorAction Stop
            if ($r -and $r.PSObject.Properties['status']) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Start-Tunnel {
    # Opens the tunnel configured in backend\.env and returns the public https URL of the
    # backend ('' on failure; a Tunnel result line is always recorded).
    if ($TunnelProvider -eq 'ngrok') {
        $exe = Find-Tool 'ngrok' @("$env:LOCALAPPDATA\Microsoft\WinGet\Links\ngrok.exe")
        if (-not $exe) { Add-Result 'Tunnel' 'FAIL' 'ngrok.exe not found. Install: winget install Ngrok.Ngrok   then once: ngrok config add-authtoken <token from dashboard.ngrok.com>'; return '' }
        if (-not $TunnelDomain) { Add-Result 'Tunnel' 'FAIL' 'TUNNEL_DOMAIN is empty - put your ngrok domain (dashboard.ngrok.com -> Domains) into backend\.env'; return '' }
        $api = 'http://127.0.0.1:4040/api/tunnels'
        $t = Get-Json $api 2
        $note = 'already running'
        if ($null -eq $t) {
            Start-Process -FilePath 'cmd.exe' -ArgumentList "/k `"`"$exe`" http $BackendPort --domain=$TunnelDomain`"" -WorkingDirectory $ProjectRoot
            Write-Host "      Starting ngrok for https://$TunnelDomain ..." -ForegroundColor DarkGray
            $deadline = (Get-Date).AddSeconds(25)
            while ((Get-Date) -lt $deadline -and $null -eq $t) { Start-Sleep -Seconds 2; $t = Get-Json $api 2 }
            $note = 'started'
        }
        $url = ''
        if ($t -and $t.tunnels) { $url = (@($t.tunnels) | Where-Object { $_.public_url -like 'https://*' } | Select-Object -First 1).public_url }
        if (-not $url) { Add-Result 'Tunnel' 'FAIL' "ngrok did not come up (see its window). Usually the authtoken is missing (ngrok config add-authtoken <token>) or the domain '$TunnelDomain' does not belong to this account."; return '' }
        if (Test-PublicHealth $url 40) { Add-Result 'Tunnel' 'PASS' "$url -> $BackendUrl ($note, /health answers through it)" }
        else { Add-Result 'Tunnel' 'WARN' "$url is open but /health did not answer through it within 40 s" }
        return $url
    }
    if ($TunnelProvider -eq 'cloudflared') {
        $exe = Find-Tool 'cloudflared' @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe")
        if (-not $exe) { Add-Result 'Tunnel' 'FAIL' 'cloudflared.exe not found. Install: winget install Cloudflare.cloudflared'; return '' }
        $log = Join-Path $LogsDir 'cloudflared.log'
        if ($TunnelName) {
            if (-not $TunnelDomain) { Add-Result 'Tunnel' 'FAIL' 'TUNNEL_DOMAIN is empty - set it to the public hostname routed to the named tunnel'; return '' }
            $url = "https://$TunnelDomain"
            if (-not (Test-PublicHealth $url 5)) {
                Start-Process -FilePath 'cmd.exe' -ArgumentList "/k `"`"$exe`" tunnel --logfile `"$log`" run $TunnelName`"" -WorkingDirectory $ProjectRoot
                Write-Host "      Starting cloudflared tunnel '$TunnelName' for $url ..." -ForegroundColor DarkGray
            }
            if (Test-PublicHealth $url 60) { Add-Result 'Tunnel' 'PASS' "$url -> $BackendUrl (named tunnel '$TunnelName', /health answers through it)" }
            else { Add-Result 'Tunnel' 'FAIL' "$url did not answer within 60 s (see the cloudflared window and logs\cloudflared.log)" }
            return $url
        }
        # No domain on Cloudflare: a quick tunnel whose address changes on every start.
        Remove-Item $log -Force -ErrorAction SilentlyContinue
        Start-Process -FilePath 'cmd.exe' -ArgumentList "/k `"`"$exe`" tunnel --url $BackendUrl --logfile `"$log`" --loglevel info`"" -WorkingDirectory $ProjectRoot
        Write-Host '      Requesting a quick tunnel (random *.trycloudflare.com address) ...' -ForegroundColor DarkGray
        $url = ''
        $deadline = (Get-Date).AddSeconds(30)
        while ((Get-Date) -lt $deadline -and -not $url) {
            Start-Sleep -Seconds 2
            if (Test-Path $log) {
                $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
                if ($m) { $url = $m.Matches[0].Value }
            }
        }
        if (-not $url) { Add-Result 'Tunnel' 'FAIL' 'cloudflared gave no quick-tunnel address within 30 s (see logs\cloudflared.log)'; return '' }
        if (Test-PublicHealth $url 60) { Add-Result 'Tunnel' 'WARN' "$url -> $BackendUrl (/health answers). This address CHANGES on every start: put it into frontend\.env.production and push, or use ngrok / a Cloudflare domain for a fixed one." }
        else { Add-Result 'Tunnel' 'WARN' "$url created, but /health did not answer through it within 60 s (DNS may still be propagating)" }
        return $url
    }
    Add-Result 'Tunnel' 'FAIL' "Unknown TUNNEL_PROVIDER '$TunnelProvider' in backend\.env (use none, ngrok or cloudflared)"
    return ''
}

function Get-CheckJson($Mode, $ArgString) {
    # Runs scripts\check_env.py inside the env and returns its JSON result (or $null).
    $out = Invoke-Native $Python "`"$CheckScript`" $Mode $ArgString"
    $line = ($out -split "`r?`n" | Where-Object { $_ -like 'CHECKENV_JSON:*' } | Select-Object -Last 1)
    if (-not $line) { Write-Host "      check_env.py $Mode gave no result: $out" -ForegroundColor Red; return $null }
    try { return ($line.Substring(14) | ConvertFrom-Json) } catch { Write-Host "      check_env.py $Mode output unreadable: $line" -ForegroundColor Red; return $null }
}

function Install-CudaTorch($Probe) {
    $why = 'torch is not installed'
    if ($Probe -and $Probe.torch) { $why = "torch $($Probe.torch) has no CUDA support" }
    elseif ($Probe -and $Probe.torch_error) { $why = "torch is broken ($($Probe.torch_error))" }
    Write-Host "      $why - installing the CUDA build from backend\requirements-torch-cuda.txt" -ForegroundColor Yellow
    Write-Host '      (about 3 GB download, one time; log: logs\pip-install.log)' -ForegroundColor Yellow
    $rc = Invoke-Live $Python "-m pip install -r `"$ReqCuda`" --log `"$PipLog`""
    if ($rc -ne 0) { Write-Host "      pip exit code $rc - see logs\pip-install.log" -ForegroundColor Red; return }
    $after = Get-CheckJson 'gpu'
    if ($after -and $after.torchaudio -and -not $after.torchaudio_ok) {
        # torchaudio is version-locked to torch, has no cu126 Windows build and CheckMate does not use it.
        Write-Host "      Removing torchaudio $($after.torchaudio) (no longer loads with this torch; not needed)..." -ForegroundColor DarkGray
        Invoke-Native $Python '-m pip uninstall -y torchaudio' | Out-Null
    }
}

# ───────────────────────────── start ────────────────────────────────────────
Write-Banner
$StartedAt = Get-Date
New-Item -ItemType Directory -Force $LogsDir | Out-Null

# [1] Project files + config ---------------------------------------------------
Write-Step 1 'Project files and configuration'
$missing = @()
foreach ($f in @("$BackendDir\main.py", "$BackendDir\requirements.txt", "$FrontendDir\package.json", "$ScriptsDir\run-backend.cmd", "$ScriptsDir\run-frontend.cmd", "$ScriptsDir\tee_run.py", $CheckScript)) {
    if (-not (Test-Path $f)) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Add-Result 'Project files' 'FAIL' ("Missing: " + ($missing -join ', '))
} else {
    Add-Result 'Project files' 'PASS' 'backend/, frontend/, scripts/ present'
}

$EnvFile = Join-Path $BackendDir '.env'
if (-not (Test-Path $EnvFile)) {
    $example = Join-Path $BackendDir '.env.example'
    if (Test-Path $example) {
        Copy-Item $example $EnvFile
        Add-Result 'backend/.env' 'WARN' 'Created from .env.example - set JWT_SECRET before sharing this server'
    } else {
        Add-Result 'backend/.env' 'FAIL' '.env and .env.example both missing'
    }
} else {
    Add-Result 'backend/.env' 'PASS' 'found'
}
$Cfg = Read-DotEnv $EnvFile
$MongoUri   = if ($Cfg['MONGO_URI']) { $Cfg['MONGO_URI'] } else { 'mongodb://localhost:27017' }
# The backend lets a real environment variable win over .env, so do the same here.
$DbName     = if ($env:DATABASE_NAME) { $env:DATABASE_NAME } elseif ($Cfg['DATABASE_NAME']) { $Cfg['DATABASE_NAME'] } else { 'checkmate_ai' }
$LmUrl      = if ($Cfg['LM_STUDIO_URL']) { $Cfg['LM_STUDIO_URL'] } else { 'http://localhost:1234/v1/chat/completions' }
$LmModel    = if ($Cfg['LM_STUDIO_MODEL']) { $Cfg['LM_STUDIO_MODEL'] } else { '' }
$OcrBackend = if ($Cfg['OCR_BACKEND']) { $Cfg['OCR_BACKEND'] } else { 'lmstudio' }
$LmContext  = if ($Cfg['LM_STUDIO_CONTEXT_LENGTH']) { [int]$Cfg['LM_STUDIO_CONTEXT_LENGTH'] } else { 16384 }
$TunnelProvider = if ($Cfg['TUNNEL_PROVIDER']) { $Cfg['TUNNEL_PROVIDER'].Trim().ToLower() } else { 'none' }
$TunnelDomain   = if ($Cfg['TUNNEL_DOMAIN']) { ($Cfg['TUNNEL_DOMAIN'].Trim() -replace '^https?://', '').TrimEnd('/') } else { '' }
$TunnelName     = if ($Cfg['TUNNEL_NAME']) { $Cfg['TUNNEL_NAME'].Trim() } else { '' }
$PublicApi      = ''
$LmBase = $LmUrl
if ($LmUrl -match '^(https?://[^/]+)') { $LmBase = $Matches[1] }
Write-Host "      LM Studio: $LmBase | model: $(if ($LmModel) { $LmModel } else { '(server default)' }) | OCR: $OcrBackend" -ForegroundColor DarkGray

# [2] Python environment -------------------------------------------------------
$CondaEnvName = if ($env:CHECKMATE_CONDA_ENV) { $env:CHECKMATE_CONDA_ENV } else { 'checkmate-ai' }
Write-Step 2 "Python environment (Anaconda env `"$CondaEnvName`")"
$condaActivate = Find-First @(
    $(if ($env:CHECKMATE_CONDA_ROOT) { Join-Path $env:CHECKMATE_CONDA_ROOT 'Scripts\activate.bat' }),
    "$env:USERPROFILE\anaconda3\Scripts\activate.bat",
    "$env:USERPROFILE\miniconda3\Scripts\activate.bat",
    "$env:LOCALAPPDATA\anaconda3\Scripts\activate.bat",
    "$env:LOCALAPPDATA\miniconda3\Scripts\activate.bat",
    'C:\ProgramData\anaconda3\Scripts\activate.bat',
    'C:\ProgramData\miniconda3\Scripts\activate.bat'
)
$CondaRoot = $null
if ($condaActivate) { $CondaRoot = Split-Path -Parent (Split-Path -Parent $condaActivate) }
if ($CondaRoot) { Write-Host "      Anaconda: $CondaRoot" -ForegroundColor DarkGray }

$Python = Resolve-EnvPython
if (-not $Python -and $CondaRoot -and -not $NoInstall) {
    Write-Host "      Env '$CondaEnvName' not found under $CondaRoot\envs - creating it with Python 3.11 (one time, 1-2 min)..." -ForegroundColor Yellow
    $rc = Invoke-Live 'cmd.exe' "/c `"`"$CondaRoot\condabin\conda.bat`" create -y -n $CondaEnvName python=3.11`""
    if ($rc -ne 0) { Write-Host "      conda create failed with exit code $rc" -ForegroundColor Red }
    $Python = Resolve-EnvPython
}

$ReqFile = Join-Path $BackendDir 'requirements.txt'
$ReqCuda = Join-Path $BackendDir 'requirements-torch-cuda.txt'
$HasNvidia = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$gpuEnv = $null

if (-not $Python) {
    if ($CondaRoot) {
        Add-Result 'Python env' 'FAIL' "conda env '$CondaEnvName' not found under $CondaRoot\envs (run without -NoInstall to create it, or set CHECKMATE_PYTHON)"
    } else {
        Add-Result 'Python env' 'FAIL' 'Anaconda/Miniconda not found. Install it (https://www.anaconda.com/download) or set CHECKMATE_CONDA_ROOT / CHECKMATE_PYTHON'
    }
} else {
    $pyVer = Invoke-Native $Python '-c "import sys; print(sys.version.split()[0])"'
    Write-Host "      Python $pyVer : $Python" -ForegroundColor DarkGray

    # 2a. CUDA PyTorch first. chandra-ocr[hf] (requirements.txt) needs torch >= 2.8 and the torch
    #     on PyPI is CPU-only on Windows, so the CUDA wheels must be in place before pip resolves it.
    $gpuEnv = Get-CheckJson 'gpu'
    if ($HasNvidia -and (Test-Path $ReqCuda) -and -not $NoInstall -and (-not $gpuEnv -or -not $gpuEnv.cuda)) {
        Install-CudaTorch $gpuEnv
        $gpuEnv = Get-CheckJson 'gpu'
    }

    # 2b. requirements.txt (direct lines + their dependencies, including extras)
    $req = Get-CheckJson 'requirements' "`"$ReqFile`""
    $reqMissing = @()
    if ($req) { $reqMissing = @($req.missing) }
    if ($reqMissing.Count -gt 0) {
        Write-Host "      Missing or outdated: $($reqMissing -join '; ')" -ForegroundColor Yellow
        if ($NoInstall) {
            Write-Host '      -NoInstall given: not installing.' -ForegroundColor Yellow
        } else {
            Write-Host '      Running pip install -r backend\requirements.txt (log: logs\pip-install.log)...' -ForegroundColor Yellow
            $rc = Invoke-Live $Python "-m pip install -r `"$ReqFile`" --log `"$PipLog`""
            if ($rc -ne 0) { Write-Host "      pip exit code $rc - see logs\pip-install.log" -ForegroundColor Red }
            $req = Get-CheckJson 'requirements' "`"$ReqFile`""
            $reqMissing = @()
            if ($req) { $reqMissing = @($req.missing) }
            # pip may have swapped torch for the CPU build while resolving - put the CUDA build back.
            $gpuEnv = Get-CheckJson 'gpu'
            if ($HasNvidia -and (Test-Path $ReqCuda) -and $gpuEnv -and -not $gpuEnv.cuda) {
                Install-CudaTorch $gpuEnv
                $gpuEnv = Get-CheckJson 'gpu'
            }
        }
    }

    # 2c. can the backend import everything it needs?
    $mods = @('fastapi', 'uvicorn', 'motor', 'pymongo', 'httpx', 'PIL', 'dotenv', 'jose', 'passlib', 'multipart', 'pydantic', 'fitz', 'pypdfium2')
    if ($OcrBackend -eq 'chandra') { $mods += @('torch', 'transformers', 'chandra') }
    $imp = Get-CheckJson 'imports' ($mods -join ' ')
    if ($imp -and $imp.ok) {
        if ($reqMissing.Count -gt 0) {
            Add-Result 'Python env' 'WARN' "Python $pyVer at $Python - imports OK but pip still reports: $($reqMissing -join '; ')"
        } else {
            Add-Result 'Python env' 'PASS' "Python $pyVer, requirements.txt satisfied ($Python)"
        }
    } else {
        $what = 'check_env.py did not run'
        if ($imp) { $what = (@($imp.missing) -join '; ') }
        Add-Result 'Python env' 'FAIL' "Backend imports fail: $what. Run: `"$Python`" -m pip install -r backend\requirements.txt"
    }

    # 2d. GPU as seen from inside the env
    if (-not $gpuEnv) {
        Add-Result 'PyTorch CUDA' 'WARN' 'could not probe torch (see messages above)'
    } elseif ($gpuEnv.cuda) {
        Add-Result 'PyTorch CUDA' 'PASS' "torch $($gpuEnv.torch) uses $($gpuEnv.device) (CUDA $($gpuEnv.cuda_version))"
    } elseif ($gpuEnv.torch) {
        Add-Result 'PyTorch CUDA' 'WARN' "torch $($gpuEnv.torch) is installed but sees no GPU - only matters for OCR_BACKEND=chandra (LM Studio uses the GPU on its own)"
    } else {
        Add-Result 'PyTorch CUDA' 'WARN' "torch not usable: $($gpuEnv.torch_error) - only matters for OCR_BACKEND=chandra"
    }
}

# [3] Node.js ------------------------------------------------------------------
Write-Step 3 'Node.js and frontend dependencies'
$NodeExe = Get-Command node -ErrorAction SilentlyContinue
$NpmCmd  = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NodeExe -or -not $NpmCmd) {
    Add-Result 'Node.js' 'FAIL' 'node / npm not on PATH. Install Node.js 18+ from https://nodejs.org'
} else {
    $nodeVer = (& node --version)
    if (-not (Test-Path "$FrontendDir\node_modules\vite")) {
        if ($NoInstall) {
            Write-Host '      node_modules missing (-NoInstall given: not running npm install)' -ForegroundColor Yellow
        } else {
            Write-Host '      node_modules missing - running npm install (first run only, may take a few minutes)...' -ForegroundColor Yellow
            Invoke-Live $NpmCmd.Source 'install' $FrontendDir | Out-Null
        }
    }
    if (Test-Path "$FrontendDir\node_modules\vite") {
        Add-Result 'Node.js' 'PASS' "node $nodeVer, frontend dependencies installed"
    } else {
        Add-Result 'Node.js' 'FAIL' "frontend dependencies missing - run npm install in $FrontendDir"
    }
}

# [4] GPU ----------------------------------------------------------------------
Write-Step 4 'GPU status'
if (-not $HasNvidia) {
    Add-Result 'GPU' 'WARN' 'nvidia-smi not found - LM Studio will run on CPU (very slow)'
} else {
    $gpuLine = (cmd /c "nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,driver_version --format=csv,noheader,nounits 2>&1" | Select-Object -First 1)
    if ($gpuLine -and $gpuLine -notmatch 'error|failed|not found') {
        $parts = $gpuLine -split ','
        $gpuName = $parts[0].Trim(); $memTotal = [int]$parts[1]; $memUsed = [int]$parts[2]; $memFree = [int]$parts[3]; $drv = $parts[4].Trim()
        $detail = "$gpuName - $memFree MiB free of $memTotal MiB (driver $drv)"
        if ($memFree -lt 4000) {
            Add-Result 'GPU' 'WARN' "$detail. Less than 4 GB free: the 7B vision model will be partly offloaded to CPU (slow). Close other GPU apps."
        } else {
            Add-Result 'GPU' 'PASS' $detail
        }
    } else {
        Add-Result 'GPU' 'WARN' "nvidia-smi gave no usable output: $gpuLine"
    }
}
$osInfo = Get-CimInstance Win32_OperatingSystem
$ramFreeGb = [math]::Round($osInfo.FreePhysicalMemory / 1MB, 1)
$ramTotalGb = [math]::Round($osInfo.TotalVisibleMemorySize / 1MB, 1)
if ($ramFreeGb -lt 2) {
    Add-Result 'System RAM' 'WARN' "$ramFreeGb GB free of $ramTotalGb GB. The vision model plus backend need several GB; close other apps or grading will be slow / may fail."
} else {
    Add-Result 'System RAM' 'PASS' "$ramFreeGb GB free of $ramTotalGb GB"
}

# [5] MongoDB ------------------------------------------------------------------
Write-Step 5 'MongoDB'
$mongoHost = 'localhost'; $mongoPort = 27017
if ($MongoUri -match '^mongodb(\+srv)?://(?:[^@/]+@)?([^:/,?]+)(?::(\d+))?') {
    $mongoHost = $Matches[2]
    if ($Matches[3]) { $mongoPort = [int]$Matches[3] }
}
# A hosted database (MongoDB Atlas, mongodb+srv://...) is not a local service: there is
# nothing to start and no single port to probe, so only the ping below counts.
$mongoRemote = ($MongoUri -like 'mongodb+srv://*') -or ($mongoHost -notin @('localhost', '127.0.0.1'))
$mongoWhere  = if ($mongoRemote) { "$mongoHost (hosted)" } else { "${mongoHost}:${mongoPort}" }
if ($mongoRemote) {
    $mongoUp = $true; $mongoNote = 'hosted database, nothing to start'
} else {
    $mongoUp = Test-Port $mongoHost $mongoPort; $mongoNote = 'already running'
}
if (-not $mongoUp -and $mongoHost -in @('localhost', '127.0.0.1')) {
    $svc = Get-Service -Name 'MongoDB' -ErrorAction SilentlyContinue
    if ($svc) {
        if ($svc.Status -ne 'Running') {
            # The service runs as NetworkService with data under Program Files: starting it
            # needs administrator rights, i.e. "net start MongoDB" from an elevated cmd.
            if (Test-IsAdmin) {
                Write-Host '      MongoDB service is stopped - running: net start MongoDB' -ForegroundColor Yellow
                $out = Invoke-Native 'net' 'start MongoDB'
                Write-Host "      $out" -ForegroundColor DarkGray
                $mongoNote = 'started with "net start MongoDB"'
            } elseif ($NoElevate) {
                $mongoNote = 'service is stopped; -NoElevate given. Open cmd as administrator and run: net start MongoDB'
            } else {
                Write-Host '      MongoDB service is stopped - running "net start MongoDB" in an administrator window. Approve the UAC prompt.' -ForegroundColor Yellow
                try {
                    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'net start MongoDB && timeout /t 3 || pause' -Verb RunAs -Wait -ErrorAction Stop
                    $mongoNote = 'started with "net start MongoDB" (administrator window)'
                } catch {
                    $mongoNote = 'UAC prompt declined. Open cmd as administrator and run: net start MongoDB'
                }
            }
        } else {
            $mongoNote = 'service is running, waited for the port'
        }
        $mongoUp = Wait-Port $mongoHost $mongoPort 30
    } else {
        $mongod = Get-ChildItem 'C:\Program Files\MongoDB\Server\*\bin\mongod.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($mongod) {
            $dataDir = Join-Path $env:LOCALAPPDATA 'CheckMateAI\mongodb-data'
            New-Item -ItemType Directory -Force $dataDir | Out-Null
            Write-Host "      No MongoDB service registered - starting mongod.exe with data dir $dataDir" -ForegroundColor Yellow
            Start-Process -FilePath $mongod.FullName -ArgumentList "--dbpath `"$dataDir`" --port $mongoPort --bind_ip 127.0.0.1" -WindowStyle Minimized
            $mongoUp = Wait-Port $mongoHost $mongoPort 25
            $mongoNote = "started mongod.exe manually (data in $dataDir)"
        }
    }
}
if (-not $mongoUp) {
    Add-Result 'MongoDB' 'FAIL' "Nothing listening on ${mongoHost}:${mongoPort} ($mongoNote). Start the service from an administrator cmd with: net start MongoDB  - last crash reason is in C:\Program Files\MongoDB\Server\<ver>\log\mongod.log"
} elseif ($Python) {
    # check_env.py reads MONGO_URI from backend\.env itself, so a database password never
    # appears on a command line.
    $mongoProbe = Get-CheckJson 'mongo' $DbName
    if ($mongoProbe -and $mongoProbe.ok) {
        Add-Result 'MongoDB' 'PASS' "ping OK on $mongoWhere (server $($mongoProbe.version), $mongoNote)"
        # A backup that travels with the project (scripts\db_backup.py) is loaded once, into an
        # EMPTY database only, so a copied project starts with its accounts and data.
        $BackupFile = Join-Path $ProjectRoot "db-backup\$DbName.jsonl.gz"
        if (-not $NoRestore -and (Test-Path $BackupFile)) {
            $docs = [string]$mongoProbe.documents
            if ($docs -eq '0') {
                Write-Host "      Database '$DbName' is empty - loading db-backup\$DbName.jsonl.gz ..." -ForegroundColor Yellow
                $restoreOut = Invoke-Native $Python "`"$ScriptsDir\db_restore.py`" --db $DbName --yes"
                $last = ($restoreOut -split "`r?`n" | Where-Object { $_ -match '^(restored|merged|error)' } | Select-Object -Last 1)
                if ($LASTEXITCODE -eq 0) {
                    Add-Result 'DB restore' 'PASS' "$last (from db-backup\$DbName.jsonl.gz)"
                } else {
                    Add-Result 'DB restore' 'WARN' "db_restore.py failed: $last"
                }
            } else {
                Write-Host "      db-backup\$DbName.jsonl.gz present but database '$DbName' already has $docs documents - not restoring (use scripts\db_restore.py --replace or --merge)." -ForegroundColor DarkGray
            }
        }
    } else {
        $why  = if ($mongoProbe) { $mongoProbe.error } else { 'check_env.py mongo gave no result' }
        $hint = if ($mongoRemote) { ' Check MONGO_URI in backend\.env, the Atlas Network Access list (allow this PC or 0.0.0.0/0) and the internet connection.' } else { '' }
        Add-Result 'MongoDB' 'FAIL' "ping failed on ${mongoWhere}: $why.$hint"
    }
} else {
    Add-Result 'MongoDB' 'PASS' "port ${mongoPort} open ($mongoNote)"
}

# [6] LM Studio ----------------------------------------------------------------
Write-Step 6 'LM Studio server and vision model'
$Lms = Find-First @($env:CHECKMATE_LMS, "$env:USERPROFILE\.lmstudio\bin\lms.exe")
if (-not $Lms) {
    $lmsCmd = Get-Command lms -ErrorAction SilentlyContinue
    if ($lmsCmd) { $Lms = $lmsCmd.Source }
}
$lmModels = Get-Json "$LmBase/api/v0/models" 4
if ($null -eq $lmModels) {
    if ($Lms) {
        Write-Host '      LM Studio server not running - starting it (lms server start)...' -ForegroundColor Yellow
        Invoke-Native $Lms 'server start' | Out-Null
        $deadline = (Get-Date).AddSeconds(40)
        while ((Get-Date) -lt $deadline -and $null -eq $lmModels) {
            Start-Sleep -Seconds 2
            $lmModels = Get-Json "$LmBase/api/v0/models" 4
        }
    }
}
if ($null -eq $lmModels) {
    Add-Result 'LM Studio' 'FAIL' "No LM Studio server at $LmBase. Install LM Studio (https://lmstudio.ai), open it once, then re-run. CLI expected at $env:USERPROFILE\.lmstudio\bin\lms.exe"
} else {
    $all = @($lmModels.data)
    $loaded = @($all | Where-Object { $_.state -eq 'loaded' })
    $wantLoaded = $false
    if ($LmModel) { $wantLoaded = @($loaded | Where-Object { $_.id -eq $LmModel }).Count -gt 0 } else { $wantLoaded = $loaded.Count -gt 0 }

    if (-not $wantLoaded -and $LmModel -and -not $SkipModelLoad -and $Lms) {
        $available = @($all | Where-Object { $_.id -eq $LmModel }).Count -gt 0
        if (-not $available) {
            Add-Result 'LM Studio' 'FAIL' "Model '$LmModel' is not downloaded. Run: lms get $LmModel  (or change LM_STUDIO_MODEL in backend/.env). Downloaded: $(($all | ForEach-Object { $_.id }) -join ', ')"
        } else {
            Write-Host "      Loading model $LmModel (this can take 1-3 minutes)..." -ForegroundColor Yellow
            $loadOut = Invoke-Native $Lms "load `"$LmModel`" -y --context-length $LmContext"
            $lmModels = Get-Json "$LmBase/api/v0/models" 10
            if ($lmModels) {
                $all = @($lmModels.data)
                $loaded = @($all | Where-Object { $_.state -eq 'loaded' })
                $wantLoaded = @($loaded | Where-Object { $_.id -eq $LmModel }).Count -gt 0
            }
            if (-not $wantLoaded) {
                Add-Result 'LM Studio' 'FAIL' "Could not load '$LmModel': $(($loadOut -split "`n" | Select-Object -Last 2) -join ' ')"
            }
        }
    }
    if ($wantLoaded) {
        $names = ($loaded | ForEach-Object { $_.id }) -join ', '
        $vision = @($loaded | Where-Object { $_.type -eq 'vlm' }).Count -gt 0
        $ctx = ($loaded | Select-Object -First 1).loaded_context_length
        $ctxNote = ''
        if ($ctx) {
            $ctxNote = ", context $ctx"
            if ([int]$ctx -lt 8192) { $ctxNote += " (small: multi-page PDFs may overflow; unload and let the launcher reload with $LmContext)" }
        }
        if ($vision) {
            Add-Result 'LM Studio' 'PASS' "server at $LmBase, loaded: $names$ctxNote"
        } else {
            Add-Result 'LM Studio' 'WARN' "server at $LmBase, loaded: $names - none is a vision (vlm) model; grading PDFs/images needs one (e.g. qwen/qwen2.5-vl-7b)"
        }
    } elseif ($SkipModelLoad -or -not $LmModel -or -not $Lms) {
        Add-Result 'LM Studio' 'FAIL' "server at $LmBase but no model is loaded. Load one in LM Studio or run: lms load qwen/qwen2.5-vl-7b"
    }
}

if ($ChecksOnly) {
    Write-Host ''
    Write-Host '  -ChecksOnly: skipping backend/frontend launch.' -ForegroundColor DarkGray
} else {
    # [7] Backend --------------------------------------------------------------
    Write-Step 7 'Backend API (FastAPI / uvicorn in the conda env)'
    if (-not $Python) {
        Add-Result 'Backend' 'FAIL' 'skipped - no Python environment'
    } else {
        $health = Get-Json "$BackendUrl/health" 3
        if ($null -eq $health) {
            if (Test-Port 'localhost' $BackendPort) {
                Add-Result 'Backend' 'FAIL' "Port $BackendPort is in use by something that is not CheckMate. Stop it (scripts\stop-checkmate.ps1) and retry."
            } else {
                # run-backend.cmd activates this env (conda activate) before starting uvicorn
                $env:CHECKMATE_PYTHON = $Python
                $env:CHECKMATE_CONDA_ENV = $CondaEnvName
                if ($CondaRoot) { $env:CHECKMATE_CONDA_ROOT = $CondaRoot }
                Start-Process -FilePath 'cmd.exe' -ArgumentList "/k `"$ScriptsDir\run-backend.cmd`"" -WorkingDirectory $BackendDir
                Write-Host '      Waiting for the backend to come up...' -ForegroundColor DarkGray
                $health = Wait-Json "$BackendUrl/health" 90
            }
        } else {
            Write-Host '      Backend already running - reusing it.' -ForegroundColor DarkGray
        }
        if ($null -ne $health) {
            $full = Get-Json "$BackendUrl/health/full" 20
            if ($null -eq $full) {
                Add-Result 'Backend' 'WARN' "$BackendUrl is up, but /health/full did not answer (older backend?)"
            } else {
                $c = $full.checks
                $bad = @()
                if (-not $c.mongodb.ok) { $bad += "MongoDB: $($c.mongodb.error)" }
                if (-not $c.lm_studio.reachable) { $bad += "LM Studio unreachable: $($c.lm_studio.error)" }
                elseif (-not $c.lm_studio.model_loaded) { $bad += "LM Studio model not loaded (configured: $($c.lm_studio.configured_model))" }
                if (-not $c.ocr.available) { $bad += "OCR: $($c.ocr.detail)" }
                if (-not $c.uploads.writable) { $bad += "uploads dir not writable: $($c.uploads.path)" }
                if ($bad.Count -eq 0) {
                    Add-Result 'Backend' 'PASS' "$BackendUrl - /health/full OK (MongoDB, LM Studio model, OCR=$($c.ocr.backend), uploads)"
                } else {
                    Add-Result 'Backend' 'FAIL' ("$BackendUrl up but not ready: " + ($bad -join '; '))
                }
            }
        } else {
            $tail = ''
            $blog = Join-Path $LogsDir 'backend.log'
            if (Test-Path $blog) { $tail = ' Last log lines: ' + ((Get-Content $blog -Tail 6) -join ' | ') }
            Add-Result 'Backend' 'FAIL' "Backend did not answer on $BackendUrl within 90 s (see logs\backend.log).$tail"
        }
    }

    # [8] Frontend -------------------------------------------------------------
    Write-Step 8 'Frontend (Vite dev server)'
    if (-not $NpmCmd) {
        Add-Result 'Frontend' 'FAIL' 'skipped - npm not available'
    } else {
        if (Test-Port 'localhost' $FrontendPort) {
            Add-Result 'Frontend' 'PASS' "$FrontendUrl already running - reusing it"
        } else {
            Start-Process -FilePath 'cmd.exe' -ArgumentList "/k `"$ScriptsDir\run-frontend.cmd`"" -WorkingDirectory $FrontendDir
            Write-Host '      Waiting for Vite to come up...' -ForegroundColor DarkGray
            if (Wait-Port 'localhost' $FrontendPort 60) {
                Add-Result 'Frontend' 'PASS' "$FrontendUrl"
            } else {
                $tail = ''
                $flog = Join-Path $LogsDir 'frontend.log'
                if (Test-Path $flog) { $tail = ' Last log lines: ' + ((Get-Content $flog -Tail 6) -join ' | ') }
                Add-Result 'Frontend' 'FAIL' "Vite did not open port $FrontendPort within 60 s (see logs\frontend.log).$tail"
            }
        }
    }

    # [9] Public tunnel (optional) ----------------------------------------------
    # Makes the backend on this PC reachable from the internet so a frontend hosted on
    # GitHub Pages can call it. Configured with TUNNEL_PROVIDER / TUNNEL_DOMAIN in backend\.env.
    if ($TunnelProvider -ne 'none' -and -not $NoTunnel) {
        Write-Step 9 "Public tunnel to the backend ($TunnelProvider)"
        $PublicApi = Start-Tunnel
        if ($PublicApi -and -not ($Cfg['CORS_ORIGINS'] -match 'github\.io')) {
            Add-Result 'CORS' 'WARN' 'CORS_ORIGINS in backend\.env has no https://<user>.github.io entry - browsers will block the GitHub Pages frontend.'
        }
    } elseif ($TunnelProvider -ne 'none') {
        Write-Host '  -NoTunnel: not opening the public tunnel.' -ForegroundColor DarkGray
    }
}

# ───────────────────────────── summary ──────────────────────────────────────
$elapsed = [int]((Get-Date) - $StartedAt).TotalSeconds
Write-Host ''
Write-Host '  ──────────────────────────── SUMMARY ────────────────────────────' -ForegroundColor Cyan
foreach ($r in $Results) {
    $color = 'Green'
    if ($r.Status -eq 'WARN') { $color = 'Yellow' }
    if ($r.Status -eq 'FAIL') { $color = 'Red' }
    Write-Host ("  {0,-14} " -f $r.Check) -NoNewline
    Write-Host ("{0,-5}" -f $r.Status) -ForegroundColor $color -NoNewline
    Write-Host ("  {0}" -f $r.Detail)
}
Write-Host '  ─────────────────────────────────────────────────────────────────' -ForegroundColor Cyan
if ($script:HasFail) {
    Write-Host "  SOME CHECKS FAILED ($elapsed s). Fix the FAIL lines above and run again." -ForegroundColor Red
    exit 1
}

if ($ChecksOnly) {
    Write-Host "  ALL CHECKS PASSED ($elapsed s)." -ForegroundColor Green
    exit 0
}

Write-Host "  ALL CHECKS PASSED ($elapsed s) - CheckMate AI is running." -ForegroundColor Green
Write-Host ''
Write-Host "    App       : $FrontendUrl"
Write-Host "    API docs  : $BackendUrl/docs"
Write-Host "    Health    : $BackendUrl/health/full"
Write-Host "    LM Studio : $LmBase"
Write-Host "    MongoDB   : $mongoWhere"
if ($PublicApi) { Write-Host "    Public API: $PublicApi   (tunnel - the address the hosted frontend uses)" }
Write-Host ''
Write-Host '  Backend and frontend run in their own windows. Close them (or run Stop-CheckMate.bat) to stop.' -ForegroundColor DarkGray
if (-not $NoBrowser) { Start-Process $FrontendUrl }
exit 0
