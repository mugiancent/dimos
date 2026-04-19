"""dimos - A fork of dimensionalOS/dimos.

A framework for building and deploying autonomous robot agents
with multimodal perception, planning, and action capabilities.

Personal fork: experimenting with agent planning and ROS2 integration.

Note: Using 'unknown' fallback for __version__ to make it clearer when
the package isn't properly installed (e.g. running from source checkout).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dimos")
except PackageNotFoundError:
    __version__ = "unknown (dev/source)"

__author__ = "dimos contributors"
__license__ = "Apache-2.0"
__fork_of__ = "dimensionalOS/dimos"

__all__ = ["__version__", "__author__", "__license__", "__fork_of__"]
