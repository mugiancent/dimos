#!/usr/bin/env python3

"""
Simple script to initialize SO101 arm, disable torque for free movement,
and continuously print the end-effector position (xyz) and orientation (quaternion) values.

Run with: python tests/so101_free_move.py
"""

import time

from dimos.hardware.so101_arm import SO101Arm


def main(port: str = "/dev/ttyACM0", update_rate: float = 0.1) -> None:
    """
    Initialize arm, disable torque, and print end-effector position and orientation values.
    
    Args:
        port: Serial port for the SO101 arm (default: "/dev/ttyACM0")
        update_rate: Time between position updates in seconds (default: 0.1)
    """
    print("=" * 60)
    print("SO101 Free Move - End-Effector Position Monitor")
    print("=" * 60)
    
    print("\nInitializing SO101Arm...")
    arm = SO101Arm(port=port)
    print("SO101Arm initialized")
    
    try:
        print("\nDisabling torque for free movement...")
        # Disable torque directly without moving to zero
        arm.arm.disable()
        print("Torque disabled - you can now freely move the arm")
        print("\nPress Ctrl+C to exit\n")
        
        print("End-effector pose (position xyz in meters, orientation quaternion):")
        print("-" * 60)
        
        while True:
            pose = arm.get_ee_pose()
            print(
                f"x={pose.position.x:.4f}, "
                f"y={pose.position.y:.4f}, "
                f"z={pose.position.z:.4f}, "
                f"qx={pose.orientation.x:.4f}, "
                f"qy={pose.orientation.y:.4f}, "
                f"qz={pose.orientation.z:.4f}, "
                f"qw={pose.orientation.w:.4f}",
                end="\r"
            )
            time.sleep(update_rate)
            
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Disconnecting arm...")
        arm.arm.disconnect()
        print("Done")


if __name__ == "__main__":
    main()

