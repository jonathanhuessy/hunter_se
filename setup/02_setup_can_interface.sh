#!/usr/bin/env bash
# 02_setup_can_interface.sh
# Run inside WSL2 Ubuntu (with sudo) after attaching the USB-CAN adapter.
# Brings up SocketCAN at 500 kbps (Hunter SE default bitrate).
# Safe to re-run at any time — skips steps already done.
#
# Prerequisite for candleLight / CANable Pro adapters:
#   The default WSL2 kernel does NOT include gs_usb.
#   If you see "Module gs_usb not found", build a custom kernel first:
#     sudo bash setup/04_build_wsl2_kernel.sh
#   Then: wsl --shutdown (in Windows PowerShell), reopen WSL2, re-run this script.
#
# If the interface keeps getting stuck, use the reset script instead:
#   Windows: .\setup\05_reset_can.ps1
#   WSL2:    sudo bash setup/05_reset_can.sh

set -uo pipefail

BITRATE=500000
IFACE=can0
MAX_RETRIES=3

echo "=== Hunter SE CAN Interface Setup ==="

# [1/4] Install can-utils (once only, skipped offline if already present)
echo "[1/4] Checking can-utils..."
if ! command -v candump &>/dev/null; then
    echo "  Installing can-utils (requires internet, one-time only)..."
    apt-get update -qq
    apt-get install -y -qq can-utils
else
    echo "  can-utils already installed, skipping."
fi

# [2/4] Load kernel modules
echo "[2/4] Loading CAN kernel modules..."
modprobe can     || true
modprobe can_raw || true
modprobe can_dev || true

if ! modprobe gs_usb 2>/dev/null; then
    echo ""
    echo "ERROR: gs_usb module not found."
    echo "Run: sudo bash setup/04_build_wsl2_kernel.sh"
    echo "Then: wsl --shutdown (PowerShell), reopen WSL2, re-run this script."
    exit 1
fi

sleep 1

# [3/4] Bring up the interface with retry (handles Timer expired)
echo "[3/4] Bringing up $IFACE at $BITRATE bps..."

if ! ip link show "$IFACE" &>/dev/null; then
    echo ""
    echo "ERROR: $IFACE not found. Attach the USB-CAN adapter first:"
    echo "  Windows PowerShell: .\\setup\\01_attach_usb_can.ps1"
    exit 1
fi

ip link set "$IFACE" down 2>/dev/null || true

BROUGHT_UP=false
for attempt in $(seq 1 $MAX_RETRIES); do
    err=$(ip link set "$IFACE" up type can bitrate $BITRATE restart-ms 100 2>&1) && BROUGHT_UP=true && break
    echo "  Attempt $attempt/$MAX_RETRIES failed: $err"
    if echo "$err" | grep -q "Timer expired"; then
        echo "  USB adapter is frozen — waiting 3 s before retry..."
        sleep 3
    elif echo "$err" | grep -q "No such device"; then
        echo ""
        echo "  Ghost interface detected. Re-attach USB-CAN adapter from Windows:"
        echo "    .\\setup\\01_attach_usb_can.ps1 -Reattach"
        echo "  Then re-run this script."
        exit 1
    else
        sleep 1
    fi
done

if ! $BROUGHT_UP; then
    echo ""
    echo "ERROR: Could not bring up $IFACE after $MAX_RETRIES attempts."
    echo "Try the full reset: Windows: .\\setup\\05_reset_can.ps1"
    echo "                    WSL2:    sudo bash setup/05_reset_can.sh"
    exit 1
fi

# restart-ms 100: auto-recover from bus-off after 100 ms
# txqueuelen 100: larger TX queue prevents ENOBUFS (errno 105) under load
ip link set "$IFACE" txqueuelen 100

# [4/4] Verify
echo "[4/4] Verifying interface..."
ip -details link show "$IFACE"

echo ""
echo "=== $IFACE is UP at $BITRATE bps ==="
echo "Next: candump $IFACE  (power on robot first)"