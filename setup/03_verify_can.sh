#!/usr/bin/env bash
# 03_verify_can.sh
# Confirms CAN bus is alive by checking for Hunter SE heartbeat frames.
# Power on the Hunter SE before running.

set -euo pipefail

IFACE=can0
TIMEOUT=5

echo "=== Hunter SE CAN Verification ==="
echo "Listening on $IFACE for ${TIMEOUT}s (power on the robot first)..."
echo ""

FRAMES=$(timeout "$TIMEOUT" candump "$IFACE" 2>/dev/null || true)

if [ -z "$FRAMES" ]; then
    echo "FAIL: No CAN frames received."
    echo ""
    echo "Troubleshooting checklist:"
    echo "  [ ] Hunter SE is powered on"
    echo "  [ ] CAN cable connected (CAN-H <-> CAN-H, CAN-L <-> CAN-L)"
    echo "  [ ] USB-CAN adapter attached to WSL2 (run 01_attach_usb_can.ps1)"
    echo "  [ ] Interface is UP: ip link show $IFACE"
    echo "  [ ] Bitrate is 500000: sudo ip link set $IFACE down && sudo ip link set $IFACE up type can bitrate 500000"
    exit 1
fi

FRAME_COUNT=$(echo "$FRAMES" | wc -l)
echo "Received $FRAME_COUNT frames in ${TIMEOUT}s. Sample:"
echo "$FRAMES" | head -10
echo ""

# Hunter SE broadcasts vehicle state at 0x211 and system state at 0x221
if echo "$FRAMES" | grep -qiE "211|221"; then
    echo "PASS: Hunter SE heartbeat frames detected."
else
    echo "WARN: Received frames but did not see expected IDs (0x211 / 0x221)."
    echo "      This may be fine — check IDs against your firmware version."
fi

echo ""
echo "CAN bus OK. Proceed to: python3 src/rc_monitor.py"
