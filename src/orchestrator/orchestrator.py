from __future__ import annotations

import time
import uuid

from orchestrator.clicker_client import ClickerClient
from orchestrator.logging_utils import RunLogger
from orchestrator.models import EndReason, RunRecord
from orchestrator.storage import Storage


class Orchestrator:
    def __init__(self, storage: Storage, clicker: ClickerClient) -> None:
        self._storage = storage
        self._clicker = clicker

    def inference(self, *, level: str, script_id: str) -> str:
        self._storage.assert_level_exists(level)
        script = self._storage.load_script(level, script_id)

        run_id = uuid.uuid4().hex
        started_at_ms = int(time.time() * 1000)
        log_path, fh = self._storage.open_run_log(level, run_id)

        with fh:
            logger = RunLogger(fh)
            logger.log(f"run_id={run_id} level={level} script_id={script_id} start")
            logger.log(f"script bins={len(script.bins)} bin_ms={script.bin_ms}")
            logger.log(f"log_path={log_path}")

            score = 0.0

            try:
                self._clicker.run_script(script)
            except NotImplementedError as e:
                logger.log(f"clicker_stub={e}")

            ended_at_ms = int(time.time() * 1000)
            logger.log(
                f"end run_id={run_id} score={score} duration_ms={ended_at_ms - started_at_ms}"
            )

        run = RunRecord(
            run_id=run_id,
            level=level,
            script_id=script_id,
            score=0.0,
        )
        self._storage.append_run(run)
        return run_id

    def train(self, *, level: str) -> None:
        self._storage.assert_level_exists(level)
        raise NotImplementedError("Training loop not implemented yet.")


