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

"""Tests for NullStore and max_size=0 discard behavior."""

from __future__ import annotations

from dimos.memory2.observationstore.memory import ListObservationStore
from dimos.memory2.store.null import NullStore
from dimos.memory2.type.filter import StreamQuery
from dimos.memory2.type.observation import Observation


def test_max_size_zero_monotonic_ids() -> None:
    """ListObservationStore(max_size=0) assigns monotonically increasing IDs."""
    store = ListObservationStore(name="test", max_size=0)
    store.start()

    id0 = store.insert(Observation(id=-1, ts=1.0, _data="hello"))
    id1 = store.insert(Observation(id=-1, ts=2.0, _data="world"))
    id2 = store.insert(Observation(id=-1, ts=3.0, _data="!"))

    assert id0 == 0
    assert id1 == 1
    assert id2 == 2


def test_max_size_zero_empty_query() -> None:
    """ListObservationStore(max_size=0) query always returns empty."""
    store = ListObservationStore(name="test", max_size=0)
    store.start()
    store.insert(Observation(id=-1, ts=1.0, _data="data"))

    assert list(store.query(StreamQuery())) == []
    assert store.count(StreamQuery()) == 0
    assert store.fetch_by_ids([0]) == []


def test_null_store_discards_history() -> None:
    """NullStore (max_size=0) discards history but still supports live streaming."""
    store = NullStore()
    with store:
        stream = store.stream("test", int)
        stream.append(1)
        stream.append(2)
        stream.append(3)

        # History is empty — max_size=0 discards everything
        assert stream.count() == 0
        assert stream.fetch() == []
