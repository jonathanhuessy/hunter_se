"""
square.py -- Square trajectory for the Agilex Hunter SE.

Drives a square: straight 2 m, 90° right turn, repeat 4 times.

Geometry (from User Manual, section 1.2):
  Wheelbase ≈ 657 mm, front track = 550 mm
  90° arc at steering=0.35 rad, speed=0.3 m/s  →  R_yaw ≈ 1.80 m, turn_time ≈ 9.4 s

The square is driven clockwise (right turns).  Pass --direction left for
counter-clockwise.

Usage:
    # Direct CAN (default)
    python3 src/square.py --dry-run
    python3 src/square.py --speed 0.2 --side 2.0 --steering 0.35

    # Via ROS2 (hunter_se_node.py must be running)
    python3 src/square.py --speed 0.2 --side 2.0 --steering 0.35 --ros
    python3 src/square.py --speed 0.3 --side 2.0 --steering 0.35 --direction left --ros

    # Simulation (no robot needed — opens a matplotlib window)
    python3 src/square.py --sim
    python3 src/square.py --sim --sim-speed 10   # 10× faster than real time
    python3 src/square.py --sim --speed 0.3 --side 3.0 --sim-speed 5

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

from trajectory import arc_duration, drive_arc, drive_straight, turning_radius
import trajectory as _trajectory


def run_square(
    speed:     float = 0.3,
    side_m:    float = 2.0,
    steering:  float = 0.35,
    direction: str   = "right",
    channel:   str   = "can0",
    dry_run:   bool  = False,
    use_ros:   bool  = False,
    use_sim:   bool  = False,
    sim_speed: float = 1.0,
) -> None:
    R         = turning_radius(steering)
    turn_time = arc_duration(math.pi / 2, steering, speed)
    side_time = side_m / speed
    total     = 4 * (side_time + turn_time)

    mode_str = "Simulation" if use_sim else ("ROS2 /cmd_vel" if use_ros else "Direct CAN")

    print("=== Hunter SE Square ===")
    print(f"  Mode:            {mode_str}" + (f"  ({sim_speed}× speed)" if use_sim and sim_speed != 1 else ""))
    print(f"  Speed:           {speed:.2f} m/s")
    print(f"  Side length:     {side_m:.2f} m  ({side_time:.1f} s per side)")
    print(f"  Steering:        {steering:.3f} rad  ({direction})")
    print(f"  Turning radius:  {R:.2f} m")
    print(f"  90° turn time:   {turn_time:.1f} s per corner")
    print(f"  Total time:      {total:.1f} s" + (f"  (~{total/sim_speed:.1f} s wall-clock)" if use_sim and sim_speed != 1 else ""))
    print()
    print("  Sequence (×4):  straight → 90° turn → straight → ...")
    print()

    if dry_run:
        print("Dry run — no commands sent.")
        return

    if not use_sim:
        input("Press Enter to start (Ctrl+C to abort)...")
        print()

    if use_sim:
        from sim_robot import SimRobot
        _trajectory.set_speed_factor(sim_speed)

        def _sim_traj(robot):
            print("Enabling CAN command mode...")
            robot.enable_can_mode()
            time.sleep(0.2 / sim_speed)
            print()
            for corner in range(1, 5):
                print(f"[Side {corner}/4]")
                drive_straight(robot, side_m, speed)
                print(f"[Corner {corner}/4]")
                drive_arc(robot, speed, steering, direction=direction, angle_rad=math.pi / 2)
            print("Simulation done.")

        SimRobot(speed_factor=sim_speed).run_simulation(_sim_traj)
        return

    elif use_ros:
        from ros_robot import RosRobot
        robot_ctx = RosRobot()
    else:
        from hunter_se import HunterSE
        robot_ctx = HunterSE(channel=channel)

    with robot_ctx as robot:
        print("Enabling CAN command mode...")
        robot.enable_can_mode()
        time.sleep(0.2)

        state = robot.get_state()
        if state.battery_voltage:
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
            "  steering=0.35, speed=0.3  →  ~9.4 s per corner\n"
            "  steering=0.35, speed=0.2  →  ~14.1 s per corner\n"
            "  steering=0.40, speed=0.3  →  ~8.1 s per corner\n"
        ),
    )
    parser.add_argument("--speed",     type=float, default=0.3,   help="Forward speed in m/s (default 0.3)")
    parser.add_argument("--side",      type=float, default=2.0,   help="Side length in metres (default 2.0)")
    parser.add_argument("--steering",  type=float, default=0.35,  help="Steering angle in rad for corners (default 0.35, max 0.4)")
    parser.add_argument("--direction", choices=["left", "right"], default="right", help="Turn direction at each corner (default right = clockwise)")
    parser.add_argument("--channel",   default="can0",            help="SocketCAN interface (default can0, CAN mode only)")
    parser.add_argument("--dry-run",   action="store_true",       help="Print plan without moving")
    parser.add_argument("--ros",       action="store_true",       help="Send commands via ROS2 /cmd_vel (hunter_se_node.py must be running)")
    parser.add_argument("--sim",       action="store_true",       help="Simulate trajectory with matplotlib visualisation (no robot needed)")
    parser.add_argument("--sim-speed", type=float, default=1.0,  metavar="N", help="Simulation speed multiplier, e.g. 10 = 10× faster (default 1.0)")
    args = parser.parse_args()

    if args.sim_speed <= 0:
        parser.error("--sim-speed must be a positive number (e.g. 1.0, 5, 10)")
    if args.speed <= 0:
        parser.error("--speed must be a positive number")
    if not (0 < args.steering <= 0.4):
        parser.error("--steering must be between 0 and 0.4 rad (hardware maximum)")
    if args.side <= 0:
        parser.error("--side must be a positive number")

    run_square(
        speed     = args.speed,
        side_m    = args.side,
        steering  = args.steering,
        direction = args.direction,
        channel   = args.channel,
        dry_run   = args.dry_run,
        use_ros   = args.ros,
        use_sim   = args.sim,
        sim_speed = args.sim_speed,
    )


if __name__ == "__main__":
    main()
