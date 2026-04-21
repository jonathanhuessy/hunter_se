"""
figure8.py -- Figure-8 trajectory for the Agilex Hunter SE.

Each lobe of the figure-8 is a 180° arc.  Left arc followed by right arc
gives one complete figure-8.  Arc time is computed automatically from the
robot geometry and the chosen speed/steering, or can be overridden.

Geometry (from User Manual, section 1.2):
  Wheelbase ≈ 657 mm, front track = 550 mm, min turning radius = 1.9 m
  At steering=0.35 rad, speed=0.3 m/s  →  R ≈ 2.07 m, arc_time ≈ 22 s

Usage:
    python3 src/figure8.py --dry-run
    python3 src/figure8.py --speed 0.2 --steering 0.35
    python3 src/figure8.py --speed 0.3 --steering 0.35 --loops 2

SAFETY:
    - Keep RC remote in hand at all times.
    - First test at --speed 0.2 on a clear surface.
    - Ensure ≥5 m clearance on all sides (turning radius ~2 m).
"""

import argparse
import logging
import math
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, str(Path(__file__).parent))

from hunter_se import HunterSE
from trajectory import arc_duration, drive_arc, turning_radius


def run_figure8(
    speed:    float = 0.3,
    steering: float = 0.35,
    arc_time: float = None,   # None = auto-compute for 180° arc
    loops:    int   = 1,
    channel:  str   = "can0",
    dry_run:  bool  = False,
) -> None:
    if arc_time is None:
        arc_time = arc_duration(math.pi, steering, speed)

    R         = turning_radius(steering)
    sweep_deg = math.degrees(speed * arc_time / R)
    total     = loops * 2 * arc_time

    print("=== Hunter SE Figure-8 ===")
    print(f"  Speed:          {speed:.2f} m/s")
    print(f"  Steering:       ±{steering:.3f} rad")
    print(f"  Turning radius: {R:.2f} m")
    print(f"  Arc duration:   {arc_time:.1f} s  (= {sweep_deg:.0f}° sweep)")
    print(f"  Loops:          {loops}")
    print(f"  Total time:     {total:.1f} s")
    print()

    if dry_run:
        print("Dry run — no commands sent.")
        return

    input("Press Enter to start (Ctrl+C to abort)...")
    print()

    with HunterSE(channel=channel) as robot:
        print("Enabling CAN command mode...")
        robot.enable_can_mode()
        time.sleep(0.2)

        state = robot.get_state()
        print(f"Battery: {state.battery_voltage:.1f}V  Mode: {state.control_mode}")
        if state.fault_code:
            print(f"WARNING: Active fault code 0x{state.fault_code:04X}")
        print()

        try:
            for loop_num in range(1, loops + 1):
                print(f"[Loop {loop_num}/{loops}]")
                drive_arc(robot, speed, steering, direction="left",  duration=arc_time)
                drive_arc(robot, speed, steering, direction="right", duration=arc_time)
        except KeyboardInterrupt:
            print("\nAborted by user.")
        finally:
            robot.stop()
            print("Robot stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Hunter SE figure-8 trajectory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "arc-time defaults to the computed 180° semicircle duration:\n"
            "  steering=0.35, speed=0.3  →  ~22 s per arc\n"
            "  steering=0.35, speed=0.2  →  ~33 s per arc\n"
            "  steering=0.40, speed=0.3  →  ~19 s per arc\n"
        ),
    )
    parser.add_argument("--speed",    type=float, default=0.3,  help="Forward speed in m/s (default 0.3)")
    parser.add_argument("--steering", type=float, default=0.35, help="Steering angle in rad (default 0.35, max 0.4)")
    parser.add_argument("--arc-time", type=float, default=None, help="Seconds per arc (default: auto for 180°)")
    parser.add_argument("--loops",    type=int,   default=1,    help="Number of figure-8 loops (default 1)")
    parser.add_argument("--channel",  default="can0",           help="SocketCAN interface (default can0)")
    parser.add_argument("--dry-run",  action="store_true",      help="Print plan without moving")
    args = parser.parse_args()

    run_figure8(
        speed    = args.speed,
        steering = args.steering,
        arc_time = args.arc_time,
        loops    = args.loops,
        channel  = args.channel,
        dry_run  = args.dry_run,
    )


if __name__ == "__main__":
    main()

