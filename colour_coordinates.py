"""Utilities to capture a single camera frame and produce a
colour -> coordinates dictionary using the detect_jenga detector.

Function provided:
- `capture_colour_coordinates(...) -> dict`

Behavior:
1. Move the robot arm to the home position.
2. Capture a single color frame from the RealSense camera.
3. Run the `JengaBlockDetector` on the frame and return a mapping
   of color -> list of (x, y, z) coordinate tuples.

Dictionary format:
{
    'red': [(x1, y1, z1), (x2, y2, z2), ...],
    'blue': [(x3, y3, z3), ...],
    ...
}
Each color appears as a key only once, with all detected blocks of that color
in the associated list.
"""

import os
import time
import importlib.util
from typing import Optional, Dict, List, Tuple
import numpy as np

try:
    import pyrealsense2 as rs
except Exception:
    rs = None

colours = {}

def _load_roarm_controller_class():
    here = os.path.dirname(__file__)
    helper_path = os.path.normpath(os.path.join(here, "roarm-m2", "roarm_helper.py"))

    spec = importlib.util.spec_from_file_location("roarm_helper", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load roarm_helper from {helper_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "RoArmController")


def _load_detector_class():
    here = os.path.dirname(__file__)
    detector_path = os.path.normpath(os.path.join(here, "detect_jenga.py"))

    spec = importlib.util.spec_from_file_location("detect_jenga", detector_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load detect_jenga from {detector_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "JengaBlockDetector")


def capture_colour_coordinates(
    arm: Optional[object] = None,
    roarm_ip: str = "192.168.4.1",
    home_x: float = 40.0,
    home_y: float = 1.0,
    home_z: float = 53.0,
    home_t: float = 3.14,
    speed: float = 0.4,
    rs_timeout: float = 5.0,
) -> Dict[str, List[Tuple[float, float, float]]]:
    """Move arm to home, capture one frame, and return color->coords dict.

    Returns a dict mapping color name -> list of (x, y, z) tuples.
    Each color key appears only once with all its detected blocks grouped in a list.
    Prefers `new_frame_coords` (calibrated robot frame) if available,
    otherwise falls back to `world_coords` (camera frame).
    """
    # 1) Move arm to home
    try:
        if arm is None:
            RoArmController = _load_roarm_controller_class()
            arm = RoArmController(ip_address=roarm_ip)

        arm.set_torque(True)
        arm.move_cartesian(x=home_x, y=home_y, z=home_z, t=home_t, speed=speed, wait=True)
    except Exception as e:
        print(f"[colour_coordinates] Warning: failed to move arm to home: {e}")

    # 2) Capture a single frame using RealSense and detect_jenga
    if rs is None:
        raise RuntimeError("pyrealsense2 is not available in this environment")

    try:
        JengaBlockDetector = _load_detector_class()
        detector = JengaBlockDetector()
    except Exception as e:
        raise RuntimeError(f"Failed to load JengaBlockDetector: {e}")

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    profile = pipeline.start(config)
    try:
        # Obtain intrinsics and set detector focal length
        color_stream = profile.get_stream(rs.stream.color)
        intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
        detector.focal_length = intrinsics.fx
        detector.camera_intrinsics = {
            'fx': intrinsics.fx,
            'fy': intrinsics.fy,
            'ppx': intrinsics.ppx,
            'ppy': intrinsics.ppy,
        }

        # Load calibration matrix to transform to robot frame
        detector.load_calibration_matrix("./calibration/calibration_matrix.npy")

        # Wait for and collect 60 color frames before running detector
        start = time.time()
        color_frame = None
        frame_count = 0
        while (time.time() - start) < rs_timeout and frame_count < 60:
            frames = pipeline.wait_for_frames(timeout_ms=1000)
            cf = frames.get_color_frame()
            if cf:
                color_frame = cf
                frame_count += 1

        if frame_count < 60:
            raise RuntimeError(f"Failed to capture 60 frames; only captured {frame_count} within timeout")

        frame = np.asanyarray(color_frame.get_data())

        # Run detection
        blocks = detector.detect_blocks(frame)

    finally:
        pipeline.stop()

    # 3) Build dictionary: color -> list of coordinates (each color key added only once)
    out: Dict[str, List[Tuple[float, float, float]]] = {}

    for block in blocks:
        color = block.get('color') or 'unknown'

        # Prefer new_frame_coords (calibrated robot frame), fall back to world_coords (camera frame)
        coords = block.get('new_frame_coords') or block.get('world_coords')

        if coords is None:
            continue

        # Extract x, y, z safely
        try:
            x = float(coords.get('x', 0))
            y = float(coords.get('y', 0))
            z = float(coords.get('z', 0))
        except (ValueError, TypeError):
            continue

        # Add color key only once (setdefault creates it on first encounter)
        # All blocks of the same color are appended to the list
        out.setdefault(color, []).append((x, y, z))
        colours = out 
        print(out)

    return out


if __name__ == "__main__":
    print("Capturing colour coordinates...")
    coords = capture_colour_coordinates()
    print("\nDetected blocks by colour:")
    for colour, coord_list in coords.items():
        print(f"  {colour}: {len(coord_list)} block(s)")
        for i, (x, y, z) in enumerate(coord_list, 1):
            print(f"    Block {i}: ({x:.1f}, {y:.1f}, {z:.1f})")
