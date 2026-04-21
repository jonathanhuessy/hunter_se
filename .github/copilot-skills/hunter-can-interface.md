---
name: hunter-can-interface
description: >-
  CAN protocol reference and Python code generation for the Agilex Hunter SE.
  Use this skill when writing code to send commands, read state, or extend
  the HunterSE Python class.
---

# Hunter SE — CAN Interface Skill

## Protocol Summary

**Bitrate:** 500 kbps  
**Standard:** CAN 2.0B, MOTOROLA byte order (big-endian)  
**Frame type:** Standard (11-bit IDs), 8-byte data  
**Reference:** Hunter SE User Manual section 3.3.3

> ⚠️ **Hunter SE is Ackermann steer-by-wire, not skid-steer.**  
> Motion commands use **(linear velocity, steering angle)** — like a car.  
> There is no "angular velocity" input.

---

## ⚠️ CAN Mode Switch Required

The robot powers on in **Standby mode** and ignores all motion commands.  
You must send a mode-switch command before any motion is accepted:

```python
# Send once after connecting
robot.enable_can_mode()   # sends 0x421 with byte[0]=0x01
```

Or manually:
```python
import can, struct
bus.send(can.Message(arbitration_id=0x421, data=struct.pack("B7x", 0x01), is_extended_id=False))
```

---

## Motion Command Frame (PC → Robot)

**ID:** `0x111`  Cycle: 20 ms  Timeout: 500 ms

| Byte | Field             | Type    | Unit        | Range   |
|------|-------------------|---------|-------------|---------|
| 0-1  | linear_velocity   | int16   | mm/s        | ±4800   |
| 2-5  | reserved          | —       | 0x00000000  | —       |
| 6-7  | steering_angle    | int16   | 0.001 rad   | ±400    |

```python
import can, struct

def send_motion_cmd(bus, linear_mps, steering_rad):
    lin   = int(linear_mps   * 1000)   # m/s  → mm/s
    steer = int(steering_rad * 1000)   # rad  → mrad
    lin   = max(-4800, min(4800, lin))
    steer = max(-400,  min(400,  steer))
    data  = struct.pack(">h4xh", lin, steer)
    bus.send(can.Message(arbitration_id=0x111, data=data, is_extended_id=False))
```

**Watchdog:** Must send at < 500 ms intervals (recommended 20 ms / 50 Hz).  
Robot enters error state and stops if command gap exceeds 500 ms.

---

## System Status Frame (Robot → PC)

**ID:** `0x211`  Rate: 100 ms

| Byte | Field           | Type    | Unit  | Notes                          |
|------|-----------------|---------|-------|--------------------------------|
| 0    | vehicle_status  | uint8   | —     | 0=Normal, 1=E-stop, 2=Exception|
| 1    | control_mode    | uint8   | —     | 0=Standby, 1=CAN, 3=RC         |
| 2-3  | battery_voltage | uint16  | 0.1 V | divide by 10 for volts         |
| 4-5  | fault_code      | uint16  | —     | bitmask (see manual Table 3.1) |
| 6    | reserved        | —       | —     |                                |
| 7    | count           | uint8   | —     | rolling 0-255 counter          |

```python
def parse_system_status(data):
    vehicle_status = data[0]
    ctrl_mode      = data[1]
    batt_v         = struct.unpack_from(">H", data, 2)[0] / 10.0
    fault_code     = struct.unpack_from(">H", data, 4)[0]
    return vehicle_status, ctrl_mode, batt_v, fault_code
```

---

## Motion Feedback Frame (Robot → PC)

**ID:** `0x221`  Rate: 20 ms

| Byte | Field             | Type  | Unit       |
|------|-------------------|-------|------------|
| 0-1  | linear_velocity   | int16 | 0.001 m/s  |
| 2-5  | reserved          | —     | —          |
| 6-7  | steering_angle    | int16 | 0.001 rad  |

```python
def parse_motion_feedback(data):
    lin_mps   = struct.unpack_from(">h", data, 0)[0] / 1000.0
    steer_rad = struct.unpack_from(">h", data, 6)[0] / 1000.0
    return lin_mps, steer_rad
```

---

## Control Mode Setting (PC → Robot)

**ID:** `0x421`  (send once to switch mode)

| byte[0] | Mode    |
|---------|---------|
| 0x00    | Standby |
| 0x01    | CAN command mode |

---

## Using the HunterSE Class

```python
from src.hunter_se import HunterSE

with HunterSE(channel="can0") as robot:
    robot.enable_can_mode()            # required first!
    robot.set_motion(0.3, 0.0)         # 0.3 m/s forward, wheels straight
    time.sleep(2.0)
    robot.set_motion(0.3, +0.3)        # 0.3 m/s, turning left
    time.sleep(2.0)
    # stop() + close() called automatically on __exit__

state = robot.get_state()
print(state.linear_velocity, state.steering_angle, state.battery_voltage)
```

---

## Fault Codes (byte[4-5] of 0x211 frame)

| Byte | Bit | Meaning |
|------|-----|---------|
| byte[4] | bit0 | Motor over-temperature |
| byte[4] | bit1 | Driver over-current |
| byte[4] | bit2 | Driver status error |
| byte[5] | bit0 | Battery under-voltage |
| byte[5] | bit1 | Steering zero setting error |
| byte[5] | bit2 | RC communication lost |
| byte[5] | bit7 | E-stop triggered |

Clear all faults: `robot.clear_faults()` → sends `0x441` byte[0]=`0x00`
