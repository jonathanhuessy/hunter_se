"""
sim_robot.py -- Kinematic simulator for the Agilex Hunter SE.

Drop-in replacement for HunterSE and RosRobot that integrates Ackermann
kinematics and visualises the trajectory in real time using matplotlib.

Features
--------
- Same set_motion() / stop() / enable_can_mode() interface as HunterSE
- Background thread integrates pose at 50 Hz (scales with speed_factor)
- Real-time matplotlib plot: trajectory trace, robot heading arrow
- Works with set_speed_factor() in trajectory.py — 10× speed_factor = 10×
  faster simulation (wall-clock time shrinks, kinematics stay correct)

Usage
-----
    from sim_robot import SimRobot
    import trajectory

    speed = 10.0
    trajectory.set_speed_factor(speed)

    def run(robot):
        robot.enable_can_mode()
        drive_straight(robot, 2.0, 0.3)
        drive_arc(robot, 0.3, 0.35, direction="left", angle_rad=math.pi/2)

    SimRobot(speed_factor=speed).run_simulation(run)
    # Matplotlib runs on the main thread — no threading warnings.
"""

import math
import threading
import time
from typing import Callable, Optional

import matplotlib
matplotlib.use("Agg")   # start with Agg; switched to interactive below on main thread
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

WHEELBASE_M = 0.657   # must match trajectory.py


class SimRobot:
    """
    Kinematic Hunter SE simulator with real-time matplotlib visualisation.

    Parameters
    ----------
    speed_factor : float
        How many times faster than real time to run.
    x0, y0, yaw0 : float
        Initial pose (metres, radians). Default: origin, facing East (yaw=0).
    trail_color : str
        Matplotlib color for the trajectory trail.
    """

    def __init__(
        self,
        speed_factor: float = 1.0,
        x0:    float = 0.0,
        y0:    float = 0.0,
        yaw0:  float = 0.0,
        trail_color: str = "steelblue",
    ):
        self._speed_factor = max(speed_factor, 0.01)
        self._dt_real = 0.02 / self._speed_factor   # integration step in wall-clock seconds

        # Pose state (written by integration thread, read by plot on main thread)
        self._lock  = threading.Lock()
        self._x     = x0
        self._y     = y0
        self._yaw   = yaw0
        self._linear   = 0.0
        self._steering = 0.0

        # Recorded trajectory
        self._xs:   list[float] = [x0]
        self._ys:   list[float] = [y0]
        self._yaws: list[float] = [yaw0]

        self._running        = False
        self._traj_done      = threading.Event()
        self._window_open    = True   # set False by plot close event → stops integration
        self._sim_thread:    Optional[threading.Thread] = None
        self._trail_color    = trail_color

        # Fake state (mimic VehicleState for trajectory scripts)
        self.state = _FakeState()

    # ------------------------------------------------------------------
    # HunterSE-compatible API
    # ------------------------------------------------------------------

    def enable_can_mode(self) -> None:
        print(f"SIM mode  (speed_factor={self._speed_factor}×)")

    def set_motion(self, linear_mps: float, steering_rad: float) -> None:
        with self._lock:
            self._linear   = linear_mps
            self._steering = steering_rad

    def stop(self) -> None:
        with self._lock:
            self._linear   = 0.0
            self._steering = 0.0

    def get_state(self):
        return self.state

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run_simulation(self, trajectory_fn: Callable[["SimRobot"], None]) -> None:
        """
        Run *trajectory_fn(robot)* in a background thread while the
        matplotlib plot runs on the **main thread**.

        This avoids the 'GUI outside main thread' warning from tkinter/matplotlib.
        Blocks until the trajectory finishes AND the user closes the plot window.
        """
        self._running = True

        # Kinematics integration thread
        self._sim_thread = threading.Thread(target=self._integrate_loop, daemon=True)
        self._sim_thread.start()

        # Trajectory execution thread
        traj_thread = threading.Thread(
            target=self._run_trajectory, args=(trajectory_fn,), daemon=True
        )
        traj_thread.start()

        # Matplotlib event loop — must be on the main thread
        self._plot_main()

        traj_thread.join(timeout=2.0)
        self._running = False
        if self._sim_thread:
            self._sim_thread.join(timeout=1.0)

    def _run_trajectory(self, fn: Callable) -> None:
        try:
            fn(self)
        except KeyboardInterrupt:
            print("\nAborted by user.")
        except Exception as e:
            print(f"\nTrajectory error: {e}")
        finally:
            self.stop()
            self._running = False
            self._traj_done.set()

    # ------------------------------------------------------------------
    # Kinematics integration (background thread)
    # ------------------------------------------------------------------

    def _integrate_loop(self) -> None:
        """
        Integrate Ackermann kinematics using elapsed wall-clock time.

        Using a fixed dt_sim (old approach) breaks at high speed_factors because
        Python thread scheduling on Linux has ~10-15 ms granularity — the thread
        can't fire every 2 ms for a 10× sim.  Instead, we measure actual elapsed
        wall-clock time and multiply by speed_factor to get the real simulated
        dt.  This keeps total simulated distance correct regardless of speed_factor.
        """
        target_dt = max(0.005, 0.02 / self._speed_factor)  # target wake rate, min 5 ms
        last_t = time.monotonic()

        while self._running and self._window_open:
            now = time.monotonic()
            wall_elapsed = now - last_t
            last_t = now

            dt_sim = wall_elapsed * self._speed_factor   # simulated seconds this step

            with self._lock:
                v     = self._linear
                delta = self._steering

            if abs(v) > 1e-6 and dt_sim > 0:
                if abs(delta) < 1e-4:
                    self._x += v * dt_sim * math.cos(self._yaw)
                    self._y += v * dt_sim * math.sin(self._yaw)
                else:
                    R    = WHEELBASE_M / math.tan(delta)
                    dyaw = v * dt_sim / R
                    dx   = R * math.sin(dyaw)
                    dy   = R * (1.0 - math.cos(dyaw))
                    # IMPORTANT: rotate the arc offset by the ORIGINAL yaw,
                    # then update yaw.  Updating yaw first (old bug) rotates
                    # the displacement by the new heading, corrupting every step.
                    self._x   += dx * math.cos(self._yaw) - dy * math.sin(self._yaw)
                    self._y   += dx * math.sin(self._yaw) + dy * math.cos(self._yaw)
                    self._yaw += dyaw

                # Hold the lock while appending so the plot thread never sees
                # a partially-updated list during its list() snapshot copy.
                with self._lock:
                    self._xs.append(self._x)
                    self._ys.append(self._y)
                    self._yaws.append(self._yaw)

            sleep_t = target_dt - (time.monotonic() - now)
            if sleep_t > 0:
                time.sleep(sleep_t)

    # ------------------------------------------------------------------
    # Matplotlib visualisation — runs on the MAIN thread
    # ------------------------------------------------------------------

    def _plot_main(self) -> None:
        """
        Set up and drive the matplotlib plot on the main thread.
        Uses plt.pause() for live updates (safe; processes GUI events).
        Blocks until the user closes the window.
        """
        # Switch to an interactive backend now that we're on the main thread
        matplotlib.use("TkAgg")
        plt.switch_backend("TkAgg")

        plt.ion()
        fig, ax = plt.subplots(figsize=(8, 8))
        try:
            fig.canvas.manager.set_window_title("Hunter SE Simulator")
        except Exception:
            pass

        def _on_close(_event):
            self._window_open = False
            self._running = False

        fig.canvas.mpl_connect("close_event", _on_close)

        ax.set_aspect("equal")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_title(f"Hunter SE Trajectory  (speed_factor={self._speed_factor}×)")

        ax.plot(self._xs[0], self._ys[0], "go", markersize=10, zorder=5)

        trail_line, = ax.plot([], [], color=self._trail_color, lw=2)

        arrow_len = 0.3
        robot_arrow = ax.annotate(
            "", xy=(0, 0), xytext=(0, 0),
            arrowprops=dict(arrowstyle="-|>", color="crimson", lw=2),
        )

        legend_patches = [
            mpatches.Patch(color="green",           label="Start"),
            mpatches.Patch(color=self._trail_color, label="Trajectory"),
            mpatches.Patch(color="crimson",         label="Robot heading"),
        ]
        ax.legend(handles=legend_patches, loc="upper left")
        plt.tight_layout()

        def _refresh():
            xs  = list(self._xs)
            ys  = list(self._ys)
            yaw = self._yaws[-1] if self._yaws else 0.0

            trail_line.set_data(xs, ys)

            xr, yr = xs[-1], ys[-1]
            robot_arrow.set_position((xr, yr))
            robot_arrow.xy = (
                xr + arrow_len * math.cos(yaw),
                yr + arrow_len * math.sin(yaw),
            )

            if len(xs) > 1:
                pad = max(1.0, (max(xs) - min(xs)) * 0.15, (max(ys) - min(ys)) * 0.15)
                ax.set_xlim(min(xs) - pad, max(xs) + pad)
                ax.set_ylim(min(ys) - pad, max(ys) + pad)

        # Live update loop — plt.pause() processes GUI events safely on the main thread
        while self._running and plt.fignum_exists(fig.number):
            _refresh()
            plt.pause(0.1)

        # Trajectory done — final update + block until window closed
        if plt.fignum_exists(fig.number):
            _refresh()
            ax.plot(self._xs[-1], self._ys[-1], "rs", markersize=10, zorder=5)
            ax.legend(handles=legend_patches + [
                mpatches.Patch(color="red", label="End")
            ], loc="upper left")
            plt.ioff()
            ax.set_title(
                f"Hunter SE Trajectory  (speed_factor={self._speed_factor}×) — COMPLETE\n"
                f"Distance: {self._path_length():.1f} m  |  "
                f"Final pose: ({self._xs[-1]:.2f}, {self._ys[-1]:.2f})  "
                f"yaw={math.degrees(self._yaws[-1]):.1f}°"
            )
            fig.canvas.draw()
            print("Simulation complete. Close the plot window to exit.")
            plt.show(block=True)

    def _path_length(self) -> float:
        xs, ys = self._xs, self._ys
        return sum(
            math.hypot(xs[i+1] - xs[i], ys[i+1] - ys[i])
            for i in range(len(xs) - 1)
        )


class _FakeState:
    """Mimics VehicleState for scripts that read battery/mode."""
    battery_voltage = 0.0
    control_mode    = 1
    fault_code      = 0

