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
        self.protocol = protocol
        self.ip_address = ip_address
        self.timeout = timeout
        self.last_response = None
        print(f"[RoArm] Initialized. Target: {protocol}://{ip_address}/js?json=")

    def _is_response_valid(self, response: Optional[Dict[str, Any]]) -> bool:
        """
        Validate if the response indicates a successful command execution.

        Args:
            response (dict): The response from RoArm.

        Returns:
            bool: True if response is valid/successful, False otherwise.
        """
        if response is None:
            return False
        
        # Check for common success indicators
        if "error" in response and response["error"]:
            return False
        
        # Check for status field
        if "status" in response:
            status = str(response["status"]).lower()
            if status in ["ok", "success", "true", "1"]:
                return True
        
        # Check for raw_response indicating fallback success
        if "raw_response" in response and "status" in response:
            return True
        
        # If response exists and doesn't have explicit error, consider it valid
        if isinstance(response, dict) and len(response) > 0:
            return True
        
        return False

    def _send_command(self, command_dict: Dict[str, Any], validate_response: bool = True) -> Optional[Dict[str, Any]]:
        """
        The CENTRAL function that all other functions call.
        It sends the JSON command to the API and waits for a valid response.

        Args:
            command_dict (dict): The Python dictionary representing the JSON command.
            validate_response (bool): If True, waits for a valid response before returning.

        Returns:
            dict: The JSON response from the RoArm, or None if failed.
        """
        try:
            # Convert dict to JSON string
            json_payload = json.dumps(command_dict)
            print(f"[RoArm] Sending: {json_payload}")

            # Build full URL by concatenating the JSON string directly (matching https_json.py)
            url = f"{self.protocol}://{self.ip_address}/js?json={json_payload}"
            
            # Send the GET request
            response = requests.get(url, timeout=self.timeout)
            
            # Raise an error for bad HTTP status codes (4xx, 5xx)
            response.raise_for_status()

            # Get response text
            content = response.text
            print(f"[RoArm] Received: {content}")
            
            # Attempt to parse as JSON
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError:
                # If not JSON, return as raw response
                response_data = {"raw_response": content, "status": "ok"}
            
            # Store the last response
            self.last_response = response_data
            
            # Validate response if requested
            if validate_response:
                if self._is_response_valid(response_data):
                    print(f"[RoArm] Response validated successfully.")
                    return response_data
                else:
                    print(f"[RoArm] Invalid response received.")
                    return None
            
            return response_data

        except requests.exceptions.RequestException as e:
            print(f"[RoArm] Network Error: {e}")
            return None

    # =========================================================================
    # WRAPPER FUNCTIONS (Specific JSON Generators)
    # =========================================================================

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get feedback/status from the arm.
        Waits for a valid response before returning.
        JSON: {"T": 105}
        """
        cmd = {"T": 405}
        response = self._send_command(cmd, validate_response=True)
        if response:
            print(f"[RoArm] Status received: {response}")
        return response

    def move_cartesian(self, x: float, y: float, z: float, t: float, speed: int = 0) -> Optional[Dict[str, Any]]:
        """
        Move the arm to a specific Coordinate (Inverse Kinematics).
        Waits for a valid response before returning.
        
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
        response = self._send_command(cmd, validate_response=True)
        if response:
            print(f"[RoArm] Movement command acknowledged.")
        return response

    def set_joints(self, base: float, shoulder: float, elbow: float, hand: float, speed: int = 0) -> Optional[Dict[str, Any]]:
        """
        Set all joint angles directly.
        Waits for a valid response before returning.
        
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
        response = self._send_command(cmd, validate_response=True)
        if response:
            print(f"[RoArm] Joint angles set acknowledged.")
        return response

    def set_single_joint(self, joint_id: int, angle: float, speed: float = 0.25) -> Optional[Dict[str, Any]]:
        """
        Control a single joint/servo.
        Waits for a valid response before returning.
        
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
        response = self._send_command(cmd, validate_response=True)
        if response:
            print(f"[RoArm] Joint {joint_id} command acknowledged.")
        return response

    def set_torque(self, enable: bool) -> Optional[Dict[str, Any]]:
        """
        Enable or disable torque (motors on/off).
        Waits for a valid response before returning.
        
        JSON: {"T": 210, "cmd": 1 or 0}
        """
        cmd = {
            "T": 210,
            "cmd": 1 if enable else 0
        }
        response = self._send_command(cmd, validate_response=True)
        if response:
            state = "enabled" if enable else "disabled"
            print(f"[RoArm] Torque {state} acknowledged.")
        return response

    def emergency_stop(self) -> Optional[Dict[str, Any]]:
        """
        Stop the arm immediately.
        Waits for a valid response before returning.
        JSON: {"T": 0} (or equivalent stop command)
        """
        cmd = {"T": 0} # T:0 is commonly Stop/Reset in these protocols
        response = self._send_command(cmd, validate_response=True)
        if response:
            print(f"[RoArm] Emergency stop acknowledged.")
        return response

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
        arm.set_torque(False)
        

        # # Example 2: Move to Home Position (Inverse Kinematics)
        # # Assuming typical home coordinates, e.g., X=200, Y=0, Z=0
        print("\n--- 3. Moving to Home ---")
        arm.move_cartesian(x=200, y=0, z=100, t=3.14)
        # time.sleep(2)

        # # Example 3: Wave Hand (Joint Control)
        # print("\n--- 4. Waving Hand ---")
        # arm.set_single_joint(joint_id=4, angle=180) # Open
        # time.sleep(1)
        # arm.set_single_joint(joint_id=4, angle=90)  # Close
        
    else:
        print("Failed to connect to RoArm.")