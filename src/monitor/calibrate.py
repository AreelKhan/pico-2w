from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_config_path() -> Path:
    return _repo_root() / "data" / "monitor" / "configuration.json"


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def _select_roi(frame_bgr, *, title: str) -> dict[str, int]:
    import cv2

    x, y, w, h = cv2.selectROI(title, frame_bgr, fromCenter=False, showCrosshair=True)
    if w <= 0 or h <= 0:
        raise RuntimeError("ROI selection cancelled")
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}


def _median_hsv(frame_bgr, roi: dict[str, int]) -> list[int]:
    import cv2
    import numpy as np

    x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
    roi_bgr = frame_bgr[y : y + h, x : x + w]
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    med = np.median(hsv, axis=0)
    return [int(med[0]), int(med[1]), int(med[2])]


def _open_camera(*, device: int, width: int, height: int, target_fps: int, fourcc: str) -> Any:
    import cv2

    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, getattr(cv2, "VideoWriter_fourcc")(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, target_fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera device={device}")
    return cap


def calibrate(*, out_path: Path, device: int, width: int, height: int, fps: int, fourcc: str) -> int:
    import cv2

    cap = _open_camera(device=device, width=width, height=height, target_fps=fps, fourcc=fourcc)
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Frame read failed")

        print("Select ROIs while the Level end pop is visible.")
        turquoise_roi = _select_roi(frame, title="Select ROI: TURQUOISE (press ENTER to confirm)")
        light_green_roi = _select_roi(frame, title="Select ROI: LIGHT GREEN (press ENTER to confirm)")
        dark_green_roi = _select_roi(frame, title="Select ROI: DARK GREEN (press ENTER to confirm)")

        cfg: dict[str, Any] = {
            "camera": {
                "device": int(device),
                "width": int(width),
                "height": int(height),
                "target_fps": int(fps),
                "fourcc": str(fourcc),
            },
            "level_end_pop": {
                "min_regions_active": 3,
                "regions": {
                    "turquoise": {
                        "roi": turquoise_roi,
                        "ref_hsv": _median_hsv(frame, turquoise_roi),
                        "tol_hsv": [12, 60, 70],
                        "min_frac": 0.08,
                        "debounce_frames": 3,
                    },
                    "light_green": {
                        "roi": light_green_roi,
                        "ref_hsv": _median_hsv(frame, light_green_roi),
                        "tol_hsv": [12, 60, 70],
                        "min_frac": 0.08,
                        "debounce_frames": 3,
                    },
                    "dark_green": {
                        "roi": dark_green_roi,
                        "ref_hsv": _median_hsv(frame, dark_green_roi),
                        "tol_hsv": [12, 70, 70],
                        "min_frac": 0.08,
                        "debounce_frames": 3,
                    },
                },
            },
        }

        _save_json(out_path, cfg)
        print(f"Wrote monitor configuration: {out_path}")
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="robot monitor calibrate")
    p.add_argument("--config", type=Path, default=_default_config_path())
    p.add_argument("--device", type=int, default=0)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--fourcc", type=str, default="MJPG", choices=["MJPG", "YUYV"])
    args = p.parse_args(argv)

    config_path = args.config
    if not config_path.is_absolute():
        config_path = (_repo_root() / config_path).resolve()

    return calibrate(
        out_path=config_path,
        device=int(args.device),
        width=int(args.width),
        height=int(args.height),
        fps=int(args.fps),
        fourcc=str(args.fourcc),
    )


if __name__ == "__main__":
    raise SystemExit(main())


