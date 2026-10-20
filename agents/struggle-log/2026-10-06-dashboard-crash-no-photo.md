# Dashboard returned 500 when no photo existed yet

**Commit:** 0f0098c

**What happened:** `GET /` failed with a 500 when the database had readings but no photo. With an empty database it rendered a broken image and blank values.

**Root cause:** The template assumed `data.file_path` and the reading fields always exist, and nothing tested the empty states.

**Fix:** `src/templates/index.html` shows "No photo yet." and "No readings yet." placeholders. `src/tests/test_app.py` covers the empty database, readings without a photo, and the full case. A leftover debug `print` was removed.

**Lesson:** A fresh install or a failed `--photo` run is a real state for this app. Test the empty and partial-data paths for any new page or API route.
