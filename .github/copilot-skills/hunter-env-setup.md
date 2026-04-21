---
name: hunter-env-setup
description: >-
  Guides setup of the WSL2 + USB-to-CAN + SocketCAN environment for the
  Agilex Hunter SE robot. Use this skill when troubleshooting usbipd,
  SocketCAN interface configuration, CAN bitrate, or driver issues.
---

# Hunter SE — Environment Setup Skill

## Overview
The Hunter SE communicates over CAN bus at **500 kbps**.
The development workflow is: Windows (usbipd-win) → WSL2 Ubuntu (SocketCAN) → python-can.

## Step 1 — Attach USB-CAN to WSL2 (Windows)

```powershell
# Install usbipd-win (one time)
winget install --id dorssel.usbipd-win

# List USB devices, find your CAN adapter
usbipd list

# Bind and attach (run as Administrator; repeat after every reboot)
usbipd bind --busid <X-Y>
usbipd attach --wsl --busid <X-Y>
```

Or use the provided helper:
```powershell
.\setup\01_attach_usb_can.ps1          # auto-detects adapter
.\setup\01_attach_usb_can.ps1 -BusId "1-3"   # manual bus ID
```

## Step 2 — Bring up SocketCAN (WSL2)

```bash
sudo bash setup/02_setup_can_interface.sh
```

This loads `gs_usb` driver, creates `can0`, and sets 500 kbps bitrate.

### SLCAN fallback (adapter appears as /dev/ttyACM*)
```bash
sudo slcand -o -s6 -t hw -S 3000000 /dev/ttyACM0 can0
sudo ip link set can0 up type can bitrate 500000
```

## Step 3 — Verify

```bash
bash setup/03_verify_can.sh
# or manually:
candump can0    # should see frames when Hunter SE is powered on
```

## Common Issues & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `can0` not found after `modprobe gs_usb` | Adapter uses SLCAN protocol | Use `slcand` (see Step 2 fallback) |
| `candump` shows no frames | Robot off / wrong bitrate / cable | Check power, verify 500 kbps, check CAN-H/L |
| Bus error frames `BUSERR` | Bitrate mismatch | `sudo ip link set can0 down && sudo ip link set can0 up type can bitrate 500000` |
| USB-CAN disappears after WSL restart | usbipd detaches on restart | Re-run `usbipd attach --wsl --busid <X-Y>` |
| `Permission denied` on can0 | User not in `netdev` group | `sudo usermod -aG netdev $USER` then re-login |

## CAN Frame Inspection

```bash
candump can0 -x -t A         # verbose with timestamps
cansniffer can0               # live interactive viewer
```

## Expected Hunter SE Heartbeat Frames
| ID     | Content            | Rate  |
|--------|--------------------|-------|
| 0x211  | Vehicle state      | 50 Hz |
| 0x221  | System/battery     | 50 Hz |
| 0x251  | Actuator state     | 50 Hz |

## Persistent CAN Setup (survive WSL restart)

Add to `~/.bashrc`:
```bash
alias hunter-up='sudo ip link set can0 up type can bitrate 500000 2>/dev/null || sudo bash ~/hunter_se/setup/02_setup_can_interface.sh'
```
