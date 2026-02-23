#!/bin/bash
# Entrypoint for running ROSNav as a DimOS DockerModule.
#
# Differences from run_both.sh:
#   - Does not start DimOS Python directly; the docker_runner does that via --payload
#   - Passes "$@" to `python -m dimos.core.docker_runner run` so the DockerModule
#     framework can inject the --payload JSON at launch time
#
# Environment variables (all optional):
#   START_ROS_NAV   - Start the ROS navigation stack in the background (default: true)
#                     Set to "false" for hardware mode where ROS is already running
#   ROS_DISTRO      - ROS distribution (default: humble)
#   DISPLAY         - X11 display; RViz is skipped if display socket is absent

set -e

# Mark git directories as safe (avoids dubious ownership warnings)
git config --global --add safe.directory /workspace/dimos 2>/dev/null || true
git config --global --add safe.directory /ros2_ws/src/ros-navigation-autonomy-stack 2>/dev/null || true

# Source ROS environment
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ros2_ws/install/setup.bash

# Activate the dimos Python venv
source /opt/dimos-venv/bin/activate

# DDS configuration
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/ros2_ws/config/fastdds.xml
if [ -f "/ros2_ws/config/custom_fastdds.xml" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE=/ros2_ws/config/custom_fastdds.xml
fi

# Optionally start the ROS navigation stack in the background.
# Skip when START_ROS_NAV=false (e.g. hardware mode where the nav stack runs elsewhere).
if [ "${START_ROS_NAV:-true}" = "true" ]; then
    echo "[dimos_module_entrypoint] Starting ROS navigation stack in background..."
    cd /ros2_ws/src/ros-navigation-autonomy-stack

    # Only launch RViz if a display is available
    DISPLAY_NUM=$(echo "${DISPLAY:-:0}" | sed 's/://')
    RVIZ_ARG=""
    if [ ! -S "/tmp/.X11-unix/X${DISPLAY_NUM}" ]; then
        echo "[dimos_module_entrypoint] No display available, RViz will not launch"
    fi

    setsid bash -c "source /opt/ros/${ROS_DISTRO:-humble}/setup.bash && \
        source /ros2_ws/install/setup.bash && \
        ros2 launch vehicle_simulator system_simulation_with_route_planner.launch.py \
        enable_bridge:=false" &
    NAV_PID=$!
    echo "[dimos_module_entrypoint] ROS nav stack started (PID: $NAV_PID), waiting for init..."
    sleep 5
fi

# Hand off to the DimOS module runner.
# The DockerModule framework passes: --payload '{"module_path":..., "args":..., "kwargs":...}'
exec python -m dimos.core.docker_runner run "$@"
