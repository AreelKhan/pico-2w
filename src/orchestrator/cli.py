from __future__ import annotations

import argparse
import sys

from orchestrator.clicker_client import ClickerClient
from orchestrator.levels import list_levels
from orchestrator.orchestrator import Orchestrator
from orchestrator.storage import LevelNotFoundError, ScriptNotFoundError, Storage


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="robot")
    sub = p.add_subparsers(dest="cmd", required=True)

    inf = sub.add_parser("inference", help="Run a specific script for a level")
    inf.add_argument("--level", required=True, choices=list_levels())
    inf.add_argument("--script-id", required=True)

    tr = sub.add_parser("train", help="Train on a level (stub)")
    tr.add_argument("--level", required=True, choices=list_levels())

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    storage = Storage()
    clicker = ClickerClient()
    orch = Orchestrator(storage=storage, clicker=clicker)

    try:
        if args.cmd == "inference":
            run_id = orch.inference(level=args.level, script_id=args.script_id)
            print(run_id)
            return 0

        if args.cmd == "train":
            orch.train(level=args.level)
            return 0

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


