from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from orchestrator.clicker.client import ClickerClient
from orchestrator.logging_utils import RunLogger
from orchestrator.models import RunRecord
from orchestrator.storage import Storage
from monitor import Monitor, MonitorEndTimeout, MonitorStartTimeout, RunObservation


class Orchestrator:
    def __init__(self, storage: Storage, clicker: ClickerClient, monitor: Monitor | None = None) -> None:
        self._storage = storage
        self._clicker = clicker
        self._monitor = monitor

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
            clicker_exc: Exception | None = None

            try:
                self._clicker.run_script(script)
            except Exception as e:
                clicker_exc = e
                logger.log(f"clicker_error={type(e).__name__} {e}")

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
        if clicker_exc is not None:
            raise clicker_exc
        return run_id

    def train(
        self,
        *,
        level: str,
        script_id: str,
        start_timeout_s: float,
        end_timeout_s: float,
    ) -> str:
        self._storage.assert_level_exists(level)
        if self._monitor is None:
            raise RuntimeError("Monitor is required for training.")

        # TODO: if no script provided, orchestrator should pick the one with best score
        script = self._storage.load_script(level, script_id)

        # TODO: this logic could be shared with inference in a helper function
        run_id = uuid.uuid4().hex
        started_at_ms = int(time.time() * 1000)
        log_path, fh = self._storage.open_run_log(level, run_id)

        obs: RunObservation | None = None
        clicker_exc: Exception | None = None
        monitor_exc: Exception | None = None

        with fh:
            logger = RunLogger(fh)
            logger.log(
                f"run_id={run_id} level={level} script_id={script_id} train_start "
                f"start_timeout_s={start_timeout_s} end_timeout_s={end_timeout_s}"
            )
            logger.log(f"script bins={len(script.bins)} bin_ms={script.bin_ms}")
            logger.log(f"log_path={log_path}")

            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    self._monitor.observe_run,
                    start_timeout_s=float(start_timeout_s),
                    end_timeout_s=float(end_timeout_s),
                )

                try:
                    self._clicker.run_script(script)
                except Exception as e:
                    clicker_exc = e
                    logger.log(f"clicker_error={type(e).__name__} {e}")

                try:
                    obs = fut.result(timeout=float(start_timeout_s) + float(end_timeout_s) + 5.0)
                    logger.log(
                        f"monitor_ok start_epoch_ms={obs.start_epoch_ms} end_epoch_ms={obs.end_epoch_ms} "
                        f"score_ms={obs.score_ms}"
                    )
                except (MonitorStartTimeout, MonitorEndTimeout) as e:
                    monitor_exc = e
                    logger.log(f"monitor_timeout={type(e).__name__} {e}")
                    try:
                        self._clicker.stop()
                    except Exception:
                        pass
                except Exception as e:
                    monitor_exc = e
                    logger.log(f"monitor_error={type(e).__name__} {e}")
                    try:
                        self._clicker.stop()
                    except Exception:
                        pass

            ended_at_ms = int(time.time() * 1000)
            score_ms = float(obs.score_ms) if obs is not None else 0.0
            if score_ms == 0.0:
                raise RuntimeError("Monitor did not observe a score.")
            if score_ms < 0.0:
                raise RuntimeError(f"Monitor observed a negative score. Start {obs.start_epoch_ms}. End {obs.end_epoch_ms}")
            logger.log(
                f"train_end run_id={run_id} score_ms={score_ms} duration_ms={ended_at_ms - started_at_ms}"
            )

        run = RunRecord(
            run_id=run_id,
            level=level,
            script_id=script_id,
            score=float(obs.score_ms) if obs is not None else 0.0,
        )
        self._storage.append_run(run)

        if clicker_exc is not None:
            raise clicker_exc
        if monitor_exc is not None:
            raise monitor_exc
        return run_id
