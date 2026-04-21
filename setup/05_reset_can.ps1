# 05_reset_can.ps1
# Windows-side CAN recovery script.
#
# Handles: ghost interface, frozen USB adapter, repeated bus-off.
#
# Usage (PowerShell as Admin):
#   .\setup\05_reset_can.ps1                 # detach + re-attach USB-CAN, then setup in WSL2
#   .\setup\05_reset_can.ps1 -ShutdownWSL    # full WSL shutdown first (most aggressive reset)

param(
    [string]$BusId      = "",   # Override with -BusId "X-Y" if auto-detect fails
    [switch]$ShutdownWSL        # Shut down WSL2 before re-attaching (clears frozen USB state)
)

$ErrorActionPreference = "Stop"

# ── helpers ──────────────────────────────────────────────────────────────────

function Find-UsbIpd {
    if (Get-Command usbipd -ErrorAction SilentlyContinue) { return (Get-Command usbipd).Source }
    foreach ($p in @(
        "$env:ProgramFiles\usbipd-win\usbipd.exe",
        "${env:ProgramFiles(x86)}\usbipd-win\usbipd.exe"
    )) { if (Test-Path $p) { return $p } }
    return $null
}

function Find-CanAdapterBusId {
    $output   = & $script:ubExe list 2>&1
    $patterns = @("CANable","CAN adapter","Geschwister Schneider","USB2CAN","PCAN","slcan","gs_usb","candleLight")
    foreach ($line in $output) {
        foreach ($p in $patterns) {
            if ($line -imatch $p -and $line -match '^\s*(\d+-\d+)') { return $Matches[1] }
        }
    }
    return $null
}

# ── main ─────────────────────────────────────────────────────────────────────

Write-Host "`n=== Hunter SE CAN Reset ===" -ForegroundColor Cyan

# Check admin
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    exit 1
}

# Check usbipd
$script:ubExe = Find-UsbIpd
if (-not $script:ubExe) {
    Write-Host "ERROR: usbipd not found. Install from https://github.com/dorssel/usbipd-win/releases" -ForegroundColor Red
    exit 1
}

# Step 1: Optional WSL shutdown (clears frozen USB firmware state)
if ($ShutdownWSL) {
    Write-Host "[1/4] Shutting down WSL2 (full reset)..." -ForegroundColor Yellow
    wsl --shutdown
    Write-Host "  Waiting 5 s for WSL to fully stop..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
} else {
    Write-Host "[1/4] Skipping WSL shutdown (use -ShutdownWSL for full reset)" -ForegroundColor Gray
}

# Step 2: Find adapter
if (-not $BusId) {
    Write-Host "[2/4] Scanning for USB-CAN adapter..." -ForegroundColor Yellow
    & $script:ubExe list
    $BusId = Find-CanAdapterBusId
    if (-not $BusId) {
        Write-Host "ERROR: Could not auto-detect CAN adapter." -ForegroundColor Red
        Write-Host "Pass -BusId manually: .\setup\05_reset_can.ps1 -BusId '1-8'" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  Detected CAN adapter at: $BusId" -ForegroundColor Green
} else {
    Write-Host "[2/4] Using bus ID: $BusId" -ForegroundColor Green
}

# Step 3: Detach (ignore error if not attached)
Write-Host "[3/4] Detaching $BusId..." -ForegroundColor Yellow
& $script:ubExe detach --busid $BusId 2>&1 | Out-Null
Start-Sleep -Seconds 2

# Step 4: Bind + attach
Write-Host "[4/4] Binding and attaching $BusId to WSL2..." -ForegroundColor Yellow
$bindResult = & $script:ubExe bind --busid $BusId 2>&1
if ($LASTEXITCODE -ne 0 -and $bindResult -notmatch "already") {
    Write-Host "  Bind: $bindResult" -ForegroundColor Yellow
}
& $script:ubExe attach --wsl --busid $BusId
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== USB-CAN re-attached ===" -ForegroundColor Green
Write-Host ""
Write-Host "Now in WSL2 run:" -ForegroundColor Cyan
Write-Host "  sudo bash setup/05_reset_can.sh --verify" -ForegroundColor White
Write-Host ""
Write-Host "If the interface is still broken, retry with:" -ForegroundColor Gray
Write-Host "  .\setup\05_reset_can.ps1 -ShutdownWSL" -ForegroundColor Gray
