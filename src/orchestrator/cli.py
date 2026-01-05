from __future__ import annotations

import argparse
import sys

from pathlib import Path

from monitor import Monitor
from monitor.calibrate import main as monitor_calibrate_main
from orchestrator.clicker.client import ClickerClient
from orchestrator.clicker.installer import PicoInstaller
from orchestrator.levels import list_levels
from orchestrator.orchestrator import Orchestrator
from orchestrator.storage import LevelNotFoundError, ScriptNotFoundError, Storage


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="robot")
    sub = p.add_subparsers(dest="cmd", required=True)

    inf = sub.add_parser("inference", help="Run a specific script for a level")
    inf.add_argument("--level", required=True, choices=list_levels())
    inf.add_argument("--script-id", required=True)
    inf.add_argument("--port", default=None)
    inf.add_argument("--baud", default=115200, type=int)

    tr = sub.add_parser("train", help="Train on a level (stub)")
    tr.add_argument("--level", required=True, choices=list_levels())
    tr.add_argument("--script-id", default="hand_coded_v0")
    tr.add_argument("--start-timeout-s", type=float, default=3.0)
    tr.add_argument("--end-timeout-s", type=float, default=30.0)
    tr.add_argument(
        "--monitor-config",
        type=Path,
        default=None,
    )

    mon = sub.add_parser("monitor", help="Monitor utilities")
    mon_sub = mon.add_subparsers(dest="monitor_cmd", required=True)
    mon_cal = mon_sub.add_parser("calibrate", help="Calibrate level end pop ROIs/colors")
    mon_cal.add_argument("--config", type=Path, default=None)
    mon_cal.add_argument("--device", type=int, default=0)
    mon_cal.add_argument("--width", type=int, default=640)
    mon_cal.add_argument("--height", type=int, default=480)
    mon_cal.add_argument("--fps", type=int, default=30)
    mon_cal.add_argument("--fourcc", type=str, default="MJPG", choices=["MJPG", "YUYV"])

    clicker = sub.add_parser("clicker", help="Manage the Pico clicker device")
    clicker_sub = clicker.add_subparsers(dest="clicker_cmd", required=True)
    install = clicker_sub.add_parser(
        "install", help="Upload clicker firmware to the Pico"
    )
    install.add_argument("--port", default=None)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    storage = Storage()
    clicker = ClickerClient(
        port=getattr(args, "port", None),
        baud=getattr(args, "baud", 115200),
    )
    monitor = None
    if args.cmd == "train":
        monitor = Monitor(config_path=getattr(args, "monitor_config", None))
    orch = Orchestrator(storage=storage, clicker=clicker, monitor=monitor)

    try:
        if args.cmd == "inference":
            run_id = orch.inference(level=args.level, script_id=args.script_id)
            print(run_id)
            return 0

        if args.cmd == "train":
            run_id = orch.train(
                level=args.level,
                script_id=args.script_id,
                start_timeout_s=float(args.start_timeout_s),
                end_timeout_s=float(args.end_timeout_s),
            )
            print(run_id)
            return 0

        if args.cmd == "monitor":
            if args.monitor_cmd == "calibrate":
                argv2 = []
                if args.config is not None:
                    argv2 += ["--config", str(args.config)]
                argv2 += [
                    "--device",
                    str(args.device),
                    "--width",
                    str(args.width),
                    "--height",
                    str(args.height),
                    "--fps",
                    str(args.fps),
                    "--fourcc",
                    str(args.fourcc),
                ]
                return int(monitor_calibrate_main(argv2))
            raise AssertionError(f"Unknown monitor command: {args.monitor_cmd}")

        if args.cmd == "clicker":
            if args.clicker_cmd == "install":
                PicoInstaller(port=args.port).install()
                return 0
            raise AssertionError(f"Unknown clicker command: {args.clicker_cmd}")

        raise AssertionError(f"Unknown command: {args.cmd}")
    except (LevelNotFoundError, ScriptNotFoundError) as e:
        print(str(e), file=sys.stderr)
        return 2
    except NotImplementedError as e:
        print(str(e), file=sys.stderr)
        return 3
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
