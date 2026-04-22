# Agilex Hunter SE — Python Interface

Control and simulate the Agilex Hunter SE from Windows + WSL2 via USB-to-CAN.
Three operating modes are supported:

| Mode | Description | Requires |
|------|-------------|----------|
| **CAN** | Direct control via SocketCAN — no middleware | USB-CAN adapter + robot |
| **ROS2** | Bridge to ROS2 Jazzy topics (`/cmd_vel`, `/odom`, …) | CAN + ROS2 Jazzy installed |
| **Simulator** | Kinematic simulation with real-time matplotlib plot | Nothing — no robot needed |

All three modes share the same trajectory primitives (`drive_straight`, `drive_arc`) and the same command-line scripts (`figure8.py`, `square.py`).

---

## Prerequisites

| Tool | Where | Purpose |
|------|-------|---------|
| [usbipd-win](https://github.com/dorssel/usbipd-win) | Windows | Forward USB-CAN adapter to WSL2 |
| WSL2 (Ubuntu 22.04+) | Windows feature | Linux environment for SocketCAN |
| Python 3.9+ with venv | WSL2 | Python dependencies |
| USB-to-CAN adapter (candleLight) | Delivered with Hunter SE | CAN bus connection |

> **Custom WSL2 kernel required (one-time):** The default WSL2 kernel does not include the `gs_usb` candleLight driver.
> See **[WSL_MODIFICATION.md](WSL_MODIFICATION.md)** for the full build guide (~15 min).

---

## One-Time Setup

### 1. Build custom WSL2 kernel
Follow **[WSL_MODIFICATION.md](WSL_MODIFICATION.md)** to add `gs_usb` support.

### 2. Install Python dependencies

```bash
# WSL2
sudo apt install -y python3-full python3-venv
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 3. (ROS2 only) Install ROS2 Jazzy

```bash
sudo bash setup/06_install_ros2.sh
```

---
## Typical Operation
- In Windows PowerShell (Admin), run `.\setup\01_attach_usb_can.ps1` to attach the USB-CAN adapter to WSL2.
- In WSL2, run `sudo bash setup/02_setup_can_interface.sh` to bring up the `can0` interface.
- In WSL2, execute any of the Python scripts in `src/` to control the robot, e.g. `python3 src/figure8.py --speed 0.3 --steering 0.35`.
- If using ROS2, start a second WSL terminal and run `python3 src/hunter_se_node.py` to start the ROS2 bridge node, then publish to `/cmd_vel` or run trajectories with `--ros`.
---

## Every Session: Start the CAN Interface

Before using CAN or ROS2 mode, attach the USB-CAN adapter and bring up the interface.

>**Important**: If the CAN communication failed, unplug the USB-CAN adapter from your laptop and plug it back in.

**Step 1 — PowerShell (Admin):**
```powershell
.\setup\01_attach_usb_can.ps1
```

**Step 2 — WSL2:**
```bash
sudo bash setup/02_setup_can_interface.sh
```

**Verify (robot must be powered on):**
```bash
bash setup/03_verify_can.sh
# or: candump can0    (should show continuous frames)
```

---

## Mode 1: Direct CAN

The simplest path — Python talks directly to the CAN bus via SocketCAN. No ROS2 required.

### RC Monitor

Decode and display live telemetry while driving with the RC remote (SWB switch in middle position on the Remote Control). Useful for verifying the CAN link and understanding the robot's response before running feedforward scripts below.

```bash
source env/bin/activate
python3 src/rc_monitor.py            # live telemetry display
python3 src/rc_monitor.py --log      # also save a CSV of all frames
```

Output includes: battery voltage, control mode, linear velocity, steering angle, fault codes.

### Feedforward Trajectories

Run pre-built trajectories directly over CAN. The robot must be in **CAN command mode** (SWB switch in top position on the Remote Control).

```bash
# Figure-8
python3 src/figure8.py --dry-run                          # preview geometry + timing
python3 src/figure8.py --speed 0.2 --steering 0.35        # slow first test
python3 src/figure8.py --speed 0.3 --steering 0.35 --loops 2

# Square
python3 src/square.py --dry-run
python3 src/square.py --speed 0.2 --side 2.0 --steering 0.35
python3 src/square.py --speed 0.3 --side 2.0 --steering 0.35 --direction left  # CCW
```

---

## Mode 2: ROS2 Bridge

`src/hunter_se_node.py` is a standalone ROS2 Jazzy node — no colcon workspace needed.
It subscribes to `/cmd_vel` and publishes `/odom`, `/battery_state`, `/diagnostics`, and TF.

> ⚠️ **Deactivate the Python venv before running** — ROS2 uses system Python.
> ```bash
> deactivate
> ```

### Start the bridge (3 terminals in WSL)

**Terminal 1 — CAN setup:**
```bash
sudo bash setup/02_setup_can_interface.sh
```

**Terminal 2 — Bridge node:**
```bash
source /opt/ros/jazzy/setup.bash
python3 src/hunter_se_node.py
# Expected: [INFO] ... CAN command mode enabled.
```

**Terminal 3 — Keyboard teleop:**
```bash
source /opt/ros/jazzy/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

### Keyboard controls

```
   u    i    o
   j    k    l        q/z : increase/decrease speed
   m    ,    .        w/x : increase/decrease turn rate
                      k   : full stop
```

| Key | Action |
|-----|--------|
| `i` | Forward |
| `,` | Backward |
| `j` / `l` | Turn left / right (while moving) |
| `k` | **Stop** |
| `u` / `o` | Forward-left / Forward-right |
| `m` / `.` | Backward-left / Backward-right |
| `q` / `z` | Speed up / slow down |

> **Ackermann note:** The Hunter SE cannot rotate in place. Angular commands are only applied when `|speed| > 0.05 m/s`. Always press `i` to move first, then steer.

### Trajectories via ROS2

Pass `--ros` to any trajectory script to route commands through `/cmd_vel` instead of direct CAN:

```bash
python3 src/figure8.py --speed 0.3 --steering 0.35 --ros
python3 src/square.py --speed 0.3 --side 2.0 --steering 0.35 --ros
```
ROS2 will then handle the CAN communication.

### ROS2 Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/cmd_vel` | `geometry_msgs/Twist` | Input: `linear.x` = m/s, `angular.z` = rad/s |
| `/odom` | `nav_msgs/Odometry` | Dead-reckoning odometry from velocity feedback |
| `/battery_state` | `sensor_msgs/BatteryState` | Battery voltage (10 Hz) |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | Control mode + fault codes (10 Hz) |
| `/tf` | TF2 | `odom` → `base_link` for RViz |

### Node Parameters

```bash
python3 src/hunter_se_node.py --ros-args \
    -p channel:=can0 \
    -p max_speed:=1.0 \
    -p cmd_vel_timeout:=0.5
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `channel` | `can0` | SocketCAN interface |
| `max_speed` | `1.5` | Speed cap (m/s) |
| `max_steering` | `0.4` | Steering cap (rad) |
| `cmd_vel_timeout` | `0.5` | Stop if no `/cmd_vel` for this many seconds |
| `publish_rate` | `20.0` | Odometry publish rate (Hz) |

---

## Mode 3: Simulator

No robot or CAN bus required. A matplotlib window shows the trajectory in real time. Execute this in WSL or any Python environment with the dependencies installed.

```bash
# Figure-8 — opens plot window, runs at real speed
python3 src/figure8.py --sim

# 10× faster than real time (22 s arc → ~2 s wall-clock)
python3 src/figure8.py --sim --sim-speed 10 --speed 0.3 --steering 0.35 --loops 2

# Square simulation
python3 src/square.py --sim
python3 src/square.py --sim --sim-speed 5 --speed 0.3 --side 2.0 --steering 0.35
```

The `--sim-speed N` factor compresses wall-clock time while keeping the kinematics correct — a 70 s trajectory at `--sim-speed 10` finishes in ~7 s.

The plot stays open after the trajectory completes showing: path trace, start/end markers, total distance, and final pose. Close the window to exit.

> **WSL2 display:** Requires WSLg (Windows 11) or an X server like VcXsrv. If the window doesn't open, set `DISPLAY=:0` before running.

---

## Trajectory Reference

All trajectories are composed from two primitives in `src/trajectory.py`.

### Primitives

| Function | Parameters | Description |
|----------|------------|-------------|
| `drive_straight(robot, distance_m, speed_mps)` | distance (m), speed (m/s) | Straight line |
| `drive_arc(robot, speed_mps, steering_rad, direction, angle_rad)` | left/right, sweep angle | Circular arc |

Arc geometry (Ackermann, derived from User Manual):
```
Wheelbase L ≈ 657 mm
Rear-axle radius (governs yaw rate and arc timing):  R_yaw = L / tan(steering)
Centre-of-vehicle radius (display / clearance only): R_ctr = L / tan(steering) + T/2

steering=0.35 rad → R_yaw ≈ 1.80 m,  R_ctr ≈ 2.07 m
steering=0.40 rad → R_yaw ≈ 1.55 m,  R_ctr ≈ 1.83 m  (hardware minimum)
```

Arc duration is **auto-computed** from the sweep angle.

### Figure-8

Two 180° arcs back-to-back with opposite steering.

```
[Left 180°] → [Right 180°]  = 1 loop
```

| Speed | Steering | R | Arc time | Total (1 loop) |
|-------|----------|---|----------|----------------|
| 0.3 m/s | 0.35 rad | 2.07 m | 18.8 s | 38 s |
| 0.2 m/s | 0.35 rad | 2.07 m | 28.3 s | 57 s |
| 0.3 m/s | 0.40 rad | 1.83 m | 16.3 s | 33 s |

### Square

Four sides with a 90° turn at each corner. Clockwise by default (`--direction right`).

```
[Straight] → [90° turn] → [Straight] → [90° turn] → ...  (×4)
```

| Speed | Side | Steering | Side time | Corner time | Total |
|-------|------|----------|-----------|-------------|-------|
| 0.3 m/s | 2.0 m | 0.35 rad | 6.7 s | 9.4 s | 64 s |
| 0.2 m/s | 2.0 m | 0.35 rad | 10 s | 14.1 s | 97 s |

### Custom Trajectories

Compose any path from primitives:

```python
from hunter_se import HunterSE          # or: SimRobot, RosRobot
from trajectory import drive_straight, drive_arc
import math

with HunterSE() as robot:
    robot.enable_can_mode()
    drive_straight(robot, 3.0, speed_mps=0.3)
    drive_arc(robot, 0.3, 0.35, direction="left", angle_rad=math.pi / 2)
    drive_straight(robot, 1.5, speed_mps=0.3)
```

---

## Safety

### RC Override (SWB switch to middle position — top-left 3-way lever on the Remote Control)

| SWB position | Mode | Effect |
|---|---|---|
| **Top** | CAN command mode | Python script controls the robot |
| **Middle** | RC mode | You take over — script commands ignored |

> From the manual: *"If the RC transmitter is turned on, the RC transmitter has the highest authority."*
> **SWB middle always overrides CAN** — flip it any time to take manual control.

### Stop priority (highest first)

1. **E-stop button** (physical, both sides of robot) — cuts motor power instantly
2. **SWB → Middle** (RC override) — software override via transmitter
3. **Ctrl+C** in terminal — calls `robot.stop()`, sends zero velocity, cleans up
4. **Watchdog** — Hunter SE stops automatically if no CAN command within 500 ms
5. **Python script** — normal autonomous operation

### Guidelines

- Always keep the RC transmitter **on and in hand** during autonomous runs.
- Use `--dry-run` to preview timing before running on the real robot.
- Use simulation mode to verify geometry and timing before running on the real robot.
- Test at `--speed 0.2` first before increasing speed.
- Required clearance: figure-8 ≥ 5 m on all sides; square ≥ (side + 2 m).

---

## CAN Recovery

When the CAN interface gets stuck (ENOBUFS, Timer expired, ghost interface):

**1. Unplug the USB-CAN adapter** (physical unplug — resets adapter firmware).

**2. PowerShell (Admin):**
```powershell
.\setup\05_reset_can.ps1
```

**3. WSL2:**
```bash
sudo bash setup/05_reset_can.sh --verify
```
The `--verify` flag runs a 3-second `candump` to confirm frames are arriving.

**If step 3 still fails** (WSL frozen / Timer expired):
```powershell
.\setup\05_reset_can.ps1 -ShutdownWSL   # shuts down WSL2 completely first
```
Then reopen WSL2 and re-run step 3.

### Symptom table

| Symptom | Fix |
|---------|-----|
| `SIOCGIFINDEX: No such device` | Run `01_attach_usb_can.ps1` then `02_setup_can_interface.sh` |
| `Module gs_usb not found` | Build custom WSL2 kernel — see [WSL_MODIFICATION.md](WSL_MODIFICATION.md) |
| `candump can0` shows no frames | Power on the Hunter SE first; check CAN cable; power cycle robot |
| `No buffer space available` (ENOBUFS) | Bus-off. Run `05_reset_can.ps1` (Win) + `05_reset_can.sh` (WSL) |
| `RTNETLINK answers: No such device` (but `ip link show` has can0) | Ghost interface. Run `05_reset_can.ps1` |
| `RTNETLINK answers: Timer expired` | Adapter firmware frozen. Run `05_reset_can.ps1 -ShutdownWSL` |
| `externally-managed-environment` (pip) | Create a Linux venv — see One-Time Setup above |

---

## CAN Protocol Reference

| Direction | ID | Content |
|-----------|-----|---------|
| PC → Robot | `0x111` | Motion command: linear velocity (mm/s, int16 BE) + steering (mrad, int16 BE) |
| PC → Robot | `0x421` | Mode switch — must send before any motion command |
| Robot → PC | `0x211` | System status: control mode, battery voltage, fault code |
| Robot → PC | `0x221` | Motion feedback: actual velocity + steering angle |

**Bitrate:** 500 kbps  
**Watchdog:** Robot stops if no `0x111` received within 500 ms.  
**Startup:** Robot powers on in Standby — send `0x421` to enable CAN control.

---

## File Structure

```
hunter_se/
├── requirements.txt
├── setup/
│   ├── 01_attach_usb_can.ps1       # Windows: attach USB-CAN adapter to WSL2
│   ├── 02_setup_can_interface.sh   # WSL2: bring up can0 at 500 kbps
│   ├── 03_verify_can.sh            # WSL2: verify CAN heartbeat frames
│   ├── 05_reset_can.ps1            # Windows: reset stuck CAN interface
│   ├── 05_reset_can.sh             # WSL2: reset + bring up can0 with retries
│   └── 06_install_ros2.sh          # WSL2: install ROS2 Jazzy (one-time)
└── src/
    ├── hunter_se.py                # HunterSE CAN interface class
    ├── ros_robot.py                # ROS2 adapter (same API as HunterSE, publishes /cmd_vel)
    ├── sim_robot.py                # Kinematic simulator with matplotlib visualisation
    ├── hunter_se_node.py           # ROS2 Jazzy bridge node
    ├── trajectory.py               # Motion primitives: drive_straight, drive_arc
    ├── rc_monitor.py               # Live CAN telemetry monitor
    ├── figure8.py                  # Figure-8 trajectory (--can / --ros / --sim)
    └── square.py                   # Square trajectory (--can / --ros / --sim)
```

---

## Future

- **Closed-loop trajectories** — use `/odom` feedback for distance-based (not time-based) primitives
- **SLAM + Nav2** — add NAV-960 for pose estimation, then run ROS2 Nav2 for autonomous navigation
- **More shapes** — circle, slalom, lane-change — composable from existing primitives
- **RViz** — add a URDF model for visual robot pose display

