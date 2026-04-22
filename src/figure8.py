"""
figure8.py -- Figure-8 trajectory for the Agilex Hunter SE.

Each lobe of the figure-8 is a 180° arc.  Left arc followed by right arc
gives one complete figure-8.  Arc time is computed automatically from the
robot geometry and the chosen speed/steering, or can be overridden.

Geometry (from User Manual, section 1.2):
  Wheelbase ≈ 657 mm, front track = 550 mm, min turning radius = 1.9 m
  At steering=0.35 rad, speed=0.3 m/s  →  R ≈ 2.07 m, arc_time ≈ 22 s

Usage:
    # Direct CAN (default)
    python3 src/figure8.py --dry-run
    python3 src/figure8.py --speed 0.2 --steering 0.35

    # Via ROS2 (hunter_se_node.py must be running)
    python3 src/figure8.py --speed 0.2 --steering 0.35 --ros
    python3 src/figure8.py --speed 0.3 --steering 0.35 --loops 2 --ros

    # Simulation (no robot needed — opens a matplotlib window)
    python3 src/figure8.py --sim
    python3 src/figure8.py --sim --sim-speed 10   # 10× faster than real time
    python3 src/figure8.py --sim --speed 0.3 --steering 0.35 --loops 2 --sim-speed 5

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

from trajectory import arc_duration, drive_arc, turning_radius
import trajectory as _trajectory


def run_figure8(
    speed:    float = 0.3,
    steering: float = 0.35,
    arc_time: float = None,   # None = auto-compute for 180° arc
    loops:    int   = 1,
    channel:  str   = "can0",
    dry_run:  bool  = False,
    use_ros:  bool  = False,
    use_sim:  bool  = False,
    sim_speed: float = 1.0,
) -> None:
    if arc_time is None:
        arc_time = arc_duration(math.pi, steering, speed)

    R         = turning_radius(steering)
    sweep_deg = math.degrees(speed * arc_time / R)
    total     = loops * 2 * arc_time

    mode_str = "Simulation" if use_sim else ("ROS2 /cmd_vel" if use_ros else "Direct CAN")

    print("=== Hunter SE Figure-8 ===")
    print(f"  Mode:           {mode_str}" + (f"  ({sim_speed}× speed)" if use_sim and sim_speed != 1 else ""))
    print(f"  Speed:          {speed:.2f} m/s")
    print(f"  Steering:       ±{steering:.3f} rad")
    print(f"  Turning radius: {R:.2f} m")
    print(f"  Arc duration:   {arc_time:.1f} s  (= {sweep_deg:.0f}° sweep)")
    print(f"  Loops:          {loops}")
    print(f"  Total time:     {total:.1f} s" + (f"  (~{total/sim_speed:.1f} s wall-clock)" if use_sim and sim_speed != 1 else ""))
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
            for loop_num in range(1, loops + 1):
                print(f"[Loop {loop_num}/{loops}]")
                drive_arc(robot, speed, steering, direction="left",  duration=arc_time)
                drive_arc(robot, speed, steering, direction="right", duration=arc_time)
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
            "  steering=0.35, speed=0.3  →  ~18.8 s per arc\n"
            "  steering=0.35, speed=0.2  →  ~28.3 s per arc\n"
            "  steering=0.40, speed=0.3  →  ~16.3 s per arc\n"
        ),
    )
    parser.add_argument("--speed",    type=float, default=0.3,  help="Forward speed in m/s (default 0.3)")
    parser.add_argument("--steering", type=float, default=0.35, help="Steering angle in rad (default 0.35, max 0.4)")
    parser.add_argument("--arc-time", type=float, default=None, help="Seconds per arc (default: auto for 180°)")
    parser.add_argument("--loops",    type=int,   default=1,    help="Number of figure-8 loops (default 1)")
    parser.add_argument("--channel",  default="can0",           help="SocketCAN interface (default can0, CAN mode only)")
    parser.add_argument("--dry-run",  action="store_true",      help="Print plan without moving")
    parser.add_argument("--ros",      action="store_true",      help="Send commands via ROS2 /cmd_vel (hunter_se_node.py must be running)")
    parser.add_argument("--sim",      action="store_true",      help="Simulate trajectory with matplotlib visualisation (no robot needed)")
    parser.add_argument("--sim-speed", type=float, default=1.0, metavar="N", help="Simulation speed multiplier, e.g. 10 = 10× faster (default 1.0)")
    args = parser.parse_args()

    if args.sim_speed <= 0:
        parser.error("--sim-speed must be a positive number (e.g. 1.0, 5, 10)")
    if args.speed <= 0:
        parser.error("--speed must be a positive number")
    if not (0 < args.steering <= 0.4):
        parser.error("--steering must be between 0 and 0.4 rad (hardware maximum)")

    run_figure8(
        speed    = args.speed,
        steering = args.steering,
        arc_time = args.arc_time,
        loops    = args.loops,
        channel  = args.channel,
        dry_run  = args.dry_run,
        use_ros  = args.ros,
        use_sim  = args.sim,
        sim_speed = args.sim_speed,
    )


if __name__ == "__main__":
    main()

