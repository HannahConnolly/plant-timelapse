import os
import time

import cv2


def capture_photo_and_save() -> str:
    os.makedirs("data/photos", exist_ok=True)

    camera = cv2.VideoCapture(0)
    try:
        # Give the camera hardware time to warm up and auto-adjust exposure/white balance
        time.sleep(2)

        # Read a frame to ensure the buffer clears and grabs a stabilized frame
        ret, frame = camera.read()
        if not ret or frame is None:
            raise RuntimeError("Could not read frame from camera.")

        timestamp = time.strftime("%m-%d-%Y")
        image_path = f"data/photos/{timestamp}.jpg"
        cv2.imwrite(image_path, frame)

        return image_path
    finally:
        camera.release()


# Test the method
if __name__ == "__main__":
    try:
        image_path = capture_photo_and_save()
        print(f"Photo saved to {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
