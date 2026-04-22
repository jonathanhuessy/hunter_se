#!/usr/bin/env bash
# 05_reset_can.sh
# WSL2-side CAN recovery script.
#
# Handles: bus-off, ENOBUFS, Timer expired, ghost interface.
#
# Usage (in WSL2):
#   sudo bash setup/05_reset_can.sh           # reset + bring up can0
#   sudo bash setup/05_reset_can.sh --verify  # also run candump for 5 s to confirm frames

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run with sudo." >&2
    echo "  sudo bash setup/05_reset_can.sh" >&2
    exit 1
fi

IFACE=can0
BITRATE=500000
MAX_RETRIES=5
VERIFY=false

for arg in "$@"; do
    [[ "$arg" == "--verify" ]] && VERIFY=true
done

echo "=== Hunter SE CAN Reset ==="

# Pre-check: is the interface present at all?
if ! ip link show "$IFACE" &>/dev/null; then
    echo ""
    echo "ERROR: $IFACE does not exist — USB-CAN adapter is not attached."
    echo "ACTION REQUIRED — in Windows PowerShell (Admin):"
    echo "  .\\setup\\01_attach_usb_can.ps1"
    echo "Then re-run: sudo bash setup/05_reset_can.sh"
    exit 1
fi

# Step 1: Force interface down (ignore all errors — it may be unresponsive)
echo "[1/3] Forcing $IFACE down..."
ip link set "$IFACE" down 2>/dev/null && echo "  Down OK." || echo "  Could not bring down (may already be gone) — continuing."

# Step 2: Bring up with retries
echo "[2/3] Bringing up $IFACE at $BITRATE bps (up to $MAX_RETRIES attempts)..."

BROUGHT_UP=false
for attempt in $(seq 1 $MAX_RETRIES); do
    err=$(ip link set "$IFACE" up type can bitrate $BITRATE restart-ms 100 2>&1) && BROUGHT_UP=true && break
    echo "  Attempt $attempt/$MAX_RETRIES: $err"
    if echo "$err" | grep -q "Timer expired"; then
        echo "  USB adapter frozen — waiting 4 s..."
        sleep 4
    elif echo "$err" | grep -q "No such device"; then
        echo ""
        echo "  Ghost interface: the USB device backing can0 has disappeared."
        echo "  ACTION REQUIRED — in Windows PowerShell (Admin):"
        echo "    .\\setup\\01_attach_usb_can.ps1 -Reattach"
        echo "  Then re-run: sudo bash setup/05_reset_can.sh"
        exit 1
    else
        sleep 2
    fi
done

if ! $BROUGHT_UP; then
    echo ""
    echo "ERROR: Could not bring up $IFACE after $MAX_RETRIES attempts."
    echo ""
    echo "Full recovery steps:"
    echo "  1. Windows PowerShell (Admin): .\\setup\\01_attach_usb_can.ps1 -Reattach"
    echo "  2. If that fails: wsl --shutdown, unplug USB-CAN, plug back in, re-attach"
    echo "  3. WSL2: sudo bash setup/02_setup_can_interface.sh"
    exit 1
fi

ip link set "$IFACE" txqueuelen 100

# Step 3: Verify
echo "[3/3] Interface status:"
ip -details link show "$IFACE"
ip -s link show "$IFACE"

echo ""
echo "=== $IFACE reset complete ==="

if $VERIFY; then
    echo ""
    echo "Listening for CAN frames for 3 seconds (robot must be powered on)..."
    timeout 3 candump "$IFACE" -e || true
    RX=$(ip -s link show "$IFACE" | awk '/RX:/{getline; print $2}')
    if [[ "$RX" -gt 0 ]]; then
        echo "✓ RX frames received — CAN bus is live."
    else
        echo "✗ No RX frames. Check:"
        echo "  - Hunter SE is powered on"
        echo "  - CAN cable is plugged into rear CAN port"
        echo "  - Robot may need a power cycle after repeated bus-off events"
    fi
fi
