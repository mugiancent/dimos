# Copyright 2025-2026 Dimensional Inc.
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


from typing import TYPE_CHECKING, Any

from pydantic import Field
from reactivex.disposable import Disposable

from dimos import spec
from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.module_coordinator import ModuleCoordinator
from dimos.core.stream import In
from dimos.msgs.geometry_msgs import Twist
from dimos.robot.unitree.connection import UnitreeWebRTCConnection
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from dimos.core.rpc_client import ModuleProxy

logger = setup_logger()


class G1Config(ModuleConfig):
    ip: str = Field(default_factory=lambda m: m["g"].robot_ip)
    connection_type: str = Field(default_factory=lambda m: m["g"].unitree_connection_type)


class G1Connection(Module[G1Config]):
    default_config = G1Config

    cmd_vel: In[Twist]
    connection: UnitreeWebRTCConnection | None = None

    @rpc
    def start(self) -> None:
        super().start()

        match self.config.connection_type:
            case "webrtc":
                self.connection = UnitreeWebRTCConnection(self.config.ip)
            case "replay":
                raise ValueError("Replay connection not implemented for G1 robot")
            case "mujoco":
                raise ValueError(
                    "This module does not support simulation, use G1SimConnection instead"
                )
            case _:
                raise ValueError(f"Unknown connection type: {self.config.connection_type}")

        assert self.connection is not None
        self.connection.start()

        self._disposables.add(Disposable(self.cmd_vel.subscribe(self.move)))

    @rpc
    def stop(self) -> None:
        assert self.connection is not None
        self.connection.stop()
        super().stop()

    @rpc
    def move(self, twist: Twist, duration: float = 0.0) -> None:
        assert self.connection is not None
        self.connection.move(twist, duration)

    @rpc
    def publish_request(self, topic: str, data: dict[str, Any]) -> dict[Any, Any]:
        logger.info(f"Publishing request to topic: {topic} with data: {data}")
        assert self.connection is not None
        return self.connection.publish_request(topic, data)  # type: ignore[no-any-return]


g1_connection = G1Connection.blueprint


def deploy(dimos: ModuleCoordinator, ip: str, local_planner: spec.LocalPlanner) -> "ModuleProxy":
    connection = dimos.deploy(G1Connection, ip=ip)
    connection.cmd_vel.connect(local_planner.cmd_vel)
    connection.start()
    return connection


__all__ = ["G1Connection", "deploy", "g1_connection"]
