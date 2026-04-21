"""
square.py -- Square trajectory for the Agilex Hunter SE.

Drives a square: straight 2 m, 90° right turn, repeat 4 times.

Geometry (from User Manual, section 1.2):
  Wheelbase ≈ 657 mm, front track = 550 mm
  90° arc at steering=0.35 rad, speed=0.3 m/s  →  R ≈ 2.07 m, turn_time ≈ 10.8 s

The square is driven clockwise (right turns).  Pass --direction left for
counter-clockwise.

Usage:
    python3 src/square.py --dry-run
    python3 src/square.py --speed 0.2 --side 2.0 --steering 0.35
    python3 src/square.py --speed 0.3 --side 2.0 --steering 0.35 --direction left

SAFETY:
    - Keep RC remote in hand at all times.
    - First test at --speed 0.2 on a clear surface.
    - Ensure ≥(side + 2×R) clearance: ~6 m for default settings.
    - Max hardware steering angle is ±0.4 rad.
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
from trajectory import arc_duration, drive_arc, drive_straight, turning_radius


def run_square(
    speed:     float = 0.3,
    side_m:    float = 2.0,
    steering:  float = 0.35,
    direction: str   = "right",
    channel:   str   = "can0",
    dry_run:   bool  = False,
) -> None:
    R         = turning_radius(steering)
    turn_time = arc_duration(math.pi / 2, steering, speed)
    side_time = side_m / speed
    total     = 4 * (side_time + turn_time)

    print("=== Hunter SE Square ===")
    print(f"  Speed:           {speed:.2f} m/s")
    print(f"  Side length:     {side_m:.2f} m  ({side_time:.1f} s per side)")
    print(f"  Steering:        {steering:.3f} rad  ({direction})")
    print(f"  Turning radius:  {R:.2f} m")
    print(f"  90° turn time:   {turn_time:.1f} s per corner")
    print(f"  Total time:      {total:.1f} s")
    print()
    print("  Sequence (×4):  straight → 90° turn → straight → ...")
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
            for corner in range(1, 5):
                print(f"[Side {corner}/4]")
                drive_straight(robot, side_m, speed)
                print(f"[Corner {corner}/4]")
                drive_arc(robot, speed, steering, direction=direction, angle_rad=math.pi / 2)
        except KeyboardInterrupt:
            print("\nAborted by user.")
        finally:
            robot.stop()
            print("Robot stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Hunter SE square trajectory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The robot drives a square clockwise by default (--direction right).\n"
            "90° corner duration is computed from geometry:\n"
            "  steering=0.35, speed=0.3  →  ~10.8 s per corner\n"
            "  steering=0.35, speed=0.2  →  ~16.2 s per corner\n"
            "  steering=0.40, speed=0.3  →   ~9.6 s per corner\n"
        ),
    )
    parser.add_argument("--speed",     type=float, default=0.3,   help="Forward speed in m/s (default 0.3)")
    parser.add_argument("--side",      type=float, default=2.0,   help="Side length in metres (default 2.0)")
    parser.add_argument("--steering",  type=float, default=0.35,  help="Steering angle in rad for corners (default 0.35, max 0.4)")
    parser.add_argument("--direction", choices=["left", "right"], default="right", help="Turn direction at each corner (default right = clockwise)")
    parser.add_argument("--channel",   default="can0",            help="SocketCAN interface (default can0)")
    parser.add_argument("--dry-run",   action="store_true",       help="Print plan without moving")
    args = parser.parse_args()

    run_square(
        speed     = args.speed,
        side_m    = args.side,
        steering  = args.steering,
        direction = args.direction,
        channel   = args.channel,
        dry_run   = args.dry_run,
    )


if __name__ == "__main__":
    main()
