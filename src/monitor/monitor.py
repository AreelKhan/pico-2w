from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class RunObservation:
    start_epoch_ms: int
    end_epoch_ms: int
    start_monotonic_ms: int
    end_monotonic_ms: int

    @property
    def score_ms(self) -> int:
        return self.end_monotonic_ms - self.start_monotonic_ms


class MonitorStartTimeout(TimeoutError):
    pass


class MonitorEndTimeout(TimeoutError):
    pass


class MonitorRuntimeError(RuntimeError):
    pass


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

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ROI":
        return ROI(x=int(data["x"]), y=int(data["y"]), w=int(data["w"]), h=int(data["h"]))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _hue_dist(h, target_h: int):
    import numpy as np

    dh = np.abs(h.astype(np.int16) - int(target_h))
    return np.minimum(dh, 180 - dh)


def _fraction_near_hsv(
    roi_bgr,
    *,
    target_h: int,
    target_s: int,
    target_v: int,
    tol_h: int,
    tol_s: int,
    tol_v: int,
) -> float:
    import cv2
    import numpy as np

    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0]
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)
    h_ok = _hue_dist(h, target_h) <= int(tol_h)
    s_ok = np.abs(s - int(target_s)) <= int(tol_s)
    v_ok = np.abs(v - int(target_v)) <= int(tol_v)
    mask = (h_ok & s_ok & v_ok).astype(np.uint8)
    return float(mask.mean())


@dataclass(frozen=True, slots=True)
class _RegionCfg:
    roi: ROI
    ref_hsv: tuple[int, int, int]
    tol_hsv: tuple[int, int, int]
    min_frac: float
    debounce_frames: int


@dataclass(slots=True)
class LevelEndPopDetector:
    min_regions_active: int
    regions: dict[str, _RegionCfg]
    _region_on: dict[str, int]

    @staticmethod
    def from_config(cfg: dict[str, Any], *, frame_w: int, frame_h: int) -> "LevelEndPopDetector":
        lep = cfg.get("level_end_pop")
        if not isinstance(lep, dict):
            raise MonitorRuntimeError("Missing level_end_pop in config")
        regions_cfg = lep.get("regions")
        if not isinstance(regions_cfg, dict):
            raise MonitorRuntimeError("Missing level_end_pop.regions in config")

        regions: dict[str, _RegionCfg] = {}
        for name in ("turquoise", "light_green", "dark_green"):
            r = regions_cfg.get(name)
            if not isinstance(r, dict):
                raise MonitorRuntimeError(f"Missing region '{name}' in config")
            roi = ROI.from_json(r["roi"]).clamp(width=frame_w, height=frame_h)
            ref = r.get("ref_hsv") or r.get("target_hsv")
            if ref is None:
                raise MonitorRuntimeError(f"Missing ref_hsv for region '{name}'")
            ref_h, ref_s, ref_v = [int(x) for x in ref]
            tol_h, tol_s, tol_v = [int(x) for x in r.get("tol_hsv", [12, 60, 70])]
            regions[name] = _RegionCfg(
                roi=roi,
                ref_hsv=(ref_h, ref_s, ref_v),
                tol_hsv=(tol_h, tol_s, tol_v),
                min_frac=float(r.get("min_frac", 0.08)),
                debounce_frames=int(r.get("debounce_frames", 3)),
            )

        min_regions_active = int(lep.get("min_regions_active", 3))
        return LevelEndPopDetector(
            min_regions_active=min_regions_active,
            regions=regions,
            _region_on={name: 0 for name in regions},
        )

    def reset(self) -> None:
        for k in self._region_on:
            self._region_on[k] = 0

    def is_popup_present(self, frame_bgr) -> bool:
        active = 0
        for name, rcfg in self.regions.items():
            y_s, x_s = rcfg.roi.slice()
            ref_h, ref_s, ref_v = rcfg.ref_hsv
            tol_h, tol_s, tol_v = rcfg.tol_hsv
            frac = _fraction_near_hsv(
                frame_bgr[y_s, x_s],
                target_h=ref_h,
                target_s=ref_s,
                target_v=ref_v,
                tol_h=tol_h,
                tol_s=tol_s,
                tol_v=tol_v,
            )
            if frac >= rcfg.min_frac:
                self._region_on[name] = min(rcfg.debounce_frames, self._region_on[name] + 1)
            else:
                self._region_on[name] = max(0, self._region_on[name] - 1)
            if self._region_on[name] >= rcfg.debounce_frames:
                active += 1
        return active >= self.min_regions_active


class Monitor:
    def __init__(self, *, config_path: Path | None = None) -> None:
        self._config_path = config_path or (_repo_root() / "data" / "monitor" / "configuration.json")

    def observe_run(
        self,
        *,
        start_timeout_s: float,
        end_timeout_s: float,
    ) -> RunObservation:
        cfg = _load_json(self._config_path)
        cam = cfg.get("camera", {})
        device = int(cam.get("device", 0))
        width = int(cam.get("width", 640))
        height = int(cam.get("height", 480))
        target_fps = int(cam.get("target_fps", 30))
        fourcc = str(cam.get("fourcc", "MJPG"))

        try:
            import cv2
        except ImportError as e:
            raise MonitorRuntimeError("OpenCV not installed (missing 'cv2'); install opencv-python.") from e

        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, getattr(cv2, "VideoWriter_fourcc")(*fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, target_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            raise MonitorRuntimeError(f"Could not open camera device={device}")

        try:
            ok, frame = cap.read()
            if not ok:
                raise MonitorRuntimeError("Frame read failed")

            fh, fw = frame.shape[:2]
            detector = LevelEndPopDetector.from_config(cfg, frame_w=fw, frame_h=fh)

            t0 = time.monotonic()
            start_deadline = t0 + float(start_timeout_s)

            saw_popup = False
            stable_absent = 0

            while time.monotonic() <= start_deadline:
                ok, frame = cap.read()
                if not ok:
                    continue
                present = detector.is_popup_present(frame)
                if present:
                    saw_popup = True
                    stable_absent = 0
                elif saw_popup:
                    stable_absent += 1
                    if stable_absent >= 2:
                        start_mon = time.monotonic()
                        start_epoch_ms = int(time.time() * 1000)
                        break
                time.sleep(0.0)
            else:
                raise MonitorStartTimeout(f"Did not observe run start within {start_timeout_s}s")

            end_deadline = start_mon + float(end_timeout_s)
            stable_present = 0
            detector.reset()

            while time.monotonic() <= end_deadline:
                ok, frame = cap.read()
                if not ok:
                    continue
                present = detector.is_popup_present(frame)
                if present:
                    stable_present += 1
                    if stable_present >= 2:
                        end_mon = time.monotonic()
                        end_epoch_ms = int(time.time() * 1000)
                        return RunObservation(
                            start_epoch_ms=start_epoch_ms,
                            end_epoch_ms=end_epoch_ms,
                            start_monotonic_ms=int(start_mon * 1000),
                            end_monotonic_ms=int(end_mon * 1000),
                        )
                else:
                    stable_present = 0
                time.sleep(0.0)

            raise MonitorEndTimeout(f"Did not observe run end within {end_timeout_s}s")
        finally:
            cap.release()


