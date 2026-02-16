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

"""ROS topic monitoring module for AGIbot validation.

Monitors the LCM-side outputs of ROSNav to verify that ROS topics are
being received and bridged correctly. This validates the full pipeline:

    ROS topic → ROSTransport → ROSNav → LCM → this module

If we see data here, the AGIbot nav stack is working end-to-end.
"""

from dataclasses import dataclass, field
import time

from dimos.core import In, Module, rpc
from dimos.msgs.geometry_msgs import PoseStamped, Twist
from dimos.msgs.nav_msgs import Path
from dimos.msgs.sensor_msgs import PointCloud2
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


@dataclass
class TopicStats:
    """Statistics for a monitored stream."""

    name: str
    msg_count: int = 0
    last_msg_time: float = 0.0
    first_msg_time: float = 0.0
    _recent_times: list[float] = field(default_factory=list)

    @property
    def rate_hz(self) -> float:
        if len(self._recent_times) < 2:
            return 0.0
        span = self._recent_times[-1] - self._recent_times[0]
        return (len(self._recent_times) - 1) / span if span > 0 else 0.0

    @property
    def latency_ms(self) -> float:
        if self.last_msg_time == 0:
            return float("inf")
        return (time.time() - self.last_msg_time) * 1000

    def record(self) -> None:
        now = time.time()
        self.msg_count += 1
        self.last_msg_time = now
        if self.first_msg_time == 0:
            self.first_msg_time = now
        self._recent_times.append(now)
        if len(self._recent_times) > 100:
            self._recent_times.pop(0)


class ROSTopicMonitor(Module):
    """Monitor DimOS streams bridged from ROS by ROSNav.

    Subscribes to the LCM-side ports that ROSNav publishes to, verifying
    that lidar, camera, velocity, and path data flow through correctly.

    Health report every 5 seconds:
        ✅ OK       - data flowing at expected rate
        ⚠️  WARN    - data flowing but slow or intermittent
        ❌ NO DATA  - nothing received
    """

    # LCM-side ports (filled by ROSNav outputs via autoconnect)
    pointcloud: In[PointCloud2]  # /lidar — from ros_registered_scan
    global_pointcloud: In[PointCloud2]  # /map — from ros_terrain_map_ext
    cmd_vel: In[Twist]  # /cmd_vel — from ros_cmd_vel
    goal_active: In[PoseStamped]  # /goal_active — from ros_way_point
    path_active: In[Path]  # /path_active — from ros_path

    def __init__(self) -> None:
        super().__init__()
        self._stats: dict[str, TopicStats] = {}

    @rpc
    def start(self) -> None:
        super().start()
        streams = {
            "pointcloud (lidar)": self.pointcloud,
            "global_pointcloud (map)": self.global_pointcloud,
            "cmd_vel": self.cmd_vel,
            "goal_active": self.goal_active,
            "path_active": self.path_active,
        }
        for name, port in streams.items():
            stats = TopicStats(name=name)
            self._stats[name] = stats
            port.subscribe(lambda _msg, s=stats: s.record())

        logger.info(f"ROSTopicMonitor: watching {len(streams)} streams")

    def tick(self) -> None:
        # Report every ~5 seconds (assuming default tick frequency)
        if self.ticks % max(1, int(5 * self.frequency)) != 0:
            return

        logger.info("═══ AGIbot ROS→LCM Health Report ═══")
        for stats in self._stats.values():
            rate = stats.rate_hz
            latency = stats.latency_ms

            if rate > 1.0 and latency < 1000:
                icon = "✅"
            elif stats.msg_count > 0:
                icon = "⚠️ "
            else:
                icon = "❌"

            logger.info(
                f"  {icon} {stats.name:30s} │ "
                f"n={stats.msg_count:6d} │ "
                f"{rate:6.1f} Hz │ "
                f"lat {latency:7.0f} ms"
            )

        # Summary verdict
        active = sum(1 for s in self._stats.values() if s.msg_count > 0)
        total = len(self._stats)
        if active == total:
            logger.info(f"  ── ALL STREAMS OK ({active}/{total}) ──")
        elif active > 0:
            logger.warning(f"  ── PARTIAL ({active}/{total} active) ──")
        else:
            logger.error(f"  ── NO DATA on any stream ({total} monitored) ──")
