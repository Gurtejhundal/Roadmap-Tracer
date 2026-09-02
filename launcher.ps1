param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$NoBrowser
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

if ($Start -and $Stop) {
    Write-Error "Choose either -Start or -Stop, not both."
    exit 1
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$BackendVenvDir = Join-Path $BackendDir ".venv"
$FrontendDir = Join-Path $Root "frontend"
$AppUrl = "http://127.0.0.1:5173"
$BackendHealthUrl = "http://127.0.0.1:8000/"
$BackendHealthMarker = '"message":"Welcome to Roadmap Tracer API"'
$FrontendHealthUrl = $AppUrl
$FrontendHealthMarker = "<title>Traqo</title>"
$LogRoot = if ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA "Traqo\logs"
} else {
    Join-Path $env:TEMP "Traqo\logs"
}
$BackendOutLog = Join-Path $LogRoot "backend.out.log"
$BackendErrLog = Join-Path $LogRoot "backend.err.log"
$FrontendOutLog = Join-Path $LogRoot "frontend.out.log"
$FrontendErrLog = Join-Path $LogRoot "frontend.err.log"
$BackendPidFile = Join-Path $LogRoot "backend.pid"
$FrontendPidFile = Join-Path $LogRoot "frontend.pid"
$BackendDependencyStamp = Join-Path $LogRoot "backend-dependencies.json"
$FrontendDependencyStamp = Join-Path $LogRoot "frontend-dependencies.json"
$script:StatusBox = $null
$script:PythonExe = $null
$script:PythonRuntime = $null
$script:NodeExe = $null
$script:NodeVersion = $null
$script:NpmExe = $null
$script:NpmVersion = $null

function Write-LauncherStatus {
    param([string]$Message)

    $timestamp = Get-Date -Format "HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line

    if ($null -ne $script:StatusBox -and -not $script:StatusBox.IsDisposed) {
        $script:StatusBox.AppendText("$line`r`n")
        $script:StatusBox.SelectionStart = $script:StatusBox.TextLength
        $script:StatusBox.ScrollToCaret()
        [System.Windows.Forms.Application]::DoEvents()
    }
}

function Test-AppFolders {
    if (-not (Test-Path (Join-Path $BackendDir "main.py"))) {
        throw "Backend folder not found: $BackendDir"
    }

    if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
        throw "Frontend folder not found: $FrontendDir"
    }
}

function Resolve-LauncherCommands {
    param(
        [switch]$NeedBackend,
        [switch]$NeedFrontend
    )

    if ($NeedBackend) {
        $venvPython = Join-Path $BackendVenvDir "Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $venvPython)) {
            $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
            if (-not $pythonCommand) {
                throw "Python was not found. Install Python 3.11+ and enable 'Add Python to PATH'."
            }

            $basePythonInfoJson = & $pythonCommand.Source -c "import json, sys; print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3]))}))"
            if ($LASTEXITCODE -ne 0) {
                throw "Python could not report its runtime information."
            }
            $basePythonVersion = [Version](($basePythonInfoJson | ConvertFrom-Json).version)
            if ($basePythonVersion -lt [Version]"3.11.0") {
                throw "Traqo requires Python 3.11 or newer. Found $basePythonVersion."
            }

            Write-LauncherStatus "Creating an isolated backend environment..."
            & $pythonCommand.Source -m venv $BackendVenvDir
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
                throw "Traqo could not create its backend environment at $BackendVenvDir."
            }
        }

        $script:PythonExe = $venvPython
        $pythonInfoJson = & $script:PythonExe -c "import json, sys; print(json.dumps({'executable': sys.executable, 'prefix': sys.prefix, 'version': '.'.join(map(str, sys.version_info[:3]))}))"
        if ($LASTEXITCODE -ne 0) {
            throw "Traqo's backend environment is not usable. Remove $BackendVenvDir and run the launcher again."
        }
        $script:PythonRuntime = $pythonInfoJson | ConvertFrom-Json
        $pythonVersion = [Version]$script:PythonRuntime.version
        if ($pythonVersion -lt [Version]"3.11.0") {
            throw "Traqo requires Python 3.11 or newer. Recreate $BackendVenvDir with a supported Python version."
        }
        $script:PythonExe = [System.IO.Path]::GetFullPath([string]$script:PythonRuntime.executable)
    }

    if ($NeedFrontend) {
        $nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue
        $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
        if (-not $nodeCommand -or -not $npmCommand) {
            throw "Node.js and npm were not found. Install Node.js 20.19+ or 22.12+, then run the launcher again."
        }

        $script:NodeExe = [System.IO.Path]::GetFullPath($nodeCommand.Source)
        $script:NpmExe = [System.IO.Path]::GetFullPath($npmCommand.Source)
        $script:NodeVersion = [string](& $script:NodeExe -p "process.versions.node")
        if ($LASTEXITCODE -ne 0) {
            throw "Node.js could not report its version."
        }
        $nodeVersion = [Version]($script:NodeVersion.Trim().Split('-')[0])
        $nodeSupported = (
            ($nodeVersion.Major -eq 20 -and $nodeVersion -ge [Version]"20.19.0") -or
            ($nodeVersion -ge [Version]"22.12.0")
        )
        if (-not $nodeSupported) {
            throw "Traqo requires Node.js 20.19+ or 22.12+. Found $nodeVersion."
        }

        $script:NpmVersion = [string](& $script:NpmExe --version)
        if ($LASTEXITCODE -ne 0) {
            throw "npm could not report its version."
        }
        $script:NodeVersion = $script:NodeVersion.Trim()
        $script:NpmVersion = $script:NpmVersion.Trim()
    }
}

function Test-ServiceReady {
    param(
        [string]$Url,
        [string]$ExpectedMarker
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return (
            $response.StatusCode -ge 200 -and
            $response.StatusCode -lt 300 -and
            [string]$response.Content -like "*$ExpectedMarker*"
        )
    } catch {
        return $false
    }
}

function Get-PortListener {
    param([int]$Port)

    try {
        return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
    } catch {
        return $null
    }
}

function Assert-PortAvailable {
    param(
        [int]$Port,
        [string]$ServiceName,
        [string]$HealthUrl,
        [string]$HealthMarker
    )

    $listener = Get-PortListener $Port
    if ($listener) {
        $processName = "unknown process"
        try {
            $processName = (Get-Process -Id $listener.OwningProcess -ErrorAction Stop).ProcessName
        } catch {}

        throw "$ServiceName cannot start because port $Port is already used by $processName (PID $($listener.OwningProcess)). Close that process and retry."
    }
}

function Get-BackendSourceHash {
    $excludedNames = @("check_db.py", "conftest.py")
    $runtimeFiles = Get-ChildItem -LiteralPath $BackendDir -Filter "*.py" -File |
        Where-Object { $_.Name -notlike "test_*.py" -and $_.Name -notin $excludedNames } |
        Sort-Object Name
    if ($runtimeFiles.Count -eq 0) {
        throw "No backend runtime modules were found in $BackendDir."
    }

    $entries = foreach ($file in $runtimeFiles) {
        "$($file.Name):$((Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash)"
    }
    $payload = [System.Text.Encoding]::UTF8.GetBytes(($entries -join "`n"))
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha256.ComputeHash($payload))).Replace("-", "")
    } finally {
        $sha256.Dispose()
    }
}

function Get-FrontendDependencyFingerprint {
    $manifest = Join-Path $FrontendDir "package.json"
    $lockFile = Join-Path $FrontendDir "package-lock.json"
    return [ordered]@{
        project_root = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
        node_executable = $script:NodeExe
        node_version = $script:NodeVersion
        npm_executable = $script:NpmExe
        npm_version = $script:NpmVersion
        package_json_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifest).Hash
        package_lock_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $lockFile).Hash
    }
}

function Get-BackendDependencyFingerprint {
    $requirements = Join-Path $BackendDir "requirements.txt"
    $pipVersion = [string](& $script:PythonExe -m pip --version)
    if ($LASTEXITCODE -ne 0) {
        throw "pip is not available for $($script:PythonExe)."
    }
    return [ordered]@{
        project_root = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
        python_executable = $script:PythonExe
        python_version = [string]$script:PythonRuntime.version
        python_prefix = [string]$script:PythonRuntime.prefix
        pip_version = $pipVersion.Trim()
        requirements_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $requirements).Hash
        backend_source_sha256 = Get-BackendSourceHash
    }
}

function Test-DependencyFingerprint {
    param(
        [System.Collections.IDictionary]$Expected,
        [string]$StampFile
    )

    if (-not (Test-Path -LiteralPath $StampFile)) {
        return $false
    }
    try {
        $saved = Get-Content -Raw -LiteralPath $StampFile | ConvertFrom-Json
        $savedJson = $saved | ConvertTo-Json -Compress
        $expectedJson = $Expected | ConvertTo-Json -Compress
        return $savedJson -eq $expectedJson
    } catch {
        return $false
    }
}

function Save-DependencyFingerprint {
    param(
        [System.Collections.IDictionary]$Fingerprint,
        [string]$StampFile
    )

    $Fingerprint | ConvertTo-Json | Set-Content -LiteralPath $StampFile -Encoding UTF8
}

function Test-FrontendDependencies {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        return $false
    }
    Push-Location $FrontendDir
    try {
        & $script:NpmExe ls --depth=0 --silent *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        Pop-Location
    }
}

function Ensure-FrontendDependencies {
    $fingerprint = Get-FrontendDependencyFingerprint
    $isCurrent = (Test-DependencyFingerprint $fingerprint $FrontendDependencyStamp) -and (Test-FrontendDependencies)
    if ($isCurrent) {
        return
    }

    Write-LauncherStatus "Installing frontend dependencies. This can take a few minutes..."
    Push-Location $FrontendDir
    try {
        & $script:NpmExe ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
    if (-not (Test-FrontendDependencies)) {
        throw "Frontend dependencies are incomplete after npm ci."
    }
    Save-DependencyFingerprint (Get-FrontendDependencyFingerprint) $FrontendDependencyStamp
}

function Test-BackendDependencies {
    $requirements = Join-Path $BackendDir "requirements.txt"
    $versionCheck = @'
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

problems = []
for raw_line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    requirement = raw_line.partition('#')[0].strip()
    if not requirement:
        continue
    if '==' not in requirement:
        problems.append(f'unpinned requirement: {requirement}')
        continue
    name, expected = (part.strip() for part in requirement.split('==', 1))
    try:
        actual = version(name)
    except PackageNotFoundError:
        problems.append(f'missing {name}')
        continue
    if actual != expected:
        problems.append(f'{name} {actual} != {expected}')

if problems:
    print('; '.join(problems), file=sys.stderr)
    raise SystemExit(1)
'@

    & $script:PythonExe -c $versionCheck $requirements 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    & $script:PythonExe -m pip check *> $null
    return $LASTEXITCODE -eq 0
}

function Ensure-BackendDependencies {
    $fingerprint = Get-BackendDependencyFingerprint
    $isCurrent = (Test-DependencyFingerprint $fingerprint $BackendDependencyStamp) -and (Test-BackendDependencies)
    if ($isCurrent) {
        return
    }

    Write-LauncherStatus "Installing backend dependencies. This can take a few minutes..."
    & $script:PythonExe -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed with exit code $LASTEXITCODE."
    }
    if (-not (Test-BackendDependencies)) {
        throw "Backend dependency versions are incomplete or inconsistent after installation."
    }
    Save-DependencyFingerprint (Get-BackendDependencyFingerprint) $BackendDependencyStamp
}

function Get-LogFailureDetails {
    param(
        [string]$ServiceName,
        [string]$OutLog,
        [string]$ErrLog
    )

    $details = @()
    if (Test-Path $ErrLog) {
        $details += Get-Content $ErrLog -Tail 12 -ErrorAction SilentlyContinue
    }
    if (($details.Count -eq 0) -and (Test-Path $OutLog)) {
        $details += Get-Content $OutLog -Tail 12 -ErrorAction SilentlyContinue
    }

    if ($details.Count -eq 0) {
        return "$ServiceName stopped before it became ready. See logs in $LogRoot."
    }

    return "$ServiceName stopped before it became ready:`n$($details -join "`n")"
}

function Wait-ServiceReady {
    param(
        [string]$ServiceName,
        [string]$Url,
        [string]$HealthMarker,
        [System.Diagnostics.Process]$Process,
        [string]$OutLog,
        [string]$ErrLog,
        [int]$TimeoutSeconds = 90
    )

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (Test-ServiceReady $Url $HealthMarker) {
            Write-LauncherStatus "$ServiceName is ready."
            return
        }

        if ($null -ne $Process -and $Process.HasExited) {
            throw (Get-LogFailureDetails $ServiceName $OutLog $ErrLog)
        }

        if ($null -ne $script:StatusBox) {
            [System.Windows.Forms.Application]::DoEvents()
        }
        Start-Sleep -Milliseconds 500
    }

    throw "$ServiceName did not become ready within $TimeoutSeconds seconds. See logs in $LogRoot."
}

function Open-TraqoBrowser {
    if (-not (Test-ServiceReady $BackendHealthUrl $BackendHealthMarker)) {
        throw "Traqo's backend is not running yet. Start the app before opening the browser."
    }
    if (-not (Test-ServiceReady $FrontendHealthUrl $FrontendHealthMarker)) {
        throw "Traqo's frontend is not running yet. Start the app before opening the browser."
    }

    Start-Process -FilePath "explorer.exe" -ArgumentList $AppUrl
    Write-LauncherStatus "Opened $AppUrl"
}

function Get-ProcessIdentity {
    param([int]$ProcessId)

    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        $cimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        return [ordered]@{
            pid = $ProcessId
            start_time_utc = $process.StartTime.ToUniversalTime().ToString("o")
            executable = [string]$process.Path
            command_line = [string]$cimProcess.CommandLine
        }
    } catch {
        return $null
    }
}

function Test-TrackedServiceOwnership {
    param(
        [string]$ServiceKind,
        [int]$Port,
        [string]$PidFile
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $false
    }

    try {
        $record = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
        $requiredRecordFields = @("version", "port", "service", "project_root", "pid", "start_time_utc", "executable", "command_line")
        if ($null -eq $record -or @($requiredRecordFields | Where-Object { $null -eq $record.PSObject.Properties[$_] }).Count -gt 0) {
            return $false
        }

        $expectedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
        if (
            [int]$record.version -ne 1 -or
            [int]$record.port -ne $Port -or
            [string]$record.service -ne $ServiceKind -or
            -not [string]::Equals([string]$record.project_root, $expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)
        ) {
            return $false
        }

        $listener = Get-PortListener $Port
        if (-not $listener -or $listener.OwningProcess -ne [int]$record.pid) {
            return $false
        }

        $identity = Get-ProcessIdentity ([int]$record.pid)
        return (
            $null -ne $identity -and
            [string]$identity.start_time_utc -eq [string]$record.start_time_utc -and
            [string]::Equals(
                [string]$identity.executable,
                [string]$record.executable,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            [string]$identity.command_line -eq [string]$record.command_line
        )
    } catch {
        return $false
    }
}

function Save-ServiceRecord {
    param(
        [string]$ServiceKind,
        [int]$Port,
        [string]$PidFile
    )

    $listener = Get-PortListener $Port
    if (-not $listener) {
        throw "Could not record $ServiceKind ownership because port $Port has no listener."
    }
    $identity = Get-ProcessIdentity $listener.OwningProcess
    if ($null -eq $identity) {
        throw "Could not verify the $ServiceKind listener process on port $Port."
    }

    $record = [ordered]@{
        version = 1
        project_root = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
        service = $ServiceKind
        port = $Port
        pid = $identity.pid
        start_time_utc = $identity.start_time_utc
        executable = $identity.executable
        command_line = $identity.command_line
    }
    $record | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding UTF8
}

function Stop-TrackedService {
    param(
        [string]$ServiceName,
        [string]$ServiceKind,
        [int]$Port,
        [string]$PidFile
    )

    if (-not (Test-Path $PidFile)) {
        Write-LauncherStatus "$ServiceName was not started by this launcher."
        return $false
    }

    try {
        $record = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
    } catch {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-LauncherStatus "$ServiceName PID record was invalid and has been cleared."
        return $false
    }
    $requiredRecordFields = @("version", "port", "service", "project_root", "pid", "start_time_utc", "executable", "command_line")
    if ($null -eq $record -or @($requiredRecordFields | Where-Object { $null -eq $record.PSObject.Properties[$_] }).Count -gt 0) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-LauncherStatus "$ServiceName PID record used an obsolete format and has been cleared."
        return $false
    }

    $expectedRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
    if (
        [int]$record.version -ne 1 -or
        [int]$record.port -ne $Port -or
        [string]$record.service -ne $ServiceKind -or
        -not [string]::Equals([string]$record.project_root, $expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        Write-LauncherStatus "$ServiceName ownership record belongs to a different launcher or service; it was not stopped."
        return $false
    }

    $listener = Get-PortListener $Port
    if (-not $listener -or $listener.OwningProcess -ne [int]$record.pid) {
        Write-LauncherStatus "$ServiceName is no longer using its recorded process."
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return ($null -eq (Get-PortListener $Port))
    }

    $identity = Get-ProcessIdentity ([int]$record.pid)
    $sameStartTime = $null -ne $identity -and [string]$identity.start_time_utc -eq [string]$record.start_time_utc
    $sameExecutable = $null -ne $identity -and [string]::Equals(
        [string]$identity.executable,
        [string]$record.executable,
        [System.StringComparison]::OrdinalIgnoreCase
    )
    $sameCommand = $null -ne $identity -and [string]$identity.command_line -eq [string]$record.command_line
    if (-not ($sameStartTime -and $sameExecutable -and $sameCommand)) {
        Write-LauncherStatus "$ServiceName process identity no longer matches its ownership record; it was not stopped."
        return $false
    }

    Stop-Process -Id ([int]$record.pid) -Force -ErrorAction Stop
    Wait-Process -Id ([int]$record.pid) -Timeout 10 -ErrorAction SilentlyContinue
    if ($null -ne (Get-PortListener $Port)) {
        throw "$ServiceName did not release port $Port after its owned process was stopped."
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-LauncherStatus "$ServiceName stopped."
    return $true
}

function Stop-Traqo {
    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
    $null = Stop-TrackedService "Frontend" "frontend" 5173 $FrontendPidFile
    $null = Stop-TrackedService "Backend" "backend" 8000 $BackendPidFile
}

function Stop-NewServiceProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$ServiceName,
        [string]$ServiceKind,
        [int]$Port,
        [string]$PidFile
    )

    try {
        if ($null -ne $Process -and -not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $Process.Id -Timeout 10 -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $PidFile) {
            try {
                $record = Get-Content -Raw -LiteralPath $PidFile | ConvertFrom-Json
                if ([int]$record.pid -eq $Process.Id) {
                    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
                }
            } catch {}
        }
    } catch {
        Write-LauncherStatus "$ServiceName cleanup warning: $($_.Exception.Message)"
    }
}

function Start-Traqo {
    Test-AppFolders
    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

    $backendReady = Test-ServiceReady $BackendHealthUrl $BackendHealthMarker
    $frontendReady = Test-ServiceReady $FrontendHealthUrl $FrontendHealthMarker
    Resolve-LauncherCommands -NeedBackend -NeedFrontend

    $backendNeedsRestart = $false
    $frontendNeedsRestart = $false

    if ($backendReady) {
        $backendDependenciesCurrent = (
            (Test-DependencyFingerprint (Get-BackendDependencyFingerprint) $BackendDependencyStamp) -and
            (Test-BackendDependencies)
        )
        if (-not $backendDependenciesCurrent) {
            $backendNeedsRestart = $true
        }
    }

    if ($frontendReady) {
        $frontendDependenciesCurrent = (
            (Test-DependencyFingerprint (Get-FrontendDependencyFingerprint) $FrontendDependencyStamp) -and
            (Test-FrontendDependencies)
        )
        if (-not $frontendDependenciesCurrent) {
            $frontendNeedsRestart = $true
        }
    }

    if ($backendNeedsRestart -and -not (Test-TrackedServiceOwnership "backend" 8000 $BackendPidFile)) {
        throw "Backend code or dependencies changed, but the running backend is not owned by this launcher. Stop the process on port 8000 and retry."
    }
    if ($frontendNeedsRestart -and -not (Test-TrackedServiceOwnership "frontend" 5173 $FrontendPidFile)) {
        throw "Frontend dependencies changed, but the running frontend is not owned by this launcher. Stop the process on port 5173 and retry."
    }

    if ($backendNeedsRestart) {
        Write-LauncherStatus "Backend code or dependencies changed; restarting the owned backend..."
        if (-not (Stop-TrackedService "Backend" "backend" 8000 $BackendPidFile)) {
            throw "The owned backend could not be stopped safely."
        }
        $backendReady = $false
    }
    if ($frontendNeedsRestart) {
        Write-LauncherStatus "Frontend dependencies changed; restarting the owned frontend..."
        if (-not (Stop-TrackedService "Frontend" "frontend" 5173 $FrontendPidFile)) {
            throw "The owned frontend could not be stopped safely."
        }
        $frontendReady = $false
    }

    if ($backendReady -and $frontendReady) {
        Write-LauncherStatus "Backend is already running with current dependencies."
        Write-LauncherStatus "Frontend is already running with current dependencies."
        if (-not $NoBrowser) {
            Open-TraqoBrowser
        }
        Write-LauncherStatus "Traqo is ready. Logs: $LogRoot"
        return
    }

    $backendProcess = $null
    $frontendProcess = $null

    try {
        if ($backendReady) {
            Write-LauncherStatus "Backend is already running."
        } else {
            Assert-PortAvailable 8000 "Backend" $BackendHealthUrl $BackendHealthMarker
            Ensure-BackendDependencies
            Write-LauncherStatus "Starting backend..."
            $backendStart = @{
                FilePath = $script:PythonExe
                ArgumentList = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000")
                WorkingDirectory = $BackendDir
                RedirectStandardOutput = $BackendOutLog
                RedirectStandardError = $BackendErrLog
                WindowStyle = "Hidden"
                PassThru = $true
            }
            $backendProcess = Start-Process @backendStart
            Wait-ServiceReady "Backend" $BackendHealthUrl $BackendHealthMarker $backendProcess $BackendOutLog $BackendErrLog
            Save-ServiceRecord "backend" 8000 $BackendPidFile
        }

        if ($frontendReady) {
            Write-LauncherStatus "Frontend is already running."
        } else {
            Assert-PortAvailable 5173 "Frontend" $FrontendHealthUrl $FrontendHealthMarker
            Ensure-FrontendDependencies
            $viteCli = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
            if (-not (Test-Path -LiteralPath $viteCli)) {
                throw "Vite was not installed at the expected path: $viteCli"
            }
            Write-LauncherStatus "Starting frontend..."
            $frontendStart = @{
                FilePath = $script:NodeExe
                ArgumentList = @("`"$viteCli`"", "--host", "127.0.0.1", "--port", "5173", "--strictPort")
                WorkingDirectory = $FrontendDir
                RedirectStandardOutput = $FrontendOutLog
                RedirectStandardError = $FrontendErrLog
                WindowStyle = "Hidden"
                PassThru = $true
            }
            $frontendProcess = Start-Process @frontendStart
            Wait-ServiceReady "Frontend" $FrontendHealthUrl $FrontendHealthMarker $frontendProcess $FrontendOutLog $FrontendErrLog
            Save-ServiceRecord "frontend" 5173 $FrontendPidFile
        }

        if (-not $NoBrowser) {
            Open-TraqoBrowser
        }

        Write-LauncherStatus "Traqo is ready. Logs: $LogRoot"
    } catch {
        Stop-NewServiceProcess $frontendProcess "Frontend" "frontend" 5173 $FrontendPidFile
        Stop-NewServiceProcess $backendProcess "Backend" "backend" 8000 $BackendPidFile
        throw
    }
}

if ($Start) {
    try {
        Start-Traqo
        exit 0
    } catch {
        Write-Error $_.Exception.Message
        Write-Host "Logs: $LogRoot"
        exit 1
    }
}

if ($Stop) {
    try {
        Stop-Traqo
        exit 0
    } catch {
        Write-Error $_.Exception.Message
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "Traqo Launcher"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(560, 450)
$form.MinimumSize = New-Object System.Drawing.Size(560, 450)
$form.BackColor = [System.Drawing.Color]::FromArgb(255, 255, 255)
$form.ForeColor = [System.Drawing.Color]::FromArgb(25, 25, 24)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$logoBox = New-Object System.Windows.Forms.PictureBox
$logoBox.Location = New-Object System.Drawing.Point(30, 24)
$logoBox.Size = New-Object System.Drawing.Size(78, 78)
$logoBox.SizeMode = "Zoom"
$logoBox.BackColor = [System.Drawing.Color]::Transparent
$logoPath = Join-Path $FrontendDir "public\traqo-mark-192.png"
if (Test-Path $logoPath) {
    $logoBox.ImageLocation = $logoPath
}

$title = New-Object System.Windows.Forms.Label
$title.Text = "Traqo"
$title.Location = New-Object System.Drawing.Point(130, 28)
$title.Size = New-Object System.Drawing.Size(360, 40)
$title.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(25, 25, 24)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Your local roadmap workspace"
$subtitle.Location = New-Object System.Drawing.Point(134, 70)
$subtitle.Size = New-Object System.Drawing.Size(360, 24)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(96, 96, 92)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "Start Traqo"
$startButton.Location = New-Object System.Drawing.Point(30, 125)
$startButton.Size = New-Object System.Drawing.Size(115, 44)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 24)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = "Flat"
$startButton.FlatAppearance.BorderSize = 0

$openButton = New-Object System.Windows.Forms.Button
$openButton.Text = "Open Browser"
$openButton.Location = New-Object System.Drawing.Point(155, 125)
$openButton.Size = New-Object System.Drawing.Size(115, 44)
$openButton.BackColor = [System.Drawing.Color]::FromArgb(247, 247, 245)
$openButton.ForeColor = [System.Drawing.Color]::FromArgb(25, 25, 24)
$openButton.FlatStyle = "Flat"
$openButton.FlatAppearance.BorderSize = 0

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "Stop Traqo"
$stopButton.Location = New-Object System.Drawing.Point(280, 125)
$stopButton.Size = New-Object System.Drawing.Size(115, 44)
$stopButton.BackColor = [System.Drawing.Color]::FromArgb(185, 76, 91)
$stopButton.ForeColor = [System.Drawing.Color]::White
$stopButton.FlatStyle = "Flat"
$stopButton.FlatAppearance.BorderSize = 0

$folderButton = New-Object System.Windows.Forms.Button
$folderButton.Text = "Open Logs"
$folderButton.Location = New-Object System.Drawing.Point(405, 125)
$folderButton.Size = New-Object System.Drawing.Size(115, 44)
$folderButton.BackColor = [System.Drawing.Color]::FromArgb(247, 247, 245)
$folderButton.ForeColor = [System.Drawing.Color]::FromArgb(25, 25, 24)
$folderButton.FlatStyle = "Flat"
$folderButton.FlatAppearance.BorderSize = 0

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Location = New-Object System.Drawing.Point(30, 195)
$statusBox.Size = New-Object System.Drawing.Size(490, 150)
$statusBox.Multiline = $true
$statusBox.ReadOnly = $true
$statusBox.ScrollBars = "Vertical"
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(247, 247, 245)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(25, 25, 24)
$statusBox.BorderStyle = "FixedSingle"
$script:StatusBox = $statusBox

$footer = New-Object System.Windows.Forms.Label
$footer.Text = "The launcher waits for both services before opening your browser."
$footer.Location = New-Object System.Drawing.Point(30, 365)
$footer.Size = New-Object System.Drawing.Size(490, 24)
$footer.ForeColor = [System.Drawing.Color]::FromArgb(96, 96, 92)

$startButton.Add_Click({
    $startButton.Enabled = $false
    $openButton.Enabled = $false
    $stopButton.Enabled = $false
    $form.ControlBox = $false
    try {
        Start-Traqo
    } catch {
        Write-LauncherStatus "ERROR: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show(
            "$($_.Exception.Message)`n`nLogs: $LogRoot",
            "Traqo could not start",
            "OK",
            "Error"
        ) | Out-Null
    } finally {
        $startButton.Enabled = $true
        $openButton.Enabled = $true
        $stopButton.Enabled = $true
        $form.ControlBox = $true
    }
})

$openButton.Add_Click({
    try {
        Open-TraqoBrowser
    } catch {
        Write-LauncherStatus "ERROR: $($_.Exception.Message)"
        [System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message,
            "Traqo is not ready",
            "OK",
            "Warning"
        ) | Out-Null
    }
})

$stopButton.Add_Click({
    try {
        Stop-Traqo
    } catch {
        Write-LauncherStatus "ERROR: $($_.Exception.Message)"
    }
})

$folderButton.Add_Click({
    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
    Start-Process -FilePath "explorer.exe" -ArgumentList @("`"$LogRoot`"")
})

$form.Controls.AddRange(@(
    $logoBox,
    $title,
    $subtitle,
    $startButton,
    $openButton,
    $stopButton,
    $folderButton,
    $statusBox,
    $footer
))

Write-LauncherStatus "Ready. Start Traqo and the browser will open when both services respond."
[void]$form.ShowDialog()
