#!/usr/bin/env python3
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

"""Minimal AGIbot navigation stack test blueprint.

Validates ROS topic connectivity between DimOS and the navigation ARM
docker image running on the AGIbot. Uses the same ros_nav() module as
the G1 integration — ROSNav bridges ROS topics to internal LCM streams
via ROSTransport.

Usage:
    dimos run agibot-nav-test

Architecture:
    AGIbot HW → ROS topics → ROSNav (ROSTransport) → LCM → DimOS modules
                                ↑
                        This is what we're testing

ROS topics consumed (via ROSTransport in ROSNav):
    /goal_reached       - Bool         (nav stack → DimOS)
    /cmd_vel            - TwistStamped (nav stack → DimOS)
    /way_point          - PoseStamped  (nav stack → DimOS)
    /registered_scan    - PointCloud2  (nav stack → DimOS, lidar)
    /terrain_map_ext    - PointCloud2  (nav stack → DimOS, global map)
    /path               - Path         (nav stack → DimOS)
    /tf                 - TFMessage    (nav stack → DimOS)

ROS topics published (via ROSTransport in ROSNav):
    /goal_pose          - PoseStamped  (DimOS → nav stack)
    /cancel_goal        - Bool         (DimOS → nav stack)
    /stop               - Int8         (DimOS → nav stack)
    /joy                - Joy          (DimOS → nav stack)

Test checklist:
    ✅ ROSNav starts without errors
    ✅ ROSTransport connects to ROS master / DDS
    ✅ Lidar pointcloud (/registered_scan) received on LCM /lidar
    ✅ Global map (/terrain_map_ext) received on LCM /map
    ✅ TF transforms received
    ✅ Can publish goal via goto(1, 0) and get cmd_vel back
"""

from dimos.core.blueprints import autoconnect
from dimos.core.transport import LCMTransport
from dimos.hardware.sensors.camera.module import camera_module
from dimos.hardware.sensors.camera.webcam import Webcam
from dimos.msgs.geometry_msgs import PoseStamped, Quaternion, Transform, Twist, Vector3
from dimos.msgs.nav_msgs import Odometry, Path
from dimos.msgs.sensor_msgs import Image, PointCloud2
from dimos.msgs.std_msgs import Bool
from dimos.navigation.rosnav import ros_nav
from dimos.robot.agibot.modules.ros_topic_monitor import ROSTopicMonitor
from dimos.robot.foxglove_bridge import foxglove_bridge
from dimos.web.websocket_vis.websocket_vis_module import websocket_vis

# AGIbot primitive: camera + visualization (no nav, no SDK yet)
_agibot_primitive = (
    autoconnect(
        camera_module(
            transform=Transform(
                translation=Vector3(0.05, 0.0, 0.5),  # approximate AGIbot camera height
                rotation=Quaternion.from_euler(Vector3(0.0, 0.2, 0.0)),
                frame_id="sensor",
                child_frame_id="camera_link",
            ),
            hardware=lambda: Webcam(
                camera_index=0,
                fps=15,
                stereo_slice="left",
            ),
        ),
        websocket_vis(),
        foxglove_bridge(),
    )
    .global_config(n_dask_workers=4, robot_model="agibot")
    .transports(
        {
            ("cmd_vel", Twist): LCMTransport("/cmd_vel", Twist),
            ("state_estimation", Odometry): LCMTransport("/state_estimation", Odometry),
            ("odom", PoseStamped): LCMTransport("/odom", PoseStamped),
            ("goal_req", PoseStamped): LCMTransport("/goal_req", PoseStamped),
            ("goal_active", PoseStamped): LCMTransport("/goal_active", PoseStamped),
            ("path_active", Path): LCMTransport("/path_active", Path),
            ("pointcloud", PointCloud2): LCMTransport("/lidar", PointCloud2),
            ("global_pointcloud", PointCloud2): LCMTransport("/map", PointCloud2),
            ("goal_pose", PoseStamped): LCMTransport("/goal_pose", PoseStamped),
            ("goal_reached", Bool): LCMTransport("/goal_reached", Bool),
            ("cancel_goal", Bool): LCMTransport("/cancel_goal", Bool),
            ("color_image", Image): LCMTransport("/agibot/color_image", Image),
        }
    )
)

# Full test blueprint: primitive + ros_nav + topic monitor
agibot_nav_test = autoconnect(
    _agibot_primitive,
    ros_nav(),
    ROSTopicMonitor.blueprint(),
)

__all__ = ["agibot_nav_test"]
