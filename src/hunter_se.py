"""
hunter_se.py -- CAN interface for the Agilex Hunter SE robot.

Protocol reference: HUNTER SE User Manual (CAN2.0B, 500 kbps, MOTOROLA byte order)
                    https://github.com/westonrobot/ugv_sdk

NOTE: Hunter SE uses Ackermann steer-by-wire, NOT differential/skid-steer.
      Motion commands specify linear velocity + front-wheel steering angle,
      not linear + angular velocity.

IMPORTANT: You must switch the robot into CAN mode before motion commands are
           accepted. Call enable_can_mode() after connecting, or the robot will
           ignore all motion commands (it powers on in Standby mode).

Quick start:
    from src.hunter_se import HunterSE
    with HunterSE() as robot:
        robot.enable_can_mode()        # required before any motion!
        robot.set_motion(0.3, 0.0)     # 0.3 m/s forward, wheels straight
        time.sleep(2)
        # stop() + close() called automatically on __exit__
"""

import can
import logging
import struct
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CAN message IDs (Hunter SE User Manual, section 3.3.3)
# ---------------------------------------------------------------------------
MOTION_CMD_ID      = 0x111   # PC -> Robot: linear velocity + steering angle
LIGHT_CMD_ID       = 0x121   # PC -> Robot: light control
MODE_CMD_ID        = 0x421   # PC -> Robot: set control mode (standby / CAN)
STATUS_CMD_ID      = 0x441   # PC -> Robot: clear faults

SYSTEM_STATUS_ID   = 0x211   # Robot -> PC: vehicle state, control mode, battery, faults (100 ms)
MOTION_FEEDBACK_ID = 0x221   # Robot -> PC: actual velocity + steering angle (20 ms)
ACTUATOR_HS_ID     = 0x251   # Robot -> PC: motor speed/current (IDs 0x251-0x253, 20 ms)
ACTUATOR_LS_ID     = 0x261   # Robot -> PC: motor voltage/temp  (IDs 0x261-0x263, 100 ms)
ODOMETER_ID        = 0x311   # Robot -> PC: left/right wheel odometer (mm)

# Control modes (byte[1] of SYSTEM_STATUS_ID frame)
CTRL_MODE_STANDBY  = 0x00
CTRL_MODE_CAN      = 0x01
CTRL_MODE_RC       = 0x03

CTRL_MODE_NAMES = {
    CTRL_MODE_STANDBY: "Standby",
    CTRL_MODE_CAN:     "CAN",
    CTRL_MODE_RC:      "RC",
}

# Physical limits per the manual
MAX_LINEAR_MPS     = 4.8    # m/s  (4800 mm/s)
MAX_STEERING_RAD   = 0.4    # rad  (400 mrad)

# Conservative defaults for safe initial use (well below hardware limits)
DEFAULT_LINEAR_MPS = 1.5    # m/s — safe starting speed for testing


@dataclass
class VehicleState:
    """Latest state received from the Hunter SE."""
    # From MOTION_FEEDBACK_ID (0x221) — actual motion
    linear_velocity:  float = 0.0   # m/s  (positive = forward)
    steering_angle:   float = 0.0   # rad  (positive = left / inner wheel)

    # From SYSTEM_STATUS_ID (0x211) — system info
    vehicle_status:   int   = 0     # 0=Normal, 1=E-stop, 2=Exception
    control_mode:     int   = 0     # 0=Standby, 1=CAN, 3=RC
    battery_voltage:  float = 0.0   # V
    fault_code:       int   = 0     # uint16 bitmask (see manual Table 3.1)
    timestamp:        float = field(default_factory=time.time)


class HunterSE:
    """
    CAN interface for the Agilex Hunter SE (Ackermann steer-by-wire chassis).

    Hunter SE is NOT a differential/skid-steer robot. It steers like a car:
    motion is controlled by (linear velocity, front-wheel steering angle).

    Parameters
    ----------
    channel : str
        SocketCAN interface name (default 'can0').
    max_linear_mps : float
        Software speed cap in m/s. Hardware limit is 4.8 m/s.
    max_steering_rad : float
        Software steering angle cap in rad. Hardware limit is ±0.4 rad.
    cmd_rate_hz : float
        Rate at which motion commands are re-sent (must be >2 Hz; recommended 20 Hz).
        Robot enters error state if no command received within 500 ms.
    """

    def __init__(
        self,
        channel: str = "can0",
        max_linear_mps: float = DEFAULT_LINEAR_MPS,
        max_steering_rad: float = MAX_STEERING_RAD,
        cmd_rate_hz: float = 20.0,
    ):
        self.max_linear   = min(max_linear_mps,  MAX_LINEAR_MPS)
        self.max_steering = min(max_steering_rad, MAX_STEERING_RAD)
        self._cmd_period  = 1.0 / cmd_rate_hz

        self.bus = can.interface.Bus(channel=channel, interface="socketcan")

        self._lock = threading.Lock()
        self._cmd_linear   = 0.0
        self._cmd_steering = 0.0
        self.state = VehicleState()

        self._running = True
        self._cmd_thread = threading.Thread(target=self._cmd_loop, daemon=True)
        self._rx_thread  = threading.Thread(target=self._rx_loop,  daemon=True)
        self._cmd_thread.start()
        self._rx_thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enable_can_mode(self) -> None:
        """
        Switch the Hunter SE into CAN command control mode.

        MUST be called before any motion commands are accepted.
        The robot powers on in Standby mode and ignores motion commands
        until this is called. (Manual section 3.3.3, Table 3.4)

        Raises RuntimeError if the CAN interface is in an error state
        (e.g. after a previous run left the TX buffer full).
        Recovery: sudo bash setup/02_setup_can_interface.sh
        """
        data = struct.pack("B7x", CTRL_MODE_CAN)
        msg  = can.Message(
            arbitration_id=MODE_CMD_ID,
            data=data,
            is_extended_id=False,
        )
        try:
            self.bus.send(msg)
        except can.CanError as e:
            raise RuntimeError(
                f"CAN TX failed ({e}).\n"
                "The interface may be in error/bus-off state.\n"
                "Recovery: sudo bash setup/02_setup_can_interface.sh"
            ) from e
        time.sleep(0.05)  # brief settle

    def set_motion(self, linear_mps: float, steering_rad: float) -> None:
        """
        Set target linear velocity and front-wheel steering angle.

        Parameters
        ----------
        linear_mps : float
            Forward speed in m/s. Negative = reverse.
        steering_rad : float
            Front wheel inner steering angle in rad.
            Positive = left turn, negative = right turn.
            Hardware limit: ±0.4 rad (±400 mrad).
        """
        with self._lock:
            self._cmd_linear   = max(-self.max_linear,   min(self.max_linear,   linear_mps))
            self._cmd_steering = max(-self.max_steering, min(self.max_steering, steering_rad))

    def stop(self) -> None:
        """Command zero velocity with wheels straight."""
        self.set_motion(0.0, 0.0)

    def get_state(self) -> VehicleState:
        """Return a snapshot of the latest vehicle state."""
        with self._lock:
            return VehicleState(
                linear_velocity = self.state.linear_velocity,
                steering_angle  = self.state.steering_angle,
                vehicle_status  = self.state.vehicle_status,
                control_mode    = self.state.control_mode,
                battery_voltage = self.state.battery_voltage,
                fault_code      = self.state.fault_code,
                timestamp       = self.state.timestamp,
            )

    def clear_faults(self) -> None:
        """Send the clear-all-faults command (0x441, byte[0]=0x00)."""
        data = struct.pack("B7x", 0x00)
        msg  = can.Message(arbitration_id=STATUS_CMD_ID, data=data, is_extended_id=False)
        self.bus.send(msg)

    def close(self) -> None:
        """Stop the robot and release resources."""
        self.stop()
        time.sleep(0.1)
        self._running = False
        self.bus.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Internal: command transmit loop
    # ------------------------------------------------------------------

    def _cmd_loop(self) -> None:
        """Re-sends the current motion command at cmd_rate_hz."""
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 5  # ~250 ms at 20 Hz before giving up
        while self._running:
            t0 = time.monotonic()
            with self._lock:
                lin   = self._cmd_linear
                steer = self._cmd_steering
            try:
                self._send_motion_cmd(lin, steer)
                consecutive_errors = 0
            except can.CanError as exc:
                consecutive_errors += 1
                err_str = str(exc)
                log.warning(
                    "CAN TX error #%d: %s  (lin=%.2f steer=%.3f)",
                    consecutive_errors, exc, lin, steer,
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log.error(
                        "CAN TX failed %d times in a row — robot watchdog will fire. "
                        "Check 'ip -details link show can0' for bus-off state.",
                        consecutive_errors,
                    )
                # ENOBUFS (errno 105): TX queue is full — retrying immediately makes
                # it worse. Sleep to let restart-ms 100 drain and recover the queue.
                if "105" in err_str or "No buffer space" in err_str:
                    time.sleep(0.15)  # 150 ms > restart-ms 100
                    continue         # skip normal sleep below; re-try sooner
            elapsed = time.monotonic() - t0
            sleep_t = self._cmd_period - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

    def _send_motion_cmd(self, linear_mps: float, steering_rad: float) -> None:
        """
        Build and send a Hunter SE motion command frame (0x111).

        Frame layout (8 bytes, big-endian / MOTOROLA format):
          byte[0-1]  linear_velocity   signed int16   unit: mm/s  (±4800)
          byte[2-5]  reserved          0x00 0x00 0x00 0x00
          byte[6-7]  steering_angle    signed int16   unit: 0.001 rad (±400)

        Reference: User Manual Table 3.3
        """
        lin_raw   = int(linear_mps  * 1000.0)          # m/s  → mm/s
        steer_raw = int(steering_rad * 1000.0)         # rad  → mrad
        lin_raw   = max(-4800, min(4800, lin_raw))
        steer_raw = max(-400,  min(400,  steer_raw))
        # ">h 4x h" = big-endian int16, 4 zero bytes, big-endian int16
        data = struct.pack(">h4xh", lin_raw, steer_raw)
        msg  = can.Message(
            arbitration_id=MOTION_CMD_ID,
            data=data,
            is_extended_id=False,
        )
        self.bus.send(msg)

    # ------------------------------------------------------------------
    # Internal: receive loop
    # ------------------------------------------------------------------

    def _rx_loop(self) -> None:
        """Parses incoming CAN frames and updates self.state."""
        while self._running:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg is None:
                    continue
                mid = msg.arbitration_id
                if mid == SYSTEM_STATUS_ID:
                    self._parse_system_status(msg.data)
                elif mid == MOTION_FEEDBACK_ID:
                    self._parse_motion_feedback(msg.data)
            except Exception:
                pass

    def _parse_system_status(self, data: bytes) -> None:
        """
        System Status Feedback Frame (0x211) — 100 ms cycle.

        byte[0]   vehicle_status  uint8   0=Normal, 1=E-stop, 2=Exception
        byte[1]   control_mode    uint8   0=Standby, 1=CAN, 3=RC
        byte[2-3] battery_voltage uint16  actual_voltage × 10  (0.1 V)
        byte[4-5] fault_code      uint16  bitmask (see manual Table 3.1)
        byte[6]   reserved
        byte[7]   count           uint8   0-255 rolling counter

        Reference: User Manual Table 3.1
        """
        if len(data) < 6:
            return
        vehicle_status = data[0]
        ctrl_mode      = data[1]
        batt_raw       = struct.unpack_from(">H", data, 2)[0]
        fault_code     = struct.unpack_from(">H", data, 4)[0]
        with self._lock:
            self.state.vehicle_status  = vehicle_status
            self.state.control_mode    = ctrl_mode
            self.state.battery_voltage = batt_raw / 10.0
            self.state.fault_code      = fault_code
            self.state.timestamp       = time.time()

    def _parse_motion_feedback(self, data: bytes) -> None:
        """
        Movement Control Feedback Frame (0x221) — 20 ms cycle.

        byte[0-1]  linear_velocity  signed int16  actual_speed × 1000 (0.001 m/s)
        byte[2-5]  reserved
        byte[6-7]  steering_angle   signed int16  actual_angle × 1000 (0.001 rad)

        Reference: User Manual Table 3.2
        """
        if len(data) < 8:
            return
        lin_raw   = struct.unpack_from(">h", data, 0)[0]
        steer_raw = struct.unpack_from(">h", data, 6)[0]
        with self._lock:
            self.state.linear_velocity = lin_raw   / 1000.0
            self.state.steering_angle  = steer_raw / 1000.0
            self.state.timestamp       = time.time()
