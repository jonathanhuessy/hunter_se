---
name: hunter-trajectory
description: >-
  Trajectory math, velocity profiling, and motion script generation for the
  Agilex Hunter SE. Use this skill for figure-8, square, circle paths, or
  adding speed ramps and closed-loop control.
---

# Hunter SE — Trajectory Skill

## Robot Kinematics

Hunter SE is an **Ackermann steer-by-wire** robot (like a car), NOT skid-steer.

```
linear_velocity = v         (m/s, positive = forward)
steering_angle  = δ         (rad, positive = left / inner wheel)
turning_radius  ≈ L / tan(δ)    where L = wheelbase (approx. 0.65 m)
```

Hardware limits: `v` ∈ ±4.8 m/s,  `δ` ∈ ±0.4 rad

> ⚠️ Always call `robot.enable_can_mode()` before sending any motion commands.

---

## Figure-8 Math (Ackermann)

A figure-8 = two timed arcs with opposite steering angles:

```
Arc 1 (left turn):   set_motion(+v, +δ)  for T seconds
Arc 2 (right turn):  set_motion(+v, -δ)  for T seconds
```

**Choosing T:** Time-based — tune empirically on your surface.
A larger `|δ|` gives a tighter turn; a larger `T` gives a bigger loop.

### Starter values

| Speed | Steering | Arc time | Approx footprint |
|-------|----------|----------|-----------------|
| 0.15  | 0.30 rad | 8 s      | ~2 m × 1.5 m    |
| 0.30  | 0.30 rad | 6 s      | ~3 m × 2 m      |
| 0.30  | 0.40 rad | 5 s      | ~2 m × 1.5 m    |

### Run figure-8

```bash
python3 src/figure8.py --dry-run
python3 src/figure8.py --speed 0.15 --steering 0.3 --arc-time 8
python3 src/figure8.py --speed 0.3  --steering 0.3 --arc-time 6 --loops 2
```

---

## Other Path Primitives

### Circle
```python
robot.enable_can_mode()
robot.set_motion(speed, steering_angle)        # constant steer = constant circle
time.sleep(arc_time)                           # tune arc_time for full circle
robot.stop()
```

### Square (4 sides)
```python
SIDE    = 1.0   # m
SPEED   = 0.3   # m/s
STEER   = 0.35  # rad — near-max for tight 90° turns
TURN_T  = 2.5   # s   — tune empirically for ~90° turn

robot.enable_can_mode()
for _ in range(4):
    robot.set_motion(SPEED, 0)          # straight
    time.sleep(SIDE / SPEED)
    robot.set_motion(SPEED, STEER)      # left 90°
    time.sleep(TURN_T)
robot.stop()
```

### Straight + return
```python
robot.enable_can_mode()
robot.set_motion(0.3, 0)
time.sleep(3.0)
robot.set_motion(-0.3, 0)   # reverse
time.sleep(3.0)
robot.stop()
```

---

## Adding a Speed Ramp (trapezoidal profile)

```python
import time

def ramp_motion(robot, target_linear, target_steering,
                ramp_time=0.5, steps=20):
    dt = ramp_time / steps
    for i in range(1, steps + 1):
        alpha = i / steps
        robot.set_motion(target_linear * alpha, target_steering * alpha)
        time.sleep(dt)
```

---

## Closed-Loop Figure-8 (future / phase 2)

Once odometry from the odometer frame (0x311) is integrated:

```python
from src.hunter_se import HunterSE
import math, time

def figure8_closed(speed=0.3, steering=0.3, arc_dist=2.0):
    x = y = 0.0
    last_t = time.time()

    with HunterSE() as robot:
        robot.enable_can_mode()
        for sign in [+1, -1]:
            robot.set_motion(speed, sign * steering)
            x = y = 0.0
            while True:
                s  = robot.get_state()
                dt = time.time() - last_t
                last_t = time.time()
                # Dead-reckoning (approximate — Ackermann path curvature)
                x += s.linear_velocity * dt
                if math.hypot(x, y) >= arc_dist:
                    break
```

---

## Safety Checklist Before Running

- [ ] Clear flat surface, ≥3 m clearance on all sides
- [ ] RC remote in hand — can cut power anytime
- [ ] First test at `--speed 0.15 --steering 0.3 --arc-time 8`
- [ ] `candump can0` in a separate terminal to confirm 0x111 commands appear
- [ ] Battery > 24.5 V (check `state.battery_voltage`)
- [ ] Robot switches to CAN mode (`rc_monitor.py` shows `mode=CAN`)

