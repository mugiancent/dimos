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

from collections import deque
from dataclasses import dataclass
import threading
import time

from dimos.protocol.service.lcmservice import LCMConfig, LCMService
from dimos.utils.human import human_bytes


class Topic:
    history_window: float = 60.0

    def __init__(self, name: str, history_window: float = 60.0) -> None:
        self.name = name
        self.history_window = history_window
        # Two fixed-size circular buffers: one bucket per second.
        # Avoids unbounded memory and the need to copy/lock the deque on reads.
        self._num_buckets = max(int(history_window), 1)
        self._count: list[int] = [0] * self._num_buckets
        self._bytes: list[int] = [0] * self._num_buckets
        self._bucket_second: list[int] = [-1] * self._num_buckets
        self.total_traffic_bytes = 0

    def msg(self, data: bytes) -> None:
        data_size = len(data)
        second = int(time.time())
        idx = second % self._num_buckets
        if self._bucket_second[idx] != second:
            self._count[idx] = 0
            self._bytes[idx] = 0
            self._bucket_second[idx] = second
        self._count[idx] += 1
        self._bytes[idx] += data_size
        self.total_traffic_bytes += data_size

    def _window_stats(self, time_window: float) -> tuple[int, int]:
        """Return (msg_count, total_bytes) for buckets within time_window seconds."""
        cutoff = time.time() - time_window
        count = 0
        total = 0
        for i in range(self._num_buckets):
            if self._bucket_second[i] + 1 > cutoff:
                count += self._count[i]
                total += self._bytes[i]
        return count, total

    # avg msg freq in the last n seconds
    def freq(self, time_window: float) -> float:
        count, _ = self._window_stats(time_window)
        return count / time_window

    # avg bandwidth in kB/s in the last n seconds
    def kbps(self, time_window: float) -> float:
        _, total_bytes = self._window_stats(time_window)
        return total_bytes / 1000 / time_window

    def kbps_hr(self, time_window: float) -> str:
        """Return human-readable bandwidth with appropriate units"""
        bps = self.kbps(time_window) * 1000
        return human_bytes(bps) + "/s"

    # avg msg size in the last n seconds
    def size(self, time_window: float) -> float:
        count, total_bytes = self._window_stats(time_window)
        if count == 0:
            return 0.0
        return total_bytes / count

    def total_traffic(self) -> int:
        """Return total traffic passed in bytes since the beginning"""
        return self.total_traffic_bytes

    def total_traffic_hr(self) -> str:
        """Return human-readable total traffic with appropriate units"""
        return human_bytes(self.total_traffic())

    def __str__(self) -> str:
        return f"topic({self.name})"


@dataclass
class LCMSpyConfig(LCMConfig):
    topic_history_window: float = 60.0


class LCMSpy(LCMService, Topic):
    default_config = LCMSpyConfig
    topic = dict[str, Topic]
    graph_log_window: float = 1.0
    topic_class: type[Topic] = Topic

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        Topic.__init__(self, name="total", history_window=self.config.topic_history_window)  # type: ignore[attr-defined]
        self.topic = {}  # type: ignore[assignment]

    def start(self) -> None:
        super().start()
        self.l.subscribe(".*", self.msg)  # type: ignore[union-attr]

    def stop(self) -> None:
        """Stop the LCM spy and clean up resources"""
        super().stop()

    def msg(self, topic, data) -> None:  # type: ignore[no-untyped-def, override]
        Topic.msg(self, data)

        if topic not in self.topic:  # type: ignore[operator]
            print(self.config)
            self.topic[topic] = self.topic_class(  # type: ignore[assignment, call-arg]
                topic,
                history_window=self.config.topic_history_window,  # type: ignore[attr-defined]
            )
        self.topic[topic].msg(data)  # type: ignore[attr-defined, type-arg]


class GraphTopic(Topic):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.freq_history = deque(maxlen=20)  # type: ignore[var-annotated]
        self.bandwidth_history = deque(maxlen=20)  # type: ignore[var-annotated]

    def update_graphs(self, step_window: float = 1.0) -> None:
        """Update historical data for graphing"""
        freq = self.freq(step_window)
        kbps = self.kbps(step_window)
        self.freq_history.append(freq)
        self.bandwidth_history.append(kbps)


@dataclass
class GraphLCMSpyConfig(LCMSpyConfig):
    graph_log_window: float = 1.0


class GraphLCMSpy(LCMSpy, GraphTopic):
    default_config = GraphLCMSpyConfig

    graph_log_thread: threading.Thread | None = None
    graph_log_stop_event: threading.Event = threading.Event()
    topic_class: type[Topic] = GraphTopic

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        GraphTopic.__init__(self, name="total", history_window=self.config.topic_history_window)  # type: ignore[attr-defined]

    def start(self) -> None:
        super().start()
        self.graph_log_thread = threading.Thread(target=self.graph_log, daemon=True)
        self.graph_log_thread.start()

    def graph_log(self) -> None:
        while not self.graph_log_stop_event.is_set():
            self.update_graphs(self.config.graph_log_window)  # type: ignore[attr-defined]  # Update global history
            # Copy to list to avoid RuntimeError: dictionary changed size during iteration
            for topic in list(self.topic.values()):  # type: ignore[call-arg]
                topic.update_graphs(self.config.graph_log_window)  # type: ignore[attr-defined]
            time.sleep(self.config.graph_log_window)  # type: ignore[attr-defined]

    def stop(self) -> None:
        """Stop the graph logging and LCM spy"""
        self.graph_log_stop_event.set()
        if self.graph_log_thread and self.graph_log_thread.is_alive():
            self.graph_log_thread.join(timeout=1.0)
        super().stop()


if __name__ == "__main__":
    lcm_spy = LCMSpy()
    lcm_spy.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("LCM Spy stopped.")
