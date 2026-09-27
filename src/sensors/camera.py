import os
import time

import cv2

# Auto-exposure only adjusts while frames are being read, so we pull frames until
# the brightness settles instead of sleeping and grabbing a single (stale) frame.
MIN_WARMUP_FRAMES = 30
MAX_WARMUP_FRAMES = 150
SETTLED_DELTA = 1.0  # mean brightness change (0-255) between frames that counts as settled
SETTLED_STREAK = 5

# Mean brightness outside this range means the frame is blown out or black
MIN_MEAN_BRIGHTNESS = 15
MAX_MEAN_BRIGHTNESS = 240


def _mean_brightness(frame) -> float:
    return float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())


def _read_settled_frame(camera):
    frame, last_mean, streak = None, None, 0
    for i in range(MAX_WARMUP_FRAMES):
        ret, frame = camera.read()
        if not ret or frame is None:
            raise RuntimeError("Could not read frame from camera.")

        mean = _mean_brightness(frame)
        if last_mean is not None and abs(mean - last_mean) < SETTLED_DELTA:
            streak += 1
        else:
            streak = 0
        last_mean = mean

        if i + 1 >= MIN_WARMUP_FRAMES and streak >= SETTLED_STREAK:
            break
    return frame


def capture_photo_and_save() -> str:
    os.makedirs("data/photos", exist_ok=True)

    camera = cv2.VideoCapture(0)
    try:
        frame = _read_settled_frame(camera)

        mean = _mean_brightness(frame)
        if not MIN_MEAN_BRIGHTNESS <= mean <= MAX_MEAN_BRIGHTNESS:
            raise RuntimeError(
                f"Photo exposure looks wrong (mean brightness {mean:.1f}/255); not saving it."
            )

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
