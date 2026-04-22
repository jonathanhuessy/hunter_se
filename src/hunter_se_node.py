#!/usr/bin/env python3
"""
hunter_se_node.py -- ROS2 bridge node for the Agilex Hunter SE.

Translates between ROS2 standard interfaces and the Hunter SE CAN protocol.

Subscribed topics
-----------------
/cmd_vel  (geometry_msgs/Twist)
    Linear.x  = forward speed in m/s    (capped to ±4.8 m/s)
    Angular.z = desired yaw rate rad/s  → converted to Ackermann steering angle

    Ackermann conversion:
        steering = atan(L × ω / v)   [L = wheelbase = 0.657 m]
    When |v| < 0.05 m/s, angular commands are ignored (Ackermann cannot rotate in place).

Published topics
----------------
/odom          (nav_msgs/Odometry)          Dead-reckoning from actual velocity feedback
/battery_state (sensor_msgs/BatteryState)   Battery voltage from CAN 0x211 frame
/diagnostics   (diagnostic_msgs/DiagnosticArray)  Robot mode, fault codes

Parameters
----------
channel         SocketCAN interface (default: 'can0')
cmd_vel_timeout Seconds without /cmd_vel before robot is stopped (default: 0.5)
max_speed       Software speed cap m/s (default: 1.5)
max_steering    Software steering cap rad (default: 0.4)
publish_rate    Odometry publish rate Hz (default: 20.0)

Usage
-----
    source /opt/ros/jazzy/setup.bash
    python3 src/hunter_se_node.py

    # Drive with keyboard (separate terminal, ROS2 sourced):
    ros2 run teleop_twist_keyboard teleop_twist_keyboard

    # Monitor topics:
    ros2 topic echo /battery_state
    ros2 topic echo /odom
"""

import math
import sys
import threading
import time
from pathlib import Path

# Make hunter_se importable from the same src/ directory
sys.path.insert(0, str(Path(__file__).parent))

import rclpy
from rclpy.node import Node
from rclpy.time import Time

from geometry_msgs.msg import Twist, TransformStamped, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from tf2_ros import TransformBroadcaster

from hunter_se import HunterSE, CTRL_MODE_NAMES

# Ackermann geometry — see trajectory.py for derivation
WHEELBASE_M = 0.657   # metres


def yaw_to_quaternion(yaw: float) -> Quaternion:
    """Convert a yaw angle (rad) to a geometry_msgs/Quaternion."""
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class HunterSENode(Node):
    """ROS2 node bridging /cmd_vel ↔ Hunter SE CAN."""

    def __init__(self):
        super().__init__("hunter_se")

        # Parameters
        self.declare_parameter("channel",         "can0")
        self.declare_parameter("cmd_vel_timeout", 0.5)
        self.declare_parameter("max_speed",       1.5)
        self.declare_parameter("max_steering",    0.4)
        self.declare_parameter("publish_rate",    20.0)

        channel         = self.get_parameter("channel").value
        self._timeout   = self.get_parameter("cmd_vel_timeout").value
        max_speed       = self.get_parameter("max_speed").value
        max_steering    = self.get_parameter("max_steering").value
        publish_rate    = self.get_parameter("publish_rate").value

        # Connect to robot
        self.get_logger().info(f"Connecting to Hunter SE on {channel}…")
        self._robot = HunterSE(
            channel=channel,
            max_linear_mps=max_speed,
            max_steering_rad=max_steering,
        )
        self._robot.enable_can_mode()
        self.get_logger().info("CAN command mode enabled.")

        # Odometry state (integrated from feedback)
        self._odom_lock = threading.Lock()
        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._last_odom_time = time.monotonic()

        # cmd_vel watchdog
        self._last_cmd_time = time.monotonic()

        # Publishers
        self._odom_pub   = self.create_publisher(Odometry,        "/odom",          10)
        self._batt_pub   = self.create_publisher(BatteryState,    "/battery_state", 10)
        self._diag_pub   = self.create_publisher(DiagnosticArray, "/diagnostics",   10)
        self._tf_broadcaster = TransformBroadcaster(self)

        # Subscriber
        self.create_subscription(Twist, "/cmd_vel", self._cmd_vel_cb, 10)

        # Timers
        period = 1.0 / publish_rate
        self.create_timer(period,  self._publish_odom)
        self.create_timer(0.1,     self._publish_status)   # 10 Hz battery/diag
        self.create_timer(0.1,     self._check_cmd_timeout)

        self.get_logger().info(
            f"Hunter SE node ready. "
            f"max_speed={max_speed} m/s  max_steering={max_steering} rad  "
            f"cmd_vel_timeout={self._timeout} s"
        )

    # ------------------------------------------------------------------
    # /cmd_vel callback
    # ------------------------------------------------------------------

    def _cmd_vel_cb(self, msg: Twist) -> None:
        """Convert Twist to Ackermann (linear + steering) and send to robot."""
        v = msg.linear.x
        omega = msg.angular.z

        # Ackermann conversion: steering = atan(L × ω / v)
        # Cannot rotate in place — ignore angular when speed is near zero.
        if abs(v) < 0.05:
            steering = 0.0
        else:
            steering = math.atan2(WHEELBASE_M * omega, v)

        self._robot.set_motion(v, steering)
        self._last_cmd_time = time.monotonic()

    # ------------------------------------------------------------------
    # Watchdog: stop robot if /cmd_vel goes silent
    # ------------------------------------------------------------------

    def _check_cmd_timeout(self) -> None:
        if time.monotonic() - self._last_cmd_time > self._timeout:
            self._robot.stop()

    # ------------------------------------------------------------------
    # Odometry (dead-reckoning from actual feedback)
    # ------------------------------------------------------------------

    def _publish_odom(self) -> None:
        now = self.get_clock().now()
        t   = time.monotonic()

        with self._robot._lock:
            v     = self._robot.state.linear_velocity
            delta = self._robot.state.steering_angle   # actual front-wheel angle

        with self._odom_lock:
            dt = t - self._last_odom_time
            self._last_odom_time = t

            # Ackermann kinematics
            if abs(delta) < 1e-4:
                # Straight line
                dx   = v * dt
                dy   = 0.0
                dyaw = 0.0
            else:
                R    = WHEELBASE_M / math.tan(delta)
                dyaw = v * dt / R
                dx   = R * math.sin(dyaw)
                dy   = R * (1.0 - math.cos(dyaw))

            # Rotate the arc chord by the ORIGINAL yaw, then update yaw.
            # Updating yaw first would rotate the displacement by the new heading,
            # corrupting the odometry on every arc step.
            self._x   += dx * math.cos(self._yaw) - dy * math.sin(self._yaw)
            self._y   += dx * math.sin(self._yaw) + dy * math.cos(self._yaw)
            self._yaw += dyaw

            x, y, yaw = self._x, self._y, self._yaw

        q = yaw_to_quaternion(yaw)

        # TF: odom → base_link
        tf = TransformStamped()
        tf.header.stamp    = now.to_msg()
        tf.header.frame_id = "odom"
        tf.child_frame_id  = "base_link"
        tf.transform.translation.x = x
        tf.transform.translation.y = y
        tf.transform.translation.z = 0.0
        tf.transform.rotation = q
        self._tf_broadcaster.sendTransform(tf)

        # nav_msgs/Odometry
        odom = Odometry()
        odom.header.stamp    = now.to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id  = "base_link"
        odom.pose.pose.position.x  = x
        odom.pose.pose.position.y  = y
        odom.pose.pose.orientation = q
        odom.twist.twist.linear.x  = v
        # Reconstruct yaw rate from actual v and delta
        if abs(WHEELBASE_M) > 1e-6 and abs(delta) > 1e-4:
            odom.twist.twist.angular.z = v * math.tan(delta) / WHEELBASE_M
        self._odom_pub.publish(odom)

    # ------------------------------------------------------------------
    # Battery + diagnostics (10 Hz)
    # ------------------------------------------------------------------

    def _publish_status(self) -> None:
        now = self.get_clock().now()
        with self._robot._lock:
            batt  = self._robot.state.battery_voltage
            mode  = self._robot.state.control_mode
            fault = self._robot.state.fault_code
            vstatus = self._robot.state.vehicle_status

        # BatteryState
        batt_msg = BatteryState()
        batt_msg.header.stamp = now.to_msg()
        batt_msg.voltage      = float(batt)
        batt_msg.present      = True
        batt_msg.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        self._batt_pub.publish(batt_msg)

        # DiagnosticArray
        status = DiagnosticStatus()
        status.name = "hunter_se"
        status.hardware_id = "agilex_hunter_se"
        status.level = DiagnosticStatus.OK if fault == 0 else DiagnosticStatus.WARN
        status.message = "OK" if fault == 0 else f"Fault code 0x{fault:04X}"
        status.values = [
            KeyValue(key="control_mode",    value=CTRL_MODE_NAMES.get(mode, str(mode))),
            KeyValue(key="vehicle_status",  value=str(vstatus)),
            KeyValue(key="battery_voltage", value=f"{batt:.1f} V"),
            KeyValue(key="fault_code",      value=f"0x{fault:04X}"),
        ]
        arr = DiagnosticArray()
        arr.header.stamp = now.to_msg()
        arr.status = [status]
        self._diag_pub.publish(arr)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def destroy_node(self):
        self.get_logger().info("Shutting down — stopping robot.")
        self._robot.stop()
        self._robot.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = HunterSENode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
