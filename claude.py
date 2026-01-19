import cv2
import numpy as np
import pyrealsense2 as rs

class JengaBlockDetector:
    def __init__(self, focal_length=None, real_block_length=7.5, camera_intrinsics=None):
        """
        Initialize the Jenga block detector
        
        Args:
            focal_length: Camera focal length in pixels
            real_block_length: The length of the Jenga block's LONGEST side in cm.
                               Standard Jenga is 1.5 x 2.5 x 7.5 cm.
                               We use the longest side for better distance stability.
            camera_intrinsics: Dict with keys 'fx', 'fy', 'ppx', 'ppy' for converting to 3D coords
        """
        self.focal_length = focal_length
        self.real_block_length = real_block_length
        
        # Camera intrinsics for 3D coordinate conversion
        self.camera_intrinsics = camera_intrinsics or {
            'fx': focal_length,
            'fy': focal_length,
            'ppx': 320,  # Default principal point x (half of 640)
            'ppy': 240   # Default principal point y (half of 480)
        }
        
        # Define HSV color ranges for each Jenga block color
        # Tightened ranges to reduce false positives
        self.color_ranges = {
            'red': [(np.array([0, 100, 100]), np.array([10, 255, 255])),
                    (np.array([160, 100, 100]), np.array([180, 255, 255]))],
            'blue': [(np.array([100, 100, 100]), np.array([130, 255, 255]))],
            'green': [(np.array([40, 50, 50]), np.array([80, 255, 255]))],
            'yellow': [(np.array([20, 100, 100]), np.array([35, 255, 255]))],
            'pink': [(np.array([140, 50, 50]), np.array([170, 255, 255]))],
            'orange': [(np.array([10, 100, 100]), np.array([25, 255, 255]))]
        }
    
    def segment_color(self, hsv_image, color_name):
        """Create mask for a specific color"""
        mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
        
        for lower, upper in self.color_ranges[color_name]:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower, upper))
        
        # Clean up the mask (Morphological operations)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        return mask
    
    def find_aligned_rectangle(self, contour):
        """Find the minimum area rectangle aligned with block edges"""
        # minAreaRect returns (center(x, y), (width, height), angle of rotation)
        rect = cv2.minAreaRect(contour)
        
        # FIX: np.int0 is deprecated in newer numpy versions, use int32
        box = cv2.boxPoints(rect)
        box = np.int32(box) 
        
        center = rect[0]
        width, height = rect[1]
        angle = rect[2]
        
        # Standardize: Ensure 'width' is always the longest side.
        # This is crucial because our distance calc relies on the known length (7.5cm).
        if width < height:
            width, height = height, width
            angle += 90  # Adjust angle to match the swap
        
        return {
            'center': center,
            'width': width,   # Longest side in pixels
            'height': height, # Shortest side in pixels
            'angle': angle,
            'box': box
        }
    
    def calculate_distance(self, pixel_width):
        """Calculate distance from camera to block center using Pinhole model"""
        if self.focal_length is None:
            return 0.0
            
        # D = (Real_Width * Focal_Length) / Pixel_Width
        distance = (self.real_block_length * self.focal_length) / pixel_width
        return distance
    
    def pixel_to_3d_world(self, pixel_x, pixel_y, distance_cm):
        """
        Convert 2D image coordinates to 3D world coordinates with camera as origin.
        
        Args:
            pixel_x: X coordinate in image (column)
            pixel_y: Y coordinate in image (row)
            distance_cm: Distance from camera (depth) in cm
            
        Returns:
            Dict with 'x', 'y', 'z' in cm, where camera is at origin (0, 0, 0)
            Z-axis points forward (away from camera)
            X-axis points right
            Y-axis points down
        """
        fx = self.camera_intrinsics['fx']
        fy = self.camera_intrinsics['fy']
        ppx = self.camera_intrinsics['ppx']
        ppy = self.camera_intrinsics['ppy']
        
        # Using pinhole camera model
        # X = (u - ppx) * Z / fx
        # Y = (v - ppy) * Z / fy
        # Z = distance
        
        x = (pixel_x - ppx) * distance_cm / fx
        y = (pixel_y - ppy) * distance_cm / fy
        z = distance_cm
        
        return {
            'x': x,
            'y': y,
            'z': z
        }
    
    def detect_blocks(self, image):
        """Detect all Jenga blocks in the image"""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        detected_blocks = []
        
        for color_name in self.color_ranges.keys():
            mask = self.segment_color(hsv, color_name)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by area - Jenga blocks should have reasonable size
                if area < 1500:  # Minimum area to filter noise
                    continue
                if area > 3000:  # Maximum area to filter large objects
                    continue
                
                rect_info = self.find_aligned_rectangle(contour)
                width = rect_info['width']
                height = rect_info['height']
                
                # Filter by aspect ratio - Jenga blocks are elongated (7.5 x 2.5 cm)
                # So we expect width/height ratio to be roughly between 1.5 and 5
                if width > 0:
                    aspect_ratio = width / height
                    if aspect_ratio < 1.2 or aspect_ratio > 6:  # Too square or too elongated
                        continue
                
                # Filter by solidity - block should be mostly filled
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = area / hull_area
                    if solidity < 0.6:  # Less than 60% filled is likely not a block
                        continue
                
                # Calculate distance using the LONGEST side
                dist = 0.0
                if self.focal_length is not None:
                    dist = self.calculate_distance(width)
                
                # Convert 2D image center to 3D world coordinates
                center_pixel = rect_info['center']
                world_coords = self.pixel_to_3d_world(center_pixel[0], center_pixel[1], dist)
                
                block_data = {
                    'color': color_name,
                    'center': rect_info['center'],
                    'width': width,
                    'height': height,
                    'angle': rect_info['angle'],
                    'box': rect_info['box'],
                    'area': area,
                    'distance': dist,
                    'aspect_ratio': aspect_ratio,
                    'solidity': solidity,
                    'world_coords': world_coords  # 3D coordinates with camera as origin
                }
                
                detected_blocks.append(block_data)
        
        return detected_blocks
    
    def draw_results(self, image, blocks):
        """Draw detected blocks and information on the image"""
        result = image.copy()
        
        for block in blocks:
            # Draw the aligned rectangle
            cv2.drawContours(result, [block['box']], 0, (0, 255, 0), 2)
            
            # Draw center point
            center = tuple(map(int, block['center']))
            cv2.circle(result, center, 5, (0, 0, 255), -1)
            
            # Text information
            text_lines = [
                f"{block['color'].upper()}",
                f"Dist: {block['distance']:.1f} cm"
            ]
            
            y_offset = -20
            for line in text_lines:
                cv2.putText(result, line, (center[0] - 40, center[1] + y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                y_offset += 20
        
        return result

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Standard Jenga block length is 7.5 cm (Longest side)
    detector = JengaBlockDetector(real_block_length=7.5)
    
    print("Starting RealSense Stream...")
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    
    # Initialize frame count variable
    frame_count = 0
    
    try:
        profile = pipeline.start(config)
        
        # Get intrinsics for automatic focal length
        color_stream = profile.get_stream(rs.stream.color)
        intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
        
        # fx is the focal length in pixels for the width axis
        detector.focal_length = intrinsics.fx
        
        # Store camera intrinsics for 3D coordinate conversion
        detector.camera_intrinsics = {
            'fx': intrinsics.fx,
            'fy': intrinsics.fy,
            'ppx': intrinsics.ppx,
            'ppy': intrinsics.ppy
        }
        
        print(f"Camera Initialized.")
        print(f"  Focal Length: fx={intrinsics.fx:.2f}px, fy={intrinsics.fy:.2f}px")
        print(f"  Principal Point: ({intrinsics.ppx:.2f}, {intrinsics.ppy:.2f})")
        print(f"  Resolution: {intrinsics.width} x {intrinsics.height}")
        
        while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            
            if not color_frame:
                continue
            
            frame = np.asanyarray(color_frame.get_data())
            frame_count += 1
            
            # Detection
            blocks = detector.detect_blocks(frame)
            result_frame = detector.draw_results(frame, blocks)
            
            # GUI Overlays
            cv2.putText(result_frame, f"Blocks: {len(blocks)}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow('RealSense Jenga Detection', result_frame)
            
            # Print periodic logs
            if frame_count % 60 == 0 and blocks:
                print(f"--- Frame {frame_count} ---")
                for b in blocks:
                    coords = b['world_coords']
                    print(f"[{b['color']}] Distance: {b['distance']:.1f}cm | Angle: {b['angle']:.1f}° | 3D Coords: X={coords['x']:.1f}cm, Y={coords['y']:.1f}cm, Z={coords['z']:.1f}cm")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()