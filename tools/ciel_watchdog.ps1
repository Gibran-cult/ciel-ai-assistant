<#
.SYNOPSIS
Keeps Ciel's backend running on the Langflow host: Ollama, Langflow Desktop
and the ngrok tunnel. Starts whatever is down, in that order.

.DESCRIPTION
Run it every few minutes with Windows Task Scheduler (-Install registers the
task). Each run:

  1. Ollama     GET 127.0.0.1:11434/api/version; starts "ollama app.exe".
  2. Langflow   GET 127.0.0.1:7860/health_check; starts Langflow Desktop. If
                Desktop has been open longer than LangflowGraceSeconds
                (default 10 min; it takes about 5 to boot) and the backend
                is still unhealthy, Desktop and its backend are restarted.
                Desktop does not respawn a dead backend, so a Desktop open
                for BackendSpawnSeconds (5 min) without one is restarted
                right away.
  3. ngrok      the agent's local API (127.0.0.1:4040) must list a tunnel on
                NGROK_URL. Otherwise a stale agent is stopped and ngrok is
                started with the Basic Auth traffic policy, then the public
                URL is checked once: it must answer 401 without credentials.

Checks are local, so a healthy run sends no request through the tunnel and
uses none of ngrok's monthly request quota.

Settings come from the environment, then the repository's .env, then the
defaults below:

  NGROK_URL             public tunnel URL (required, same as the app's)
  NGROK_POLICY_FILE     default %USERPROFILE%\ngrok-ciel-policy.yml
  LANGFLOW_DESKTOP_EXE  default C:\Program Files\Langflow\Langflow .exe
  OLLAMA_APP_EXE        default %LOCALAPPDATA%\Programs\Ollama\ollama app.exe

Log: %USERPROFILE%\.ciel_ai\logs\watchdog.log (rotated at 1 MB).

.EXAMPLE
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1 -Install
powershell -ExecutionPolicy Bypass -File tools\ciel_watchdog.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Install,
    [switch]$Uninstall,
    [int]$IntervalMinutes = 5,
    [int]$LangflowGraceSeconds = 600,
    [int]$BackendSpawnSeconds = 300
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$TaskName = 'Ciel backend watchdog'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $HOME '.ciel_ai\logs'
$LogFile = Join-Path $LogDir 'watchdog.log'
$NgrokLog = Join-Path $LogDir 'ngrok.log'
$LangflowPort = 7860

function Write-Log([string]$Message) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force $LogDir | Out-Null }
    if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 1MB) {
        Move-Item -Force $LogFile "$LogFile.1"
    }
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (Test-Path $Path) {
        foreach ($line in Get-Content $Path) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
                $values[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
            }
        }
    }
    return $values
}

$DotEnv = Read-DotEnv (Join-Path $RepoRoot '.env')

function Get-Setting([string]$Name, [string]$Default = '') {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if (-not $value -and $DotEnv.ContainsKey($Name)) { $value = $DotEnv[$Name] }
    if (-not $value) { $value = $Default }
    return $value
}

function Get-HttpStatus([string]$Url, [hashtable]$Headers = @{}, [int]$TimeoutSec = 5) {
    # Status code, or 0 when nothing answered.
    try {
        return (Invoke-WebRequest $Url -Headers $Headers -UseBasicParsing -TimeoutSec $TimeoutSec).StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

function Wait-For([scriptblock]$Check, [int]$TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (& $Check) { return $true }
        Start-Sleep -Seconds 5
    }
    return (& $Check)
}

# --- Ollama -----------------------------------------------------------------

function Test-Ollama { (Get-HttpStatus 'http://127.0.0.1:11434/api/version') -eq 200 }

function Repair-Ollama {
    if (Test-Ollama) { return $true }
    $exe = Get-Setting 'OLLAMA_APP_EXE' (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe')
    if ($DryRun) { Write-Log "ollama: down, would start $exe"; return $false }
    if (-not (Test-Path $exe)) { Write-Log "ollama: down and $exe not found"; return $false }
    Write-Log 'ollama: down, starting'
    Start-Process -FilePath $exe
    $ok = Wait-For { Test-Ollama } 90
    Write-Log ("ollama: " + $(if ($ok) { 'up' } else { 'still down after 90 s' }))
    return $ok
}

# --- Langflow ---------------------------------------------------------------

function Test-Langflow {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$LangflowPort/health_check" -TimeoutSec 5
        return $health.status -eq 'ok'
    } catch { return $false }
}

function Get-LangflowProcesses([string]$DesktopExe) {
    # Desktop shell plus its backend (langflow.exe / python.exe in the Desktop venv).
    Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -eq $DesktopExe -or $_.CommandLine -like '*com.LangflowDesktop*langflow*run*'
    }
}

function Repair-Langflow {
    if (Test-Langflow) { return $true }
    $exe = Get-Setting 'LANGFLOW_DESKTOP_EXE' 'C:\Program Files\Langflow\Langflow .exe'
    $running = @(Get-LangflowProcesses $exe)

    if ($running.Count -gt 0) {
        # Desktop takes 2 to 5 minutes from launch to a healthy backend, longer
        # than the task interval, so judge by how long its processes have existed.
        $oldest = ($running | Sort-Object CreationDate | Select-Object -First 1).CreationDate
        $age = [int]((Get-Date) - $oldest).TotalSeconds
        $remaining = $LangflowGraceSeconds - $age
        # Desktop does not respawn a backend that died; it starts one within about
        # 3 minutes of launch, so a Desktop older than that without one will not recover.
        $backend = @($running | Where-Object { $_.ExecutablePath -ne $exe })
        if ($backend.Count -eq 0 -and $age -ge $BackendSpawnSeconds) {
            $remaining = 0
            Write-Log "langflow: Desktop open for $age s without a backend"
        }
        if ($remaining -gt 0) {
            Write-Log "langflow: starting for $age s, waiting up to $remaining s"
            $ok = Wait-For { Test-Langflow } $remaining
            Write-Log ("langflow: " + $(if ($ok) { 'up' } else { 'still starting, the next run decides' }))
            return $ok
        }
        # Open longer than the boot window: allow a short blip before restarting.
        if ($backend.Count -gt 0 -and (Wait-For { Test-Langflow } 60)) { Write-Log 'langflow: up'; return $true }
        if ($DryRun) { Write-Log "langflow: unhealthy after $age s, would restart Desktop"; return $false }
        Write-Log "langflow: unhealthy after $age s, stopping Desktop and backend"
        foreach ($p in @(Get-LangflowProcesses $exe)) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 5
    }

    if ($DryRun) { Write-Log "langflow: down, would start $exe"; return $false }
    if (-not (Test-Path $exe)) { Write-Log "langflow: down and $exe not found"; return $false }
    Write-Log 'langflow: starting Desktop'
    Start-Process -FilePath $exe
    $ok = Wait-For { Test-Langflow } $LangflowGraceSeconds
    Write-Log ("langflow: " + $(if ($ok) { 'up' } else { "still down after $LangflowGraceSeconds s" }))
    return $ok
}

# --- ngrok ------------------------------------------------------------------

function Get-NgrokHost([string]$Url) { ([Uri]$Url).Host.ToLowerInvariant() }

function Test-NgrokTunnel([string]$PublicHost) {
    try {
        $tunnels = (Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 5).tunnels
        return [bool]($tunnels | Where-Object { (Get-NgrokHost $_.public_url) -eq $PublicHost })
    } catch { return $false }
}

function Repair-Ngrok {
    $url = Get-Setting 'NGROK_URL'
    if (-not $url) { Write-Log 'ngrok: NGROK_URL is not set (environment or .env), skipping'; return $false }
    $publicHost = Get-NgrokHost $url
    if (Test-NgrokTunnel $publicHost) { return $true }

    $policy = Get-Setting 'NGROK_POLICY_FILE' (Join-Path $HOME 'ngrok-ciel-policy.yml')
    if (-not (Test-Path $policy)) {
        # Never open the tunnel without Basic Auth.
        Write-Log "ngrok: down and policy file $policy not found, not starting an unprotected tunnel"
        return $false
    }
    if ($DryRun) { Write-Log "ngrok: down, would start a tunnel on $publicHost with $policy"; return $false }

    $stale = @(Get-Process ngrok -ErrorAction SilentlyContinue)
    if ($stale.Count -gt 0) {
        # An agent without our tunnel still holds the session; ngrok refuses a second one.
        Write-Log "ngrok: $($stale.Count) agent(s) running without the tunnel, stopping them"
        foreach ($agent in $stale) {
            try {
                Stop-Process -Id $agent.Id -Force -ErrorAction Stop
            } catch {
                # Started from an administrator window; this task runs without admin rights.
                Write-Log "ngrok: cannot stop agent $($agent.Id) (started as administrator?); close it or start ngrok from a normal window"
                return $false
            }
        }
        Start-Sleep -Seconds 3
    }

    Write-Log "ngrok: starting tunnel on $publicHost"
    $arguments = @(
        'http', "http://localhost:$LangflowPort",
        '--url', "https://$publicHost",
        '--traffic-policy-file', "`"$policy`"",
        '--log', "`"$NgrokLog`""
    )
    Start-Process -FilePath 'ngrok' -ArgumentList $arguments -WindowStyle Hidden
    if (-not (Wait-For { Test-NgrokTunnel $publicHost } 60)) {
        Write-Log "ngrok: tunnel did not come up in 60 s, see $NgrokLog"
        return $false
    }

    # One request through the tunnel: without credentials it must be refused.
    $status = Get-HttpStatus "https://$publicHost/health_check" @{ 'ngrok-skip-browser-warning' = '1' } 15
    if ($status -eq 401) {
        Write-Log 'ngrok: up, Basic Auth active'
        return $true
    }
    Write-Log "ngrok: public URL answered $status instead of 401, stopping the tunnel"
    Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    return $false
}

# --- Task Scheduler ---------------------------------------------------------

function Install-Watchdog {
    # conhost --headless keeps the console window from flashing every run.
    $action = New-ScheduledTaskAction -Execute 'conhost.exe' `
        -Argument "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $atLogOn = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $atLogOn.Delay = 'PT1M'
    $repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
    # Langflow Desktop is a windowed app, so the task runs in the user's session.
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($atLogOn, $repeat) `
        -Settings $settings -Principal $principal -Force `
        -Description "Starts Ollama, Langflow Desktop and the ngrok tunnel for Ciel when they are down. Log: $LogFile" | Out-Null
    Write-Log "installed task '$TaskName' (at logon and every $IntervalMinutes min)"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Log "removed task '$TaskName'"
    exit 0
}
if ($Install) {
    Install-Watchdog
    exit 0
}

$ollama = Repair-Ollama
$langflow = Repair-Langflow
$ngrok = if ($langflow) { Repair-Ngrok } else { Write-Log 'ngrok: skipped, Langflow is down'; $false }

if ($ollama -and $langflow -and $ngrok) {
    Write-Verbose 'all healthy'
    exit 0
}
Write-Log ("status: ollama={0} langflow={1} ngrok={2}" -f $ollama, $langflow, $ngrok)
exit 1
