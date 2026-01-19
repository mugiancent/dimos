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

from collections.abc import Generator
import threading
import time

import pytest

from dimos.msgs.geometry_msgs.Vector3 import Vector3
from dimos.protocol.pubsub.rospubsub import DimosROS, ROSTopic


def ros_node():
    ros = DimosROS()
    ros.start()
    try:
        yield ros
    finally:
        ros.stop()


@pytest.fixture()
def publisher() -> Generator[DimosROS, None, None]:
    yield from ros_node()


@pytest.fixture()
def subscriber() -> Generator[DimosROS, None, None]:
    yield from ros_node()


def test_basic_conversion(publisher, subscriber):
    topic = ROSTopic("/test_ros_topic", Vector3)

    received = []
    event = threading.Event()

    def callback(msg, t):
        received.append(msg)
        event.set()

    subscriber.subscribe(topic, callback)
    time.sleep(0.1)  # let subscription establish
    publisher.publish(topic, Vector3(1.0, 2.0, 3.0))

    assert event.wait(timeout=2.0), "No message received"
    assert len(received) == 1
    msg = received[0]
    assert msg.x == 1.0
    assert msg.y == 2.0
    assert msg.z == 3.0
