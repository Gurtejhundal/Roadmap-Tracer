Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$AppUrl = "http://127.0.0.1:5173"
$LogoCandidates = @(
    (Join-Path $Root "launcher-logo.png"),
    (Join-Path $Root "launcher-logo.jpg"),
    (Join-Path $Root "launcher-logo.jpeg"),
    (Join-Path $Root "launcher-logo.ico")
)

function Add-Status {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    $statusBox.AppendText("[$timestamp] $Message`r`n")
}

function Test-AppFolders {
    if (-not (Test-Path (Join-Path $BackendDir "main.py"))) {
        [System.Windows.Forms.MessageBox]::Show(
            "Backend folder not found:`n$BackendDir",
            "Roadmap Tracer Launcher",
            "OK",
            "Error"
        ) | Out-Null
        return $false
    }

    if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
        [System.Windows.Forms.MessageBox]::Show(
            "Frontend folder not found:`n$FrontendDir",
            "Roadmap Tracer Launcher",
            "OK",
            "Error"
        ) | Out-Null
        return $false
    }

    return $true
}

function Start-RoadmapTracer {
    if (-not (Test-AppFolders)) {
        return
    }

    Add-Status "Starting backend window..."
    $backendCommand = "cd /d `"$BackendDir`" && python -c `"import fastapi, sqlalchemy, pypdf, docx`" || python -m pip install -r requirements.txt && python -m uvicorn main:app --host 127.0.0.1 --port 8000"
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", $backendCommand) -WindowStyle Normal

    Add-Status "Starting frontend window..."
    $frontendCommand = "cd /d `"$FrontendDir`" && if not exist node_modules npm install && npm run dev -- --host 127.0.0.1 --port 5173"
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", $frontendCommand) -WindowStyle Normal

    Add-Status "Opening $AppUrl in 5 seconds..."
    Start-Sleep -Seconds 5
    Start-Process $AppUrl
    Add-Status "App opened. Keep the backend and frontend windows open."
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Roadmap Tracer Launcher"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(520, 430)
$form.MinimumSize = New-Object System.Drawing.Size(520, 430)
$form.BackColor = [System.Drawing.Color]::FromArgb(8, 18, 28)
$form.ForeColor = [System.Drawing.Color]::White
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$logoBox = New-Object System.Windows.Forms.PictureBox
$logoBox.Location = New-Object System.Drawing.Point(30, 24)
$logoBox.Size = New-Object System.Drawing.Size(92, 92)
$logoBox.SizeMode = "Zoom"
$logoBox.BackColor = [System.Drawing.Color]::FromArgb(12, 31, 45)

$logoPath = $LogoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($logoPath) {
    $logoBox.ImageLocation = $logoPath
} else {
    $placeholder = New-Object System.Windows.Forms.Label
    $placeholder.Text = "TRAQO"
    $placeholder.TextAlign = "MiddleCenter"
    $placeholder.ForeColor = [System.Drawing.Color]::FromArgb(117, 232, 255)
    $placeholder.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $placeholder.Dock = "Fill"
    $logoBox.Controls.Add($placeholder)
}

$title = New-Object System.Windows.Forms.Label
$title.Text = "Roadmap Tracer"
$title.Location = New-Object System.Drawing.Point(145, 28)
$title.Size = New-Object System.Drawing.Size(330, 34)
$title.Font = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(117, 232, 255)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = "Local roadmap tracker launcher"
$subtitle.Location = New-Object System.Drawing.Point(149, 68)
$subtitle.Size = New-Object System.Drawing.Size(330, 24)
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(170, 184, 205)

$logoHelp = New-Object System.Windows.Forms.Label
$logoHelp.Text = "Logo: place launcher-logo.png beside launcher.bat"
$logoHelp.Location = New-Object System.Drawing.Point(149, 96)
$logoHelp.Size = New-Object System.Drawing.Size(330, 24)
$logoHelp.ForeColor = [System.Drawing.Color]::FromArgb(135, 150, 170)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "Start App"
$startButton.Location = New-Object System.Drawing.Point(30, 145)
$startButton.Size = New-Object System.Drawing.Size(140, 42)
$startButton.BackColor = [System.Drawing.Color]::FromArgb(26, 188, 249)
$startButton.ForeColor = [System.Drawing.Color]::White
$startButton.FlatStyle = "Flat"
$startButton.FlatAppearance.BorderSize = 0
$startButton.Add_Click({ Start-RoadmapTracer })

$openButton = New-Object System.Windows.Forms.Button
$openButton.Text = "Open Browser"
$openButton.Location = New-Object System.Drawing.Point(190, 145)
$openButton.Size = New-Object System.Drawing.Size(140, 42)
$openButton.BackColor = [System.Drawing.Color]::FromArgb(42, 58, 80)
$openButton.ForeColor = [System.Drawing.Color]::White
$openButton.FlatStyle = "Flat"
$openButton.FlatAppearance.BorderSize = 0
$openButton.Add_Click({
    Start-Process $AppUrl
    Add-Status "Opened $AppUrl"
})

$folderButton = New-Object System.Windows.Forms.Button
$folderButton.Text = "Open Folder"
$folderButton.Location = New-Object System.Drawing.Point(350, 145)
$folderButton.Size = New-Object System.Drawing.Size(130, 42)
$folderButton.BackColor = [System.Drawing.Color]::FromArgb(42, 58, 80)
$folderButton.ForeColor = [System.Drawing.Color]::White
$folderButton.FlatStyle = "Flat"
$folderButton.FlatAppearance.BorderSize = 0
$folderButton.Add_Click({
    Start-Process $Root
    Add-Status "Opened project folder"
})

$statusBox = New-Object System.Windows.Forms.TextBox
$statusBox.Location = New-Object System.Drawing.Point(30, 215)
$statusBox.Size = New-Object System.Drawing.Size(450, 135)
$statusBox.Multiline = $true
$statusBox.ReadOnly = $true
$statusBox.ScrollBars = "Vertical"
$statusBox.BackColor = [System.Drawing.Color]::FromArgb(5, 12, 20)
$statusBox.ForeColor = [System.Drawing.Color]::FromArgb(210, 225, 240)
$statusBox.BorderStyle = "FixedSingle"

$footer = New-Object System.Windows.Forms.Label
$footer.Text = "Backend: 127.0.0.1:8000    Frontend: 127.0.0.1:5173"
$footer.Location = New-Object System.Drawing.Point(30, 360)
$footer.Size = New-Object System.Drawing.Size(450, 24)
$footer.ForeColor = [System.Drawing.Color]::FromArgb(135, 150, 170)

$form.Controls.AddRange(@(
    $logoBox,
    $title,
    $subtitle,
    $logoHelp,
    $startButton,
    $openButton,
    $folderButton,
    $statusBox,
    $footer
))

Add-Status "Ready. Add launcher-logo.png next to launcher.bat to customize the logo."
[void]$form.ShowDialog()
