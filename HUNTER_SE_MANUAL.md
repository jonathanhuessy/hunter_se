# Hunter SE User Manual (Markdown)

> Converted from `HUNTER_SE_USER_MANUAL.pdf` (v2.1.0, 2024-05-13, AgileX Robotics).
> Images and figures are not included. Protocol tables are fully reproduced.

---

## Table of Contents

1. [Hunter SE Introduction](#1-hunter-se-introduction)
   - 1.1 [Component List](#11-component-list)
   - 1.2 [Tech Specifications](#12-tech-specifications)
   - 1.3 [Requirement for Development](#13-requirement-for-development)
2. [The Basics](#2-the-basics)
   - 2.1 [Status Indication](#21-status-indication)
   - 2.2 [Electrical Interfaces](#22-electrical-interfaces)
   - 2.3 [Remote Control](#23-remote-control)
   - 2.4 [Control Demands and Movements](#24-control-demands-and-movements)
3. [Getting Started](#3-getting-started)
   - 3.1 [Use and Operation](#31-use-and-operation)
   - 3.2 [Charging and Battery Replacement](#32-charging-and-battery-replacement)
   - 3.3 [Development / CAN Protocol](#33-development--can-protocol)
   - 3.4 [Firmware Upgrade](#34-firmware-upgrade)
   - 3.5 [ROS Package Example](#35-ros-package-example)
4. [Q&A](#4-qa)
5. [Product Dimensions](#5-product-dimensions)

---

## Safety Information

- Do not carry people.
- Use in open areas; no automatic obstacle avoidance.
- Keep safe distance of >2 m when the robot is moving.
- Operating temperature: -10 °C to 45 °C. IP22 rating.
- Max payload: 50 kg.
- Emergency stop switches are on both sides of the vehicle body.

### Battery Safety

- Do not deplete the battery fully; charge when low-voltage alarm sounds.
- Storage: charge/discharge once every 2 months; store fully charged.
- Do not charge below 0 °C.
- Only use batteries and chargers supplied by AgileX.
- Fully charged voltage: ~26.8 V; normal range: 24.5–26.8 V.
- Low-voltage alarm: <24.5 V (beep). Power cut: <24 V (expansion power and driver power off).

### Electrical Extension

- Rear extension: max 10 A, 240 W total.
- Top/tail extension: max 24 V × 10 A per socket, 15 A total, 360 W total.

---

## 1. Hunter SE Introduction

HUNTER SE is an Ackermann-steering programmable UGV with characteristics similar to a car.
It has high load capacity, high speed, and low tire wear. Equipped with swing-arm suspension
for crossing common obstacles. Suitable for unmanned inspection, security, logistics, etc.

### 1.1 Component List

| Item | Quantity |
|------|----------|
| Hunter SE robot body | ×1 |
| Battery charger (AC 220 V) | ×1 |
| Aviation plug (4-pin) | ×1 |
| FS remote controller (optional) | ×1 |
| USB-to-CAN communication module | ×1 |

### 1.2 Tech Specifications

#### Mechanical

| Parameter | Value |
|-----------|-------|
| Dimensions (L×W×H) | 820 × 640 × 310 mm |
| Axle track (front) | 550 mm |
| Front/rear track | 460 mm |
| Kerb weight | 42 kg |
| Ground clearance | 120 mm |
| IP grade | IP22 |

#### Battery & Motors

| Parameter | Value |
|-----------|-------|
| Battery type | Lithium (24 V 30 Ah) |
| Power drive motors | DC brushless, 2 × 350 W |
| Steering drive motor | DC brushless, 150 W |
| Drive motor reduction ratio | 1:4 |
| Drive motor sensor | Magnetic encoder 1000 |
| Parking type | Loss-of-power electromagnetic brake |
| Steering type | Front-wheel Ackermann |
| Suspension | Front: non-independent; Rear: independent |

#### Performance

| Parameter | Value |
|-----------|-------|
| Maximum speed | 4.8 km/h |
| Minimum turning radius | 1.9 m (centre of vehicle) |
| Maximum inner wheel steering angle | 22° (≈ 0.384 rad; CAN limit = 400 mrad = 0.4 rad) |
| Maximum gradeability | ≤20° (full load) |
| Maximum endurance | 8 h |
| Maximum travel | 20 km (24 V 30 Ah battery) |
| Charging time | 3 h (30 Ah); 1.5 h (60 Ah) |
| Working temperature | -10 °C to 40 °C |

#### Control

| Parameter | Value |
|-----------|-------|
| Control modes | Remote control mode, CAN command control mode |
| RC transmitter | 2.4 GHz, range 100 m |
| Communication interface | CAN 2.0B, 500 kbps |

### 1.3 Requirement for Development

- CAN 2.0B interface at 500 kbps.
- MOTOROLA (big-endian) byte order.
- USB-to-CAN adapter (e.g. candleLight) + host computer.

---

## 2. The Basics

### 2.1 Status Indication

Accessible via voltmeter, beeper, and status LEDs on the rear panel.

| Status | Description |
|--------|-------------|
| Current voltage | Displayed on rear voltmeter |
| Low-voltage alarm | <24.5 V (BMS: SOC <15%) → beep-beep-beep |
| Power cut | <24 V (BMS: SOC <10%) → external power and driver power cut |
| Power-on display | Rear voltmeter lights up |

### 2.2 Electrical Interfaces

#### 2.2.1 Rear Electrical Interface (Q-connectors)

| Connector | Function |
|-----------|----------|
| Q1 | Charging interface |
| Q2 | Power switch (knob: horizontal = ON, vertical = OFF) |
| Q3 | Power display interaction |
| Q4 | CAN + 24 V power extension interface (4-pin aviation) |

#### Q4 CAN Pin Definition

| Pin | Signal |
|-----|--------|
| 1 | CAN_H |
| 2 | CAN_L |
| 3 | GND |
| 4 | +24 V |

### 2.3 Remote Control

The FS transmitter uses **left-hand throttle** design.

#### Switch and Button Definitions

| Control | Function |
|---------|----------|
| **SWA** | Not activated (reserved) |
| **SWB** (3-way, top-left) | **Top** = CAN command control mode · **Middle** = RC mode · Bottom = unused |
| **SWC** (3-way, speed) | Top = 1.5 m/s · Middle = 3 m/s · Bottom = 4.8 m/s |
| **S1** (left stick, throttle) | Forward / backward |
| **S2** (right stick, steering) | Left / right front-wheel steering |
| **POWER** | Press and hold to turn on |

> **RC priority:** When the RC transmitter is on, it has highest authority and can override CAN commands regardless of SWB position.

#### RC Display Fields

| Field | Meaning |
|-------|---------|
| Hunter | Model name |
| Vol | Battery voltage |
| Car | Chassis status |
| Batt | Battery percentage |
| P | Park |
| Remoter | RC transmitter battery level |
| Fault Code | Error code (see fault table in section 3.3) |

### 2.4 Control Demands and Movements

Coordinate system: ISO 8855 standard. Vehicle X-axis = forward direction.

| Mode | S1 push forward | S1 push back | S2 push left | S2 push right |
|------|-----------------|--------------|--------------|---------------|
| RC | +X (forward) | −X (reverse) | Left steer | Right steer |
| CAN | Positive linear vel. = +X | Negative = −X | Positive steer angle = left | Negative = right |

**Steering angle** = inner wheel angle.

---

## 3. Getting Started

### 3.1 Use and Operation

#### Startup Procedure

1. Check for visible anomalies; check E-stop buttons are released.
2. First use: confirm Q2 knob is vertical (OFF).
3. Turn Q2 to horizontal (ON); voltmeter shows battery voltage.
4. Normal voltage range: 24.5–26.8 V.

#### Shutdown

- Turn Q2 knob to vertical.

#### Emergency Stop

- Press either E-stop button on the sides of the chassis.

#### RC Operation

1. Start chassis (Q2 ON).
2. Turn on FS transmitter.
3. Set **SWB to middle** (RC mode).
4. Control with S1 (speed) and S2 (steering).

### 3.2 Charging and Battery Replacement

#### Charging

1. Chassis must be powered off (Q2 vertical).
2. Insert charger into Q1 (rear).
3. Connect charger to AC power and switch on.
4. Charge time: ~3 h from 24.5 V. Full = 26.8 V. Green LED on charger = done.

#### Battery Replacement

1. Power off chassis.
2. Press lock on battery panel to open.
3. Unplug XT60 connector and BMS connector.
4. Remove old battery; install new one.
5. Plug connectors back in; close and lock panel.

---

### 3.3 Development / CAN Protocol

CAN standard: **CAN 2.0B**, 500 kbps, **MOTOROLA** (big-endian) byte order.

#### CAN Frame Summary

| Direction | ID | Name | Cycle |
|-----------|-----|------|-------|
| Robot → PC | `0x211` | System status feedback | 100 ms |
| Robot → PC | `0x221` | Motion feedback (velocity + steer) | 20 ms |
| Robot → PC | `0x251–0x253` | Motor drive high-speed info (speed, current) | 20 ms |
| Robot → PC | `0x261–0x263` | Motor drive low-speed info (voltage, temp) | 100 ms |
| Robot → PC | `0x311` | Odometer feedback | 20 ms |
| Robot → PC | `0x361` | BMS data feedback | 500 ms |
| Robot → PC | `0x362` | BMS status feedback | 500 ms |
| Robot → PC | `0x231` | Light control feedback | 20 ms |
| Robot → PC | `0x43B` | Steering zero feedback | on request |
| PC → Robot | `0x111` | Motion command | 20 ms (watchdog 500 ms) |
| PC → Robot | `0x421` | Control mode setting | on demand |
| PC → Robot | `0x441` | Status / error clearing | on demand |
| PC → Robot | `0x121` | Light control | 20 ms |
| PC → Robot | `0x432` | Steering zero setting | on demand |
| PC → Robot | `0x433` | Steering zero query | on demand |

---

#### Table 3.1 — System Status Feedback (`0x211`, 100 ms)

Robot → PC. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0]` | Vehicle status | uint8 | `0x00` Normal · `0x01` E-stop · `0x02` Exception |
| `[1]` | Control mode | uint8 | `0x00` Standby · `0x01` CAN · `0x03` RC |
| `[2–3]` | Battery voltage | uint16 BE | Actual voltage × 10 (0.1 V resolution) |
| `[4–5]` | Fault code | uint16 BE | See fault bitmask below |
| `[6]` | Reserved | — | `0x00` |
| `[7]` | Count | uint8 | 0–255 rolling counter |

**Fault Bitmask — byte[4]:**

| Bit | Fault |
|-----|-------|
| 0 | Motor over-temperature |
| 1 | Driver over-current |
| 2 | Driver status error |
| 3–7 | Reserved |

**Fault Bitmask — byte[5]:**

| Bit | Fault |
|-----|-------|
| 0 | Battery under-voltage |
| 1 | Steering zero setting error |
| 2 | RC communication lost |
| 3 | Steering motor driver communication failure |
| 4 | Rear-right motor driver communication failure |
| 5 | Rear-left motor driver communication failure |
| 6 | Reserved |
| 7 | E-stop triggered |

---

#### Table 3.2 — Motion Feedback (`0x221`, 20 ms)

Robot → PC. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Linear velocity | int16 BE | Actual speed × 1000 (0.001 m/s); range ±4800 |
| `[2–5]` | Reserved | — | `0x00` |
| `[6–7]` | Steering angle | int16 BE | Actual inner angle × 1000 (0.001 rad); range ±400 |

---

#### Table 3.3 — Motion Command (`0x111`, 20 ms, watchdog 500 ms)

PC → Robot. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Linear velocity | int16 BE | Target speed in mm/s; range ±4800 |
| `[2–5]` | Reserved | — | `0x00` |
| `[6–7]` | Steering angle | int16 BE | Inner wheel angle × 1000 in mrad; range ±400 |

> **Watchdog:** 0x111 must be sent within every 500 ms window (recommended: 20 ms).
> If the interval exceeds 500 ms, the robot enters error state → Standby.
> Resuming normal 0x111 transmission clears the error automatically.

---

#### Table 3.4 — Control Mode Setting (`0x421`)

PC → Robot. DLC = 1. No cycle, no timeout.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0]` | Control mode | uint8 | `0x00` Standby · `0x01` CAN command mode |

> Robot powers on in **Standby** by default. Must send `0x421` with `0x01` before motion commands take effect.
> If RC transmitter is on, RC has highest authority and overrides CAN mode setting.

---

#### Table 3.5 — Status / Error Clearing (`0x441`)

PC → Robot. DLC = 1.

| Byte | Value | Action |
|------|-------|--------|
| `[0]` | `0x00` | Clear all non-critical failures |
| `[0]` | `0x01` | Clear battery under-voltage failure |
| `[0]` | `0x04` | Clear steering motor driver communication failure |
| `[0]` | `0x05` | Clear rear-right motor driver communication failure |
| `[0]` | `0x06` | Clear rear-left motor driver communication failure |

---

#### Table 3.6 — Motor Drive High-Speed Feedback (`0x251–0x253`, 20 ms)

Robot → PC. DLC = 8. One frame per motor (steering=1, right-rear=2, left-rear=3).

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Motor speed | int16 BE | RPM |
| `[2–3]` | Motor current | int16 BE | 0.1 A resolution |
| `[4–7]` | Reserved | — | `0x00` |

---

#### Table 3.7 — Motor Drive Low-Speed Feedback (`0x261–0x263`, 100 ms)

Robot → PC. DLC = 8. One frame per motor.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Drive voltage | uint16 BE | 0.1 V resolution |
| `[2–3]` | Drive temperature | int16 BE | 1 °C resolution |
| `[4]` | Motor temperature | int8 | 1 °C resolution |
| `[5]` | Drive status | uint8 | See bitmask below |
| `[6–7]` | Reserved | — | `0x00` |

**Drive Status Bitmask — byte[5]:**

| Bit | Meaning |
|-----|---------|
| 0 | Supply voltage too low |
| 1 | Motor overheated |
| 2 | Drive over-current |
| 3 | Drive overheated |
| 4 | Sensor abnormal |
| 5 | Drive error |
| 6 | Drive enabled (1 = enabled) |
| 7 | Reserved |

---

#### Table 3.10 — Steering Zero Setting (`0x432`)

PC → Robot. DLC = 2.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Zero offset | int16 BE | Pulse count; reference value 22000 ± 10000 |

---

#### Table 3.11 — Steering Zero Feedback (`0x43B`)

Robot → PC. DLC = 2. Triggered by query `0x433`.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–1]` | Zero offset | int16 BE | Returns current value; out-of-range defaults to 22000 |

---

#### Table 3.12 — Steering Zero Query (`0x433`)

PC → Robot. DLC = 1.

| Byte | Value | Description |
|------|-------|-------------|
| `[0]` | `0xAA` | Query current zero offset; reply via `0x43B` |

---

#### Table 3.13 — BMS Data Feedback (`0x361`, 500 ms)

Robot → PC. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0]` | Battery SOC | uint8 | 0–100 % |
| `[1]` | Battery SOH | uint8 | 0–100 % |
| `[2–3]` | Battery voltage | uint16 BE | 0.01 V resolution |
| `[4–5]` | Battery current | int16 BE | 0.1 A resolution |
| `[6–7]` | Battery temperature | int16 BE | 0.1 °C resolution |

---

#### Table 3.14 — BMS Status Feedback (`0x362`, 500 ms)

Robot → PC. DLC = 4.

| Byte | Field | Bits |
|------|-------|------|
| `[0]` | Alarm Status 1 | BIT1=overvoltage, BIT2=undervoltage, BIT3=high temp, BIT4=low temp, BIT7=discharge overcurrent |
| `[1]` | Alarm Status 2 | BIT0=charge overcurrent |
| `[2]` | Warning Status 1 | BIT1=overvoltage, BIT2=undervoltage, BIT3=high temp, BIT4=low temp, BIT7=discharge overcurrent |
| `[3]` | Warning Status 2 | BIT0=charge overcurrent |

---

#### Table 3.15 — Light Control (`0x121`, 20 ms, watchdog 500 ms)

PC → Robot. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0]` | Enable | uint8 | `0x00` invalid · `0x01` enabled |
| `[1]` | Light mode | uint8 | `0x00` always off · `0x01` always on |
| `[2–7]` | Reserved | — | `0x00` |

---

#### Table 3.16 — Light Control Feedback (`0x231`, 20 ms)

Robot → PC. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0]` | Enable status | uint8 | `0x00` invalid · `0x01` enabled |
| `[1]` | Current mode | uint8 | `0x00` off · `0x01` on |
| `[2–6]` | Reserved | — | `0x00` |
| `[7]` | Count | uint8 | 0–255 rolling counter |

---

#### Table 3.17 — Odometer Feedback (`0x311`, 20 ms)

Robot → PC. DLC = 8.

| Byte | Field | Type | Description |
|------|-------|------|-------------|
| `[0–3]` | Left wheel odometer | int32 BE | mm |
| `[4–7]` | Right wheel odometer | int32 BE | mm |

---

#### Sample CAN Data

Forward at 0.15 m/s:

```
0x111  [0x00, 0x96, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
```
`0x0096` = 150 mm/s = 0.15 m/s ✓

Steering 0.2 rad:

```
0x111  [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC8]
```
`0x00C8` = 200 mrad = 0.200 rad ✓

---

### 3.3.2 CAN Cable Connection

Connect CAN_H and CAN_L from the Q4 aviation plug (rear panel) to the USB-to-CAN adapter.

### 3.3.3 CAN Command Control — Startup Sequence

1. Power on Hunter SE (Q2 knob horizontal).
2. Turn on FS transmitter; set **SWB to top** (CAN command mode).
3. Connect USB-to-CAN adapter to host PC.
4. Bring up CAN interface: `sudo ip link set can0 up type can bitrate 500000`
5. Send mode switch frame `0x421` with `byte[0]=0x01` to enter CAN mode.
6. Start sending `0x111` motion frames at ≤500 ms intervals.

---

### 3.4 Firmware Upgrade

**Requirements:**
- AgileX CAN debugging module × 1
- Micro USB cable × 1
- Windows PC with `AgxCandoUpgradeToolV1.3.exe`

**Procedure:**
1. Plug in USB-to-CAN module; open upgrade tool **before** plugging in module.
2. Click "Open Serial"; power on chassis. Version info appears if connected.
3. Click "Load Firmware File" to load firmware.
4. Select node in list; click "Start Upgrade Firmware".

---

### 3.5 ROS Package Example

> Environment: Ubuntu 18.04 LTS, ROS Melodic

```bash
# Install dependency
sudo apt install -y ros-$ROS_DISTRO-teleop-twist-keyboard

# Clone and build
cd ~/catkin_ws/src
git clone https://github.com/agilexrobotics/ugv_sdk.git
git clone https://github.com/agilexrobotics/hunter_ros.git
cd ..
catkin_make

# Launch base node
roslaunch hunter_bringup hunter_robot_base.launch

# Launch keyboard teleoperation
roslaunch hunter_bringup hunter_teleop_keyboard.launch
```

References:
- https://github.com/agilexrobotics/agx_sdk
- https://github.com/agilexrobotics/hunter_ros

---

## 4. Q&A

**Q: RC transmitter cannot control the robot after correct startup?**
A: Check drive power switch is pressed down and E-stop switches are released. Check SWB is in middle position (RC mode).

**Q: CAN feedback frames received correctly but motion commands don't work?**
A: If RC mode is active (SWB middle), it overrides CAN. Set SWB to top. Verify `0x421` mode switch was sent with `byte[0]=0x01`. Check CAN frame data for correctness.

**Q: Robot makes beep-beep-beep sound?**
A: Battery voltage is in alarm state (<24.5 V). Charge immediately.

---

## 5. Product Dimensions

> Figures not available in text extraction. See original PDF pages 40–41 for dimension diagrams.

- Overall: 820 × 640 × 310 mm (L × W × H)
- Axle track: 550 mm
- Front/rear track: 460 mm
- Ground clearance: 120 mm
- Derived wheelbase (Ackermann geometry): ≈ 657 mm

*(Wheelbase derived from: R_min = 1.9 m, max inner steer = 22°, front track = 550 mm →
L = (1.9 − 0.275) × tan(22°) ≈ 0.657 m)*
