import os
import time
import cv2

def capture_photo_and_save() -> str:
    os.makedirs("data/photos", exist_ok=True)

    camera = cv2.VideoCapture(0)
    try:
        time.sleep(2)
        camera.set(cv2.CAP_PROP_EXPOSURE, -4)

        ret, frame = camera.read()
        if not ret or frame is None:
            raise RuntimeError("Could not read frame from camera.")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        mean, std_dev = cv2.meanStdDev(blurred)

        if std_dev[0] > 100:
            if mean[0] < 100:
                camera.set(cv2.CAP_PROP_EXPOSURE, -3)
            else:
                camera.set(cv2.CAP_PROP_EXPOSURE, -5)
            ret, frame = camera.read()
            if not ret or frame is None:
                raise RuntimeError("Could not read adjusted frame from camera.")

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
