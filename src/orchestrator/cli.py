from __future__ import annotations

import argparse
import sys

from monitor import Monitor, MonitorStubConfig
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
    tr.add_argument("--sim-start-delay-s", type=float, default=0.25) # stub config
    tr.add_argument("--sim-run-duration-s", type=float, default=2.0) # stub config

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
        monitor = Monitor(
            # TODO: remove the sim start and run duration when unstubbing the monitor
            stub=MonitorStubConfig(
                start_delay_s=float(getattr(args, "sim_start_delay_s", 0.25)),
                run_duration_s=float(getattr(args, "sim_run_duration_s", 2.0)),
            )
        )
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
