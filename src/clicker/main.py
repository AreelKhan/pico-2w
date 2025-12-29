import binascii
import sys
import time

try:
    import uselect as select
except ImportError:
    import select

try:
    from servo import Servo
except ImportError:
    from .servo import Servo

try:
    from clicker import Clicker
except ImportError:
    from .clicker import Clicker


SERVO_PIN = 16
BASE_ANGLE = 150
CLICK_ANGLE = 180
TICK_SLEEP_MS = 1


def _writeln(s: str) -> None:
    sys.stdout.write(s + "\n")
    try:
        sys.stdout.flush()
    except Exception:
        pass


def _pack_info(script_id: str, msg: str) -> str:
    return f"{msg} {script_id}"


def _unpack_bits(payload_b64: str, n: int) -> list[int]:
    raw = binascii.a2b_base64(payload_b64)
    bins = []
    for byte in raw:
        for bit in range(7, -1, -1):
            bins.append(1 if (byte >> bit) & 1 else 0)
            if len(bins) >= n:
                return bins
    return bins[:n]


def main() -> None:
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    loaded_id = None
    loaded_bin_ms = None
    loaded_n = None
    loaded_bins = None

    servo = None
    clicker = None
    running_id = None

    _writeln("READY")

    while True:
        if clicker is not None and clicker.is_running():
            clicker.tick()
            if poller.poll(0):
                line = sys.stdin.readline()
                if not line:
                    time.sleep_ms(TICK_SLEEP_MS)
                    continue
                line = line.strip()
                if not line:
                    time.sleep_ms(TICK_SLEEP_MS)
                    continue
                parts = line.split()
                cmd = parts[0].upper()
                if cmd == "STOP":
                    clicker.stop()
                    _writeln(_pack_info(running_id or "NONE", "STOPPED"))
                    running_id = None

            if clicker is not None and not clicker.is_running():
                _writeln(_pack_info(running_id or "NONE", "DONE"))
                running_id = None
            time.sleep_ms(TICK_SLEEP_MS)
            continue

        line = sys.stdin.readline()
        if not line:
            time.sleep_ms(TICK_SLEEP_MS)
            continue

        line = line.strip()
        if not line:
            continue

        parts = line.split()
        cmd = parts[0].upper()

        if cmd == "PING":
            _writeln("PONG")
            continue

        if cmd == "LOAD":
            if len(parts) != 4:
                _writeln("ERR LOAD")
                continue
            loaded_id = parts[1]
            loaded_bin_ms = int(parts[2])
            loaded_n = int(parts[3])
            loaded_bins = None
            _writeln(_pack_info(loaded_id, "LOADED"))
            continue

        if cmd == "DATA":
            if loaded_id is None:
                _writeln("ERR NOLOAD")
                continue
            if len(parts) < 3:
                _writeln("ERR DATA")
                continue
            script_id = parts[1]
            payload = line.split(" ", 2)[2]
            if script_id != loaded_id:
                _writeln("ERR ID_MISMATCH")
                continue
            loaded_bins = _unpack_bits(payload, loaded_n)
            if len(loaded_bins) != loaded_n:
                _writeln("ERR BADLEN")
                loaded_bins = None
                continue
            _writeln(_pack_info(script_id, "DATA_OK"))
            continue

        if cmd == "START":
            if len(parts) != 2:
                _writeln("ERR START")
                continue
            script_id = parts[1]
            if loaded_id is None or loaded_bins is None:
                _writeln("ERR NOTREADY")
                continue
            if script_id != loaded_id:
                _writeln("ERR ID_MISMATCH")
                continue

            if servo is None:
                servo = Servo(SERVO_PIN)
            if clicker is None:
                clicker = Clicker(servo, base_angle=BASE_ANGLE, click_angle=CLICK_ANGLE)
            clicker.load(loaded_bins, bin_ms=loaded_bin_ms)
            clicker.start()
            running_id = script_id
            _writeln(_pack_info(script_id, "STARTED"))
            continue

        _writeln("ERR UNKNOWN")


if __name__ == "__main__":
    main()
