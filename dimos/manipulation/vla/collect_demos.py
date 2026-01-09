# collect demos from real robot and convert to lerobot dataset format

import threading
import numpy as np

from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs import Image, JointCommand, JointState
from dimos.msgs.sensor_msgs.image_impls.AbstractImage import ImageFormat
from dimos.msgs.sensor_msgs import JointCommand
from dimos.manipulation.vla.utils import get_camera_image, get_joint_positions, get_joint_velocities

