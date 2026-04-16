# Copyright 2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ClickToGoal: forwards clicked_point to the global planner's goal stream."""

from __future__ import annotations

import math
import time

from dimos_lcm.std_msgs import Bool  # type: ignore[import-untyped]

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.PointStamped import PointStamped
from dimos.msgs.nav_msgs.Odometry import Odometry
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


class ClickToGoalConfig(ModuleConfig):
    """Config for ClickToGoal."""

    # When True, stop_movement publishes the robot's current pose as the goal
    # instead of a NaN sentinel. This is a fallback for planners that don't
    # handle the NaN "clear goal" convention.
    stop_publishes_current_pose: bool = False


class ClickToGoal(Module):
    """Relay clicked_point → way_point + goal for click-to-navigate.

    Publishes only in response to user actions (clicks or stop_movement).

    Ports:
        clicked_point (In[PointStamped]): Click from viewer.
        odometry (In[Odometry]): Vehicle pose (only used when stop_publishes_current_pose=True).
        stop_movement (In[Bool]): Cancel active goal.
        way_point (Out[PointStamped]): Navigation waypoint for LocalPlanner.
        goal (Out[PointStamped]): Navigation goal for global planner.
    """

    config: ClickToGoalConfig

    clicked_point: In[PointStamped]
    odometry: In[Odometry]
    stop_movement: In[Bool]
    way_point: Out[PointStamped]
    goal: Out[PointStamped]

    _robot_x: float = 0.0
    _robot_y: float = 0.0
    _robot_z: float = 0.0

    @rpc
    def start(self) -> None:
        super().start()
        if self.config.stop_publishes_current_pose:
            self.odometry.subscribe(self._on_odom)
        self.clicked_point.subscribe(self._on_click)
        self.stop_movement.subscribe(self._on_stop_movement)

    def _on_odom(self, msg: Odometry) -> None:
        self._robot_x = msg.pose.position.x
        self._robot_y = msg.pose.position.y
        self._robot_z = msg.pose.position.z

    def _on_click(self, msg: PointStamped) -> None:
        # Reject invalid clicks (sky/background gives inf or huge coords)
        if not all(math.isfinite(v) for v in (msg.x, msg.y, msg.z)):
            logger.warning("Ignored invalid click", x=msg.x, y=msg.y, z=msg.z)
            return
        if abs(msg.x) > 500 or abs(msg.y) > 500 or abs(msg.z) > 50:
            logger.warning("Ignored out-of-range click", x=msg.x, y=msg.y, z=msg.z)
            return

        logger.info("Goal", x=round(msg.x, 1), y=round(msg.y, 1), z=round(msg.z, 1))
        self.way_point.publish(msg)
        self.goal.publish(msg)

    def _on_stop_movement(self, msg: Bool) -> None:
        """Cancel navigation.

        Default behaviour publishes a NaN sentinel so downstream planners
        clear their goal.  When ``stop_publishes_current_pose`` is enabled,
        the robot's last-known pose is published instead — a fallback for
        planners that don't handle NaN.
        """
        if not msg.data:
            return

        if self.config.stop_publishes_current_pose:
            stop = PointStamped(
                ts=time.time(),
                frame_id="map",
                x=self._robot_x,
                y=self._robot_y,
                z=self._robot_z,
            )
        else:
            stop = PointStamped(
                ts=time.time(), frame_id="map", x=float("nan"), y=float("nan"), z=float("nan")
            )

        self.way_point.publish(stop)
        self.goal.publish(stop)
        logger.info("Navigation cancelled — waiting for new goal")
