import cv2
import numpy as np
import pickle
import time
import sys

# --- CONFIGURATION ---
MODEL_PATH = 'beewasp_model.tflite'
LABELS_PATH = 'labels.pkl'
CONFIDENCE_THRESHOLD = 0.75
INFERENCE_FPS = 5
INFERENCE_INTERVAL = 1.0 / INFERENCE_FPS
COOLDOWN_SECONDS = 0.5 # Don't fire twice in 3 seconds

# Import TFLite Runtime
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

def load_labels(path):
    with open(path, 'rb') as f:
        return pickle.load(f)

def main():
    labels = load_labels(LABELS_PATH)
    print(f"Loaded classes: {labels}")

    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    h = input_details[0]['shape'][1]
    w = input_details[0]['shape'][2]

    cap = cv2.VideoCapture(0)
    # Lower resolution saves USB bandwidth on weak devices
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: No camera found.")
        sys.exit(1)

    print(f"--- DETECTOR ACTIVE ({INFERENCE_FPS} checks/sec) ---")
    
    last_inference_time = 0
    last_fire_time = 0

    try:
        while True:
            # Always grab the frame to clear the hardware buffer
            ret, frame = cap.read()
            if not ret: break

            now = time.time()

            # Only process if enough time has passed
            if (now - last_inference_time) >= INFERENCE_INTERVAL:
                
                # --- PROCESS ---
                img = cv2.resize(frame, (w, h))
                img = img.astype(np.float32)
                img = np.expand_dims(img, axis=0)
                img = (img / 127.5) - 1.0

                interpreter.set_tensor(input_details[0]['index'], img)
                interpreter.invoke()
                output_data = interpreter.get_tensor(output_details[0]['index'])[0]

                class_idx = np.argmax(output_data)
                confidence = output_data[class_idx]
                class_name = labels[class_idx]

                last_inference_time = now

                # Optional: Alive check (prints a dot every check)
                # print(".", end="", flush=True) 

                # --- TRIGGER ---
                if class_name == 'wasp' and confidence > CONFIDENCE_THRESHOLD:
                    if (now - last_fire_time) > COOLDOWN_SECONDS:
                        print(f"\n[ALERT] WASP DETECTED! (Conf: {confidence*100:.1f}%)")
                        print("aaah!! thats a wasp. Fire!")
                        
                        # Add your hardware trigger here
                        # fire_mechanism()
                        
                        last_fire_time = now
            
            # Tiny sleep to yield CPU to other processes
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        cap.release()

if __name__ == "__main__":
    main()
