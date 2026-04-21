"""
trajectory.py -- Primitive motion building blocks for the Agilex Hunter SE.

Geometry derived from User Manual (section 1.2):
  Front wheel track T:    550 mm
  Min turning radius:     1.9 m  (centre of vehicle at max steer = 22° = 0.4 rad)
  Derived wheelbase L:    ~657 mm

  Turning radius at steering angle δ (rad):
    R_centre = L / tan(δ) + T/2

  Duration for arc sweep of θ (rad) at speed v (m/s):
    t = θ × R_centre / v

Building blocks
---------------
  drive_straight(robot, distance_m, speed_mps)
  drive_arc(robot, speed_mps, steering_rad, direction, angle_rad, duration)

These two functions are the sole motion primitives.  All trajectories are
composed from them.  Both accept a `HunterSE` instance that must already be
in CAN command mode (call robot.enable_can_mode() before starting).
"""

import math
import time
from typing import Literal

# Geometry constants — derived from Hunter SE User Manual section 1.2
WHEELBASE_M    = 0.657   # m   estimated from: R_min=1.9 m, max_steer=22°, T=0.55 m
FRONT_TRACK_M  = 0.550   # m   front wheel track width (axle track)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def turning_radius(steering_rad: float) -> float:
    """
    Centre-of-vehicle turning radius for a given Ackermann steering angle.

    Parameters
    ----------
    steering_rad : magnitude of front-wheel inner steering angle (rad).

    Returns
    -------
    Radius in metres.
    """
    return WHEELBASE_M / math.tan(abs(steering_rad)) + FRONT_TRACK_M / 2


def arc_duration(angle_rad: float, steering_rad: float, speed_mps: float) -> float:
    """
    Time (seconds) needed to sweep `angle_rad` along a circular arc.

    Parameters
    ----------
    angle_rad    : heading change / arc sweep angle (rad).  e.g. math.pi for 180°.
    steering_rad : front-wheel inner steering angle magnitude (rad).
    speed_mps    : forward speed (m/s).
    """
    return angle_rad * turning_radius(steering_rad) / speed_mps


# ---------------------------------------------------------------------------
# Motion primitives
# ---------------------------------------------------------------------------

def drive_straight(robot, distance_m: float, speed_mps: float) -> None:
    """
    Drive forward in a straight line.

    Parameters
    ----------
    robot       : HunterSE instance (must be in CAN mode).
    distance_m  : distance to travel (m).
    speed_mps   : forward speed (m/s).
    """
    duration = distance_m / speed_mps
    print(f"  → Straight  {distance_m:.2f} m  @ {speed_mps:.2f} m/s  ({duration:.1f} s)")
    robot.set_motion(speed_mps, 0.0)
    _wait(duration)


def drive_arc(
    robot,
    speed_mps:    float,
    steering_rad: float,
    direction:    Literal["left", "right"] = "left",
    angle_rad:    float = math.pi,
    duration:     float = None,
) -> None:
    """
    Drive along a circular arc.

    Parameters
    ----------
    robot        : HunterSE instance (must be in CAN mode).
    speed_mps    : forward speed (m/s).
    steering_rad : front-wheel inner steering angle magnitude (rad, 0 < x ≤ 0.4).
    direction    : 'left' turns the robot left, 'right' turns it right.
    angle_rad    : arc sweep / heading change in radians (default π = 180° semicircle).
                   Ignored when `duration` is provided explicitly.
    duration     : arc duration in seconds.  If None, computed from angle_rad + geometry.
    """
    R = turning_radius(steering_rad)
    if duration is None:
        duration = arc_duration(angle_rad, steering_rad, speed_mps)
    actual_deg = math.degrees(speed_mps * duration / R)
    signed_steer = steering_rad if direction == "left" else -steering_rad
    print(
        f"  → Arc  {direction:5s}  steer={steering_rad:.3f} rad  "
        f"R={R:.2f} m  {actual_deg:.0f}°  ({duration:.1f} s)"
    )
    robot.set_motion(speed_mps, signed_steer)
    _wait(duration)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wait(duration: float, report_hz: float = 2.0) -> None:
    """Busy-sleep for `duration` seconds, printing a live countdown."""
    t0    = time.monotonic()
    dt    = 1.0 / report_hz
    steps = max(1, int(duration / dt))
    for _ in range(steps):
        elapsed   = time.monotonic() - t0
        remaining = max(0.0, duration - elapsed)
        print(f"    {elapsed:.1f}s elapsed  ({remaining:.1f}s remaining)", end="\r")
        time.sleep(dt)
    time.sleep(max(0.0, duration - (time.monotonic() - t0)))
    print()
