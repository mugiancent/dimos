#!/usr/bin/env python3

"""
IK Diagnostic Test for SO101Arm (Interface Version).

This script tests IK accuracy using the SO101Arm interface by:
1. Getting current end-effector pose via interface
2. Commanding a target pose via interface (IK computed internally)
3. Verifying final pose matches target

Run with: python tests/so101_ik_test_use_interface.py
"""

import time

import numpy as np
from scipy.spatial.transform import Rotation as R

from dimos.hardware.so101_arm import SO101Arm
from dimos.msgs.geometry_msgs import Pose, Quaternion, Vector3


def test_ik_accuracy(port: str = "/dev/ttyACM0") -> None:
    """
    Diagnostic test using SO101Arm interface to verify IK accuracy.
    """
    print("=" * 60)
    print("SO101Arm IK Diagnostic Test (Interface Version)")
    print("=" * 60)
    
    print("\nInitializing SO101Arm...")
    arm = SO101Arm(port=port)
    print("SO101Arm initialized")
    
    # Target pose (recorded from physical movement using so101_free_move.py)
    target_pose = Pose(
        position=Vector3(0.2286, 0.1650, 0.0975),
        orientation=Quaternion(
            -0.0240,  # x
            0.0587,   # y
            0.3224,   # z
            0.94453   # w
        ),
    )
    
    try:
        # ============================================================
        # STEP 1: Get current state via interface
        # ============================================================
        print("\n" + "=" * 60)
        print("STEP 1: Current State (via get_ee_pose)")
        print("=" * 60)
        
        current_pose = arm.get_ee_pose()
        
        print(f"  Current position: x={current_pose.position.x:.4f}, "
              f"y={current_pose.position.y:.4f}, z={current_pose.position.z:.4f}")
        print(f"  Current orientation: qx={current_pose.orientation.x:.4f}, "
              f"qy={current_pose.orientation.y:.4f}, qz={current_pose.orientation.z:.4f}, "
              f"qw={current_pose.orientation.w:.4f}")
        
        # ============================================================
        # STEP 2: Target pose info
        # ============================================================
        print("\n" + "=" * 60)
        print("STEP 2: Target Pose")
        print("=" * 60)
        
        target_pos = np.array([target_pose.position.x, target_pose.position.y, target_pose.position.z])
        target_quat_wxyz = np.array([target_pose.orientation.w, target_pose.orientation.x, 
                                      target_pose.orientation.y, target_pose.orientation.z])
        
        print(f"  Target position: {target_pos}")
        print(f"  Target orientation (wxyz): {target_quat_wxyz}")
        
        # Convert to rotation matrix for display
        target_quat_xyzw = np.array([target_quat_wxyz[1], target_quat_wxyz[2], 
                                      target_quat_wxyz[3], target_quat_wxyz[0]])
        target_rot = R.from_quat(target_quat_xyzw)
        print(f"  Target rotation matrix:\n{target_rot.as_matrix()}")
        
        # ============================================================
        # STEP 3: Command target pose via interface
        # ============================================================
        print("\n" + "=" * 60)
        print("STEP 3: Command Target Pose (via cmd_ee_pose)")
        print("=" * 60)
        
        print("  Sending target pose via cmd_ee_pose() (IK computed internally)...")
        arm.cmd_ee_pose(target_pose, line_mode=False, duration=2.0)
        time.sleep(2.5)
        
        # ============================================================
        # STEP 4: Verify final pose via interface
        # ============================================================
        print("\n" + "=" * 60)
        print("STEP 4: Verify Final Pose (via get_ee_pose)")
        print("=" * 60)
        
        final_pose = arm.get_ee_pose()
        final_pos = np.array([final_pose.position.x, final_pose.position.y, final_pose.position.z])
        final_quat_wxyz = np.array([final_pose.orientation.w, final_pose.orientation.x,
                                     final_pose.orientation.y, final_pose.orientation.z])
        
        print(f"  Final position: {final_pos}")
        print(f"  Final orientation (wxyz): {final_quat_wxyz}")
        
        # Position error
        pos_error = final_pos - target_pos
        pos_error_norm = np.linalg.norm(pos_error)
        print(f"\n  Position error (Final vs Target): {pos_error_norm*1000:.2f} mm")
        print(f"  Position error components: x={pos_error[0]*1000:.2f} mm, "
              f"y={pos_error[1]*1000:.2f} mm, z={pos_error[2]*1000:.2f} mm")
        
        # Orientation error (angle between quaternions)
        final_quat_xyzw = np.array([final_quat_wxyz[1], final_quat_wxyz[2], 
                                     final_quat_wxyz[3], final_quat_wxyz[0]])
        final_rot = R.from_quat(final_quat_xyzw)
        rot_error = target_rot.inv() * final_rot
        angle_error_deg = np.degrees(rot_error.magnitude())
        print(f"  Orientation error: {angle_error_deg:.2f} degrees")
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Final position error: {pos_error_norm*1000:.2f} mm")
        print(f"  Final orientation error: {angle_error_deg:.2f} degrees")
        
        if pos_error_norm > 0.01:  # > 10mm error
            print("\n  ⚠️  WARNING: Significant position error detected!")
            print("     The error could be in IK computation or motor control.")
        else:
            print("\n  ✓ IK and motion are accurate!")
        
    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        arm.gotoObserve()
        print("\nDisabling arm...")
        arm.disable()
        print("✓ Arm disabled")


if __name__ == "__main__":
    test_ik_accuracy()

