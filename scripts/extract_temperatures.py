"""Extract 4-corner bed temperatures from the FLIR thermal video via OCR.

Samples every 0.5s and writes results to CSV.
"""

import csv
import re
import sys

import cv2
import numpy as np
import pytesseract

VIDEO_PATH = (
    "/home/erik-work/code/fiftyone/data/timeseries_demo/"
    "Artillery Sidewinder X2 - Bed Temperature Uniformity - FLIR Cam.mp4"
)
OUTPUT_CSV = (
    "/home/erik-work/code/fiftyone/data/timeseries_demo/temperatures.csv"
)
INTERVAL_S = 0.5

# ROI bounding boxes (x1, y1, x2, y2) in the 1440x1080 frame
ROIS: dict[str, tuple[int, int, int, int]] = {
    "top_left": (510, 325, 670, 380),
    "top_right": (1050, 350, 1200, 400),
    "bottom_left": (460, 863, 660, 920),
    "bottom_right": (1050, 855, 1200, 910),
}

TESSERACT_CFG = "--psm 7 -c tessedit_char_whitelist=0123456789."


def extract_temp(
    frame: np.ndarray, roi: tuple[int, int, int, int]
) -> float | None:
    x1, y1, x2, y2 = roi
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    scaled = cv2.resize(
        binary, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC
    )
    raw = pytesseract.image_to_string(scaled, config=TESSERACT_CFG)
    match = re.search(r"(\d+\.?\d*)", raw)
    if match:
        val = float(match.group(1))
        # Sanity: bed temps should be between 15°C and 200°C
        if 15.0 <= val <= 200.0:
            return val
    return None


def main() -> None:
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"ERROR: cannot open {VIDEO_PATH}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    total_samples = int(duration / INTERVAL_S) + 1

    print(f"Video: {fps:.2f} FPS, {total_frames} frames, {duration:.1f}s")
    print(f"Extracting every {INTERVAL_S}s => ~{total_samples} samples")
    print(f"Output: {OUTPUT_CSV}")

    channels = list(ROIS.keys())
    rows: list[list] = []
    failed = 0

    for i in range(total_samples):
        t = i * INTERVAL_S
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret:
            break

        row: list = [round(t, 1)]
        any_none = False
        for ch in channels:
            val = extract_temp(frame, ROIS[ch])
            row.append(val)
            if val is None:
                any_none = True

        if any_none:
            failed += 1
        rows.append(row)

        if i % 100 == 0:
            print(f"  {i}/{total_samples}  t={t:.1f}s  vals={row[1:]}")

    cap.release()

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp"] + channels)
        writer.writerows(rows)

    print(f"\nDone: {len(rows)} rows written to {OUTPUT_CSV}")
    print(
        f"Failed OCR on {failed}/{len(rows)} rows ({failed/len(rows)*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
