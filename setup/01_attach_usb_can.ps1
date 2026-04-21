# 01_attach_usb_can.ps1
# Run this on Windows (as Administrator) every time WSL2 restarts.
# Prerequisite: usbipd-win must be installed manually from:
#   https://github.com/dorssel/usbipd-win/releases

param(
    [string]$BusId    = "",    # Override with -BusId "X-Y" if you know your adapter bus ID
    [switch]$Reattach          # Detach first, then re-attach (fixes ghost interface in WSL2)
)

$ErrorActionPreference = "Stop"

function Find-UsbIpd {
    if (Get-Command usbipd -ErrorAction SilentlyContinue) { return (Get-Command usbipd).Source }
    foreach ($p in @(
        "$env:ProgramFiles\usbipd-win\usbipd.exe",
        "${env:ProgramFiles(x86)}\usbipd-win\usbipd.exe"
    )) {
        if (Test-Path $p) { return $p }
    }
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

Write-Host "`n=== USB-to-CAN WSL2 Attach Script ===" -ForegroundColor Cyan

# 0. Verify running as Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> 'Run as Administrator', then re-run." -ForegroundColor Yellow
    exit 1
}

# 1. Check usbipd is installed
$script:ubExe = Find-UsbIpd
if (-not $script:ubExe) {
    Write-Host "usbipd not found." -ForegroundColor Red
    Write-Host "Download and install the MSI from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/dorssel/usbipd-win/releases" -ForegroundColor White
    Write-Host "Then restart this terminal and re-run the script." -ForegroundColor Yellow
    exit 1
}
Write-Host "usbipd: $script:ubExe" -ForegroundColor Green

# 2. Find USB-CAN adapter bus ID
if (-not $BusId) {
    Write-Host "`nScanning USB devices..." -ForegroundColor Yellow
    & $script:ubExe list
    $BusId = Find-CanAdapterBusId
    if (-not $BusId) {
        Write-Host "`nCould not auto-detect CAN adapter." -ForegroundColor Red
        Write-Host "Check the list above and pass -BusId manually:" -ForegroundColor Yellow
        Write-Host "  .\setup\01_attach_usb_can.ps1 -BusId '1-3'" -ForegroundColor White
        Write-Host "`nCommon adapter names: CANable, Geschwister Schneider, candleLight, PCAN, slcan" -ForegroundColor Gray
        exit 1
    }
    Write-Host "Detected CAN adapter at bus ID: $BusId" -ForegroundColor Green
}

# 3. Bind (one-time; safe to repeat)
Write-Host "Binding $BusId..." -ForegroundColor Yellow
$bindResult = & $script:ubExe bind --busid $BusId 2>&1
if ($LASTEXITCODE -ne 0) {
    # Already bound is not an error
    if ($bindResult -notmatch "already") {
        Write-Host "Bind output: $bindResult" -ForegroundColor Yellow
    }
}

# 4. Detach first if -Reattach flag is set (fixes ghost interface)
if ($Reattach) {
    Write-Host "Detaching $BusId first (Reattach mode)..." -ForegroundColor Yellow
    & $script:ubExe detach --busid $BusId 2>&1 | Out-Null
    Start-Sleep -Seconds 2
}

# 5. Attach to WSL2
Write-Host "Attaching $BusId to WSL2..." -ForegroundColor Yellow
& $script:ubExe attach --wsl --busid $BusId

Write-Host "`nDone! In WSL2 run:" -ForegroundColor Green
Write-Host "  sudo bash setup/02_setup_can_interface.sh"
