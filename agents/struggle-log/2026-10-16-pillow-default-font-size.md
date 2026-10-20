# Animation caption crashed on older Pillow

**Commit:** 6cd390a

**What happened:** The growth GIF builder failed on the Pi when it drew the date caption on each frame.

**Root cause:** `ImageFont.load_default(size=...)` only accepts `size` from Pillow 10.1. Older versions raise `TypeError`.

**Fix:** `_load_font` in `src/services/animation.py` tries `load_default(size=...)`, then falls back to DejaVuSans, then to the unsized default font.

**Lesson:** Installed package versions can differ between machines. Check a library's minimum version before using a newer keyword argument, and add a fallback.
