from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ROI:
    x: int
    y: int
    w: int
    h: int

    def clamp(self, *, width: int, height: int) -> "ROI":
        x = max(0, min(self.x, width - 1))
        y = max(0, min(self.y, height - 1))
        w = max(1, min(self.w, width - x))
        h = max(1, min(self.h, height - y))
        return ROI(x=x, y=y, w=w, h=h)

    def slice(self) -> tuple[slice, slice]:
        return slice(self.y, self.y + self.h), slice(self.x, self.x + self.w)

    def to_json(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ROI":
        return ROI(x=int(data["x"]), y=int(data["y"]), w=int(data["w"]), h=int(data["h"]))


def _open_camera(
    *,
    device: int,
    width: int,
    height: int,
    target_fps: int,
    fourcc: str = "MJPG",
    convert_rgb: bool = True,
) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, getattr(cv2, "VideoWriter_fourcc")(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, target_fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 1 if convert_rgb else 0)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera device={device}")
    return cap


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def _select_roi(frame_bgr: np.ndarray, *, title: str) -> ROI:
    x, y, w, h = cv2.selectROI(title, frame_bgr, fromCenter=False, showCrosshair=True)
    if w <= 0 or h <= 0:
        raise RuntimeError("ROI selection cancelled")
    return ROI(x=int(x), y=int(y), w=int(w), h=int(h))


def _hue_dist(h: np.ndarray, target_h: int) -> np.ndarray:
    dh = np.abs(h.astype(np.int16) - int(target_h))
    return np.minimum(dh, 180 - dh)


def _fraction_near_hsv(
    roi_bgr: np.ndarray,
    *,
    target_h: int,
    target_s: int,
    target_v: int,
    tol_h: int,
    tol_s: int,
    tol_v: int,
) -> float:
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)
    h_ok = _hue_dist(h, target_h) <= int(tol_h)
    s_ok = np.abs(s - int(target_s)) <= int(tol_s)
    v_ok = np.abs(v - int(target_v)) <= int(tol_v)
    mask = (h_ok & s_ok & v_ok).astype(np.uint8)
    return float(mask.mean())


def _mean_hsv(roi_bgr: np.ndarray) -> tuple[int, int, int]:
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    mean = hsv.reshape(-1, 3).mean(axis=0)
    return int(mean[0]), int(mean[1]), int(mean[2])

def _median_hsv(roi_bgr: np.ndarray) -> tuple[int, int, int]:
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    med = np.median(hsv, axis=0)
    return int(med[0]), int(med[1]), int(med[2])


def _build_default_config() -> dict[str, Any]:
    return {
        "camera": {"device": 0, "width": 640, "height": 480, "target_fps": 30},
        "level_end_pop": {
            "min_regions_active": 3,
            "regions": {
                "turquoise": {
                    "roi": None,
                    "ref_hsv": None,
                    "tol_hsv": [12, 60, 70],
                    "min_frac": 0.08,
                    "debounce_frames": 3,
                },
                "light_green": {
                    "roi": None,
                    "ref_hsv": None,
                    "tol_hsv": [12, 60, 70],
                    "min_frac": 0.08,
                    "debounce_frames": 3,
                },
                "dark_green": {
                    "roi": None,
                    "ref_hsv": None,
                    "tol_hsv": [12, 70, 70],
                    "min_frac": 0.08,
                    "debounce_frames": 3,
                },
            },
        },
    }


def calibrate(*, out_path: Path, device: int, width: int, height: int, target_fps: int) -> int:
    cap = _open_camera(
        device=device,
        width=width,
        height=height,
        target_fps=target_fps,
        fourcc=str(_load_json(out_path).get("camera", {}).get("fourcc", "MJPG")) if out_path.exists() else "MJPG",
        convert_rgb=True,
    )
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Frame read failed")
        cfg = _build_default_config()
        cfg["camera"] = {
            "device": device,
            "width": width,
            "height": height,
            "target_fps": target_fps,
            "fourcc": str(cfg.get("camera", {}).get("fourcc", "MJPG")),
        }

        lep = cfg["level_end_pop"]["regions"]

        def pick(name: str, title: str) -> None:
            roi = _select_roi(frame, title=title)
            y_s, x_s = roi.slice()
            ref = _median_hsv(frame[y_s, x_s])
            lep[name]["roi"] = roi.to_json()
            lep[name]["ref_hsv"] = [int(ref[0]), int(ref[1]), int(ref[2])]
            print(f"Calibrated {name}: roi={lep[name]['roi']} ref_hsv={lep[name]['ref_hsv']}")

        pick("turquoise", "Select Level end pop ROI: TURQUOISE (press ENTER to confirm)")
        pick("light_green", "Select Level end pop ROI: LIGHT GREEN (press ENTER to confirm)")
        pick("dark_green", "Select Level end pop ROI: DARK GREEN (press ENTER to confirm)")
        _save_json(out_path, cfg)
        print(f"Wrote config: {out_path}")
        return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


def run(*, config_path: Path, no_gui: bool = False, log_every_s: float = 1.0) -> int:
    cfg = _load_json(config_path)
    cam = cfg.get("camera", {})
    device = int(cam.get("device", 0))
    width = int(cam.get("width", 640))
    height = int(cam.get("height", 480))
    target_fps = int(cam.get("target_fps", 30))
    fourcc = str(cam.get("fourcc", "MJPG"))
    raw_yuyv = bool(cam.get("raw_yuyv", False))

    lep = cfg.get("level_end_pop")
    if not isinstance(lep, dict):
        raise RuntimeError("Missing level_end_pop in config (re-run --calibrate)")
    regions_cfg = lep.get("regions")
    if not isinstance(regions_cfg, dict):
        raise RuntimeError("Missing level_end_pop.regions in config (re-run --calibrate)")
    for name in ("turquoise", "light_green", "dark_green"):
        r = regions_cfg.get(name)
        if not isinstance(r, dict) or r.get("roi") is None:
            raise RuntimeError(f"Missing level_end_pop.regions.{name}.roi in config (re-run --calibrate)")
        if r.get("ref_hsv") is None and r.get("target_hsv") is None:
            raise RuntimeError(f"Missing level_end_pop.regions.{name}.ref_hsv in config (re-run --calibrate)")

    gui = not no_gui
    if raw_yuyv and fourcc == "YUYV" and gui:
        raise RuntimeError("raw_yuyv requires --no-gui")

    cap = _open_camera(
        device=device,
        width=width,
        height=height,
        target_fps=target_fps,
        fourcc=fourcc,
        convert_rgb=not (raw_yuyv and fourcc == "YUYV"),
    )
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Frame read failed")

        fh, fw = frame.shape[:2]
        region_rois: dict[str, ROI] = {
            name: ROI.from_json(regions_cfg[name]["roi"]).clamp(width=fw, height=fh)
            for name in ("turquoise", "light_green", "dark_green")
        }
        region_on: dict[str, int] = {name: 0 for name in region_rois}

        mark_ts: float | None = None
        end_ts: float | None = None

        last_fps_ts = time.time()
        frames = 0
        fps = 0.0

        if gui:
            print("Keys: q quit | m mark 'I see level end pop now' | r reset marks | p print mean HSV in ROIs")
        else:
            print("Headless mode: Ctrl-C to quit")

        last_log_ts = time.time()

        try:
            while True:
                t_read0 = time.perf_counter()
                ok, frame = cap.read()
                t_read1 = time.perf_counter()
                if not ok:
                    continue
                t_proc0 = time.perf_counter()

                frames += 1
                now = time.time()
                if now - last_fps_ts >= 1.0:
                    fps = frames / (now - last_fps_ts)
                    frames = 0
                    last_fps_ts = now

                fracs: dict[str, float] = {}
                active: dict[str, bool] = {}
                region_proc_ms: dict[str, float] = {}
                for name, roi in region_rois.items():
                    t_r0 = time.perf_counter()
                    rcfg = regions_cfg[name]
                    ref = rcfg.get("ref_hsv") or rcfg.get("target_hsv")
                    target_h, target_s, target_v = [int(x) for x in ref]
                    tol_h, tol_s, tol_v = [int(x) for x in rcfg.get("tol_hsv", [12, 60, 70])]
                    roi_bgr = _roi_bgr(frame, roi=roi, fourcc=fourcc, raw_yuyv=raw_yuyv)
                    frac = _fraction_near_hsv(
                        roi_bgr,
                        target_h=target_h,
                        target_s=target_s,
                        target_v=target_v,
                        tol_h=tol_h,
                        tol_s=tol_s,
                        tol_v=tol_v,
                    )
                    fracs[name] = frac
                    region_proc_ms[name] = (time.perf_counter() - t_r0) * 1000.0

                    min_frac = float(rcfg.get("min_frac", 0.08))
                    db = int(rcfg.get("debounce_frames", 3))
                    if frac >= min_frac:
                        region_on[name] = min(db, region_on[name] + 1)
                    else:
                        region_on[name] = max(0, region_on[name] - 1)
                    active[name] = region_on[name] >= db

                min_regions_active = int(lep.get("min_regions_active", 3))
                end_active = sum(1 for v in active.values() if v) >= min_regions_active
                if end_active and end_ts is None:
                    end_ts = time.time()
                    flags = " ".join(f"{k}={int(active[k])}" for k in ("turquoise", "light_green", "dark_green"))
                    print(f"LEVEL_END_POP_DETECTED t={end_ts:.3f} {flags}")

                t_proc1 = time.perf_counter()
                read_ms = (t_read1 - t_read0) * 1000.0
                proc_ms = (t_proc1 - t_proc0) * 1000.0
                total_ms = (t_proc1 - t_read0) * 1000.0

                if now - last_log_ts >= max(0.05, log_every_s):
                    last_log_ts = now
                    flags = " ".join(
                        f"{k}_frac={fracs[k]:.3f} {k}_db={region_on[k]}/{int(regions_cfg[k].get('debounce_frames', 3))} {k}_active={int(active[k])}"
                        for k in ("turquoise", "light_green", "dark_green")
                    )
                    parts = " ".join(
                        f"{k}_ms={region_proc_ms.get(k, 0.0):.2f}"
                        for k in ("turquoise", "light_green", "dark_green")
                    )
                    print(
                        "STATUS "
                        f"fps={fps:.1f} read_ms={read_ms:.2f} proc_ms={proc_ms:.2f} total_ms={total_ms:.2f} "
                        f"level_end_pop={int(end_active)} min_regions_active={min_regions_active} "
                        f"{parts} {flags}"
                    )

                if not gui:
                    continue

                out = frame.copy()
                colors = {
                    "turquoise": (255, 255, 0),
                    "light_green": (0, 255, 0),
                    "dark_green": (0, 140, 0),
                }
                for name, roi in region_rois.items():
                    cv2.rectangle(
                        out,
                        (roi.x, roi.y),
                        (roi.x + roi.w, roi.y + roi.h),
                        colors.get(name, (255, 255, 255)),
                        2,
                    )

                y = 30

                def put(line: str) -> None:
                    nonlocal y
                    cv2.putText(
                        out,
                        line,
                        (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2,
                    )
                    y += 26

                put(f"FPS {fps:.1f} | read {read_ms:.2f} ms | proc {proc_ms:.2f} ms | total {total_ms:.2f} ms")
                put(f"Level end pop {int(end_active)} (min_regions_active {min_regions_active})")
                for name in ("turquoise", "light_green", "dark_green"):
                    rcfg = regions_cfg[name]
                    min_frac = float(rcfg.get("min_frac", 0.08))
                    db = int(rcfg.get("debounce_frames", 3))
                    put(
                        f"{name} frac {fracs[name]:.3f} (min {min_frac:.3f}) db {region_on[name]}/{db} active {int(active[name])} ({region_proc_ms.get(name, 0.0):.2f} ms)"
                    )

                if mark_ts is not None:
                    put(f"mark_t {mark_ts:.3f}")
                if end_ts is not None:
                    put(f"end_t  {end_ts:.3f}")
                if mark_ts is not None and end_ts is not None:
                    put(f"delta (end - mark) {(end_ts - mark_ts) * 1000.0:.1f} ms")

                cv2.imshow("monitor validation", out)
                k = cv2.waitKey(1) & 0xFF
                if k == ord("q"):
                    return 0
                if k == ord("m"):
                    mark_ts = time.time()
                if k == ord("r"):
                    mark_ts = None
                    end_ts = None
                if k == ord("p"):
                    for name, roi in region_rois.items():
                        roi_bgr = _roi_bgr(frame, roi=roi, fourcc=fourcc, raw_yuyv=raw_yuyv)
                        mh, ms, mv = _mean_hsv(roi_bgr)
                        print(f"ROI_HSV {name} mean_hsv=[{mh},{ms},{mv}]")
        except KeyboardInterrupt:
            return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


def _roi_bgr(frame: np.ndarray, *, roi: ROI, fourcc: str, raw_yuyv: bool) -> np.ndarray:
    y_s, x_s = roi.slice()
    if raw_yuyv and fourcc == "YUYV":
        h = roi.h
        w = roi.w
        x0 = roi.x & ~1
        w2 = w & ~1
        if w2 <= 0:
            w2 = 2
        if frame.ndim == 3 and frame.shape[2] == 2:
            raw = frame[roi.y : roi.y + h, x0 : x0 + w2, :]
            return cv2.cvtColor(raw, cv2.COLOR_YUV2BGR_YUY2)
        if frame.ndim == 2:
            raw = frame[roi.y : roi.y + h, x0 * 2 : (x0 + w2) * 2]
            raw2 = raw.reshape(h, w2, 2)
            return cv2.cvtColor(raw2, cv2.COLOR_YUV2BGR_YUY2)
    return frame[y_s, x_s]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="validate_end_detection")
    p.add_argument(
        "--config",
        type=Path,
        default=_repo_root() / "data" / "monitor" / "validation_config.json",
    )
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--log-every", type=float, default=1.0)
    p.add_argument("--device", type=int, default=0)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--fourcc", type=str, default=None, choices=["MJPG", "YUYV"])
    args = p.parse_args(argv)

    config_path = args.config
    if not config_path.is_absolute():
        config_path = (_repo_root() / config_path).resolve()

    if args.calibrate:
        if args.fourcc is not None:
            cfg = _build_default_config()
            cfg["camera"]["fourcc"] = str(args.fourcc)
            _save_json(config_path, cfg)
        return calibrate(
            out_path=config_path,
            device=args.device,
            width=args.width,
            height=args.height,
            target_fps=args.fps,
        )
    if args.fourcc is not None:
        cfg = _load_json(config_path)
        cfg.setdefault("camera", {})
        cfg["camera"]["fourcc"] = str(args.fourcc)
        _save_json(config_path, cfg)
    return run(config_path=config_path, no_gui=bool(args.no_gui), log_every_s=float(args.log_every))


if __name__ == "__main__":
    raise SystemExit(main())


