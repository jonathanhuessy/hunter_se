"""
ros_robot.py -- ROS2 adapter that mimics the HunterSE interface.

Provides a drop-in replacement for HunterSE that publishes geometry_msgs/Twist
to /cmd_vel instead of writing to the CAN bus directly.

Use this when hunter_se_node.py is already running and you want trajectory
scripts to go via ROS2 (e.g. for logging, Nav2 integration, or remote control).

Steering → angular velocity conversion (inverse of hunter_se_node.py):
    angular.z = v × tan(steering) / wheelbase

Usage (inside trajectory scripts):
    from ros_robot import RosRobot
    with RosRobot() as robot:
        robot.enable_can_mode()   # no-op in ROS mode
        robot.set_motion(0.3, 0.0)
"""

import math
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

WHEELBASE_M = 0.657   # metres — must match trajectory.py and hunter_se_node.py


class _CmdVelNode(Node):
    """Minimal ROS2 node: publishes Twist to /cmd_vel."""

    def __init__(self):
        super().__init__("trajectory_ros_client")
        self._pub = self.create_publisher(Twist, "/cmd_vel", 10)
        # Spin in background thread so publish() is non-blocking
        self._executor = rclpy.executors.SingleThreadedExecutor()
        self._executor.add_node(self)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

    def publish_motion(self, linear: float, steering: float) -> None:
        msg = Twist()
        msg.linear.x = float(linear)
        # Ackermann → differential: ω = v × tan(δ) / L
        if abs(linear) < 0.05:
            msg.angular.z = 0.0
        else:
            msg.angular.z = float(linear * math.tan(steering) / WHEELBASE_M)
        self._pub.publish(msg)

    def shutdown(self):
        self._executor.shutdown(wait=False)


class RosRobot:
    """
    Drop-in replacement for HunterSE that sends commands via ROS2 /cmd_vel.

    Requirements:
      - rclpy must be importable (source /opt/ros/jazzy/setup.bash)
      - hunter_se_node.py must be running and subscribed to /cmd_vel
    """

    def __init__(self, publish_rate_hz: float = 20.0):
        """
        Parameters
        ----------
        publish_rate_hz : rate at which set_motion() heartbeat is re-published.
                          Matches the default cmd_vel_timeout of hunter_se_node.py.
        """
        if not rclpy.ok():
            rclpy.init()
        self._node = _CmdVelNode()
        self._linear  = 0.0
        self._steering = 0.0
        self._lock    = threading.Lock()
        self._running = True
        self._period  = 1.0 / publish_rate_hz

        # Heartbeat thread — re-publishes current command so node watchdog doesn't fire
        self._heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat.start()

    def _heartbeat_loop(self):
        while self._running:
            t0 = time.monotonic()
            with self._lock:
                lin, steer = self._linear, self._steering
            self._node.publish_motion(lin, steer)
            elapsed = time.monotonic() - t0
            sleep_t = self._period - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

    def enable_can_mode(self) -> None:
        """No-op in ROS mode — hunter_se_node.py handles CAN mode."""
        print("ROS mode: CAN mode managed by hunter_se_node.py")

    def set_motion(self, linear_mps: float, steering_rad: float) -> None:
        with self._lock:
            self._linear   = linear_mps
            self._steering = steering_rad

    def stop(self) -> None:
        with self._lock:
            self._linear   = 0.0
            self._steering = 0.0
        self._node.publish_motion(0.0, 0.0)

    def get_state(self):
        """Returns a dummy state — subscribe to /battery_state or /diagnostics for real data."""
        class _State:
            battery_voltage = 0.0
            control_mode    = 1     # assume CAN
            fault_code      = 0
        return _State()

    def close(self) -> None:
        self._running = False
        self.stop()
        self._heartbeat.join(timeout=1.0)
        self._node.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
