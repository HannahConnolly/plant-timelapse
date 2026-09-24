import logging
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

logger = logging.getLogger(__name__)

# Matches the filename format written by sensors/camera.py
PHOTO_DATE_FORMAT = "%m-%d-%Y"


def collect_photos(photos_dir: Path) -> list[tuple[date, Path]]:
    """Returns (date, path) pairs for every dated photo, oldest first."""
    photos = []

    for path in Path(photos_dir).glob("*.jpg"):
        try:
            photo_date = datetime.strptime(path.stem, PHOTO_DATE_FORMAT).date()
        except ValueError:
            continue  # Skip files that aren't daily captures (e.g. demo.jpg)
        photos.append((photo_date, path))

    return sorted(photos)


def _label_frame(image: Image.Image, text: str) -> Image.Image:
    """Draws a date caption in the bottom-left corner of the frame."""
    frame = image.convert("RGB")
    draw = ImageDraw.Draw(frame)
    font_size = max(16, frame.height // 20)
    font = ImageFont.load_default(size=font_size)

    margin = font_size // 2
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = margin
    y = frame.height - (bottom - top) - margin * 2
    draw.rectangle(
        (x - margin // 2, y - margin // 2, x + right + margin // 2, y + bottom + margin // 2),
        fill=(0, 0, 0),
    )
    draw.text((x, y), text, font=font, fill=(255, 255, 255))
    return frame


def create_growth_animation(
    photos: list[tuple[date, Path]],
    output_path: Path,
    frame_duration_ms: int = 175,
    final_frame_hold_ms: int = 2000,
    max_width: int = 640,
) -> Path | None:
    """Builds a looping GIF from dated photos. Returns the output path, or None if no frames loaded."""
    frames = []
    for photo_date, path in photos:
        try:
            with Image.open(path) as img:
                if img.width > max_width:
                    img = img.resize(
                        (max_width, round(img.height * max_width / img.width))
                    )
                frames.append(_label_frame(img, photo_date.strftime("%a %b %d")))
        except (OSError, UnidentifiedImageError) as e:
            logger.warning(f"Skipping unreadable photo '{path}': {e}")

    if not frames:
        logger.error("No readable photos available to build an animation.")
        return None

    # Keep every frame the same size as the first so the GIF doesn't jump around
    size = frames[0].size
    frames = [f if f.size == size else f.resize(size) for f in frames]

    durations = [frame_duration_ms] * len(frames)
    durations[-1] = final_frame_hold_ms

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    logger.info(f"Saved {len(frames)}-frame growth animation to {output_path}")
    return output_path
