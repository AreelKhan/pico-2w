from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


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


class PopupSignal(Protocol):
    def is_popup_present(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class MonitorStubConfig:
    start_delay_s: float = 0.25
    run_duration_s: float = 2.0
    poll_interval_s: float = 0.02


@dataclass(slots=True)
class _SimulatedPopupSignal:
    t0: float
    start_delay_s: float
    run_duration_s: float

    def is_popup_present(self) -> bool:
        t = time.monotonic() - self.t0
        if t < self.start_delay_s:
            return True
        if t < self.start_delay_s + self.run_duration_s:
            return False
        return True


class Monitor:
    def __init__(self, *, stub: MonitorStubConfig | None = None) -> None:
        self._stub = stub or MonitorStubConfig()

    def observe_run(
        self,
        *,
        start_timeout_s: float,
        end_timeout_s: float,
    ) -> RunObservation:
        t0 = time.monotonic()
        signal: PopupSignal = _SimulatedPopupSignal(
            t0=t0,
            start_delay_s=float(self._stub.start_delay_s),
            run_duration_s=float(self._stub.run_duration_s),
        )

        poll_s = max(0.001, float(self._stub.poll_interval_s))

        start_deadline = t0 + float(start_timeout_s)
        start_monotonic: float | None = None
        start_epoch_ms: int | None = None

        while time.monotonic() <= start_deadline:
            if not signal.is_popup_present():
                start_monotonic = time.monotonic()
                start_epoch_ms = int(time.time() * 1000)
                break
            time.sleep(poll_s)

        if start_monotonic is None or start_epoch_ms is None:
            raise MonitorStartTimeout(f"Did not observe run start within {start_timeout_s}s")

        end_deadline = start_monotonic + float(end_timeout_s)
        end_monotonic: float | None = None
        end_epoch_ms: int | None = None

        while time.monotonic() <= end_deadline:
            if signal.is_popup_present():
                end_monotonic = time.monotonic()
                end_epoch_ms = int(time.time() * 1000)
                break
            time.sleep(poll_s)

        if end_monotonic is None or end_epoch_ms is None:
            raise MonitorEndTimeout(f"Did not observe run end within {end_timeout_s}s")

        return RunObservation(
            start_epoch_ms=start_epoch_ms,
            end_epoch_ms=end_epoch_ms,
            start_monotonic_ms=int(start_monotonic * 1000),
            end_monotonic_ms=int(end_monotonic * 1000),
        )


