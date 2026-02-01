import requests
import json
import time
from typing import Optional, Dict, Any, Union

class RoArmController:
    """
    A controller class for the RoArm-M2 robotic arm via HTTP/HTTPS.
    """

    def __init__(self, ip_address: str, port: int = 80, protocol: str = "http", timeout: int = 10):
        """
        Initialize the controller.

        Args:
            ip_address (str): The IP address of the RoArm-M2.
            port (int): The port number (default is 80).
            protocol (str): 'http' or 'https'.
            timeout (int): Seconds to wait for a response before timing out.
        """
        self.base_url = f"{protocol}://{ip_address}:{port}/js"
        self.timeout = timeout
        print(f"[RoArm] Initialized. Target URL: {self.base_url}")

    def _send_command(self, command_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        The CENTRAL function that all other functions call.
        It sends the JSON command to the API and waits for the response.

        Args:
            command_dict (dict): The Python dictionary representing the JSON command.

        Returns:
            dict: The JSON response from the RoArm, or None if failed.
        """
        try:
            # Convert dict to JSON string for logging/debugging
            json_payload = json.dumps(command_dict)
            print(f"[RoArm] Sending: {json_payload}")

            # Send the request. We send it as a 'json' query parameter 
            # as is common with RoArm ESP32 web implementations, 
            # but this can be switched to json=command_dict for REST bodies.
            # Using params={'json': json_payload} ensures it works with the default web app.
            response = requests.get(
                self.base_url, 
                params={'json': json_payload}, 
                timeout=self.timeout
            )
            
            # Alternatively, if your server expects a POST body:
            # response = requests.post(self.base_url, json=command_dict, timeout=self.timeout)

            # Raise an error for bad HTTP status codes (4xx, 5xx)
            response.raise_for_status()

            # Attempt to parse the response
            # Note: Some simple ESP32 servers return plain text or empty strings.
            try:
                response_data = response.json()
                print(f"[RoArm] Received: {response_data}")
                return response_data
            except json.JSONDecodeError:
                print(f"[RoArm] Received raw text: {response.text}")
                return {"raw_response": response.text, "status": "ok"}

        except requests.exceptions.RequestException as e:
            print(f"[RoArm] Network Error: {e}")
            return None

    # =========================================================================
    # WRAPPER FUNCTIONS (Specific JSON Generators)
    # =========================================================================

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get feedback/status from the arm.
        JSON: {"T": 105}
        """
        cmd = {"T": 105}
        return self._send_command(cmd)

    def move_cartesian(self, x: float, y: float, z: float, t: float, speed: int = 0) -> Optional[Dict[str, Any]]:
        """
        Move the arm to a specific Coordinate (Inverse Kinematics).
        
        Args:
            x, y, z (float): Target coordinates in mm.
            t (float): Angle of the grabber/end-effector in radians.
            speed (int): Movement speed (0 is default/auto).
            
        JSON: {"T": 104, "x": x, "y": y, "z": z, "t": t, "spd": speed}
        """
        cmd = {
            "T": 104,
            "x": x,
            "y": y,
            "z": z,
            "t": t,
            "spd": speed
        }
        return self._send_command(cmd)

    def set_joints(self, base: float, shoulder: float, elbow: float, hand: float, speed: int = 0) -> Optional[Dict[str, Any]]:
        """
        Set all joint angles directly.
        
        Args:
            base, shoulder, elbow, hand (float): Angles in degrees (or radians depending on config).
            speed (int): Movement speed.
            
        JSON: {"T": 102, "b": base, "s": shoulder, "e": elbow, "h": hand, "spd": speed}
        """
        cmd = {
            "T": 102,
            "base": base,
            "shoulder": shoulder,
            "elbow": elbow,
            "hand": hand,
            "spd": speed
        }
        return self._send_command(cmd)

    def set_single_joint(self, joint_id: int, angle: float, speed: int = 0) -> Optional[Dict[str, Any]]:
        """
        Control a single joint/servo.
        
        Args:
            joint_id (int): 1=Base, 2=Shoulder, 3=Elbow, 4=Hand/Gripper.
            angle (float): Target angle.
            
        JSON: {"T": 101, "joint": id, "angle": angle, "spd": speed}
        """
        cmd = {
            "T": 101,
            "joint": joint_id,
            "angle": angle,
            "spd": speed
        }
        return self._send_command(cmd)

    def set_torque(self, enable: bool) -> Optional[Dict[str, Any]]:
        """
        Enable or disable torque (motors on/off).
        
        JSON: {"T": 210, "cmd": 1 or 0}
        """
        cmd = {
            "T": 210,
            "cmd": 1 if enable else 0
        }
        return self._send_command(cmd)

    def emergency_stop(self) -> Optional[Dict[str, Any]]:
        """
        Stop the arm immediately.
        JSON: {"T": 0} (or equivalent stop command)
        """
        cmd = {"T": 0} # T:0 is commonly Stop/Reset in these protocols
        return self._send_command(cmd)

# =============================================================================
# EXAMPLE USAGE
# =============================================================================
if __name__ == "__main__":
    # CONFIGURATION
    ROARM_IP = "192.168.4.1"  # Replace with your RoArm's IP
    
    # Instantiate
    arm = RoArmController(ip_address=ROARM_IP, protocol="http")

    print("\n--- 1. Checking Connection ---")
    status = arm.get_status()
    if status:
        print("Connected successfully.")
        
        # Example 1: Turn Torque On
        print("\n--- 2. Enabling Torque ---")
        arm.set_torque(True)
        time.sleep(1)

        # Example 2: Move to Home Position (Inverse Kinematics)
        # Assuming typical home coordinates, e.g., X=200, Y=0, Z=0
        print("\n--- 3. Moving to Home ---")
        arm.move_cartesian(x=200, y=0, z=100, t=3.14)
        time.sleep(2)

        # Example 3: Wave Hand (Joint Control)
        print("\n--- 4. Waving Hand ---")
        arm.set_single_joint(joint_id=4, angle=180) # Open
        time.sleep(1)
        arm.set_single_joint(joint_id=4, angle=90)  # Close
        
    else:
        print("Failed to connect to RoArm.")