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

from pathlib import Path

from dimos.core.native_module import NativeModule, NativeModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.sensor_msgs.PointCloud2 import PointCloud2

_RUST_DIR = Path(__file__).parent / "voxelmapper_rust"


class RustVoxelMapperConfig(NativeModuleConfig):
    executable: str = str(_RUST_DIR / "target" / "release" / "voxelmapper")
    build_command: str = "cargo build --release"
    cwd: str = str(_RUST_DIR)
    stdin_config: bool = True
    voxel_size: float = 0.05
    block_count: int = 2_000_000
    device: str = "CUDA:0"
    carve_columns: bool = True
    output_frame_id: str = "world"


class RustVoxelMapper(NativeModule):
    config: RustVoxelMapperConfig
    lidar: In[PointCloud2]
    global_map: Out[PointCloud2]
