from __future__ import annotations

from dataclasses import dataclass
import time

from orchestrator.clicker.protocol import encode_bins, expected_run_seconds
from orchestrator.clicker.serial_ports import auto_port
from orchestrator.clicker.serial_transport import SerialTransport
from orchestrator.models import ScriptRecord


@dataclass(slots=True)
class ClickerClient:
    port: str | None = None
    baud: int = 115_200
    timeout_s: float = 3.0

    def run_script(self, script: ScriptRecord) -> None:
        if not script.script_id:
            raise ValueError("script_id is required")

        port = self.port or auto_port()
        transport = SerialTransport(port=port, baud=self.baud, timeout_s=self.timeout_s)

        with transport.open() as ser:
            time.sleep(1.8)
            transport.drain(ser)

            transport.sendline(ser, "PING")
            transport.expect_one_of(
                transport.readline(ser, stage="PING"),
                ["PONG"],
                stage="PING",
            )

            script_id = script.script_id
            n = len(script.bins)

            transport.sendline(ser, f"LOAD {script_id} {int(script.bin_ms)} {n}")
            transport.expect_one_of(
                transport.readline(ser, stage="LOAD"),
                [f"LOADED {script_id}"],
                stage="LOAD",
            )

            payload = encode_bins(script.bins)
            transport.sendline(ser, f"DATA {script_id} {payload}")
            transport.expect_one_of(
                transport.readline(ser, stage="DATA"),
                [f"DATA_OK {script_id}"],
                stage="DATA",
            )

            transport.sendline(ser, f"START {script_id}")
            transport.expect_one_of(
                transport.readline(ser, stage="START"),
                [f"STARTED {script_id}"],
                stage="START",
            )

            old_timeout = ser.timeout
            ser.timeout = max(
                float(self.timeout_s),
                expected_run_seconds(n_bins=n, bin_ms=int(script.bin_ms)) + 2.0,
            )
            try:
                done = transport.readline(ser, stage="DONE")
            finally:
                ser.timeout = old_timeout

            transport.expect_one_of(
                done,
                [f"DONE {script_id}", f"STOPPED {script_id}"],
                stage="DONE",
            )

    def stop(self) -> str:
        port = self.port or auto_port()
        transport = SerialTransport(port=port, baud=self.baud, timeout_s=self.timeout_s)

        with transport.open() as ser:
            time.sleep(0.5)
            transport.drain(ser)
            transport.sendline(ser, "STOP")
            return transport.readline(ser, stage="STOP")


