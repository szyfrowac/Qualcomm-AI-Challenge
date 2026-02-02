# Jenga Robot Project Context

I am working on a voice-controlled robotic arm project ("UNO Q Challenge") that sorts Jenga blocks. The system uses a Python-based controller running on a host (or Raspberry Pi/similar) that communicates with an Arduino-based robotic arm. It features speech recognition (Whisper/Vosk), natural language processing to JSON commands, and serial communication for hardware control.

Here is the complete project structure and file contents. Please help me continue developing this.

## Project Structure
```
d:/Projects/unoq Challenge/
├── main.py
├── gemma_client.py
├── arduino_controller.py
├── speech_input.py
├── arm_functions.py
├── setup_unoq.sh
├── requirements.txt
└── arduino/
    └── arm_controller/
        └── arm_controller.ino
```

## File Contents

### `main.py`
Entry point for the application. Handles the main loop, user input (text/speech), and coordination between the interpreter and the robot controller.
```python
"""
Main - SO101 Jenga Robot Controller

Converts natural language commands to JSON for controlling
a robotic arm that sorts Jenga blocks.

Usage:
  python main.py           # Mock mode (no hardware)
  python main.py --hardware # Real robot
"""

import argparse
import json
from gemma_client import JengaCommandInterpreter
from arduino_controller import JengaRobotController, MockJengaController


def main(use_hardware: bool = False):
    print("""
╔══════════════════════════════════════════════════╗
║      🤖 JENGA ROBOT COMMAND INTERPRETER 🧱      ║
║      SO101 Arm + RealSense Camera                ║
╚══════════════════════════════════════════════════╝
""")
    
    # Initialize interpreter
    print("[1/2] Loading command interpreter...")
    interpreter = JengaCommandInterpreter()
    print("      ✓ Ready")
    
    # Initialize robot controller
    print(f"[2/2] Robot: {'hardware' if use_hardware else 'mock'}")
    if use_hardware:
        robot = JengaRobotController()
        if not robot.connect():
            print("      ⚠ Hardware not found, using mock")
            robot = MockJengaController()
    else:
        robot = MockJengaController()
    robot.connect()
    print()
    
    # Instructions
    print("═" * 55)
    print("COMMANDS:")
    print("  PICK: 'grab the red block', 'get 3 blue pieces'")
    print("        'pick the top block', 'get nearest green one'")
    print("  SORT: 'organize by color', 'sort the blocks'")
    print("  ")
    print("  Type 'quit' to exit")
    print("═" * 55)
    print()
    
    # Main loop
    while True:
        try:
            user_input = input("🎮 > ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit", "q"):
                break
            
            # Interpret command
            result = interpreter.interpret(user_input)
            
            # Output raw JSON
            print(json.dumps(result))
            
            # Execute on robot
            robot.execute(result)
            print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            error_response = {
                "action_type": "DECLINE",
                "parameters": {"target_color": None, "quantity": None, "sort_criteria": None},
                "reasoning": f"Error: {str(e)}"
            }
            print(json.dumps(error_response))
    
    robot.disconnect()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jenga Robot Controller")
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Use real robot hardware"
    )
    args = parser.parse_args()
    
    main(use_hardware=args.hardware)
```

### `gemma_client.py`
Handles natural language understanding, converting text commands into structured JSON actions (PICK, SORT, DECLINE).
```python
"""
Robotic Command Interpreter for SO101 Jenga Arm

Converts natural language to structured JSON commands for a robotic arm
that sorts Jenga blocks using a RealSense depth camera.

Actions:
- PICK: Retrieve specific block(s)
- SORT: Organize blocks by attribute
- DECLINE: Request outside capabilities
"""

import re
import json
from typing import Optional, Dict, Any

# ============================================================
# VALID VALUES
# ============================================================
VALID_COLORS = {"red", "blue", "green", "yellow", "pink", "wood", "any"}
VALID_ACTIONS = {"PICK", "SORT", "DECLINE"}

# Color synonyms mapping
COLOR_MAP = {
    # Red variants
    "red": "red", "crimson": "red", "scarlet": "red", "ruby": "red", "maroon": "red",
    # Blue variants  
    "blue": "blue", "azure": "blue", "navy": "blue", "cyan": "blue", "teal": "blue",
    # Green variants
    "green": "green", "lime": "green", "emerald": "green", "olive": "green", "mint": "green",
    # Yellow variants
    "yellow": "yellow", "gold": "yellow", "amber": "yellow", "lemon": "yellow",
    # Pink variants
    "pink": "pink", "magenta": "pink", "rose": "pink", "fuchsia": "pink",
    # Wood/natural
    "wood": "wood", "brown": "wood", "tan": "wood", "beige": "wood", "natural": "wood",
}

# Action keyword mapping
PICK_KEYWORDS = {"grab", "get", "bring", "lift", "pick", "take", "fetch", "retrieve", "collect"}
SORT_KEYWORDS = {"sort", "organize", "arrange", "clean", "tidy", "group", "order"}
DECLINE_KEYWORDS = {"dance", "wave", "stack", "build", "throw", "jump", "spin"}

# Spatial context mapping
SPATIAL_MAP = {
    # Top/nearest
    "top": "top", "topmost": "top", "upper": "top", "highest": "top",
    "nearest": "nearest", "closest": "nearest", "close": "nearest",
    # Bottom
    "bottom": "bottom", "lowest": "bottom", "base": "bottom",
    # Left/Right
    "left": "left", "leftmost": "left",
    "right": "right", "rightmost": "right",
    # Center
    "center": "center", "middle": "center", "central": "center",
    # First/Last
    "first": "first", "last": "last",
}


class JengaCommandInterpreter:
    """
    Interprets natural language commands for Jenga robot.
    Outputs structured JSON.
    """
    
    def interpret(self, user_input: str) -> Dict[str, Any]:
        """
        Convert natural language to JSON command.
        
        Returns dict with:
        - action_type: PICK | SORT | DECLINE
        - parameters: {target_color, quantity, sort_criteria}
        - reasoning: Brief explanation
        """
        text = user_input.lower().strip()
        
        # Determine action type
        action_type = self._detect_action(text)
        
        # Build response based on action
        if action_type == "DECLINE":
            return {
                "action_type": "DECLINE",
                "parameters": {
                    "target_color": None,
                    "quantity": None,
                    "sort_criteria": None
                },
                "reasoning": "Request outside robot capabilities."
            }
        
        elif action_type == "SORT":
            sort_criteria = self._detect_sort_criteria(text)
            return {
                "action_type": "SORT",
                "parameters": {
                    "target_color": None,
                    "quantity": None,
                    "sort_criteria": sort_criteria
                },
                "reasoning": f"Organize all blocks by {sort_criteria}."
            }
        
        else:  # PICK
            color = self._detect_color(text)
            quantity = self._detect_quantity(text)
            spatial = self._detect_spatial(text)
            
            # Build reasoning
            parts = []
            if quantity == -1:
                parts.append("Pick all")
            else:
                parts.append(f"Pick {quantity}")
            if color and color != "any":
                parts.append(color)
            if spatial:
                parts.append(f"({spatial})")
            parts.append("block(s).")
            reasoning = " ".join(parts)
            
            return {
                "action_type": "PICK",
                "parameters": {
                    "target_color": color,
                    "quantity": quantity,
                    "spatial_context": spatial,
                    "sort_criteria": None
                },
                "reasoning": reasoning
            }
    
    def _detect_action(self, text: str) -> str:
        """Detect action type from text."""
        words = set(text.split())
        
        # Check for decline keywords first
        if words & DECLINE_KEYWORDS:
            return "DECLINE"
        
        # Check for sort keywords
        if words & SORT_KEYWORDS:
            return "SORT"
        
        # Check for pick keywords
        if words & PICK_KEYWORDS:
            return "PICK"
        
        # Default to PICK for ambiguous requests about blocks
        if any(w in text for w in ["block", "piece", "jenga"]):
            return "PICK"
        
        # If nothing matches, decline
        return "DECLINE"
    
    def _detect_color(self, text: str) -> Optional[str]:
        """Extract color from text."""
        words = text.split()
        
        for word in words:
            # Clean punctuation
            clean = re.sub(r'[^\w]', '', word)
            if clean in COLOR_MAP:
                return COLOR_MAP[clean]
        
        # Check for "any" color
        if "any" in text or "random" in text:
            return "any"
        
        return None
    
    def _detect_quantity(self, text: str) -> int:
        """Extract quantity from text."""
        text_lower = text.lower()
        
        # Check for "all"
        if any(w in text_lower for w in ["all", "every", "everything"]):
            return -1
        
        # Look for numbers
        numbers = re.findall(r'\b(\d+)\b', text)
        if numbers:
            return int(numbers[0])
        
        # Word numbers
        word_nums = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        for word, num in word_nums.items():
            if word in text_lower:
                return num
        
        # Default to 1
        return 1
    
    def _detect_sort_criteria(self, text: str) -> str:
        """Detect sorting criteria."""
        if "color" in text or "colour" in text:
            return "color"
        if "random" in text:
            return "random"
        # Default to color
        return "color"
    
    def _detect_spatial(self, text: str) -> Optional[str]:
        """Detect spatial context from text."""
        words = text.split()
        
        for word in words:
            clean = re.sub(r'[^\w]', '', word)
            if clean in SPATIAL_MAP:
                return SPATIAL_MAP[clean]
        
        return None
    
    def get_json(self, user_input: str) -> str:
        """Get raw JSON string output."""
        result = self.interpret(user_input)
        return json.dumps(result)


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    interpreter = JengaCommandInterpreter()
    
    test_inputs = [
        "grab the red block",
        "pick up the blue piece",
        "get me 3 green blocks",
        "bring all the yellow ones",
        "organize the blocks by color",
        "sort everything",
        "clean up the table",
        "get the emerald block",  # Should map to green
        "dance around",  # Should DECLINE
        "stack the blocks",  # Should DECLINE
        "pick any block",
        "get two pink blocks",
        # Spatial context tests
        "grab the top block",
        "get the nearest red piece",
        "pick the bottom yellow block",
        "bring the leftmost green one",
    ]
    
    print("=" * 60)
    print("Jenga Command Interpreter Test")
    print("=" * 60)
    
    for inp in test_inputs:
        result = interpreter.interpret(inp)
        print(f"\nInput: \"{inp}\"")
        print(json.dumps(result, indent=2))
```

### `arduino_controller.py`
Manages serial communication with the robot hardware, sending JSON commands and receiving responses.
```python
"""
Arduino Controller for SO101 Jenga Robot

Sends JSON commands to the Arduino/MCU for execution.
Handles PICK, SORT, and DECLINE actions.
"""

import serial
import serial.tools.list_ports
import time
import json
import platform
from typing import Optional, List, Tuple, Dict, Any


class JengaRobotController:
    """
    Controller for SO101 Jenga robot arm.
    Sends JSON commands via serial to the MCU.
    """
    
    BAUD_RATE = 115200
    TIMEOUT = 2
    
    def __init__(self, port: Optional[str] = None):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        
    @staticmethod
    def list_ports() -> List[Tuple[str, str]]:
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [(p.device, p.description) for p in ports]
    
    @staticmethod
    def find_robot() -> Optional[str]:
        """Auto-detect robot port."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = port.description.lower()
            if any(x in desc for x in ['arduino', 'stm32', 'usb serial', 'acm']):
                return port.device
        return None
    
    def connect(self) -> bool:
        """Connect to robot."""
        if self.serial and self.serial.is_open:
            return True
        
        # Auto-detect if no port specified
        if not self.port:
            self.port = self.find_robot()
            if not self.port:
                print("Robot not found. Available ports:")
                for device, desc in self.list_ports():
                    print(f"  {device}: {desc}")
                return False
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.BAUD_RATE,
                timeout=self.TIMEOUT
            )
            time.sleep(2)  # Wait for MCU reset
            self.connected = True
            print(f"✓ Connected to robot on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.connected = False
            print("Disconnected from robot")
    
    def execute(self, command: Dict[str, Any]) -> bool:
        """
        Execute a command on the robot.
        
        Args:
            command: JSON command dict with action_type and parameters
            
        Returns:
            True if successful
        """
        if not self.connected or not self.serial:
            print("Not connected to robot")
            return False
        
        action = command.get("action_type", "DECLINE")
        
        # Don't send DECLINE to robot
        if action == "DECLINE":
            print("⚠ Action declined - not sending to robot")
            return True
        
        try:
            # Send JSON command
            cmd_str = json.dumps(command) + "\n"
            self.serial.write(cmd_str.encode())
            
            # Wait for acknowledgment
            response = self.serial.readline().decode().strip()
            
            if response == "OK":
                return True
            elif response.startswith("ERR"):
                print(f"Robot error: {response}")
                return False
            else:
                return True  # Assume success if no error
                
        except serial.SerialException as e:
            print(f"Serial error: {e}")
            self.connected = False
            return False


class MockJengaController(JengaRobotController):
    """Mock controller for testing without hardware."""
    
    def __init__(self):
        super().__init__()
        self.connected = True
        self.last_command = None
    
    def connect(self) -> bool:
        print("[MOCK] Simulated robot connected")
        self.connected = True
        return True
    
    def disconnect(self):
        print("[MOCK] Simulated robot disconnected")
        self.connected = False
    
    def execute(self, command: Dict[str, Any]) -> bool:
        self.last_command = command
        action = command.get("action_type", "UNKNOWN")
        params = command.get("parameters", {})
        reasoning = command.get("reasoning", "")
        
        if action == "DECLINE":
            print(f"[MOCK] ⚠ DECLINED: {reasoning}")
            return True
        
        elif action == "PICK":
            color = params.get("target_color") or "any"
            qty = params.get("quantity", 1)
            spatial = params.get("spatial_context")
            
            location = f" from {spatial}" if spatial else ""
            print(f"[MOCK] 🤖 PICKING {qty}x {color} block(s){location}")
            return True
        
        elif action == "SORT":
            criteria = params.get("sort_criteria", "color")
            print(f"[MOCK] 🤖 SORTING all blocks by {criteria}")
            return True
        
        print(f"[MOCK] Unknown action: {action}")
        return False


# Backward compatibility
ArduinoController = JengaRobotController
MockArduinoController = MockJengaController


if __name__ == "__main__":
    print("Testing Mock Controller...")
    
    controller = MockJengaController()
    controller.connect()
    
    # Test commands
    commands = [
        {"action_type": "PICK", "parameters": {"target_color": "red", "quantity": 1, "spatial_context": "top"}, "reasoning": "Pick 1 red (top) block."},
        {"action_type": "SORT", "parameters": {"sort_criteria": "color"}, "reasoning": "Sort by color."},
        {"action_type": "DECLINE", "parameters": {}, "reasoning": "Request outside capabilities."},
    ]
    
    for cmd in commands:
        print(f"\nExecuting: {cmd['action_type']}")
        controller.execute(cmd)
    
    controller.disconnect()
```

### `speech_input.py`
Handles voice input using OpenAI Whisper (local execution) or falls back to text input.
```python
"""
Speech-to-Text for Arduino UNO Q

Uses OpenAI Whisper (FREE, runs locally, no API needed).
- Model: tiny (~75MB, downloads automatically)
- RAM: ~300MB
- Accuracy: Much better than Vosk
- Cost: FREE (runs 100% locally)
"""

import os
import sys
import tempfile
import wave
from typing import Optional

# Check for Whisper
WHISPER_AVAILABLE = False
try:
    import whisper
    import numpy as np
    import sounddevice as sd
    WHISPER_AVAILABLE = True
except ImportError:
    pass


class WhisperInput:
    """
    Speech recognition using OpenAI Whisper.
    FREE, runs locally, very accurate.
    
    Requires: pip install openai-whisper sounddevice
    """
    
    def __init__(self, model_size: str = "tiny"):
        print(f"Loading Whisper {model_size} model (first run downloads ~75MB)...")
        self.model = whisper.load_model(model_size)
        self.sample_rate = 16000
        print("✓ Whisper ready (FREE, local, accurate)")
    
    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """Record audio and transcribe with Whisper."""
        
        print("🎤 Listening... (speak now)")
        
        try:
            # Record audio
            audio = sd.rec(
                int(timeout * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()
            
            # Check if there's actual audio (not just silence)
            if np.max(np.abs(audio)) < 0.01:
                return None
            
            # Flatten to 1D
            audio = audio.flatten()
            
            # Transcribe directly from numpy array
            result = self.model.transcribe(
                audio,
                language="en",
                fp16=False,  # CPU mode
            )
            
            text = result.get("text", "").strip()
            return text if text else None
            
        except Exception as e:
            print(f"Audio error: {e}")
            return None


class TextInput:
    """Fallback text input."""
    
    def __init__(self):
        print("Using text input (type commands)")
    
    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        try:
            return input("Command > ").strip()
        except EOFError:
            return None


# For backward compatibility
VOSK_AVAILABLE = False


def get_input_handler(prefer_voice: bool = True):
    """Get the best available input handler."""
    if not prefer_voice:
        return TextInput()
    
    if WHISPER_AVAILABLE:
        try:
            return WhisperInput("tiny")
        except Exception as e:
            print(f"Whisper failed: {e}")
    
    return TextInput()


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("Testing Speech-to-Text (Whisper - FREE)")
    print(f"  Whisper available: {WHISPER_AVAILABLE}")
    print("=" * 50)
    
    if not WHISPER_AVAILABLE:
        print("\n❌ Whisper not installed")
        print("Run: pip install openai-whisper sounddevice")
        sys.exit(1)
    
    handler = get_input_handler()
    print("\nSay something (5 seconds):")
    text = handler.listen_once(timeout=5.0)
    
    if text:
        print(f"\n✓ You said: \"{text}\"")
    else:
        print("\n? No speech detected")
```

### `arm_functions.py`
Legacy/Alternative function definitions for identifying arm capabilities and mapping low-level servo moves.
```python
"""
Arm Functions - Robotic Arm Action Definitions

Defines the available functions for the robotic arm and
maps Gemma's parsed commands to Arduino controller actions.
"""

from typing import Dict, Any, Callable, Optional
from arduino_controller import ArduinoController, MockArduinoController


class ArmExecutor:
    """
    Executes robotic arm functions based on Gemma's parsed commands.
    """
    
    def __init__(self, controller: Optional[ArduinoController] = None, mock: bool = True):
        """
        Initialize arm executor.
        
        Args:
            controller: ArduinoController instance (creates one if None)
            mock: If True and no controller provided, use MockArduinoController
        """
        if controller:
            self.controller = controller
        elif mock:
            self.controller = MockArduinoController()
        else:
            self.controller = ArduinoController()
        
        # Map function names to handlers
        self.functions: Dict[str, Callable] = {
            "move_to": self._move_to,
            "grip": self._grip,
            "rotate_joint": self._rotate_joint,
            "home": self._home,
            "set_speed": self._set_speed,
        }
    
    def connect(self) -> bool:
        """Connect to Arduino."""
        return self.controller.connect()
    
    def disconnect(self):
        """Disconnect from Arduino."""
        self.controller.disconnect()
    
    def execute(self, parsed_command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a parsed command from Gemma.
        
        Args:
            parsed_command: Dictionary with 'function', 'parameters', 'explanation'
            
        Returns:
            Dictionary with 'success', 'message', and optional 'data'
        """
        function_name = parsed_command.get("function")
        parameters = parsed_command.get("parameters", {})
        explanation = parsed_command.get("explanation", "")
        
        # Handle null/unknown function
        if not function_name or function_name not in self.functions:
            return {
                "success": False,
                "message": f"Unknown function: {function_name}",
                "explanation": explanation
            }
        
        # Execute the function
        try:
            handler = self.functions[function_name]
            result = handler(**parameters)
            return {
                "success": result,
                "message": f"Executed {function_name}" if result else f"Failed to execute {function_name}",
                "explanation": explanation
            }
        except TypeError as e:
            return {
                "success": False,
                "message": f"Invalid parameters for {function_name}: {e}",
                "explanation": explanation
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error executing {function_name}: {e}",
                "explanation": explanation
            }
    
    # Function handlers
    
    def _move_to(self, x: float = 0, y: float = 50, z: float = 40) -> bool:
        """Move arm to position."""
        print(f"  → Moving to ({x}, {y}, {z})")
        return self.controller.move_to(x, y, z)
    
    def _grip(self, state: str = "open") -> bool:
        """Control gripper."""
        print(f"  → Gripper: {state}")
        return self.controller.grip(state)
    
    def _rotate_joint(self, joint_id: int = 1, angle: float = 0) -> bool:
        """Rotate joint."""
        print(f"  → Rotating joint {joint_id} to {angle}°")
        return self.controller.rotate_joint(joint_id, angle)
    
    def _home(self) -> bool:
        """Return to home position."""
        print("  → Returning to home position")
        return self.controller.home()
    
    def _set_speed(self, speed: int = 5) -> bool:
        """Set movement speed."""
        print(f"  → Setting speed to {speed}")
        return self.controller.set_speed(speed)


# Standalone function definitions for direct use

def move_to(x: float, y: float, z: float) -> Dict[str, Any]:
    """
    Move the arm end effector to position (x, y, z).
    
    Args:
        x: X position in cm (-50 to 50)
        y: Y position in cm (0 to 100, forward)  
        z: Z position in cm (0 to 80, up)
        
    Returns:
        Status dictionary
    """
    return {
        "action": "move_to",
        "parameters": {"x": x, "y": y, "z": z},
        "description": f"Move arm to position ({x}, {y}, {z}) cm"
    }


def grip(state: str) -> Dict[str, Any]:
    """
    Control the gripper.
    
    Args:
        state: 'open' or 'close'
        
    Returns:
        Status dictionary
    """
    return {
        "action": "grip",
        "parameters": {"state": state},
        "description": f"{'Opening' if state == 'open' else 'Closing'} gripper"
    }


def rotate_joint(joint_id: int, angle: float) -> Dict[str, Any]:
    """
    Rotate a specific joint.
    
    Args:
        joint_id: Joint number (1=base, 2=shoulder, 3=elbow, 4=wrist_pitch, 5=wrist_roll, 6=gripper)
        angle: Angle in degrees (-180 to 180)
        
    Returns:
        Status dictionary
    """
    joint_names = {
        1: "base",
        2: "shoulder", 
        3: "elbow",
        4: "wrist_pitch",
        5: "wrist_roll",
        6: "gripper"
    }
    return {
        "action": "rotate_joint",
        "parameters": {"joint_id": joint_id, "angle": angle},
        "description": f"Rotating {joint_names.get(joint_id, 'joint')} to {angle}°"
    }


def home() -> Dict[str, Any]:
    """
    Return arm to home/rest position.
    
    Returns:
        Status dictionary
    """
    return {
        "action": "home",
        "parameters": {},
        "description": "Returning arm to home position"
    }


def set_speed(speed: int) -> Dict[str, Any]:
    """
    Set movement speed.
    
    Args:
        speed: Speed level (1=slow, 10=fast)
        
    Returns:
        Status dictionary
    """
    return {
        "action": "set_speed",
        "parameters": {"speed": speed},
        "description": f"Setting movement speed to {speed}"
    }


if __name__ == "__main__":
    # Test the executor with mock controller
    print("Testing ArmExecutor with mock controller...")
    
    executor = ArmExecutor(mock=True)
    executor.connect()
    
    # Simulate parsed commands from Gemma
    test_commands = [
        {"function": "move_to", "parameters": {"x": 10, "y": 30, "z": 20}, "explanation": "Moving forward"},
        {"function": "grip", "parameters": {"state": "close"}, "explanation": "Grabbing object"},
        {"function": "home", "parameters": {}, "explanation": "Going home"},
    ]
    
    for cmd in test_commands:
        print(f"\nExecuting: {cmd['explanation']}")
        result = executor.execute(cmd)
        print(f"Result: {result}")
    
    executor.disconnect()
```

### `requirements.txt`
```text
requests>=2.31.0
pyserial>=3.5
faster-whisper>=1.0.0
sounddevice>=0.4.6
numpy>=1.24.0
```

### `arduino/arm_controller/arm_controller.ino`
Arduino sketch for the STM32 microcontroller.
```cpp
/*
 * Arduino UNO Q - STM32 MCU Firmware
 * 
 * Runs on the STM32U585 microcontroller side of the UNO Q.
 * Receives commands from the Qualcomm side via internal serial bridge
 * and controls the 6-DOF robotic arm servos.
 * 
 * Upload this using Arduino IDE with UNO Q board selected.
 */

#include <Servo.h>

// ============ PIN CONFIGURATION ============
// Adjust these pins based on your wiring
#define SERVO_BASE      3    // Joint 1: Base rotation
#define SERVO_SHOULDER  5    // Joint 2: Shoulder
#define SERVO_ELBOW     6    // Joint 3: Elbow  
#define SERVO_WRIST_P   9    // Joint 4: Wrist pitch
#define SERVO_WRIST_R   10   // Joint 5: Wrist roll
#define SERVO_GRIPPER   11   // Joint 6: Gripper

// ============ SERVO OBJECTS ============
Servo servos[6];
const int servoPins[6] = {SERVO_BASE, SERVO_SHOULDER, SERVO_ELBOW, 
                          SERVO_WRIST_P, SERVO_WRIST_R, SERVO_GRIPPER};

// ============ POSITIONS ============
// Home position for each servo
const int homePos[6] = {90, 90, 90, 90, 90, 30};

// Current positions
int currentPos[6] = {90, 90, 90, 90, 90, 30};

// Movement step size (degrees per step)
const int STEP = 15;

// Speed delay (ms between steps)
int speedDelay = 15;

// ============ SETUP ============
void setup() {
    Serial.begin(115200);
    
    // Attach all servos
    for (int i = 0; i < 6; i++) {
        servos[i].attach(servoPins[i]);
        servos[i].write(homePos[i]);
        currentPos[i] = homePos[i];
    }
    
    delay(1000);
    Serial.println("READY");
}

// ============ MAIN LOOP ============
void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\\n');
        cmd.trim();
        processCommand(cmd);
    }
}

// ============ COMMAND PROCESSING ============
void processCommand(String cmd) {
    // Extract command from JSON: {"cmd": "move_left"}
    int cmdStart = cmd.indexOf("\"cmd\"");
    if (cmdStart == -1) {
        Serial.println("ERR: No cmd");
        return;
    }
    
    // Find the command value
    int valueStart = cmd.indexOf(":", cmdStart) + 1;
    int valueEnd = cmd.indexOf("}", valueStart);
    String cmdValue = cmd.substring(valueStart, valueEnd);
    cmdValue.replace("\"", "");
    cmdValue.trim();
    
    // Execute command
    bool success = executeCommand(cmdValue);
    
    if (success) {
        Serial.println("OK");
    } else {
        Serial.println("ERR: Unknown cmd");
    }
}

bool executeCommand(String cmd) {
    // === GRIPPER COMMANDS ===
    if (cmd == "pick_up") {
        return moveServo(5, 150);  // Close gripper
    }
    else if (cmd == "put_down") {
        return moveServo(5, 30);   // Open gripper
    }
    
    // === MOVEMENT COMMANDS ===
    else if (cmd == "move_left") {
        return moveServo(0, currentPos[0] + STEP);  // Rotate base left
    }
    else if (cmd == "move_right") {
        return moveServo(0, currentPos[0] - STEP);  // Rotate base right
    }
    else if (cmd == "move_forward") {
        return moveServo(1, currentPos[1] - STEP);  // Shoulder forward
    }
    else if (cmd == "move_backward") {
        return moveServo(1, currentPos[1] + STEP);  // Shoulder back
    }
    else if (cmd == "move_up") {
        return moveServo(2, currentPos[2] + STEP);  // Elbow up
    }
    else if (cmd == "move_down") {
        return moveServo(2, currentPos[2] - STEP);  // Elbow down
    }
    
    // === ROTATION COMMANDS ===
    else if (cmd == "rotate_clockwise") {
        return moveServo(4, currentPos[4] + STEP);  // Wrist roll CW
    }
    else if (cmd == "rotate_counterclockwise") {
        return moveServo(4, currentPos[4] - STEP);  // Wrist roll CCW
    }
    
    // === UTILITY COMMANDS ===
    else if (cmd == "home") {
        return goHome();
    }
    else if (cmd == "stop") {
        // Already stopped - do nothing
        return true;
    }
    
    return false;  // Unknown command
}

// ============ SERVO CONTROL ============
bool moveServo(int servoIndex, int targetPos) {
    if (servoIndex < 0 || servoIndex > 5) return false;
    
    // Constrain to valid range
    targetPos = constrain(targetPos, 0, 180);
    
    // Smooth movement
    int start = currentPos[servoIndex];
    int step = (targetPos > start) ? 1 : -1;
    
    for (int pos = start; pos != targetPos; pos += step) {
        servos[servoIndex].write(pos);
        delay(speedDelay);
    }
    servos[servoIndex].write(targetPos);
    currentPos[servoIndex] = targetPos;
    
    return true;
}

bool goHome() {
    // Move all servos to home position
    for (int i = 0; i < 6; i++) {
        moveServo(i, homePos[i]);
    }
    return true;
}
```
