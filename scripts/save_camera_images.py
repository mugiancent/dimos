#!/usr/bin/env python3
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

from __future__ import annotations

import argparse
import os
import time

from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs import Image


def main() -> None:
    parser = argparse.ArgumentParser(description="Save LCM camera images to disk.")
    parser.add_argument("--topic", default="/camera/color", help="LCM image topic (no #schema).")
    parser.add_argument(
        "--count", type=int, default=1, help="Number of frames to save (0 = infinite)."
    )
    parser.add_argument("--out-dir", default="captures", help="Output directory.")
    parser.add_argument("--prefix", default="color", help="Filename prefix.")
    parser.add_argument("--ext", default="png", help="File extension (e.g., png, jpg).")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    state = {"count": 0, "done": False}

    def on_img(msg: Image) -> None:
        state["count"] += 1
        filename = f"{args.prefix}_{state['count']:06d}.{args.ext}"
        msg.save(os.path.join(args.out_dir, filename))
        if args.count > 0 and state["count"] >= args.count:
            state["done"] = True

    transport = LCMTransport(args.topic, Image)
    transport.subscribe(on_img)

    try:
        while not state["done"]:
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        transport.stop()

    print(f"saved {state['count']} frame(s) to {args.out_dir}/")


if __name__ == "__main__":
    main()
