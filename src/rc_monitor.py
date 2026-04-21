"""
rc_monitor.py -- Monitor CAN traffic while operating the Hunter SE with RC.

Run this while controlling the robot via remote control. It will:
  - Print live vehicle state (velocities, battery, control mode)
  - Log all raw CAN frames to a timestamped .log file for later analysis

Usage:
    python3 src/rc_monitor.py [--channel can0] [--log]

Ctrl+C to stop.
"""

import argparse
import can
import csv
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from hunter_se import CTRL_MODE_NAMES, HunterSE


_VEHICLE_STATUS_NAMES = ["Normal", "E-stop", "Exception"]


def main():
    parser = argparse.ArgumentParser(description="Hunter SE RC monitor")
    parser.add_argument("--channel", default="can0", help="SocketCAN interface (default: can0)")
    parser.add_argument("--log", action="store_true", help="Log all raw frames to CSV file")
    args = parser.parse_args()

    robot = HunterSE(channel=args.channel)

    log_file = None
    log_writer = None
    if args.log:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(f"rc_session_{ts}.csv")
        log_file = open(log_path, "w", newline="")
        log_writer = csv.writer(log_file)
        log_writer.writerow(["timestamp", "id_hex", "dlc", "data_hex"])

        # Tap into the bus to log raw frames alongside normal rx processing
        original_recv = robot.bus.recv
        def _logging_recv(timeout=None):
            msg = original_recv(timeout=timeout)
            if msg is not None and log_writer:
                log_writer.writerow([
                    f"{msg.timestamp:.6f}",
                    f"0x{msg.arbitration_id:03X}",
                    msg.dlc,
                    msg.data.hex(),
                ])
            return msg
        robot.bus.recv = _logging_recv

        print(f"Logging raw frames to: {log_path}")

    def _stop(sig, frame):
        print("\nStopping...")
        robot.stop()
        if log_file:
            log_file.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)

    print(f"Monitoring {args.channel}  (Ctrl+C to stop)")
    print("-" * 60)

    while True:
        time.sleep(0.2)
        s = robot.state
        vstatus  = _VEHICLE_STATUS_NAMES[min(s.vehicle_status, 2)]
        mode     = CTRL_MODE_NAMES.get(s.control_mode, f"0x{s.control_mode:02X}")
        fault_str = f" FAULT=0x{s.fault_code:04X}" if s.fault_code else ""
        print(
            f"\r  mode={mode:7s}  status={vstatus:6s}  "
            f"lin={s.linear_velocity:+.3f} m/s  "
            f"steer={s.steering_angle:+.4f} rad  "
            f"batt={s.battery_voltage:.1f}V"
            f"{fault_str}          ",
            end="",
            flush=True,
        )


if __name__ == "__main__":
    main()

